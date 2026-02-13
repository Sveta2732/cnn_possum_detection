import os
import re

#  Folder containing the ROI files
folder_path = "crops/file_name"


#  Threshold filename: all files with lower frame/ROI numbers will be deleted
threshold_name = "frame_000087_roi_01"

# Function to extract frame and ROI numbers from filename
def get_frame_roi_number(filename):
    """
    From a filename like 'frame_000031_roi_57', returns a tuple: (31, 57)

    """
    match = re.match(r"frame_(\d+)_roi_(\d+)", filename)
    if match:
        frame_num = int(match.group(1))
        roi_num = int(match.group(2))
        return frame_num, roi_num
    return None

# Get frame and ROI numbers from threshold filename
threshold_numbers = get_frame_roi_number(threshold_name)
if threshold_numbers is None:
    raise ValueError(f" Wrong threshold_name: {threshold_name}")

threshold_frame, threshold_roi = threshold_numbers

# Process each file in the folder
folder_full_path = os.path.join(os.getcwd(), folder_path)

for filename in os.listdir(folder_full_path):
    file_path = os.path.join(folder_full_path, filename)
    
    numbers = get_frame_roi_number(filename)
    if numbers is None:
        # ignore files that don't match the pattern
        continue  
    
    frame_num, roi_num = numbers
    
    # 1 Delete files with frame/ROI numbers less than the threshold
    if (frame_num, roi_num) < (threshold_frame, threshold_roi):
        os.remove(file_path)
        print(f"Deleted {filename}")
    
    # 2 Delete files with frame/ROI numbers greater than the threshold (if needed, currently commented out)
    # if (frame_num, roi_num) > (threshold_frame, threshold_roi):
    #     os.remove(file_path)
    #     print(f"Deleted {filename}")
    
    # 3 Delete files within a specific range (if needed, currently commented out)
    # lower = get_frame_roi_number("frame_000050_roi_20")
    # upper = get_frame_roi_number("frame_000100_roi_50")
    # if lower and upper and lower <= (frame_num, roi_num) <= upper:
    #     os.remove(file_path)
    #     print(f"Deleted {filename}")