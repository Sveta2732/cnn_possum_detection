# OpenCV for video stream processing and drawing bounding boxes
import cv2
import os
import time
# Logging system for debugging and monitoring runtime behaviour
import logging
import numpy as np

from datetime import datetime
# Sliding window implementation for stabilising detection signals
from collections import deque
# PyTorch for model inference and device handling
import torch
# Project configuration
from config import RTSP_URL, MODEL_PATH
# Custom logging setup
from logger import setup_logger
# Motion detection module returning Regions of Interest (ROIs) and bounding boxes
from vision.crops_for_videos import get_crops_from_frame
# Model loading logic
from inference.model_loader import load_model
# Core ML inference logic (possum classification)
from inference.detector import detect_possums
# Image preprocessing pipeline used before feeding ROIs into model
from inference.transforms import build_test_transform
# Video capture initialisation with auto-reconnect logic
from video_utils.video_capture import initialise_video_capture
# Visit lifecycle management
from visits.visit_manager import create_new_visit, close_visit

# Initialise project-wide logging
setup_logger()

# PARAMETERS
# Skip frames to reduce computational load and latency
SKIP_FRAMES = 5                  # Only process every N-th frame
# Generate folder per day
today = datetime.now().strftime("%Y-%m-%d")
# Directory for storing possum-related media files
POSSUM_DIR = os.path.join("possum_detected", today)   
os.makedirs(POSSUM_DIR, exist_ok=True)
# Select GPU if available, otherwise fallback to CPU
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# Save only every N-th confirmed possum frame 
FRAME_SAVE_INTERVAL = 3

# ML PREPARATION
# Transform for inference
test_transform = build_test_transform()
# LOAD TRAINED MODEL
model = load_model(MODEL_PATH, DEVICE)
             
# VIDEO CAPTURE INITIALISATION
# Opens RTSP camera stream and retrieves FPS
cap, v_fps = initialise_video_capture(RTSP_URL)

# PIPELINE STATE VARIABLES
# Global frame counter
frame_idx = 0
# Timer for periodic log
start_time = time.time()    
# Sliding window size     
window_size = 5       
# Stores last N detection results to reduce false positives         
possum_window = deque(maxlen=window_size) 

# Seconds without possum to close a visit
VISIT_TIMEOUT = 120 
# Current possum visit
current_visit = None  

# MOTION DETECTION PARAMETERS
PADDING_RATIO = 0.3
MIN_AREA = 400
# Kernel used to clean motion masks
KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

# Background subtractor used to detect moving objects
BG_SUBTRACTOR = cv2.createBackgroundSubtractorMOG2(
    history=500,
    varThreshold=25,
    detectShadows=False
)

# MAIN VIDEO PROCESSING LOOP
while True:
    # Read frame from camera stream
    ret, frame = cap.read()

    # Camera reconnect logic
    if not ret:
        logging.info("Frame not received. Reconnecting...")

        try:
            cap.release()
        except:
            pass
        # Wait before reconnect attempt
        time.sleep(2)
        cap, v_fps = initialise_video_capture(RTSP_URL)

        continue

    # Frame integrity checks (protect pipeline from corrupted frames)
    if frame is None:
        logging.warning("Frame is None")
        time.sleep(1)
        continue

    if not isinstance(frame, np.ndarray):
        logging.warning("Frame is not ndarray")
        time.sleep(1)
        continue


    if frame.size == 0:
        logging.warning("Frame is empty")
        time.sleep(1)
        continue

    # Visit timeout logic
    if current_visit is not None:
        if (datetime.now() - current_visit["last_seen_time"]).total_seconds() > VISIT_TIMEOUT:

            # Close visit session and trigger upload asynchronously
            close_visit(current_visit, v_fps)
 
            current_visit = None
            possum_window.clear()

    # Save raw video if visit is active
    if current_visit is not None and current_visit["video_writer"] is not None:
        current_visit["video_writer"].write(frame)   
        #current_visit["frame_timestamps"].append(frame_idx)


    # Only process every SKIP_FRAMES-th frame
    if frame_idx % SKIP_FRAMES == 0:
        # Motion detection: get ROIs and bounding boxes
        rois, bboxes = get_crops_from_frame(frame, bg_subtractor=BG_SUBTRACTOR, min_area=MIN_AREA, padding_ratio=PADDING_RATIO, kernel=KERNEL)

        #  Initialize flag for possum detection in this frame
        # ML inference block
        try:
            # Run CNN classification on ROIs
            possum_detected_in_frame, possum_rois_in_frame, possum_bboxes_in_frame, possum_indices = detect_possums(
                rois,
                bboxes,
                model,
                test_transform,
                DEVICE
            )
        except Exception:
            # Fault-tolerance: prevents full pipeline crash if ML inference fails
            logging.exception("Inference failed")
            frame_idx += 1
            # Assume no possum detected
            possum_window.append(False)
            continue
        # Draw bounding boxes on frame
        display_frame = frame.copy()

        for i, bbox in enumerate(bboxes):
            x1, y1, x2, y2 = bbox
            # Green = possum, Red = other motion
            color = (0, 255, 0) if i in possum_indices else (0, 0, 255)
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)

        cv2.imshow("Video Feed", display_frame)


        # Save possum ROIs in separate folder
        if possum_detected_in_frame:

            for roi_num, roi in enumerate(possum_rois_in_frame):
                # Add timestamp to filename
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                roi_path = os.path.join(POSSUM_DIR, f"roi_{frame_idx:06d}_{roi_num:03d}_{timestamp_str}.jpg")
                cv2.imwrite(roi_path, roi)

            
        # Update sliding window
        possum_window.append(possum_detected_in_frame)

        # Check if 3 out of 5 last frames have possum
        if len(possum_window) == window_size and sum(possum_window) >= 3:
            logging.info(f"POSSUM DETECTED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            # Update existing visit timestamp
            now_time = datetime.now()
            if current_visit is not None and possum_detected_in_frame:
                current_visit["last_seen_time"] = now_time
                current_visit["last_seen_frame"] = frame_idx

            # Create new visit if none active
            if current_visit is None:
                current_visit = create_new_visit(frame, POSSUM_DIR, frame_idx, v_fps                    )
           

            # Save visit frames and ROIs
            if frame_idx % FRAME_SAVE_INTERVAL == 0 and possum_detected_in_frame:
                current_visit["last_seen_time"] = now_time
                current_visit["last_seen_frame"] = frame_idx
                

                frame_path = os.path.join(current_visit["frames_dir"], f"frame_{frame_idx:06d}.jpg")
                cv2.imwrite(frame_path, frame)
                visit_id = current_visit["visit_id"]
                current_visit["frame_upload_queue"].append(
                    (frame_path, now_time)
                )
 
                for roi_num, roi in enumerate(possum_rois_in_frame):

                    roi_path = os.path.join(
                        current_visit["rois_dir"],
                        f"roi_{frame_idx:06d}_{roi_num:03d}.jpg"
                    )

                    cv2.imwrite(roi_path, roi)


                    current_visit["roi_upload_queue"].append(
                        (roi_path, possum_bboxes_in_frame[roi_num], frame_path, now_time)
                    )

    frame_idx += 1

    # Periodic logging every 60 seconds if no possum
    if time.time() - start_time > 60:
        if not any(possum_window):
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"[{now_str}] 1 minute passed, processing continues. No possums detected so far.")
        start_time = time.time()

    # Manual exit handler
    if cv2.waitKey(1) & 0xFF == ord('q'):
        logging.info("Exiting by user request.")
        break

# CLEANUP
cap.release()
cv2.destroyAllWindows()
logging.info("Video feed processing stopped, all resources released.")



