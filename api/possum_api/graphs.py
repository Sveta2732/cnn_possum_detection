from pydantic import BaseModel
from typing import List, Dict, Any

class ChartResponse(BaseModel):
    title: str
    chart_type: str
    x_label: str
    y_label: str
    data: List[Dict[str, Any]]


def execute_chart_query(
    conn,
    query,
    title,
    chart_type,
    x_label,
    y_label,
    fetch_one=True,
    params=None
):
    cursor = conn.cursor(dictionary=True)

    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetch_one:
            row = cursor.fetchone()
            data = [row] if row else []
        else:
            data = cursor.fetchall()

        return ChartResponse(
            title=title,
            chart_type=chart_type,
            x_label=x_label,
            y_label=y_label,
            data=data if data else []
        )

    finally:
        cursor.close()

def total_visits(conn):
    query = """
        SELECT COUNT(*) as total_number_of_visits
        FROM visits
    """

    return execute_chart_query(
        conn,
        query,
        "Total Visits",
        "metric",
        "",
        "Total Visits"
    )

def average_visits_per_day(conn):
    query = """
            SELECT 
            ROUND(AVG(visits), 1) as average_visits_per_day
            FROM (
                SELECT night_date, COUNT(*) as visits
                FROM visits
                GROUP BY night_date
            ) AS daily_visits
    """

    return execute_chart_query(
        conn,
        query,
        "Average Visits per Night",
        "metric",
        "",
        "Average Visits"
    )

def average_duration(conn):
    query = """
        SELECT ROUND(AVG(duration_seconds), 1) as average_duration_seconds
        FROM visits
    """

    return execute_chart_query(
        conn,
        query,
        "Average Visit Duration",
        "metric",
        "",
        "Average Duration (seconds)"
    )

def pick_hour(conn):
    query = """
        SELECT HOUR(start_time) as hour, 
                COUNT(*) as total_number_of_visits
        FROM visits
        GROUP BY hour
        ORDER BY total_number_of_visits DESC
        LIMIT 1
    """

    return execute_chart_query(
        conn,
        query,
        "Most Popular Hour",
        "metric",
        "",
        "Total Visits"
    )

def max_day(conn):
    query = """
        SELECT night_date, visits AS max_visits_per_day
        FROM (
            SELECT night_date, COUNT(*) AS visits
            FROM visits
            GROUP BY night_date
        ) daily_visits
        ORDER BY visits DESC
        LIMIT 1
    """

    return execute_chart_query(
        conn,
        query,
        "Maximum Visits per Day",
        "metric",
        "",
        "Maximum Visits per Day"
    )

def weeks_comparison(conn):
    query = """
        SELECT 
            day_of_week,
            ROUND(AVG(visits_per_day), 0) AS average_number_of_visits
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
    """

    return execute_chart_query(
        conn,
        query,
        "Average Visits by Day of the Week",
        "bar",
        "Day of Week",
        "Average Number of Visits",
        fetch_one=False
    )

def month_comparison(conn):
    query = """
        SELECT MONTH(night_date) as month, 
            COUNT(visit_id) as number_of_visits
        FROM visits
        GROUP BY month
        ORDER BY month
    """

    return execute_chart_query(
        conn,
        query,
        "Monthly Possum Visit Trends",
        "line",
        "Month",
        "Number of Visits",
        fetch_one=False
    )

def hours_comparison(conn):
    query = """
        SELECT HOUR(start_time) as hour, 
            COUNT(*) as number_of_visits
        FROM visits
        GROUP BY hour
        ORDER BY hour
    """

    return execute_chart_query(
        conn,
        query,
        "Possum Visits by Hour of the Night",
        "line",
        "Hour of Night",
        "Number of Visits",
        fetch_one=False
    )

def time_percentage(conn):
    query = """
        SELECT CASE WHEN HOUR(start_time) >= 21  THEN 'Evening' 
                    WHEN HOUR(start_time) >= 0 AND HOUR(start_time) < 3 THEN 'Late Night'
                    ELSE 'Early Morning' END as time_of_day,
            COUNT(*) as number_of_visits,
            ROUND(COUNT(*) / (SELECT COUNT(*) FROM visits) * 100, 2) as percentage_of_visits
        FROM visits
        GROUP BY time_of_day
        ORDER BY FIELD(time_of_day, 'Late Night', 'Early Morning', 'Evening')
    """

    return execute_chart_query(
        conn,
        query,
        "When Possums Are Most Active During the Night",
        "pie",
        "Night Period",
        "Percentage of Visits",
        fetch_one=False
    )


def hist_duration(conn):
    query = """
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
    """

    return execute_chart_query(
        conn,
        query,
        "How Long Possums Stay During Each Visit",
        "histogram",
        "Visit Duration",
        "Number of Visits",
        fetch_one=False
    )

def start_fence_position(conn):
    query = """
        WITH fence_positions AS (
            SELECT 
                r.roi_id,
                (r.bbox_x1 + r.bbox_x2) / 2 AS box_center,
                v.visit_id
            FROM visits v
            JOIN frames f ON v.visit_id = f.visit_id
            JOIN rois r ON f.frame_id = r.frame_id
            WHERE r.bbox_x1 IS NOT NULL AND r.bbox_x2 IS NOT NULL
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
                WHEN box_center >= 100 AND box_center < 500 THEN 'Left Fence Zone'
                WHEN box_center >= 500 AND box_center < 840 THEN 'Centre Fence Zone'
                WHEN box_center >= 840 AND box_center < 1400 THEN 'Right Fence Zone'
                ELSE 'Outside Fence'
            END AS fence_position,
            COUNT(*) AS number_of_visits
        FROM ranked_rois
        WHERE roi_count = 1
        GROUP BY fence_position
    """

    return execute_chart_query(
        conn,
        query,
        "Where Possums Enter the Fence",
        "pie",
        "Fence Entry Zone",
        "Number of Visits",
        fetch_one=False
    )

def end_fence_position(conn):
    query = """
        WITH fence_positions AS (
            SELECT 
                r.roi_id,
                (r.bbox_x1 + r.bbox_x2) / 2 AS box_center,
                v.visit_id
            FROM visits v
            JOIN frames f ON v.visit_id = f.visit_id
            JOIN rois r ON f.frame_id = r.frame_id
            WHERE r.bbox_x1 IS NOT NULL AND r.bbox_x2 IS NOT NULL
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
                WHEN box_center >= 100 AND box_center < 500 THEN 'Left Fence Zone'
                WHEN box_center >= 500 AND box_center < 840 THEN 'Centre Fence Zone'
                WHEN box_center >= 840 AND box_center < 1400 THEN 'Right Fence Zone'
                ELSE 'Outside Fence'
            END AS fence_position,
            COUNT(*) AS number_of_visits
        FROM ranked_rois
        WHERE roi_count = 1
        GROUP BY fence_position
    """

    return execute_chart_query(
        conn,
        query,
        "Where Possums Leave the Fence",
        "pie",
        "Fence Exit Zone",
        "Number of Visits",
        fetch_one=False
    )

def heatmap_position(conn):
    query = """
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
        SELECT position_bin, COUNT(*) as number_of_detections
        FROM positions
        WHERE position_bin IS NOT NULL
        GROUP BY position_bin
        ORDER BY position_bin
    """

    return execute_chart_query(
        conn,
        query,
        "Most Frequent Possum Positions",
        "heatmap",
        "Fence Position Segments",
        "Number of Detections",
        fetch_one=False
    )



