import cv2
import os
import time
from datetime import datetime
import torch
from torchvision import transforms
from PIL import Image
from crops_for_videos import get_crops_from_frame, save_debug_frame
from collections import deque

# PARAMETERS
SKIP_FRAMES = 5                  # Only process every N-th frame
DEBUG_DIR = "debug_feed"         
POSSUM_DIR = "possum_detected"   
os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(POSSUM_DIR, exist_ok=True)

DEBUG_FRAME_LIMIT = 10           # Number of initial frames to save for debug
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# TRANSFORMS FOR CNN
mean = [0.485, 0.456, 0.406]
std = [0.229, 0.224, 0.225]

# Custom Resize with padding
class ResizeWithPadding:
    def __init__(self, size=224, fill=0):
        self.size = size
        self.fill = fill

    def __call__(self, img):
        # Original image size
        w, h = img.size
        scale = self.size / max(w, h)
        new_w, new_h = int(w*scale), int(h*scale)
        img = transforms.functional.resize(img, (new_h, new_w))
        pad_w = self.size - new_w
        pad_h = self.size - new_h
        padding = (pad_w//2, pad_h//2, pad_w - pad_w//2, pad_h - pad_h//2)
        return transforms.functional.pad(img, padding, fill=self.fill)

# Transform for inference
test_transform = transforms.Compose([
    ResizeWithPadding(224),
    transforms.ToTensor(),
    transforms.Normalize(mean, std)
])

# LOAD TRAINED MODEL
model = torch.load("tf_model")  
model = model.to(DEVICE)
 # Set model to evaluation mode
model.eval()                   

# OPEN VIDEO FEED
cap = cv2.VideoCapture(CAMERA_RTSP_URL)  

# INITIALIZATION
frame_idx = 0
debug_idx = 0
# Timer for periodic log
start_time = time.time()    
# Sliding window size     
window_size = 5       
# Store last 5 frames info          
possum_window = deque(maxlen=window_size) 

PADDING_RATIO = 0.3
MIN_AREA = 400
KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))


BG_SUBTRACTOR = cv2.createBackgroundSubtractorMOG2(
    history=500,
    varThreshold=25,
    detectShadows=False
)



# MAIN LOOP
while True:
    ret, frame = cap.read()

    if not ret:
        print("Frame not received. Waiting 1 second before retry...")
        time.sleep(1)
        
        if not cap.isOpened():
            print("Reopening camera...")
            cap.release()
            cap = cv2.VideoCapture(CAMERA_RTSP_URL)
        continue


    # Only process every SKIP_FRAMES-th frame
    if frame_idx % SKIP_FRAMES == 0:
        # 1 Motion detection: get ROIs and bounding boxes
        rois, bboxes = get_crops_from_frame(frame, bg_subtractor=BG_SUBTRACTOR, min_area=MIN_AREA, padding_ratio=PADDING_RATIO, kernel=KERNEL)

        #  2 Initialize flag for possum detection in this frame
        possum_detected_in_frame = False
        # Save only ROIs where possum is detected
        possum_rois_in_frame = []  
        # 3 Loop through ROIs
        for roi in rois:
            # Convert OpenCV BGR PIL RGB
            img = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
            input_tensor = test_transform(img).unsqueeze(0).to(DEVICE)  

            # Run inference
            with torch.no_grad():
                outputs = model(input_tensor)
                _, pred = torch.max(outputs, 1)

            if pred.item() == 1:  
                possum_detected_in_frame = True
                # Keep only possum ROIs
                possum_rois_in_frame.append(roi)  

        # Draw bounding boxes on frame
        for bbox in bboxes:
            x1, y1, x2, y2 = bbox
            color = (0, 255, 0) if possum_detected_in_frame else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Display the frame
        cv2.imshow("Video Feed", frame)

        # 4 Save first 10 debug frames (all ROIs)
        if debug_idx < DEBUG_FRAME_LIMIT:
            debug_path = os.path.join(DEBUG_DIR, f"frame_{debug_idx:06d}.jpg")
            save_debug_frame(frame, bboxes, debug_path)
            # Save all ROIs
            for roi_num, roi in enumerate(rois):
                roi_name = os.path.join(DEBUG_DIR, f"frame_{debug_idx:06d}_roi_{roi_num:03d}.jpg")
                cv2.imwrite(roi_name, roi)
            debug_idx += 1

        # 5 Save possum ROIs immediately in separate folder
        if possum_detected_in_frame:
            frame_possum_dir = os.path.join(POSSUM_DIR, f"frame_{frame_idx:06d}")
            os.makedirs(frame_possum_dir, exist_ok=True)
            for roi_num, roi in enumerate(possum_rois_in_frame):
                roi_name = os.path.join(frame_possum_dir, f"roi_{roi_num:03d}.jpg")
                cv2.imwrite(roi_name, roi)

        # 6 Update sliding window
        possum_window.append(possum_detected_in_frame)

        # 7 Check if 3 out of 5 last frames have possum
        if len(possum_window) == window_size and sum(possum_window) >= 3:
            print(f"POSSUM DETECTED! Stopping process at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            # Show possum ROIs from last 5 frames
            print("Showing possum ROIs from last 5 frames...")
            # Stop the main loop
            break  

        # Print frame info
        print(f"Frame {frame_idx}: {len(rois)} ROIs detected, possum detected: {possum_detected_in_frame}")

    frame_idx += 1

    # 8 Periodic logging every 60 seconds if no possum
    if time.time() - start_time > 60:
        if not any(possum_window):
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now_str}] 1 minute passed, processing continues. No possums detected so far.")
        start_time = time.time()

    # 9 Exit on 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Exiting by user request.")
        break

# CLEANUP
cap.release()
cv2.destroyAllWindows()
print("Video feed processing stopped, all resources released.")

