from fastapi import FastAPI, Query
import mysql.connector
import os
from datetime import date, timedelta
from google.cloud import storage
from fastapi import HTTPException
from google.cloud import storage
from google.auth.transport.requests import Request
from google.auth import default
from google.auth import iam
from graphs import (
    total_visits,
    average_visits_per_day,
    average_duration,
    pick_hour,
    max_day,
    weeks_comparison,
    month_comparison,
    hours_comparison,
    time_percentage,
    hist_duration,
    start_fence_position,
    end_fence_position,
    heatmap_position
)

#App Initialization
app = FastAPI()
storage_client = storage.Client()

# Database connection function
def get_connection():
    return mysql.connector.connect(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        database=os.environ["DB_NAME"],
        unix_socket=f"/cloudsql/{os.environ['INSTANCE_CONNECTION_NAME']}"
    )

# Google Storage helper logic
def generate_signed_url(gcs_path: str):

    if not gcs_path:
        return None

    credentials, _ = default()
    credentials.refresh(Request())

    path = gcs_path.replace("gs://", "")
    bucket_name, blob_name = path.split("/", 1)

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    return blob.generate_signed_url(
        expiration=timedelta(minutes=6),
        method="GET",
        service_account_email=credentials.service_account_email,
        access_token=credentials.token,
    )


# Querty functions
# Function to fetch visit statistics aggregated by night_date with number of visits, average duration and number of videos
def fetch_visit_statistics(start_date: date, end_date: date):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT night_date,
               COUNT(visit_id) as number_of_visits,
               AVG(duration_seconds) as average_duration_seconds,
               SUM(CASE WHEN video_url IS NOT NULL AND approved = 1 THEN 1 ELSE 0 END) as number_of_videos
        FROM visits
        WHERE night_date BETWEEN %s AND %s
        GROUP BY night_date
        ORDER BY night_date
    """

    try:
        cursor.execute(query, (start_date, end_date))
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


# Function to fetch videos and their ROIs for a given night_date. For each visit, it returns one video and one ROI (the one with the median roi_id for that visit).
def fetch_median_rois_by_date(current_date: date):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
            visit_id,
            duration_seconds,
            start_time,
            night_date,
            video_url,
            roi_id,
            roi_url
        FROM (
            SELECT
                v.visit_id,
                v.night_date,
                v.duration_seconds,
                v.start_time,
                v.video_url,
                r.roi_id,
                r.roi_url,
                ROW_NUMBER() OVER (
                    PARTITION BY v.visit_id
                    ORDER BY f.frame_id, r.roi_id
                ) AS rn,
                COUNT(*) OVER (
                    PARTITION BY v.visit_id
                ) AS number_of_rois
            FROM visits v
            JOIN frames f ON f.visit_id = v.visit_id
            JOIN rois r ON r.frame_id = f.frame_id
            WHERE v.night_date = %s AND v.approved = 1
        ) t
        WHERE rn = FLOOR((number_of_rois + 1) / 2);
    """

    try:
        cursor.execute(query, (current_date,))
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()



# API Endpoints
# Visit endpoint 
@app.get("/visits")
def get_visits(
    start_date: date = Query(...),
    end_date: date = Query(...)
):

    if start_date > end_date:
        raise HTTPException(400, "start_date must be before end_date")

    return fetch_visit_statistics(start_date, end_date)

# Videos and ROIs endpoint
@app.get("/videos_rois")
def get_videos(current_date: date = Query(...)):

    rows = fetch_median_rois_by_date(current_date)

    return [
        {
            "visit_id": r["visit_id"],
            "video_url": generate_signed_url(r["video_url"]) if r["video_url"] else None,
            "roi_url": generate_signed_url(r["roi_url"]) if r["roi_url"] else None,
            "roi_id": r["roi_id"],
            "night_date": r["night_date"].isoformat()
        }
        for r in rows
    ]

# Dashboard endpoint
@app.get("/statistics/dashboard")
def dashboard(start_date: date, end_date: date):

    conn = get_connection()

    try:
        return {
            "total_visits": total_visits(conn),
            "average_visits_per_day": average_visits_per_day(conn),
            "average_duration": average_duration(conn),
            "most_popular_hour": pick_hour(conn),
            "max_visits_per_day": max_day(conn),
            "average_visits_per_weekday": weeks_comparison(conn),
            "visits_per_month": month_comparison(conn),
            "visits_per_hour": hours_comparison(conn),
            "visits_by_time_of_night": time_percentage(conn),
            "duration_histogram": hist_duration(conn),
            "start_fence_position": start_fence_position(conn),
            "end_fence_position": end_fence_position(conn),
            "heatmap_position": heatmap_position(conn)
        }
    finally:
        conn.close()




# gcloud run deploy possum-api --source . --region australia-southeast1 --allow-unauthenticated
