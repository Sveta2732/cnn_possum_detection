from dotenv import load_dotenv
import os
import shutil

load_dotenv()

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASS"],
    "database": os.environ["DB_NAME"]
}
RTSP_URL = os.environ["RTSP_URL"]

def get_ffmpeg_path():

    ffmpeg_path = os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")

    if ffmpeg_path is None:
        raise RuntimeError(
            "ffmpeg not found. Install ffmpeg or set FFMPEG_PATH environment variable."
        )

    return ffmpeg_path

BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "models", "full_model_weight.pt")

