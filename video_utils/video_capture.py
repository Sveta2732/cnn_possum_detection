import cv2
import logging
import time

# Function to initialise RTSP video stream capture and retrieve FPS
def initialise_video_capture(rtsp_url):
    # Attempts to open video stream using RTSP URL
    cap = cv2.VideoCapture(rtsp_url)


    if not cap.isOpened():
        logging.warning("Initial video capture failed. Retrying...") # Logs warning message
        time.sleep(2) # Waits 2 seconds before retrying connection
        cap = cv2.VideoCapture(rtsp_url)


    fps = int(cap.get(cv2.CAP_PROP_FPS)) # Retrieves frames per second from video stream metadata
    if fps == 0:
        fps = 25 # Assigns default FPS value


    return cap, fps

