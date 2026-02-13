# Import helper function that resolves the ffmpeg executable path.
from config import get_ffmpeg_path
# Import subprocess module to execute ffmpeg for video transcoding.
import subprocess


def convert_to_h264(input_path):

    ffmpeg_path = get_ffmpeg_path()

    output_path = input_path.replace(".mp4", "_h264.mp4")

    # Build ffmpeg command to convert video to H.264 codec
    command = [
        ffmpeg_path,
        "-y",                    # Overwrite output file if it already exists
        "-i", input_path,        # Input video file
        "-vcodec", "libx264",    # Use H.264 video codec
        "-preset", "medium",     # Balance encoding speed and compression efficiency
        "-crf", "23",            # Constant Rate Factor (quality vs compression trade-off)
        "-acodec", "aac",        # Encode audio using AAC codec
        "-b:a", "128k",          # Set audio bitrate
        "-movflags", "+faststart",  # Enable progressive streaming (important for web playback)
        output_path              # Output video file
    ]

    # Execute ffmpeg conversion command
    # check=True raises exception if encoding fails
    subprocess.run(command, check=True)

    return output_path