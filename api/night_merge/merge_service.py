from datetime import date, timedelta
import json
# Database connection helper
from db import get_connection
# Recalculate statistics after merge
from statistics_service import recalculate_visit_statistics
import logging
import os
from mysql.connector.pooling import MySQLConnectionPool


# Maximum allowed gap (in seconds) between visits to consider merging
gap_seconds = 20


# Fetch all visits for a given night_date ordered by start time
def get_night_visits(night_date):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    # SQL query to retrieve visit metadata
    query = """
        SELECT visit_id, start_time, end_time
        FROM visits
        WHERE night_date = %s
        ORDER BY start_time
    """

    try:
        cursor.execute(query, (night_date,))
        return cursor.fetchall()
    finally:
        # Always close cursor and connection
        cursor.close()
        conn.close()


# Build groups of visits that should be merged
def build_groups(visits):
    groups = []
    current_group = []

    for visit in visits:
        # Start first group
        if not current_group:
            current_group.append(visit)
            continue

        # Previous visit in current group
        prev = current_group[-1]

        # Calculate time gap between visits
        gap = (visit["start_time"] - prev["end_time"]).total_seconds()

        # If gap is small enough - same group
        if gap < gap_seconds:
            current_group.append(visit)
        else:
            # If group contains multiple visits - save it
            if len(current_group) > 1:
                groups.append(current_group)
            # Start new group
            current_group = [visit]

    # Append last group if valid
    if len(current_group) > 1:
        groups.append(current_group)

    return groups


# Merge all visits inside a single group
def merge_group(group):
    logging.info(f"Processing group: {[v['visit_id'] for v in group]}")

    # Skip if group has less than 2 visits
    if len(group) < 2:
        return

    # First visit becomes main visit
    main_visit = group[0]
    last_visit = group[-1]

    # IDs to merge into main visit
    other_ids = [v["visit_id"] for v in group[1:]]
    main_id = main_visit["visit_id"]

    conn = get_connection()
    cursor = conn.cursor()

    logging.info(
        f"Starting merge group: main={main_id}, "
        f"others={other_ids}"
    )
    
    try:
        conn.start_transaction()

        if other_ids:
            # Prepare placeholders for SQL IN clause
            format_strings = ",".join(["%s"] * len(other_ids))

            # Reassign frames to main visit
            cursor.execute(
                f"UPDATE frames SET visit_id = %s WHERE visit_id IN ({format_strings})",
                [main_id] + other_ids
            )

            # Update end_time of main visit
            cursor.execute(
                "UPDATE visits SET end_time = %s WHERE visit_id = %s",
                (last_visit["end_time"], main_id)
            )
            logging.info(
                f"Updated visit {main_id} end_time to {last_visit['end_time']}"
            )

            # Delete merged visits
            cursor.execute(
                f"DELETE FROM visits WHERE visit_id IN ({format_strings})",
                other_ids
            )


            deleted_count = cursor.rowcount
            logging.info(
                f"Deleted {deleted_count} visits: {other_ids}"
            )

            # Insert audit record for each merged visit
            for vid in other_ids:
                cursor.execute("""
                    INSERT INTO night_merge_audit (
                        executed_at,
                        main_visit_id,
                        merged_visit_id
                    )
                    VALUES (NOW(), %s, %s)
                """, (main_id, vid))

        conn.commit()

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM night_merge_audit")
        logging.warning(f"AUDIT COUNT AFTER COMMIT: {cursor.fetchone()}")
        cursor.close()
        
        logging.info(f"Merged visits into {main_id}")

        # Recalculate statistics for updated visit
        recalculate_visit_statistics(main_id)

        # Structured JSON log entry
        logging.info(json.dumps({
            "event": "night_merge",
            "main_visit": main_id,
            "merged_visits": other_ids
        }))

    except Exception:
        # Rollback on failure
        conn.rollback()
        logging.exception("Merge failed")
        raise

    finally:
        # Always close cursor and connection
        cursor.close()
        conn.close()