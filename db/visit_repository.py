# MySQL driver used to connect and interact with MySQL database
import mysql.connector
from datetime import datetime
# Import database configuration
from config import DB_CONFIG
import logging
import numpy as np
import cv2

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
#def insert_frame(visit_id, frame_url, timestamp):
def insert_frame(visit_id, timestamp):
    """
    Inserts a frame associated with a visit.
    """
    db.ping(reconnect=True)
    # cur.execute("""
    #     INSERT INTO frames (visit_id, frame_url, frame_timestamp)
    #     VALUES (%s, %s, %s)
    # """, (visit_id, frame_url, timestamp))

    cur.execute("""
        INSERT INTO frames (visit_id, frame_timestamp)
        VALUES (%s, %s)
    """, (visit_id, timestamp))

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
    return cur.lastrowid

def update_roi_url(roi_id, roi_url):
    db.ping(reconnect=True)
    cur.execute("""
        UPDATE rois
        SET roi_url = %s
        WHERE roi_id = %s
    """, (roi_url, roi_id))
    db.commit()

def update_representative_roi(visit_id, roi_id):
    db.ping(reconnect=True)
    cur.execute("""
        UPDATE visits
        SET representative_roi_id = %s
        WHERE visit_id = %s
    """, (roi_id, visit_id))
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




ZONE_SPLIT_X = 700
# coefficients to convert pixel measurements to cm (based on calibration)
PIXEL_TO_CM = {
    "LEFT": 365 / 603,   # ≈ 0.605
    "RIGHT": 360 / 366   # ≈ 0.98
}

def get_zone(x):
    if x < ZONE_SPLIT_X:
        return "LEFT"
    return "RIGHT"

# LEFT
left_img = np.array([
    [110, 397],
    [700, 340],
    [711, 680],
    [128, 740]
], dtype=np.float32)

left_real = np.array([
    [0, 0],
    [365, 0],
    [365, 195],
    [0, 195]
], dtype=np.float32)

H_left = cv2.getPerspectiveTransform(left_img, left_real)


# RIGHT
right_img = np.array([
    [700, 340],
    [1065, 380],
    [1067, 818],
    [711, 680]
], dtype=np.float32)

right_real = np.array([
    [0, 0],
    [360, 0],
    [360, 192],
    [0, 192]
], dtype=np.float32)

H_right = cv2.getPerspectiveTransform(right_img, right_real)





def recalculate_visit_statistics(visit_id):
    """
    Recalculate visit statistics using adaptive movement threshold
    and smart handling of large time gaps.
    """

    try:
        db.ping(reconnect=True)

        cur.execute("""
            SELECT
                r.roi_id,
                r.roi_timestamp,
                CAST((r.bbox_x1 + r.bbox_x2)/2 AS DOUBLE) AS cx,
                CAST((r.bbox_y1 + r.bbox_y2)/2 AS DOUBLE) AS cy,
                CAST((r.bbox_x2 - r.bbox_x1) AS DOUBLE) AS bbox_width
            FROM rois r
            JOIN frames f ON r.frame_id = f.frame_id
            WHERE f.visit_id = %s
              AND r.bbox_x1 IS NOT NULL
              AND r.bbox_x2 IS NOT NULL
              AND r.bbox_y1 IS NOT NULL
              AND r.bbox_y2 IS NOT NULL
            ORDER BY r.roi_timestamp, r.roi_id
        """, (visit_id,))

        rows = cur.fetchall()



        if len(rows) < 2:
            return

        # FILTER ROIS: keep one ROI per timestamp (compare by X only)
        filtered_rows = []

        prev_cx = None
        i = 0

        while i < len(rows):

            current_ts = rows[i][1]
            same_ts_group = []

            # collect all ROIs with same timestamp
            while i < len(rows) and rows[i][1] == current_ts:
                same_ts_group.append(rows[i])
                i += 1

            # if only one ROI → keep it
            if len(same_ts_group) == 1:
                chosen = same_ts_group[0]

            else:
                # multiple ROIs in same timestamp
                if prev_cx is None:
                    # first frame → take first ROI
                    chosen = same_ts_group[0]
                else:
                    # choose ROI closest by X only
                    min_dx = float("inf")
                    chosen = None

                    for roi in same_ts_group:
                        _, _, cx, _, _ = roi
                        cx = float(cx)

                        dx = abs(cx - prev_cx)

                        if dx < min_dx:
                            min_dx = dx
                            chosen = roi

            filtered_rows.append(chosen)

            # update previous X
            _, _, cx, _, _ = chosen
            prev_cx = float(cx)

        total_time = 0.0
        moving_time = 0.0
        idle_time = 0.0
        total_distance_cm = 0.0
        max_speed = 0.0

        prev_ts = None
        prev_cx = None
        prev_cy = None

        for roi_id, ts, cx, cy, bbox_width in filtered_rows:

            cx = float(cx)
            cy = float(cy)
            bbox_width = float(bbox_width)

            if prev_ts is not None:

                delta_time = (ts - prev_ts).total_seconds()

                if delta_time > 0:

                    zone_prev = get_zone(prev_cx)
                    zone_curr = get_zone(cx)

                    # --- COEFFICIENTS (always defined before usage) ---
                    coef_prev = PIXEL_TO_CM[zone_prev]
                    coef_curr = PIXEL_TO_CM[zone_curr]
                    coef = (coef_prev + coef_curr) / 2

                    point_prev = np.array([[[prev_cx, prev_cy]]], dtype=np.float32)
                    point_curr = np.array([[[cx, cy]]], dtype=np.float32)

                    # SAME ZONE → use homography
                    if zone_prev == zone_curr:

                        if zone_curr == "LEFT":
                            real_prev = cv2.perspectiveTransform(point_prev, H_left)
                            real_curr = cv2.perspectiveTransform(point_curr, H_left)
                        else:
                            real_prev = cv2.perspectiveTransform(point_prev, H_right)
                            real_curr = cv2.perspectiveTransform(point_curr, H_right)

                        x1, y1 = real_prev[0][0]
                        x2, y2 = real_curr[0][0]

                        distance_cm = ((x2 - x1)**2 + (y2 - y1)**2)**0.5

                    # DIFFERENT ZONES → fallback to pixel coef
                    else:

                        distance_cm_px = ((cx - prev_cx)**2 + (cy - prev_cy)**2)**0.5
                        distance_cm = distance_cm_px * coef


                    # convert bbox width to cm
                    bbox_width_cm = bbox_width * coef

                    # convert minimal noise threshold (5px) to cm
                    noise_cm = 10 * coef

                    min_shift_cm = max(noise_cm, bbox_width_cm * 0.05)

                    # print(
                    #     f"visit={visit_id} "
                    #     f"dt={delta_time:.3f}s "
                    #     f"dist_cm={distance_cm:.2f} "
                    #     f"cx_prev={prev_cx:.1f} "
                    #     f"cx={cx:.1f}"
                    #     f"min_shift_cm={min_shift_cm:.2f}"
# )

                    # Always accumulate total observed time
                    total_time += delta_time

                    # Handle large time gaps (likely idle period)
                    if delta_time > 2:

                        if distance_cm >= min_shift_cm:
                            # Assume movement lasted at most 1 second
                            move_part = 1.0
                            moving_time += move_part
                            idle_time += (delta_time - move_part)
                            total_distance_cm += distance_cm
                            speed = distance_cm / move_part
                        else:
                            # No significant displacement → full idle
                            idle_time += delta_time
                            speed = 0.0

                    else:
                        # Normal time interval
                        if distance_cm >= min_shift_cm:
                            moving_time += delta_time
                            total_distance_cm += distance_cm
                            speed = distance_cm / delta_time
                        else:
                            idle_time += delta_time
                            speed = 0.0

                    # Track peak speed (only meaningful for movement)
                    if speed > max_speed:
                        max_speed = speed

            prev_ts = ts
            prev_cx = cx
            prev_cy = cy

        if total_time == 0:
            return

        activity_ratio = moving_time / total_time if total_time > 0 else 0
        avg_speed = total_distance_cm / moving_time if moving_time > 0 else 0

        # Fetch stored visit duration
        cur.execute(
            "SELECT duration_seconds FROM visits WHERE visit_id = %s",
            (visit_id,)
        )
        duration_stored = cur.fetchone()[0]

        # Upsert statistics
        cur.execute("""
            INSERT INTO visit_statistics (
            visit_id,
            visit_duration_sec_stored,
            visit_duration_sec_calculated,
            moving_time_sec,
            idle_time_sec,
            activity_ratio,
            total_distance_px,
            avg_speed_px_per_sec,
            max_speed_px_per_sec,
            calculated_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        ON DUPLICATE KEY UPDATE
            visit_duration_sec_stored = VALUES(visit_duration_sec_stored),
            visit_duration_sec_calculated = VALUES(visit_duration_sec_calculated),
            moving_time_sec = VALUES(moving_time_sec),
            idle_time_sec = VALUES(idle_time_sec),
            activity_ratio = VALUES(activity_ratio),
            total_distance_px = VALUES(total_distance_px),
            avg_speed_px_per_sec = VALUES(avg_speed_px_per_sec),
            max_speed_px_per_sec = VALUES(max_speed_px_per_sec),
            calculated_at = NOW()
        """, (
            int(visit_id),
            float(duration_stored),
            float(round(total_time, 3)),
            float(round(moving_time, 3)),
            float(round(idle_time, 3)),
            float(round(activity_ratio, 3)),
            float(round(total_distance_cm, 2)),
            float(round(avg_speed, 2)),
            float(round(max_speed, 2))
        ))

        db.commit()

    except Exception:
        logging.exception(f"Statistics recalculation failed for visit {visit_id}")
        db.rollback()