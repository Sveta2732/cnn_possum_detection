import logging
from datetime import date, timedelta
from merge_service import get_night_visits, build_groups, merge_group
from db import get_connection
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)

def acquire_lock(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT GET_LOCK('night_merge_lock', 0)")
    result = cursor.fetchone()[0]
    cursor.close()
    return result == 1


def release_lock(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT RELEASE_LOCK('night_merge_lock')")
    cursor.close()

def run():
    conn = get_connection()
    if not acquire_lock(conn):
        logging.info("Another night merge is running. Exiting.")
        return

    try:
        yesterday = date.today() - timedelta(days=1)

        logging.info(f"Starting night merge for {yesterday}")

        visits = get_night_visits(yesterday)

        if not visits:
            logging.info("No visits found")
            return

        groups = build_groups(visits)
        if not groups:
            logging.info("No groups to merge")
            return
        
        for group in groups:
            merge_group(group)

        logging.info("Night merge completed")

    finally:
        release_lock(conn)
        conn.close()

if __name__ == "__main__":
    run()

# gcloud builds submit . --tag gcr.io/possum-tracker/night-merge-job
# gcloud run jobs update night-merge   --region australia-southeast1  --add-cloudsql-instances possum-tracker:australia-southeast2:possum-project
# gcloud run jobs execute night-merge --region australia-southeast1
# gcloud scheduler jobs create http night-merge-schedule  --schedule "0 7 * * *" --uri https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/night-merge:run  --http-method POST  --oauth-service-account-email 1033750149860-compute@developer.gserviceaccount.com