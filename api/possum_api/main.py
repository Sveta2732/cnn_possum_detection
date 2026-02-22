# FastAPI framework — used to create REST API endpoints
from fastapi import FastAPI, Query
import mysql.connector
# Access environment variables (database credentials, connection strings)
import os
from datetime import date, timedelta
# Google Cloud Storage SDK — used to generate signed URLs and access storage buckets
from google.cloud import storage
# Used to raise HTTP errors when invalid request parameters are received
from fastapi import HTTPException
# Google authentication utilities for generating signed URLs securely
from google.auth.transport.requests import Request
from google.auth import default
from google.auth import iam
# Allows running multiple database queries in parallel (performance optimisation)
from concurrent.futures import ThreadPoolExecutor, as_completed
# MySQL connection pooling — reduces cost of creating new connections for each request by reusing a pool of connections
from mysql.connector.pooling import MySQLConnectionPool
# Threading utilities — used for caching and locking
import threading
import time
# Enables cross-origin requests 
from fastapi.middleware.cors import CORSMiddleware
from graphs import (
    total_visits,
    average_visits_per_day,
    average_duration,
    pick_hour,
    max_day,
    max_duration,
    weeks_comparison,
    month_comparison,
    hours_comparison,
    time_percentage,
    hist_duration,
    start_fence_position,
    end_fence_position,
    heatmap_position,
    activity_speed_distance,
    activity_hour
)


#App Initialization
app = FastAPI()

# Allows browser frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "https://possum-tracker.sveta.com.au",
    "https://possum-tracker.vercel.app",
    "http://localhost:3000", 
    "http://192.168.7.252:3000"
],   
    allow_credentials=True,
    # allow GET, POST, etc
    allow_methods=["*"],  
    # allow all headers
    allow_headers=["*"],   
)

#Creates connection to GCS.
storage_client = storage.Client()
# Fetches default credentials for the service account running this code (Cloud Run service account).
credentials, _ = default()

# Function to refresh credentials if they are expired. 
def get_credentials():

    global credentials

    if not credentials.valid:
        credentials.refresh(Request())

    return credentials


# Creates pool of reusable connections. 
db_pool = MySQLConnectionPool(
    pool_name="possum_pool",
    # Can be Adjusted
    pool_size=10,  
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    database=os.environ["DB_NAME"],
    #Connects directly to Cloud SQL instance via Unix socket.
    unix_socket=f"/cloudsql/{os.environ['INSTANCE_CONNECTION_NAME']}"
)

# Returns a connection from the pool.
def get_connection():
    return db_pool.get_connection()

# Google Storage helper logic
def generate_signed_url(gcs_path: str):

    if not gcs_path:
        return None

    creds = get_credentials()

    path = gcs_path.replace("gs://", "")
    bucket_name, blob_name = path.split("/", 1)

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    return blob.generate_signed_url(
        expiration=timedelta(minutes=6),
        method="GET",
        service_account_email=creds.service_account_email,
        access_token=creds.token,
    )

# Prevents recalculating expensive dashboard metrics for every request.
dashboard_cache = {
    "data": None,
    "timestamp": 0
}
# Cache validity 
CACHE_TTL_SECONDS = 120  
# Prevents multiple threads updating cache simultaneously.
cache_lock = threading.Lock()

# Runs a dashboard metric query in its own DB connection.
def run_query_parallel(func):

    conn = get_connection()
    try:
        return func(conn)
    finally:
        conn.close()


# Querty functions
# Function to fetch visit statistics aggregated by night_date with number of visits, average duration and number of videos
def fetch_visit_statistics(start_date: date, end_date: date):

    conn = get_connection()
    # Returns rows as dictionaries instead of tuples.
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

def fetch_recent_activity():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
            v.visit_id,
            v.start_time,
            v.night_date,
            r.roi_id,
            r.roi_url
        FROM visits v
        LEFT JOIN rois r
            ON r.roi_id = v.representative_roi_id
        WHERE v.approved = 1
        ORDER BY v.start_time DESC
        LIMIT 6
    """

    try:
        cursor.execute(query)
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
            v.visit_id,
            v.duration_seconds,
            v.start_time,
            v.night_date,
            v.video_url,
            r.roi_id,
            r.roi_url
        FROM visits v
        LEFT JOIN rois r
            ON r.roi_id = v.representative_roi_id
        WHERE v.night_date = %s
          AND v.approved = 1
    """

    try:
        cursor.execute(query, (current_date,))
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

def fetch_record():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
            record_link
        FROM records
    """

    try:
        cursor.execute(query)
        return cursor.fetchone()

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

    def build_row(r):
        return {
            "visit_id": r["visit_id"],
            "video_url": generate_signed_url(r["video_url"]) if r["video_url"] else None,
            "roi_url": generate_signed_url(r["roi_url"]) if r["roi_url"] else None,
            "roi_id": r["roi_id"],
            "night_date": r["night_date"].isoformat() if r["night_date"] else None,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(build_row, rows))
    
@app.get("/recent_activity")
def get_recent_activity():

    rows = fetch_recent_activity()

    def build_row(r):
        return {
            "visit_id": r["visit_id"],
            "start_time": r["start_time"].isoformat() if r["start_time"] else None,
            "roi_url": generate_signed_url(r["roi_url"]) if r["roi_url"] else None,
            "roi_id": r["roi_id"],
            "night_date": r["night_date"].isoformat() if r["night_date"] else None,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(build_row, rows))


# Dashboard endpoint
@app.get("/statistics/dashboard")
def dashboard():

    #Check cache
    with cache_lock:
        if (
            dashboard_cache["data"] is not None and
            time.time() - dashboard_cache["timestamp"] < CACHE_TTL_SECONDS
        ):
            return dashboard_cache["data"]

    #Define dashboard queries
    queries = {
        "total_visits": total_visits,
        "average_visits_per_day": average_visits_per_day,
        "average_duration": average_duration,
        "most_popular_hour": pick_hour,
        "max_visits_per_day": max_day,
        "max_duration": max_duration,
        "average_visits_per_weekday": weeks_comparison,
        "visits_per_month": month_comparison,
        "visits_per_hour": hours_comparison,
        "visits_by_time_of_night": time_percentage,
        "duration_histogram": hist_duration,
        "start_fence_position": start_fence_position,
        "end_fence_position": end_fence_position,
        "heatmap_position": heatmap_position,
        "activity_speed_distance": activity_speed_distance,
        "activity_hour": activity_hour
    }

    results = {}

    # Execute queries in parallel 
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {
            executor.submit(run_query_parallel, func): key
            for key, func in queries.items()
        }

        for future in as_completed(future_map):
            key = future_map[future]
            results[key] = future.result()

    # Store results in cache
    with cache_lock:
        dashboard_cache["data"] = results
        dashboard_cache["timestamp"] = time.time()

    return results

# records
@app.get("/records")
def get_records():

    row = fetch_record()

    if not row:
        return []

    return [{
        "record_url": generate_signed_url(row["record_link"])
            if row["record_link"] else None
    }]



#  Cloud CLI command to deploy the API to Google Cloud Run. 
# gcloud run deploy possum-api --source . --region australia-southeast1 --allow-unauthenticated
# gcloud config list
