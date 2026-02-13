import cv2
import os
import logging

# def trim_video(video_path, timestamps, last_seen_time, fps):
def trim_video(video_path, start_frame, last_seen_frame, fps):
    """
    Trims a recorded visit video to keep only relevant frames.
    """
    if last_seen_frame is None:
        return

    #trim_time = last_seen_time + timedelta(seconds=2)

    # Calculate frame index relative to visit start
    local_last_frame = max(0, last_seen_frame - start_frame)
    # Keep several seconds of video after last detection
    keep_frames = local_last_frame + fps * 3
 
    # Open recorded video file
    video_cap = cv2.VideoCapture(video_path)
    if not video_cap.isOpened():
        logging.error(f"Failed to open video for trimming: {video_path}")
        return
    total_frames = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Ensure we do not exceed actual video length
    keep_frames = min(keep_frames, total_frames)

    # Temporary file for trimmed video output
    temp_path = video_path.replace(".mp4", "_trimmed.mp4")

    # Define video codec
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    # Create video writer with original resolution and FPS
    out = cv2.VideoWriter(
        temp_path,
        fourcc, # mp4v codec for .mp4 output
        fps, # preserve the original camera FPS to maintain correct timing.
        (
            int(video_cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )
    )

    frame_idx = 0

    # Read frames sequentially and write only relevant ones
    while True:
        ret, frame = video_cap.read()
        # Stop if video ended or enough frames were saved
        if not ret or frame_idx >= keep_frames:
            break

        out.write(frame)
        frame_idx += 1

    # Release video resources
    video_cap.release()
    out.release()

    # Replace original video with trimmed version
    if os.path.exists(temp_path):
        os.replace(temp_path, video_path)