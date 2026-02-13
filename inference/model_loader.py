# Imports ResNet-18 CNN architecture
from torchvision.models import resnet18
import torch.nn as nn
import torch

# Loads model weights and prepares model for inference.
def load_model(model_path, device):
    # Creates ResNet-18 model without pretrained weights
    model = resnet18(weights=None)

    # Retrieves number of input features for final fully connected layer
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, 2)

    # Load saved weights
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)

    model = model.to(device)
    model.eval()

    return model