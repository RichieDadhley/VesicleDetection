import matplotlib.pyplot as plt
import numpy as np
import napari
import zarr

def imshow_napari_validation(data_path, save_location):
    f = zarr.open(data_path + "/validate", mode='r')
    raw_data = f['raw_clahe'][:,:,:]
    target_data = f['target'][:,:,:]
    background_pred = f[f'{save_location}/Background'][:,:,:]
    positive_pred = f[f'{save_location}/Positive'][:,:,:]
    negative_pred = f[f'{save_location}/Negative'][:,:,:]

    # Obtain difference between input shape and output shape, to allow alignment in napari
    padding = [int((raw_data.shape[0]-positive_pred.shape[0])/2), 
               int((raw_data.shape[1]-positive_pred.shape[1])/2), 
               int((raw_data.shape[2]- positive_pred.shape[2])/2)]

    viewer = napari.Viewer()
    viewer.add_image(data=raw_data, name='Raw')
    viewer.add_image(data=target_data, name='Target', blending='additive', colormap='inferno')
    viewer.add_image(data=positive_pred, name='Positive', blending='additive', colormap='yellow', translate=padding)
    viewer.add_image(data=negative_pred, name='Negative', blending='additive', colormap='red', translate=padding)
    napari.run()

if __name__ == "__main__":

    data_path = input("Provide the path to zarr container: ")
    date = input("Provide the prediction date (d_m_Y): ")

    imshow_napari_validation(data_path=data_path, save_location= 'Predictions/' + date) 
