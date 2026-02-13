from google.cloud import storage
import mimetypes
import os
import logging

# Name of Google Cloud Storage bucket where media files are stored
GCS_BUCKET = "possum-tracker-media-sveta"

# Resolve path to service account credentials file
BASE_DIR = os.path.dirname(__file__)
KEY_PATH = os.path.join(BASE_DIR, "..", "gcs-key.json")

# Initialize GCS client using service account authentication
storage_client = storage.Client.from_service_account_json(KEY_PATH)
# Reference to the target storage bucket
bucket = storage_client.bucket(GCS_BUCKET)

def upload_file(local_path, gcs_path):
    # Create a blob object representing destination file in GCS
    blob = bucket.blob(gcs_path)
    
    try:
        logging.info(f"Uploading {local_path} - {gcs_path}")
        # Automatically detect MIME type based on file extension
        content_type, _ = mimetypes.guess_type(local_path)

        # Upload file to GCS
        blob.upload_from_filename(
            local_path,
            content_type=content_type
)

    except Exception as e:
        print("Upload failed:", e)
        raise e  

    # Return canonical GCS URI for storing in database
    return f"gs://{GCS_BUCKET}/{gcs_path}"