import cv2
 # Pillow library used for image format conversion compatible with torchv
from PIL import Image
import torch

# Function to classify ROIs and identify possums using trained model
def detect_possums(rois, bboxes, model, transform, device):

    possum_detected = False
    possum_rois = []
    possum_bboxes = []
    possum_indices = []

    for i, roi in enumerate(rois):
         # Converts ROI from OpenCV BGR format to RGB and converts numpy array to PIL image
        img = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
        # Applies preprocessing transform, adds batch dimension, and moves tensor to device
        input_tensor = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            # Runs forward pass through model
            outputs = model(input_tensor)
            # Selects class with highest prediction score
            _, pred = torch.max(outputs, 1)

        if pred.item() == 1:
            # Marks that at least one possum was detected
            possum_detected = True
            # Keep only possum ROIs
            possum_rois.append(roi)
            possum_bboxes.append(bboxes[i])
            possum_indices.append(i)

    return (
        possum_detected,
        possum_rois,
        possum_bboxes,
        possum_indices
    )