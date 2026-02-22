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
STATIC_SAVE_INTERVAL_SEC = 10
# Generate folder per day
today = datetime.now().strftime("%Y-%m-%d")
# Directory for storing possum-related media files
POSSUM_DIR = os.path.join("possum_detected", today)   
os.makedirs(POSSUM_DIR, exist_ok=True)
# Select GPU if available, otherwise fallback to CPU
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# Save only every N-th confirmed possum frame 
FRAME_SAVE_INTERVAL = 2

# ML PREPARATION
# Transform for inference
test_transform = build_test_transform()
# LOAD TRAINED MODEL
model = load_model(MODEL_PATH, DEVICE)
             
# VIDEO CAPTURE INITIALISATION
USE_VIDEO_FILE = False
#VIDEO_PATH = "test_video.mp4"
VIDEO_PATH = r"C:\Users\Home\Desktop\for_git\video_project\possum_detected\2026-02-21\visit_0125\visit.mp4"
# Opens RTSP camera stream and retrieves FPS
if USE_VIDEO_FILE:
    cap = cv2.VideoCapture(VIDEO_PATH)
    v_fps = cap.get(cv2.CAP_PROP_FPS)
else:
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
no_motion_window = deque(maxlen=window_size)


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
    frame_timestamp = datetime.now()

    # Camera reconnect logic
    if not ret:
        if USE_VIDEO_FILE:
            logging.info("Video ended.")
            if current_visit is not None:
                logging.info("Closing active visit before exit.")
                close_visit(current_visit, v_fps)

            break
            
        else:

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

    # # Visit timeout logic
    # if current_visit is not None:
    #     if (datetime.now() - current_visit["last_seen_time"]).total_seconds() > VISIT_TIMEOUT:

    #         # Close visit session and trigger upload asynchronously
    #         close_visit(current_visit, v_fps)
 
    #         current_visit = None
    #         possum_window.clear()

    # Save raw video if visit is active
    if current_visit is not None and current_visit["video_writer"] is not None:
        current_visit["video_writer"].write(frame)   
        #current_visit["frame_timestamps"].append(frame_idx)


    # Only process every SKIP_FRAMES-th frame
    if frame_idx % SKIP_FRAMES == 0:
        # Motion detection: get ROIs and bounding boxes
        rois, bboxes = get_crops_from_frame(frame, bg_subtractor=BG_SUBTRACTOR, min_area=MIN_AREA, padding_ratio=PADDING_RATIO, kernel=KERNEL)

        if len(rois) > 0:
            no_motion_window.clear()
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

         # --- NEW: Handle no-motion but active visit ---
        if current_visit is not None and len(rois) == 0:

            if current_visit.get("last_bbox") is not None:

                x1, y1, x2, y2 = current_visit["last_bbox"]

                h, w = frame.shape[:2]
                x1 = max(0, min(w, x1))
                x2 = max(0, min(w, x2))
                y1 = max(0, min(h, y1))
                y2 = max(0, min(h, y2))

                roi = frame[y1:y2, x1:x2]

                if roi.size > 0:
                    try:
                        possum_detected, _, _, _ = detect_possums(
                            [roi],
                            [(x1, y1, x2, y2)],
                            model,
                            test_transform,
                            DEVICE
                        )

                        no_motion_window.append(possum_detected)

                    except Exception:
                        logging.exception("Inference failed in no-motion mode")
                        no_motion_window.append(False)

                else:
                    no_motion_window.append(False)

                if len(no_motion_window) == window_size:

                    # Continue visit if still enough positives
                    if sum(no_motion_window) >= 3:
                        logging.info("No motion but possum still detected - continuing visit")
                        # Still possum - continue visit
                        current_visit["last_seen_time"] = frame_timestamp
                        current_visit["last_seen_frame"] = frame_idx

                        # Save frame periodically
                        #if frame_idx % FRAME_SAVE_INTERVAL == 0:
                        now = frame_timestamp

                        last_saved = current_visit.get("last_static_saved_time")

                        should_save_static = (
                            last_saved is None or
                            (now - last_saved).total_seconds() >= STATIC_SAVE_INTERVAL_SEC
                        )

                        if should_save_static:    

                            frame_path = os.path.join(
                                current_visit["frames_dir"],
                                f"frame_{frame_idx:06d}.jpg"
                            )

                            cv2.imwrite(frame_path, frame)

                            current_visit["frame_upload_queue"].append(
                                (frame_path, frame_timestamp)
                            )

                            # Save ROI
                            roi_path = os.path.join(
                                current_visit["rois_dir"],
                                f"roi_{frame_idx:06d}_static.jpg"
                            )

                            cv2.imwrite(roi_path, roi)

                            current_visit["roi_upload_queue"].append(
                                (roi_path, (x1, y1, x2, y2), frame_path, frame_timestamp)
                            )

                            current_visit["last_static_saved_time"] = now

                    # Close visit only if strong negative evidence
                    elif sum(no_motion_window) <= 1:
                        logging.info("Closing visit (no motion + no possum confirmed)")
                        close_visit(current_visit, v_fps)
                        current_visit = None
                        no_motion_window.clear()

        # Check if 3 out of 5 last frames have possum
        if len(possum_window) == window_size and sum(possum_window) >= 3:
            logging.info(f"POSSUM DETECTED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            # Update existing visit timestamp
            #now_time = datetime.now()

            if current_visit is not None and possum_detected_in_frame:
                #current_visit["last_seen_time"] = now_time
                current_visit["last_seen_time"] = frame_timestamp
                current_visit["last_seen_frame"] = frame_idx
                if possum_detected_in_frame and len(possum_bboxes_in_frame) > 0:
                    current_visit["last_bbox"] = possum_bboxes_in_frame[0]

            # Create new visit if none active
            if current_visit is None:
                current_visit = create_new_visit(frame, POSSUM_DIR, frame_idx, v_fps)
                no_motion_window.clear()
                current_visit["last_static_saved_time"] = None
                if possum_detected_in_frame and len(possum_bboxes_in_frame) > 0:
                    current_visit["last_bbox"] = possum_bboxes_in_frame[0]
           

            # Save visit frames and ROIs
            if frame_idx % FRAME_SAVE_INTERVAL == 0 and possum_detected_in_frame:
                #current_visit["last_seen_time"] = now_time
                current_visit["last_seen_time"] = frame_timestamp
                current_visit["last_seen_frame"] = frame_idx
                

                frame_path = os.path.join(current_visit["frames_dir"], f"frame_{frame_idx:06d}.jpg")
                cv2.imwrite(frame_path, frame)
                visit_id = current_visit["visit_id"]
                current_visit["frame_upload_queue"].append(

                    #(frame_path, now_time)
                    (frame_path, frame_timestamp)
                )
 
                for roi_num, roi in enumerate(possum_rois_in_frame):

                    roi_path = os.path.join(
                        current_visit["rois_dir"],
                        f"roi_{frame_idx:06d}_{roi_num:03d}.jpg"
                    )

                    cv2.imwrite(roi_path, roi)


                    current_visit["roi_upload_queue"].append(
                        #(roi_path, possum_bboxes_in_frame[roi_num], frame_path, now_time)
                        (roi_path, possum_bboxes_in_frame[roi_num], frame_path, frame_timestamp)
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



