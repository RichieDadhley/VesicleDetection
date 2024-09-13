import gunpowder as gp 

from src.gp_filters import AddChannelDim, RemoveChannelDim, TransposeDims
from src.data_loader import EMData
from src.model.model import DetectionModel
from src.model.model import UnetOutputShape

class Prediction:
     
    def __init__(self,
                data: EMData,
                model: DetectionModel, 
                input_shape: tuple):
        
        self.data = data
        self.detection_model = model
        self.voxel_size = self.data.voxel_size
        self.input_shape = input_shape

        if len(self.data.raw_data.shape) == 3:
            self.raw_channels = 1
        elif len(self.data.raw_data.shape) == 4:
            self.raw_channels = self.data.raw_data.shape[0]

        if self.raw_channels == 1:
            self.channel_dims = 0
        else:
            self.channel_dims = 1

        output_shape, border = UnetOutputShape(
                                        model = self.detection_model,
                                        input_shape = self.input_shape
                                       )

        self.output_shape = output_shape
        self.border = border

        # Obtain shape for prediciton
        if self.input_shape[0] >= self.data.raw_data.shape[0]:
            predict_shape_z = self.input_shape[0]
        else:
            predict_shape_z = self.data.raw_data.shape[0]
        
        if self.input_shape[1] >= self.data.raw_data.shape[1]:
            predict_shape_y = self.input_shape[1]
        else:
            predict_shape_y = self.data.raw_data.shape[1]

        if self.input_shape[2] >= self.data.raw_data.shape[2]:
            predict_shape_x = self.input_shape[2]
        else:
            predict_shape_x = self.data.raw_data.shape[2]

        self.predict_shape = (predict_shape_z, predict_shape_y, predict_shape_x)

        # Switch to world units for use with gunpowder
        input_shape = gp.Coordinate(self.input_shape)
        output_shape = gp.Coordinate(self.output_shape)
        predict_shape = gp.Coordinate(self.predict_shape)
        border_shape = gp.Coordinate(self.border)
        self.input_size = self.data.voxel_size * input_shape
        self.output_size = self.data.voxel_size * output_shape
        self.predict_size = self.data.voxel_size * predict_shape
        self.border_size = self.data.voxel_size * border_shape

    def predict_pipeline(self):
    
        self.detection_model.eval()

        # Define the gunpowder arrays
        raw = gp.ArrayKey('RAW')
        prediction = gp.ArrayKey('PREDICTION')

        # Create scan request (i.e. where each prediction will happen)
        scan_request = gp.BatchRequest()
        scan_request.add(raw, self.input_size)
        scan_request.add(prediction, self.output_size)

        # Create the source node for pipeline
        source = gp.ZarrSource(
                self.data.zarr_path,
                {
                    raw: self.data.raw_data_path
                },
                {
                    raw: gp.ArraySpec(interpolatable=True)
                }
            )

        # Start building the pipeline
        pipeline = source

        pipeline += gp.Pad(raw, None)
        #pipeline += gp.Pad(raw, (self.input_size-self.output_size)/2)

        pipeline += gp.Normalize(raw)

        if self.channel_dims == 0:
            pipeline += AddChannelDim(raw)
        
        # This accounts for us having a batch with size 1
        pipeline += AddChannelDim(raw)

        pipeline += gp.torch.Predict(
                model=self.detection_model,
                inputs={'x': raw},
                outputs={0: prediction}
                )
        
        # Remove the created batch dimension
        pipeline += RemoveChannelDim(raw)
        pipeline += RemoveChannelDim(prediction)
        
        if self.channel_dims == 0:
            pipeline += RemoveChannelDim(raw)

        pipeline += gp.Scan(scan_request)

        total_request = gp.BatchRequest()
        total_request.add(raw, self.predict_size)
        total_request.add(prediction, self.predict_size - self.border_size*2)


        with gp.build(pipeline):
            batch = pipeline.request_batch(total_request)
            ret = {
                    'raw': batch[raw],
                    'prediction': batch[prediction]
                }
        return ret
    
    def print_border_message(self):
        print("-----"*5)
        print(f"The model will divide the image into samples of shape (in voxels) {self.input_shape} " \
                f"and return a corresponding prediction with shape {self.output_shape}.")
        print(f"The full prediction of the validation image will have a border of shape {self.border}.")
        print("-----"*5)