import math
import numpy as np
import torch 
import zarr 
import gunpowder as gp
import napari

from datetime import datetime

from src.training import Training
from src.visualisation import imshow_napari_validation

class Run():

    def __init__(
            self,
            zarr_path: str,
            clahe = False,
            training_has_mask = False
            ):
        self.zarr_path = zarr_path
        self.training = Training(self.zarr_path, clahe=clahe, training_has_mask=training_has_mask)
        self.augmentations = [
            gp.SimpleAugment(transpose_only=(1, 2)),
            gp.ElasticAugment((1, 10, 10), (0, 0.1, 0.1), (0, math.pi/2))
        ]

    def run_training(self, batch_size=1, iterations=1):

        # Get pipeline and request for training
        pipeline, request, raw, target, prediction = self.training.training_pipeline(augmentations=self.augmentations,
                                                            batch_size = batch_size)

        # run the training pipeline for interations
        print(f"Starting training for {iterations} iterations...")
        with gp.build(pipeline):
            for i in range(iterations):
                batch = pipeline.request_batch(request)
                if i % 100 == 0 and i>0:
                    print(f"Completed training iteration {i}")
                    print("Loss: ", batch.loss)

        print("Training complete!")

        # Predict on the validation data
        print("Starting validation...")
        ret = self.training.validate_pipeline()

        return batch, ret, raw, target, prediction 


if __name__ == "__main__":

    data_path = input("Provide path to zarr container: ")

    print("-----")
    use_clahe = input("Would you like to use clahe data? (y/n): ")

    while use_clahe.lower() != 'y' and use_clahe.lower() != 'n':
        print("-----")
        print("Invalid input. Please enter 'y' or 'n' only.")
        use_clahe = input("Would you like to use clahe data? (y/n): ")

    if use_clahe.lower() == 'y':
        CLAHE = True
    elif use_clahe.lower() == 'n':
        CLAHE = False

    print("-----")
    has_mask = input("Does your training data have a mask? (y/n): ")

    while has_mask.lower() != 'y' and has_mask.lower() != 'n':
        print("-----")
        print("Invalid input. Please enter 'y' or 'n' only.")
        has_mask = input("Does your training data have a mask? (y/n): ")

    if has_mask.lower() == 'y':
        HAS_MASK = True
    else:
        HAS_MASK = False

    print("-----")
    print(f"Loading data from {data_path}...")

    run = Run(data_path, clahe=CLAHE, training_has_mask=HAS_MASK)
    batch, ret, train_raw, train_target, train_prediction = run.run_training(batch_size=1, iterations=1)
    # Check for convergence issue with batch size (Jan's UNet doesn't have batch normalisation)

    # Convert logits output from data to probabilities using softmax.
    probs = torch.nn.Softmax(dim=0)(torch.tensor(ret['prediction'].data))

    # Convert prediction probabilities into numpy arrays
    back_pred = probs[0,:,:,:].detach().numpy()
    pos_pred = probs[1,:,:,:].detach().numpy()
    neg_pred = probs[2,:,:,:].detach().numpy()

    date = datetime.today().strftime('%d_%m_%Y')

    # Save the validation prediction in zarr dictionary. 
    f = zarr.open(data_path + "/validate", mode='r+')
    f[f'Predictions/{date}/Background'] = back_pred
    f[f'Predictions/{date}/Positive'] = pos_pred
    f[f'Predictions/{date}/Negative'] = neg_pred 

    # Copy over attributes from target to predictions
    for atr in f['target'].attrs:
        f[f'Predictions/{date}/Background'].attrs[atr] = f['target'].attrs[atr]
        f[f'Predictions/{date}/Positive'].attrs[atr] = f['target'].attrs[atr]
        f[f'Predictions/{date}/Negative'].attrs[atr] = f['target'].attrs[atr]

    print("-----")
    visualise = input("Would you like to visualise the prediction? (y/n): ")

    while visualise.lower() != 'y' and visualise.lower() != 'n':
        print("-----")
        print("Invalid input. Please enter 'y' or 'n' only.")
        visualise = input("Would you like to visualise the prediction? (y/n): ")

    if visualise.lower() == 'y':
        imshow_napari_validation(data_path, date)