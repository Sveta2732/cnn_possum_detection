import logging
import os
from .encoder import convert_to_h264
from .gcs_client import upload_file
from db.visit_repository import (
    update_visit_video,
    insert_frame,
    insert_roi,
    compute_representative_roi,
    recalculate_visit_statistics
)


def upload_visit_media(visit):
    """
    Uploads all media related to a possum visit:
    - Converts and uploads video to GCS
    - Uploads frames and ROIs to GCS
    - Stores metadata in database
    - Computes representative ROI for the visit
    """
        
    try:
        visit_id = visit["visit_id"]

        # VIDEO
        # Convert recorded visit video to H264 format for better compatibility and streaming
        #video_local = convert_to_h264(visit["video_path"])
        video_local = visit["video_path"]
        # Define destination path in Google Cloud Storage
        gcs_video_path = f"visits/visit_{visit_id}/visit.mp4"

        # Upload video file to GCS and store returned URL
        video_url = upload_file(video_local, gcs_video_path)
        # Save video URL into visits table in the database
        update_visit_video(visit_id, video_url)
        #if os.path.exists(video_local):
            #os.remove(video_local)

        # FRAMES
        # Dictionary to map local frame paths to DB frame IDs
        frame_id_map = {}

        
        for frame_path, timestamp in visit["frame_upload_queue"]:
            # # Extract filename from full local path
            # filename = os.path.basename(frame_path)
            #  # Define GCS storage path for frame
            # gcs_path = f"visits/visit_{visit_id}/frames/{filename}"
            # # Upload frame image to GCS and get public URL
            # frame_url = upload_file(frame_path, gcs_path)
            # Insert frame record into DB and retrieve frame_id
            # frame_id = insert_frame(visit_id, frame_url, timestamp)
            # # Store mapping for ROI linking later
            # frame_id_map[frame_path] = frame_id

            
            frame_id = insert_frame(visit_id, timestamp)

            frame_id_map[frame_path] = frame_id

        # ROIS
        # for roi_path, bbox, frame_path, roi_timestamp in visit["roi_upload_queue"]:

            # filename = os.path.basename(roi_path)
            # # Define GCS path for ROI image
            # gcs_path = f"visits/visit_{visit_id}/rois/{filename}"
            # # Upload ROI image
            # roi_url = upload_file(roi_path, gcs_path)
            # # Insert ROI record if matching frame exists
            # if frame_path in frame_id_map:
            #     insert_roi(frame_id_map[frame_path], roi_url, bbox, roi_timestamp)
            # else:
            #     print("ROI skipped, frame not found:", frame_path)

        all_roi_records = []

        for roi_path, bbox, frame_path, roi_timestamp in visit["roi_upload_queue"]:
            # Insert ROI record if matching frame exists
            if frame_path in frame_id_map:
                roi_id = insert_roi(frame_id_map[frame_path], None, bbox, roi_timestamp)
                all_roi_records.append((roi_id, roi_path))
            else:
                logging.warning(f"ROI skipped, frame not found: {frame_path}")

        n = len(all_roi_records)

        if n == 0:
            update_representative_roi(visit_id, None)
            try:
                recalculate_visit_statistics(visit_id)
            except Exception:
                logging.exception("Statistics recalculation failed")
            return

        if n < 5:
            selected = all_roi_records
        else:
            indices = [
                0,
                min(n - 1, int(n * 0.25)),
                min(n - 1, int(n * 0.50)),
                min(n - 1, int(n * 0.75)),
                n - 1
            ]

            indices = sorted(set(indices))
            selected = [all_roi_records[i] for i in indices]

        median_index = (n - 1) // 2

        for roi_id, roi_path in selected:

            filename = os.path.basename(roi_path)
            gcs_path = f"visits/visit_{visit_id}/rois/{filename}"

            roi_url = upload_file(roi_path, gcs_path)

            update_roi_url(roi_id, roi_url)

        representative_roi_id = all_roi_records[median_index][0]

        update_representative_roi(visit_id, representative_roi_id)

        
        
        # logging
        logging.info(f"Uploading {len(visit['frame_upload_queue'])} frames")
        logging.info(f"Uploading {len(visit['roi_upload_queue'])} rois")

        # Select middle ROI for visit preview
        #compute_representative_roi(visit["visit_id"])
        try:
            recalculate_visit_statistics(visit_id)
        except Exception as e:
            logging.exception(
                f"Failed to recalculate statistics for visit {visit_id}"
            )
        
        #for frame_path, _ in visit["frame_upload_queue"]:
            #if os.path.exists(frame_path):
                #os.remove(frame_path)

        #for roi_path, _, _ in visit["roi_upload_queue"]:
            #if os.path.exists(roi_path):
                #os.remove(roi_path)

    except Exception as e:
        logging.exception("Upload failed")




