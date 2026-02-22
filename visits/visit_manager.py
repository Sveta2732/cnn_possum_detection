import os
import cv2
from datetime import datetime
import logging
from db.visit_repository import insert_visit
# Enables running background threads for parallel execution
import threading
from db.visit_repository import update_visit_end
from cloud.uploader import upload_visit_media
from video_utils.trimming import trim_video

# Function to initialize a new visit session with video and folder setup
def create_new_visit(frame, base_dir, frame_idx, fps):

    now_time = datetime.now()
    visit_id = insert_visit(now_time)
    # Logs visit start time
    logging.info(f"Visit {visit_id} started at {now_time.strftime('%Y-%m-%d %H:%M:%S')}")

    visit_folder = os.path.join(base_dir, f"visit_{visit_id:04d}")
    frames_dir = os.path.join(visit_folder, "frames")
    rois_dir = os.path.join(visit_folder, "rois")

    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(rois_dir, exist_ok=True)

    video_path = os.path.join(visit_folder, "visit.mp4")

    # Extracts height and width from the frame dimensions
    h, w, _ = frame.shape
    # Defines video codec for MP4 video format
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    video_writer = cv2.VideoWriter(
        video_path,
        fourcc,
        fps,
        (w, h)
    )

    return {
        "visit_id": visit_id,
        "start_time": now_time,
        "last_seen_time": now_time,
        "last_seen_frame": frame_idx,
        "frames_dir": frames_dir,
        "rois_dir": rois_dir,
        "start_frame": frame_idx,
        "video_path": video_path,
        "video_writer": video_writer,
        "frame_timestamps": [],
        "frame_upload_queue": [],
        "roi_upload_queue": []
    }


# Function to finalize visit session, trim video, update DB, and upload media
def close_visit(current_visit, fps):

    if current_visit["video_writer"] is not None:
        # Releases video writer and finalizes video file
        current_visit["video_writer"].release()

        trim_video(
            current_visit["video_path"],
            current_visit["start_frame"],
            current_visit["last_seen_frame"],
            fps
        )

    update_visit_end(
        current_visit["visit_id"],
        current_visit["last_seen_time"]
    )

    visit_snapshot = {
        "visit_id": current_visit["visit_id"],
        "video_path": current_visit["video_path"],
        "frame_upload_queue": list(current_visit["frame_upload_queue"]),
        "roi_upload_queue": list(current_visit["roi_upload_queue"])
    }

    # Background function that uploads visit media to cloud storage without blocking main thread
    threading.Thread(
        target=upload_visit_media,
        args=(visit_snapshot,),
        # Marks thread as daemon so it stops when main program exits
        #daemon=True
    ).start()

    logging.info(
        f"Visit {current_visit['visit_id']} closed."
    )