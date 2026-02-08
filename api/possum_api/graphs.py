from pydantic import BaseModel
from typing import List, Dict, Any

class ChartResponse(BaseModel):
    title: str
    chart_type: str
    x_label: str
    y_label: str
    data: List[Dict[str, Any]]


def total_visits(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT COUNT(*) as total_number_of_visits
            FROM visits
        """)

        row = cursor.fetchone()

        return ChartResponse(
            title="Total Visits",
            chart_type="metric",
            x_label="",
            y_label="Total Visits",
            data=[row] if row else []
        )

    finally:
        cursor.close()


def average_visits_per_day(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
            Avg(visits) as average_visits_per_day
            FROM (
                SELECT night_date, COUNT(*) as visits
                FROM visits
                GROUP BY night_date
            ) AS daily_visits
        """)

        row = cursor.fetchone()

        return ChartResponse(
            title="Average Visits per Night",
            chart_type="metric",
            x_label="",
            y_label="Average Visits",
            data=[row] if row else []
        )
    
    finally:
            cursor.close()


def average_duration(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT AVG(duration_seconds) as average_duration_seconds
            FROM visits
        """)

        row = cursor.fetchone()

        return ChartResponse(
            title="Average Visit Duration",
            chart_type="metric",
            x_label="",
            y_label="Average Duration (seconds)",
            data=[row] if row else []
        )

    finally:
        cursor.close()


def pick_hour(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT HOUR(start_time) as hour, 
                COUNT(*) as total_number_of_visits
            FROM visits
            GROUP BY hour
            ORDER BY total_number_of_visits DESC
            LIMIT 1
        """)

        row = cursor.fetchone()

        return ChartResponse(
            title="Most Popular Hour",
            chart_type="metric",
            x_label="",
            y_label="Total Visits",
            data=[row] if row else []
        )

    finally:
        cursor.close()

def max_day(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT night_date, visits AS max_visits_per_day
            FROM (
                SELECT night_date, COUNT(*) AS visits
                FROM visits
                GROUP BY night_date
            ) daily_visits
            ORDER BY visits DESC
            LIMIT 1
            """)

        row = cursor.fetchone()

        return ChartResponse(
            title="Maximum Visits per Day",
            chart_type="metric",
            x_label="",
            y_label="Maximum Visits per Day",
            data=[row] if row else []
        )

    finally:
        cursor.close()

def weeks_comparison(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                day_of_week,
                AVG(visits_per_day) AS average_number_of_visits
            FROM (
                SELECT 
                    DAYOFWEEK(night_date) AS day_of_week,
                    night_date,
                    COUNT(*) AS visits_per_day
                FROM visits
                GROUP BY night_date
            ) AS daily_counts
            GROUP BY day_of_week
            ORDER BY day_of_week;
                    """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="Average Visits per Day of Week",
            chart_type="bar",
            x_label="Day of Week",
            y_label="Number of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()

def month_comparison(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT MONTH(night_date) as month, 
                COUNT(visit_id) as number_of_visits
            FROM visits
            GROUP BY month
            ORDER BY month
        """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="Number of Visits per Month",
            chart_type="bar",
            x_label="Month",
            y_label="Number of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()


def hours_comparison(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT HOUR(start_time) as hour, 
                COUNT(*) as number_of_visits
            FROM visits
            GROUP BY hour
            ORDER BY hour
        """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="Number of Visits per Hour",
            chart_type="bar",
            x_label="Hour",
            y_label="Number of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()

def time_percentage(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT CASE WHEN HOUR(start_time) >= 21  THEN 'early_night' 
                       WHEN HOUR(start_time) >= 0 AND HOUR(start_time) < 3 THEN 'deep_night'
                       ELSE 'morning' END as time_of_day,
                COUNT(*) as number_of_visits,
                ROUND(COUNT(*) / (SELECT COUNT(*) FROM visits) * 100, 2) as percentage_of_visits
            FROM visits
            GROUP BY time_of_day
            ORDER BY FIELD(time_of_day, 'deep_night', 'morning', 'early_night')
        """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="Percentage of Visits by Time of Night",
            chart_type="pie",
            x_label="Time of Night",
            y_label="Percentage of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()

def hist_duration(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN duration_seconds < 10 THEN '0-10 sec'
                    WHEN duration_seconds >= 10 AND duration_seconds < 30 THEN '10-30 sec'
                    WHEN duration_seconds >= 30 AND duration_seconds < 60 THEN '30-60 sec'
                    ELSE '>60 sec'
                END as duration_range,
                COUNT(*) as number_of_visits
            FROM visits
            GROUP BY duration_range
            ORDER BY FIELD(duration_range, '0-10 sec', '10-30 sec', '30-60 sec', '>60 sec')
        """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="Distribution of Visit Durations",
            chart_type="histogram",
            x_label="Duration Range",
            y_label="Number of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()

def start_fence_position(conn):
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            WITH fence_positions AS (
                SELECT 
                    r.roi_id,
                    (r.bbox_x1 + r.bbox_x2) / 2 AS box_center,
                    v.visit_id
                FROM visits v
                JOIN frames f ON v.visit_id = f.visit_id
                JOIN rois r ON f.frame_id = r.frame_id
            ),
            ranked_rois AS (
                SELECT 
                    roi_id,
                    visit_id,
                    box_center,
                    ROW_NUMBER() OVER (PARTITION BY visit_id ORDER BY roi_id) AS roi_count
                FROM fence_positions
            )
            SELECT 
                CASE 
                    WHEN box_center >= 100 AND box_center < 500 THEN 'Left Fence'
                    WHEN box_center >= 500 AND box_center < 840 THEN 'Centre Fence'
                    WHEN box_center >= 840 AND box_center < 1200 THEN 'Right Fence'
                    ELSE 'Outside Fence'
                END AS fence_position,
                COUNT(*) AS number_of_visits
            FROM ranked_rois
            WHERE roi_count = 1
            GROUP BY fence_position
                    """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="Pie Chart of Start Fence Positions",
            chart_type="pie",
            x_label="Start Fence Position",
            y_label="Number of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()

def end_fence_position(conn):
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            WITH fence_positions AS (
                SELECT 
                    r.roi_id,
                    (r.bbox_x1 + r.bbox_x2) / 2 AS box_center,
                    v.visit_id
                FROM visits v
                JOIN frames f ON v.visit_id = f.visit_id
                JOIN rois r ON f.frame_id = r.frame_id
            ),
            ranked_rois AS (
                SELECT 
                    roi_id,
                    visit_id,
                    box_center,
                    ROW_NUMBER() OVER (PARTITION BY visit_id ORDER BY roi_id DESC) AS roi_count
                FROM fence_positions
            )
            SELECT 
                CASE 
                    WHEN box_center >= 100 AND box_center < 500 THEN 'Left Fence'
                    WHEN box_center >= 500 AND box_center < 840 THEN 'Centre Fence'
                    WHEN box_center >= 840 AND box_center < 1200 THEN 'Right Fence'
                    ELSE 'Outside Fence'
                END AS fence_position,
                COUNT(*) AS number_of_visits
            FROM ranked_rois
            WHERE roi_count = 1
            GROUP BY fence_position
        """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="Pie Chart of End Fence Positions",
            chart_type="pie",
            x_label="End Fence Position",
            y_label="Number of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()

def heatmap_position(conn):

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            WITH fence_positions AS (
            SELECT 
                (bbox_x1 + bbox_x2) / 2 AS box_center
            FROM rois),
            positions AS (
            SELECT 
                       CASE
                        WHEN box_center < 0 THEN NULL
                        WHEN box_center <= 150 THEN 1
                        WHEN box_center <= 300 THEN 2
                        WHEN box_center <= 450 THEN 3
                        WHEN box_center <= 600 THEN 4
                        WHEN box_center <= 750 THEN 5
                        WHEN box_center <= 900 THEN 6
                        WHEN box_center <= 1050 THEN 7
                        WHEN box_center <= 1200 THEN 8
                        WHEN box_center <= 1350 THEN 9
                        WHEN box_center <= 1500 THEN 10
                        ELSE NULL
                        END AS position_bin
            FROM fence_positions)
            SELECT position_bin, COUNT(*) as number_of_visits
            FROM positions
            WHERE position_bin IS NOT NULL
            GROUP BY position_bin
            ORDER BY position_bin
        """)

        rows = cursor.fetchall()

        return ChartResponse(
            title="horizontal Heatmap of Visit Positions",
            chart_type="heatmap",
            x_label="possum position (bin)",
            y_label="Number of Visits",
            data=rows if rows else []
        )

    finally:
        cursor.close()


