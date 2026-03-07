# Logging library for runtime information and debugging
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from merge_service import get_night_visits, build_groups, merge_group
# Database connection helper
from db import get_connection
# Loads environment variables from .env file
from dotenv import load_dotenv

# Load environment variables into runtime environment
load_dotenv()

# Configure global logging level
logging.basicConfig(level=logging.INFO)


# Try to acquire MySQL named lock to prevent concurrent execution
def acquire_lock(conn):
    
    cursor = conn.cursor()
    # Attempt to acquire non-blocking named lock
    cursor.execute("SELECT GET_LOCK('night_merge_lock', 0)")
    # Fetch result (1 = success, 0 = already locked)
    result = cursor.fetchone()[0]
    cursor.close()
    # Return True if lock acquired
    return result == 1


# Release previously acquired MySQL named lock
def release_lock(conn):
    
    cursor = conn.cursor()
    # Release lock
    cursor.execute("SELECT RELEASE_LOCK('night_merge_lock')")
    cursor.close()


# Main job execution logic
def run():
    conn = get_connection()

    # Attempt to acquire exclusive lock
    if not acquire_lock(conn):
        logging.info("Another night merge is running. Exiting.")
        return

    try:
        melb_tz = ZoneInfo("Australia/Melbourne")
        now_melb = datetime.now(melb_tz)
        yesterday = (now_melb - timedelta(days=1)).date()
        logging.info(f"Starting night merge for {yesterday}")

        # Fetch visits for that night
        visits = get_night_visits(yesterday)
        if not visits:
            logging.info("No visits found")
            return

        # Build groups of visits that should be merged
        groups = build_groups(visits)
        if not groups:
            logging.info("No groups to merge")
            return
        
        # Iterate over each group
        for group in groups:
            merge_group(group)
        logging.info("Night merge completed")

    finally:
        # Always release DB lock
        release_lock(conn)
        conn.close()


if __name__ == "__main__":
    run()

# gcloud builds submit . --tag gcr.io/possum-tracker/night-merge-job
# gcloud run jobs update night-merge   --region australia-southeast1  --add-cloudsql-instances possum-tracker:australia-southeast2:possum-project
# gcloud run jobs execute night-merge --region australia-southeast1
# gcloud scheduler jobs create http night-merge-schedule  --schedule "0 7 * * *" --uri https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/night-merge:run  --http-method POST  --oauth-service-account-email 1033750149860-compute@developer.gserviceaccount.com