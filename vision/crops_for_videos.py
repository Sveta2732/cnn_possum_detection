import cv2
import os
import numpy as np

# PARAMETERS 
PADDING_RATIO = 0.3  # additional padding around detected motion
MIN_AREA = 400       # minimum area of contour to be considered a valid motion
KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))  # kernel for morphological operations

# Background subtractor for motion detection
BG_SUBTRACTOR = cv2.createBackgroundSubtractorMOG2(
    history=500,        # number of frames for background history
    varThreshold=25,    # threshold on pixel variance to consider it foreground
    detectShadows=False # do not detect shadows
)


def get_crops_from_frame(frame, bg_subtractor=BG_SUBTRACTOR, min_area=MIN_AREA, padding_ratio=PADDING_RATIO, kernel=KERNEL):
    """
    Apply motion detection to a single frame and extract candidate ROIs.

    """
    # Safety checks 
    if frame is None:
        return [], []

    if not hasattr(frame, "shape"):
        return [], []

    if frame.size == 0:
        return [], []

    if bg_subtractor is None or kernel is None:
        return [], []

    # Apply background subtraction
    try:
        fg_mask = bg_subtractor.apply(frame)
    except Exception:
        return [], []

    if fg_mask is None or fg_mask.size == 0:
        return [], []

    try:
        # Remove small noise
        # MORPH_OPEN = erosion followed by dilation  removes small white noise (isolated pixels)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        # MORPH_CLOSE = dilation followed by erosion  closes small black holes inside detected objects
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        
        # Dilate to fill gaps in contours
        # This makes each moving object contour more solid and continuous
        fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)
    except Exception:
        return [], []  
    
    try:
        # Find contours of moving objects
        # fg_mask: binary mask (white = motion, black = background)
        # cv2.RETR_EXTERNAL: retrieve only the external contours (ignore nested/child contours)
        # cv2.CHAIN_APPROX_SIMPLE: compress contour points to save memory (only key points)
        # contours: list of contours, each contour is an array of points
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    except Exception:
        return [], []

    h_frame, w_frame = frame.shape[:2]

    rois = []
    bboxes = []

    for cnt in contours:
        try:
            area = cv2.contourArea(cnt)

        except Exception:
            continue
        if area < min_area:  # ignore small noisy contours
            continue

        # Get bounding rectangle and add padding
        # (x, y) is the top-left corner of the bounding rectangle
        # In OpenCV coordinate system, (0,0) is the top-left of the image
        x, y, w, h = cv2.boundingRect(cnt)
        pad_w = int(w * padding_ratio)
        pad_h = int(h * padding_ratio)
        # Apply padding but make sure coordinates do not go outside the image boundaries
        x1 = max(0, x - pad_w)        # left
        y1 = max(0, y - pad_h)        # top
        x2 = min(w_frame, x + w + pad_w)  # right
        y2 = min(h_frame, y + h + pad_h)  # bottom

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            continue

        rois.append(roi)
        bboxes.append((x1, y1, x2, y2))

    return rois, bboxes


def save_debug_frame(frame, bboxes, debug_path):
    """
    Draw bounding boxes on the frame for visualization and save the debug image.
    """
    # Make a copy of the original frame so we don't modify it
    debug_frame = frame.copy()
    for (x1, y1, x2, y2) in bboxes:
        # Draw a green rectangle (color=(0,255,0)) with thickness=2
        cv2.rectangle(debug_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.imwrite(debug_path, debug_frame)


def process_video(video_path, output_dir, skip_frames=10, min_area=MIN_AREA, save_to_disk=True):
    """
    Process a video file and extract crops from motion detection.

    """
    # Extract video file name without extension for creating output directories
    # (root, ext)
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    if save_to_disk:
        video_output_dir = os.path.join(output_dir, video_name)
        os.makedirs(video_output_dir, exist_ok=True)
        debug_dir = os.path.join(video_output_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)

    # Open video file
    cap = cv2.VideoCapture(video_path)
    # Initialize frame and crop indices
    frame_idx = 0
    crop_idx = 0
    rois_all = []    # only used if save_to_disk=False
    bboxes_all = []

    while True:
        # ret: boolean flag, True if the frame was successfully read, False if end of video or error
        # frame: the actual frame/image as a numpy array with shape (height, width, channels)
        ret, frame = cap.read()
        if not ret:
            break
        # Apply frame skipping: only process every N-th frame
        if frame_idx % skip_frames == 0:
                    # Extract ROIs and bounding boxes from current frame
                    rois, bboxes = get_crops_from_frame(frame)

                    if save_to_disk:
                        # save each ROI to disk
                        for i, roi in enumerate(rois):
                            crop_name = f"frame_{frame_idx:06d}_roi_{i}.jpg"
                            cv2.imwrite(os.path.join(video_output_dir, crop_name), roi)
                            crop_idx += 1

                        # save debug frame
                        debug_name = f"frame_{frame_idx:06d}.jpg"
                        save_debug_frame(frame, bboxes, os.path.join(debug_dir, debug_name))
                    else:
                        # keep ROIs in memory
                        rois_all.extend(rois)
                        bboxes_all.extend(bboxes)

        frame_idx += 1
    # Release the video capture object
    cap.release()
    if save_to_disk:
        print(f"Processed {video_name}, saved {crop_idx} crops")
    else:
        return rois_all, bboxes_all


# MAIN SCRIPT
if __name__ == "__main__":
    VIDEO_DIR = "videos"
    OUTPUT_DIR = "crops"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for video_file in os.listdir(VIDEO_DIR):
        if video_file.lower().endswith((".mp4", ".avi", ".mov")):
            process_video(os.path.join(VIDEO_DIR, video_file), OUTPUT_DIR, skip_frames=1)

    print("Done.")






