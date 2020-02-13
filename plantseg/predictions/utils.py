import os

import torch
import wget
import yaml

from plantseg import plantseg_global_path, PLANTSEG_MODELS_DIR
from plantseg.pipeline import gui_logger

# define constant values
CONFIG_TRAIN_YAML = "config_train.yml"
BEST_MODEL_PYTORCH = "best_checkpoint.pytorch"
LAST_MODEL_PYTORCH = "last_checkpoint.pytorch"

STRIDE_ACCURATE = "Accurate (slowest)"
STRIDE_BALANCED = "Balanced"
STRIDE_DRAFT = "Draft (fastest)"

STRIDE_MENU = {
    STRIDE_ACCURATE: 0.5,
    STRIDE_BALANCED: 0.75,
    STRIDE_DRAFT: 0.9
}


def create_predict_config(paths, cnn_config):
    """ Creates the configuration file needed for running the neural network inference"""

    def _stride_shape(patch_shape, stride_key):
        return [int(p * STRIDE_MENU[stride_key]) for p in patch_shape]

    # Load template config
    prediction_config = yaml.load(
        open(os.path.join(plantseg_global_path, "resources", "config_predict_template.yaml"), 'r'),
        Loader=yaml.FullLoader)

    # update loaders
    prediction_config["loaders"]["num_workers"] = cnn_config.get("num_workers", 8)
    prediction_config["loaders"]["mirror_padding"] = cnn_config.get("mirror_padding", True)

    # Add patch and stride to the config
    patch_shape = cnn_config["patch"]
    prediction_config["loaders"]["test"]["slice_builder"]["patch_shape"] = patch_shape
    stride_key, stride_shape = cnn_config["stride"], _stride_shape(patch_shape, "Balanced")

    if type(stride_key) is list:
        prediction_config["loaders"]["test"]["slice_builder"]["stride_shape"] = stride_key
    elif type(stride_key) is str:
        stride_shape = _stride_shape(patch_shape, stride_key)
        prediction_config["loaders"]["test"]["slice_builder"]["stride_shape"] = stride_shape
    else:
        raise RuntimeError(f"Unsupported stride type: {type(stride)}")

    # Add paths to raw data
    prediction_config["loaders"]["test"]["file_paths"] = paths

    # Add correct device for inference
    if cnn_config["device"] == 'cuda':
        prediction_config["device"] = torch.device("cuda:0")
    elif cnn_config["device"] == 'cpu':
        prediction_config["device"] = torch.device("cpu")
    else:
        raise RuntimeError(f"Unsupported device type: {cnn_config['device']}")

    # check if all files are in the data directory (~/.plantseg_models/) and download if needed
    check_models(cnn_config['model_name'], update_files=cnn_config['model_update'])

    # Add model path
    home = os.path.expanduser("~")
    prediction_config["model_path"] = os.path.join(home,
                                                   PLANTSEG_MODELS_DIR,
                                                   cnn_config['model_name'],
                                                   f"{cnn_config['version']}_checkpoint.pytorch")

    # Load train config and add missing info
    config_train = yaml.full_load(
        open(os.path.join(home,
                          PLANTSEG_MODELS_DIR,
                          cnn_config['model_name'],
                          CONFIG_TRAIN_YAML),
             'r'))

    # Load model configuration
    for key, value in config_train["model"].items():
        prediction_config["model"][key] = value

    # Additional attributes
    prediction_config["model_name"] = cnn_config["model_name"]
    prediction_config["model_update"] = cnn_config['model_update']
    prediction_config["state"] = cnn_config["state"]

    return prediction_config


def check_models(model_name, update_files=False):
    """
    Simple script to check and download trained modules
    """
    model_dir = os.path.join(os.path.expanduser("~"), PLANTSEG_MODELS_DIR, model_name)

    # Check if model directory exist if not create it
    if ~os.path.exists(model_dir):
        os.makedirs(model_dir, exist_ok=True)

    model_config_path = os.path.exists(os.path.join(model_dir, CONFIG_TRAIN_YAML))
    model_best_path = os.path.exists(os.path.join(model_dir, BEST_MODEL_PYTORCH))
    model_last_path = os.path.exists(os.path.join(model_dir, LAST_MODEL_PYTORCH))

    # Check if files are there, if not download them
    if (not model_config_path or
            not model_best_path or
            not model_last_path or
            update_files):

        # Read config
        model_file = os.path.join(plantseg_global_path, "resources", "models_zoo.yaml")
        config = yaml.load(open(model_file, 'r'), Loader=yaml.FullLoader)

        if model_name in config:
            url = config[model_name]["path"]

            gui_logger.info(f"Downloading model files from: '{url}' ...")
            wget.download(url + CONFIG_TRAIN_YAML, out=model_dir)
            wget.download(url + BEST_MODEL_PYTORCH, out=model_dir)
            wget.download(url + LAST_MODEL_PYTORCH, out=model_dir)
        else:
            raise RuntimeError(f"Custom model {model_name} corrupted. Required files not found.")
