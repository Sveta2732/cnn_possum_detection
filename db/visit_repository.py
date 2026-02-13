import mysql.connector
from datetime import datetime
# Import database configuration
from config import DB_CONFIG

# Connect to the database
db = mysql.connector.connect(**DB_CONFIG)
# Create cursor object used to execute SQL queries
cur = db.cursor()


# Visit Repository functions

def insert_visit(start_time):
    """
    Inserts a new possum visit record.
    """
    # Ensure connection is alive and reconnect if necessary
    db.ping(reconnect=True)
    now_time = datetime.now()
    cur.execute("""
        INSERT INTO visits (start_time, created_at)
        VALUES (%s, %s)
    """, (start_time, now_time))
    # Commit transaction to persist changes
    db.commit()
    # Return generated visit ID
    return cur.lastrowid

def update_visit_end(visit_id, end_time):
    """
    Updates the visit end timestamp when possum activity stops.
    """
    db.ping(reconnect=True)
    cur.execute("""
        UPDATE visits
        SET end_time = %s
        WHERE visit_id = %s
    """, (end_time, visit_id))

    db.commit()

def update_visit_video(visit_id, video_url):
    """
    Stores the cloud storage URL of the recorded visit video.
    """
    db.ping(reconnect=True)
    cur.execute("""
        UPDATE visits
        SET video_url = %s
        WHERE visit_id = %s
    """, (video_url, visit_id))

    db.commit()

# Frame functions
def insert_frame(visit_id, frame_url, timestamp):
    """
    Inserts a frame associated with a visit.
    """
    db.ping(reconnect=True)
    cur.execute("""
        INSERT INTO frames (visit_id, frame_url, frame_timestamp)
        VALUES (%s, %s, %s)
    """, (visit_id, frame_url, timestamp))

    db.commit()
    # Return generated frame ID
    return cur.lastrowid

# ROI functions
def insert_roi(frame_id, roi_url, bbox, timestamp):
    """
    Inserts a Region of Interest (ROI) extracted from a frame.
    """
    x1, y1, x2, y2 = bbox
    db.ping(reconnect=True)
    cur.execute("""
        INSERT INTO rois (frame_id, roi_url, bbox_x1, bbox_y1, bbox_x2, bbox_y2, roi_timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (frame_id, roi_url, x1, y1, x2, y2, timestamp))

    db.commit()


def compute_representative_roi(visit_id: int):
    """
    Selects and stores a representative ROI for a visit.
    """
    db.ping(reconnect=True)

    cur.execute("""
        SELECT roi_id
        FROM (
            SELECT
                r.roi_id,
                ROW_NUMBER() OVER (
                    PARTITION BY v.visit_id
                    ORDER BY f.frame_id, r.roi_id
                ) AS rn,
                COUNT(*) OVER (
                    PARTITION BY v.visit_id
                ) AS total
            FROM visits v
            JOIN frames f ON f.visit_id = v.visit_id
            JOIN rois r ON r.frame_id = f.frame_id
            WHERE v.visit_id = %s
        ) t
        WHERE rn = FLOOR((total + 1) / 2)
    """, (visit_id,))

    row = cur.fetchone()

    if row:
        rep_roi_id = row[0]

        cur.execute("""
            UPDATE visits
            SET representative_roi_id = %s
            WHERE visit_id = %s
        """, (rep_roi_id, visit_id))

        db.commit()