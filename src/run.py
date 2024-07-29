import zarr 
import gunpowder as gp 
import math 

from training import Training 

class Run():

    def __init__(
            self,
            zarr_path: str, 
            clahe = False
            ):
        self.zarr_path = zarr_path
        self.training = Training(self.zarr_path, clahe=clahe)
        self.augmentations = [ 
            gp.SimpleAugment(transpose_only=(1, 2)), 
            gp.ElasticAugment((1, 10, 10), (0, 0.1, 0.1), (0, math.pi/2))
        ]
        

    def run_training(self, batch_size= 2, iterations = 1):

        # Get pipeline and request for training
        pipeline, request = self.training.training_pipeline(augmentations=self.augmentations, batch_size = batch_size)  

        # run the training pipeline for interations
        with gp.build(pipeline):
            for i in range(iterations):
                batch = pipeline.request_batch(request)

        # Predict on the validation data 
        ret = self.training.validate_pipeline()

        return batch, ret 
    


if __name__ == "__main__":

    run = Run("data/17_1A_data.zarr", clahe=True)

    batch, ret = run.run_training(iterations=1)

    # Output the predicitions for background, PC+ and PC-
    # Total should be 1 everywhere. Something seems to be wrong! 

    back_pred = ret['prediction'].data[0,:,:,:]
    pos_pred = ret['prediction'].data[1,:,:,:]
    neg_pred = ret['prediction'].data[2,:,:,:]
    total = back_pred + pos_pred + neg_pred 

    print(total)