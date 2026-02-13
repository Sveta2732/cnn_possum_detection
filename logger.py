# Provides logging functionality for tracking system events
import logging
import os
from datetime import datetime

def setup_logger():
    today = datetime.now().strftime("%Y-%m-%d")
    run_time = datetime.now().strftime("%H-%M-%S")

    # Creates path for daily log folder inside 'logs' directory
    log_dir = os.path.join("logs", today)
    os.makedirs(log_dir, exist_ok=True)
    # Creates unique log file name for each run
    log_file = os.path.join(log_dir, f"possum_run_{run_time}.log")

    logging.basicConfig(
        level=logging.INFO, # Sets minimum logging level to INFO
        format="%(asctime)s | %(levelname)s | %(message)s", # Defines log message format
        handlers=[
            logging.FileHandler(log_file, mode="a"), # Writes logs to file in append mode
            logging.StreamHandler() # Outputs logs to console
        ]
    )

    logging.info("Logger initialized")