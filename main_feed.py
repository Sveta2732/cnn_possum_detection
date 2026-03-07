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

import threading
# Project configuration
from config import RTSP_URL, MODEL_PATH, FENCE_Y_THRESHOLD, UNDER_FENCE_WAIT_SEC
# Custom logging setup
from logger import setup_logger
# Motion detection module returning Regions of Interest (ROIs) and bounding boxes
from vision.crops_for_videos import get_crops_from_frame
from vision.spatial_rules import is_under_fence, DEFAULT_FENCE_Y_THRESHOLD
# Model loading logic
from inference.model_loader import load_model
# Core ML inference logic (possum classification)
from inference.detector import detect_possums
# Image preprocessing pipeline used before feeding ROIs into model
from inference.transforms import build_test_transform, expand_bbox
# Video capture initialisation with auto-reconnect logic
from video_utils.video_capture import initialise_video_capture
# Visit lifecycle management
from visits.visit_manager import create_new_visit, close_visit, upload_queue, should_close_visit
from hardware.feeder import trigger_feeder

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
VIDEO_PATH = r"C:\Users\Home\Desktop\for_git\video_project\possum_detected\2026-02-27\visit_0222\visit2.mp4"
# Opens RTSP camera stream and retrieves FPS
if USE_VIDEO_FILE:
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("❌ Failed to open video")
    else:
        print("✅ Video opened successfully")

    print("FPS:", cap.get(cv2.CAP_PROP_FPS))
    print("Frame count:", cap.get(cv2.CAP_PROP_FRAME_COUNT))
    v_fps = cap.get(cv2.CAP_PROP_FPS)
else:
    cap, v_fps = initialise_video_capture(RTSP_URL)
    print("Camera FPS:", v_fps)


# PIPELINE STATE VARIABLES
# Global frame counter
frame_idx = 0

# THREADING SHARED STATE
shared_frame = None
shared_timestamp = None
frame_lock = threading.Lock()
stop_event = threading.Event()
visit_active = False
request_close_visit = False
# Timer for periodic log
start_time = time.time()    
    
# Stores last N detection results to reduce false positives         
safe_fps = v_fps if v_fps and v_fps > 0 else 25
inference_fps = safe_fps / SKIP_FRAMES
window_size = int(inference_fps * 4)

# Last 5 detections to confirm stable possum presence (3/5 rule)
possum_window = deque(maxlen=5)

# Last 20 detections with motion; close if all are negative
possum_absence_window = deque(maxlen=20)

# Detections during no-motion; close if all are negative
no_motion_window = deque(maxlen=window_size)

# Last 5 no-motion detections to keep visit alive if possum is stationary
still_window = deque(maxlen=5)

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

def capture_loop():
    global shared_frame, shared_timestamp, visit_active, current_visit, cap, v_fps, request_close_visit

    while not stop_event.is_set():
        
        ret, frame = cap.read()
        timestamp = datetime.now()
        if USE_VIDEO_FILE:
            time.sleep(1 / v_fps)

        if not ret:
            if USE_VIDEO_FILE:
                
                logging.info("Video ended.")
                stop_event.set()
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
        

        visit_to_close = None

        with frame_lock:
            if visit_active and current_visit is not None and current_visit["video_writer"] is not None:
                current_visit["video_writer"].write(frame)

                if request_close_visit:
                    logging.info("Closing visit from capture thread")

                    visit_to_close = current_visit
                    current_visit = None
                    visit_active = False
                    request_close_visit = False

        if visit_to_close is not None:
            close_visit(visit_to_close, v_fps)

        with frame_lock:
            shared_frame = frame.copy()
            shared_timestamp = timestamp

capture_thread = threading.Thread(target=capture_loop, daemon=True)
capture_thread.start()

# MAIN VIDEO PROCESSING LOOP
while not stop_event.is_set():
    # Read frame from camera stream
    # ret, frame = cap.read()
    # frame_timestamp = datetime.now()

    with frame_lock:
        if shared_frame is None:
            time.sleep(0.01)
            continue
        frame = shared_frame.copy()
        frame_timestamp = shared_timestamp
        local_visit = current_visit


    # Only process every SKIP_FRAMES-th frame
    if frame_idx % SKIP_FRAMES == 0:
        # Motion detection: get ROIs and bounding boxes
        rois, bboxes = get_crops_from_frame(frame, bg_subtractor=BG_SUBTRACTOR, min_area=MIN_AREA, padding_ratio=PADDING_RATIO, kernel=KERNEL)

        if len(rois) > 0:
            no_motion_window.clear()
            still_window.clear()
        #  Initialize flag for possum detection in this frame
        # ML inference block
        try:
            # start_inf = time.time()
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
            possum_absence_window.append(False)
            continue
        # Draw bounding boxes on frame
        display_frame = frame.copy()
        # torch.cuda.synchronize()
        # processing_time = time.time() - start_inf
        # if processing_time > 0:
        #     print(1 / processing_time)

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
        if len(rois) > 0:
            possum_absence_window.append(possum_detected_in_frame)

         # NEW: Handle no-motion but active visit ---
        if local_visit is not None and len(rois) == 0:

            if local_visit.get("last_bbox") is not None:

                expanded_bbox = expand_bbox(
                    local_visit["last_bbox"],
                    frame.shape,
                    scale=1.5
                )

                x1, y1, x2, y2 = expanded_bbox

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
                        still_window.append(possum_detected)
                        possum_absence_window.append(possum_detected)

                    except Exception:
                        logging.exception("Inference failed in no-motion mode")
                        no_motion_window.append(False)
                        still_window.append(False)

                else:
                    no_motion_window.append(False)
                    still_window.append(False)

                # Continue visit if still enough positives
                if len(still_window) == 5 and sum(still_window) >= 3:
                    logging.info("No motion but possum still detected - continuing visit")
                    # Still possum - continue visit
                    with frame_lock:
                        if current_visit is not None:
                            current_visit["last_seen_time"] = frame_timestamp
                            current_visit["last_seen_frame"] = frame_idx


                    # Save frame periodically
                    #if frame_idx % FRAME_SAVE_INTERVAL == 0:
                    now = frame_timestamp

                    last_saved = local_visit.get("last_static_saved_time")

                    should_save_static = (
                        last_saved is None or
                        (now - last_saved).total_seconds() >= STATIC_SAVE_INTERVAL_SEC
                    )

                    if should_save_static:    

                        frame_path = os.path.join(
                            local_visit["frames_dir"],
                            f"frame_{frame_idx:06d}.jpg"
                        )

                        cv2.imwrite(frame_path, frame)

                        local_visit["frame_upload_queue"].append(
                            (frame_path, frame_timestamp)
                        )

                        # Save ROI
                        roi_path = os.path.join(
                            local_visit["rois_dir"],
                            f"roi_{frame_idx:06d}_static.jpg"
                        )

                        cv2.imwrite(roi_path, roi)

                        local_visit["roi_upload_queue"].append(
                            (roi_path, (x1, y1, x2, y2), frame_path, frame_timestamp)
                        )

                        local_visit["last_static_saved_time"] = now


        if should_close_visit(
            local_visit,
            possum_absence_window,
            no_motion_window,
            frame_timestamp,
            window_size,
            FENCE_Y_THRESHOLD,
            UNDER_FENCE_WAIT_SEC
        ):
            logging.info("Close condition triggered")

            with frame_lock:
                request_close_visit = True

            possum_window.clear()
            possum_absence_window.clear()
            no_motion_window.clear()
            still_window.clear()

            continue

        # Check if 3 out of 5 last frames have possum
        if len(possum_window) == 5 and sum(possum_window) >= 3:
            logging.info(f"POSSUM DETECTED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            # Update existing visit timestamp
            #now_time = datetime.now()

            if local_visit is not None and possum_detected_in_frame:
                #current_visit["last_seen_time"] = now_time
                with frame_lock:
                    if current_visit is not None:
                        current_visit["last_seen_time"] = frame_timestamp
                        current_visit["last_seen_frame"] = frame_idx
                if possum_detected_in_frame and len(possum_bboxes_in_frame) > 0:
                    with frame_lock:
                        if current_visit is not None:
                            current_visit["last_bbox"] = possum_bboxes_in_frame[0]

            # Create new visit if none active
            with frame_lock:
                if current_visit is None:
                    current_visit = create_new_visit(frame, POSSUM_DIR, frame_idx, v_fps)
                    visit_active = True
                    trigger_feeder()
                    no_motion_window.clear()
                    possum_absence_window.clear()
                    current_visit["last_static_saved_time"] = None
                    if possum_detected_in_frame and len(possum_bboxes_in_frame) > 0:
                        current_visit["last_bbox"] = possum_bboxes_in_frame[0]
                    local_visit = current_visit
           

            # Save visit frames and ROIs
            if local_visit is not None and frame_idx % FRAME_SAVE_INTERVAL == 0 and possum_detected_in_frame:
                #current_visit["last_seen_time"] = now_time
                with frame_lock:
                    if current_visit is local_visit and current_visit is not None:
                        current_visit["last_seen_time"] = frame_timestamp
                        current_visit["last_seen_frame"] = frame_idx
                

                frame_path = os.path.join(local_visit["frames_dir"], f"frame_{frame_idx:06d}.jpg")
                cv2.imwrite(frame_path, frame)
                visit_id = local_visit["visit_id"]
                local_visit["frame_upload_queue"].append(

                    #(frame_path, now_time)
                    (frame_path, frame_timestamp)
                )
 
                for roi_num, roi in enumerate(possum_rois_in_frame):

                    roi_path = os.path.join(
                        local_visit["rois_dir"],
                        f"roi_{frame_idx:06d}_{roi_num:03d}.jpg"
                    )

                    cv2.imwrite(roi_path, roi)


                    local_visit["roi_upload_queue"].append(
                        #(roi_path, possum_bboxes_in_frame[roi_num], frame_path, now_time)
                        (roi_path, possum_bboxes_in_frame[roi_num], frame_path, frame_timestamp)
                    )

    frame_idx += 1

    # Periodic logging every 60 seconds if no active visit
    if time.time() - start_time > 60:
        if current_visit is None:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(
                f"[{now_str}] 1 minute passed, processing continues. No possums detected."
            )

        # Always reset timer
        start_time = time.time()

    # Manual exit handler
    if cv2.waitKey(1) & 0xFF == ord('q'):
        logging.info("Exiting by user request.")
        break

# CLEANUP
if USE_VIDEO_FILE:
    logging.info("Waiting for uploads to finish (video mode)...")
    upload_queue.join()
    logging.info("All uploads completed.")

cap.release()

with frame_lock:
    request_close_visit = True
stop_event.set()
capture_thread.join()
cv2.destroyAllWindows()
logging.info("Video feed processing stopped, all resources released.")




