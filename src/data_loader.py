import os
import zarr
import gunpowder as gp
import numpy as np 
from skimage import exposure
from torch.utils.data import Dataset

from config.load_configs import TRAINING_CONFIG


class EMData(Dataset):

    def __init__(self,
                 zarr_path: str,
                 train_validate_predict: str,
                 has_mask = False,
                 clahe = False
                 ):
        
        """
            Dataset subclass that loads in the EM data and defines required characteristics.
            Will perform consistency checks, e.g. if train or validate data, will ensure that 
            attributes for raw and gt match. 

            Attributes 
            -------------------
            has_mask (bool):
                Whether to expect mask data. Default is False.
            mode (str):
                The type of data. Options: 'train', 'validate' or 'predict'.
            zarr_path (str):
                Path to the zarr container. 
            data (zarr group):
                The zarr group containing the data.
            raw_data_path (str):
                Path to the raw zarr data within the zarr folder.
            raw_data (zarr array):
                The raw zarr data.
            gt_data_path (str): 
                Path to the ground truth data within the zarr folder. Only
                relevant for mode = 'train' or mode = 'validate'.
            gt_data (zarr array):
                The ground truth zarr data. Only relevant for mode = 'train'
                or mode = 'validate'.
            has_target (bool):
                Wether there already exists a 'target' zarr array. 
            target_data_path (str): 
                Path to the target data within the zarr folder. Only
                relevant for mode = 'train' or mode = 'validate'.
            target_data (zarr array):
                The target zarr data. Only relevant for mode = 'train'
                or mode = 'validate'.
            mask_data_path (str): 
                Path to the mask data within the zarr folder. Only
                relevant for has_mask = True.
            mask_data (zarr array):
                The mask zarr data. Only relevant for has_mask = True. 
            resolution (tuple):
                The resolution of the zarr data.
            axes (tuple):
                The axes orientation of the zarr data.
            voxel_size (gunpowder.coordinate):
                A gunpowder coordiante of the resolution. 

            Parameters
            -------------------
            zarr_path (str): 
                The path to the zarr group containing the data. 
            train_validate_predict (str): 
                The type of data. Options: 'train', 'validate', 'predict'. 
            has_mask (bool):
                Whether to expect the zarr group to contain mask data. Default: False.
            clahe (bool):
                Whether to use clahe raw data. If set to True but no clahe zarr array found, will 
                ask whether to create the clahe array on the fly. Default: False.
        """
        
        self.has_mask = has_mask
        
        train_validate_predict = train_validate_predict.lower()
        if train_validate_predict == "train" or train_validate_predict == "validate" or train_validate_predict == "predict":
            
            # Set the data mode type
            self.mode = train_validate_predict
        
            # Locate the zarr file and find the paths to different data types
            self.zarr_path = zarr_path

            # Check if the proviced zarr path is a zarr group
            if '.zgroup' not in os.listdir(self.zarr_path):
                raise FileNotFoundError(f"{self.zarr_path} does not contain required '.zgroup' file.")
            
            # Check if the zarr group has the required train/validate/predict folder
            if self.mode not in os.listdir(self.zarr_path):
                raise FileNotFoundError(f"{self.zarr_path} does not contain a {self.mode} folder.")
            
            # Check if train/validate/predict folder is a zarr group
            if '.zgroup' not in os.listdir(self.zarr_path + "/" + self.mode):
                raise FileNotFoundError(f"{self.zarr_path + "/" + self.mode} does not contain required '.zgroup' file.")

            # Read in the main zarr folder
            self.data = zarr.open(self.zarr_path, mode = 'r')

            # Locate correct raw data and assign
            if clahe:
                if 'raw_clahe' in os.listdir(self.zarr_path + "/" + self.mode):
                    self.raw_data_path = f"/{self.mode}/raw_clahe"
                    self.raw_data = self.data[self.mode]["raw_clahe"]
                else:
                    make_clahe = input(f"'raw_clahe' file not found in {self.zarr_path}/{self.mode}. Would you like to create a clahe file? (y/n) ")
                    if make_clahe.lower() == 'y':
                        self.create_clahe()
                        self.raw_data_path = f"/{self.mode}/raw_clahe"
                        self.raw_data = self.data[self.mode]["raw_clahe"]
                    else:
                        self.raw_data_path = f"/{self.mode}/raw"
                        self.raw_data = self.data[self.mode]["raw"]
            else:
                self.raw_data_path = f"/{self.mode}/raw"
                self.raw_data = self.data[self.mode]["raw"]

            # If train or validate, assign ground-truth data
            if self.mode == "train" or self.mode == "validate":

                if 'gt' not in os.listdir(self.zarr_path + "/" + self.mode):
                    raise FileNotFoundError(f"Ground-truth file is missing in {self.zarr_path}/{self.mode}")
                
                self.gt_data_path = f"/{self.mode}/gt"
                self.gt_data = self.data[self.mode]["gt"]

                # Check if target folder exists and assign target_data_path and target_data
                if 'target' in os.listdir(self.zarr_path + "/" + self.mode):
                    self.has_target = True
                    self.target_data_path = f"/{self.mode}/target"
                    self.target_data = self.data[self.mode]["target"]
                    # Check to see if the target data is at least as big as the input shape
                    if self.target_data.shape < TRAINING_CONFIG.input_shape:
                        self.has_target = False
                else:
                    self.has_target = False

                # Check if the data has a mask
                if self.has_mask:
                    if 'mask' in os.listdir(self.zarr_path + "/" + self.mode):
                        self.mask_data_path = f"/{self.mode}/mask"
                        self.mask_data = self.data[self.mode]["mask"]
                    else:
                        raise FileNotFoundError(f"Mask file is missing in {self.zarr_path}/{self.mode}")

            # Check raw data has zarr attributes
            if ".zattrs" in os.listdir(self.zarr_path + self.raw_data_path):

                # Check raw data has resolution attribute
                if "resolution" in self.raw_data.attrs:
                    self.resolution = self.raw_data.attrs["resolution"]
                else:
                    raise FileNotFoundError(f"{self.mode} raw data requires resolution attribute.")
                
                if "axes" in self.raw_data.attrs:
                    if self.raw_data.attrs["axes"] == ['z','y','x']:
                        self.axes = self.raw_data.attrs["axes"]
                    else:
                        raise ValueError(f"Raw data axes {self.raw_data.attrs["axes"]}. Axes must be ['z','y','x'].")
                else:
                    raise FileNotFoundError(f"{self.mode} raw data requires axes attribute with orientation [z,y,x].")

                # Check whether raw and gt data have same attributes
                if self.mode == "train" or self.mode == "validate":
                    if ".zattrs" in os.listdir(self.zarr_path + self.gt_data_path):
                        for atr in self.raw_data.attrs:
                            if atr in self.gt_data.attrs:
                                if self.raw_data.attrs[atr] != self.gt_data.attrs[atr]:
                                    raise ValueError(f"{atr} of raw and gt data does not match.")
                    else:
                        raise FileNotFoundError(f"{self.mode} ground-truth data has no attributes. Required attributes: resolution.")
            
            else:
                raise FileNotFoundError(f"{self.mode} raw data has no attributes. Required attributes: resolution.")

            self.voxel_size = gp.Coordinate(self.resolution)

        else:
            raise ValueError("Train_Validate_Test must be either 'Train', 'Validate' or 'Predict'.")
        
    def __len__(self):
        """ 
            Returns the length of the raw data shape 
        """
        return len(self.raw_data.shape)

    def __getitem__(self, index):
        """ 
            Returns a dictionary containing the raw and ground truth data at index.
        """

        if self.mode == "predict":
            raw_data = self.raw_data[index]
            return {"raw": raw_data}

        else:
            # Load the raw and ground truth data
            raw_data = self.raw_data[index]
            gt_data = self.gt_data[index]

            # Return a dictionary containing data
            return {"raw": raw_data, "gt": gt_data}
        
    def create_target(self, data_type = 'int64'):
        """ 
            Create new zarr array, 'target', that is a copy of 'gt' but with different dtype. 
            If 'target' already exists, it will be overwritten. 

            Parameters
            -------------------
            data_type (str):
                The data type that target should take. Default: int64. 
        """

        # Open the zarr file in read and write mode
        f = zarr.open(self.zarr_path + "/" + self.mode , mode='r+')

        # change data type of gt
        gt = f['gt'].astype(data_type)

        # Check if the gt data is at least as big as the input shape for the model
        if gt.shape < TRAINING_CONFIG.input_shape:
    
            diff_z = TRAINING_CONFIG.input_shape[0] - gt.shape[0]
            diff_y = TRAINING_CONFIG.input_shape[1] - gt.shape[1]
            diff_x = TRAINING_CONFIG.input_shape[2] - gt.shape[2]

            # Account for dimesions with gt.shape[i] > input_shape[i]
            if diff_z < 0:
                diff_z = 0
            if diff_y < 0:
                diff_y =0
            if diff_x <0:
                diff_x = 0 

            # Pad gt to account for difference between input shape
            gt = np.pad(gt, ((0, diff_z), (0, diff_y), (0, diff_x)), 'constant')

        # Create target zarr array
        f['target'] = gt
        
        # Copy over attributes from gt to target
        for atr in f['gt'].attrs:
            f['target'].attrs[atr] = f['gt'].attrs[atr]
        
        self.target_data_path = f"/{self.mode}/target"
        self.target_data = self.data[self.mode]["target"]
        self.has_target = True 

    def create_clahe(self):
        """
            Create a clahe version of the raw data.
        """
        f = zarr.open(self.zarr_path + "/" + self.mode , mode='r+')
        raw = f['raw'] 
        raw_clahe = np.array([
                    exposure.equalize_adapthist(raw[z], kernel_size=128)
                    for z in range(raw.shape[0])
                ], dtype=np.float32)
        f['raw_clahe'] = raw_clahe
        for atr in f['raw'].attrs:
            f['raw_clahe'].attrs[atr] = f['raw'].attrs[atr]