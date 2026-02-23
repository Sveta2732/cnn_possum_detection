# FastAPI framework to create an HTTP endpoint
from fastapi import FastAPI, Request
# Google Cloud Storage client
from google.cloud import storage
# Used to create temporary local files inside Cloud Run container
import tempfile
# Used to execute the ffmpeg command
import subprocess
# Used for file cleanup (removing temp files)
import os


# Create FastAPI app instance
app = FastAPI()
# Initialize GCS client 
storage_client = storage.Client()


# Cloud Run will send a POST request with GCS event payload
@app.post("/")
async def process_video(request: Request):
    # Parse incoming JSON event from Cloud Storage
    event = await request.json()
    # Extract bucket name and object name from event
    bucket_name = event["bucket"]
    object_name = event["name"]

    # Process only video files
    if not object_name.lower().endswith((".mp4", ".mov")):
        return {"status": "ignored"}

    bucket = storage_client.bucket(bucket_name)

    # Get blob (file) reference
    blob = bucket.blob(object_name)

    # Reload blob metadata from GCS
    blob.reload()

    metadata = blob.metadata or {}

    # Prevent infinite trigger loop
    if metadata.get("processed") == "true":
        return {"status": "already processed"}

    # Download original video into a temporary local file
    # Cloud Run container has writable /tmp storage
    with tempfile.NamedTemporaryFile(delete=False) as temp_input:
        blob.download_to_filename(temp_input.name)
        input_path = temp_input.name

    output_path = input_path + "_converted.mp4"

    # Build ffmpeg command
    command = [
        "ffmpeg",              # ffmpeg executable
        "-y",                  # overwrite output if exists
        "-i", input_path,      # input file
        "-c:v", "libx264",     # convert video codec to H.264
        "-preset", "slow",     # better compression 
        "-crf", "22",          # quality level (lower = better quality)
        "-pix_fmt", "yuv420p", # browser compatibility
        "-movflags", "+faststart",  # web streaming optimization
        output_path            # output file
    ]

    # Execute ffmpeg conversion
    subprocess.run(command, check=True)

    # Prepare to overwrite the same object in GCS
    new_blob = bucket.blob(object_name)

    # Add metadata to prevent re-processing
    new_blob.metadata = {"processed": "true"}

    # Upload converted file and overwrite original
    new_blob.upload_from_filename(
        output_path,
        content_type="video/mp4"
    )

    # Clean up temporary files
    os.remove(input_path)
    os.remove(output_path)

    return {"status": "processed"}

# gcloud builds submit --tag gcr.io/possum-tracker/video-processor
# gcloud run deploy video-processor --image gcr.io/possum-tracker/video-processor --region australia-southeast1 --platform managed --allow-unauthenticated --memory 2Gi --cpu 2