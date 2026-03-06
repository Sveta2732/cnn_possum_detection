from datetime import date, timedelta
import json
from db import get_connection
from statistics_service import recalculate_visit_statistics
import logging
import os
from mysql.connector.pooling import MySQLConnectionPool

gap_seconds = 20


def get_night_visits(night_date):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

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
        cursor.close()
        conn.close()


def build_groups(visits):
    groups = []
    current_group = []

    for visit in visits:
        if not current_group:
            current_group.append(visit)
            continue

        prev = current_group[-1]

        gap = (visit["start_time"] - prev["end_time"]).total_seconds()

        if gap < gap_seconds:
            current_group.append(visit)
        else:
            if len(current_group) > 1:
                groups.append(current_group)
            current_group = [visit]

    if len(current_group) > 1:
        groups.append(current_group)

    return groups


def merge_group(group):
    logging.info(f"Processing group: {[v['visit_id'] for v in group]}")

    if len(group) < 2:
        return

    main_visit = group[0]
    last_visit = group[-1]

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
            format_strings = ",".join(["%s"] * len(other_ids))

            cursor.execute(
                f"UPDATE frames SET visit_id = %s WHERE visit_id IN ({format_strings})",
                [main_id] + other_ids
            )

            cursor.execute(
                "UPDATE visits SET end_time = %s WHERE visit_id = %s",
                (last_visit["end_time"], main_id)
            )
            logging.info(
                f"Updated visit {main_id} end_time to {last_visit['end_time']}"
            )
            cursor.execute(
                f"DELETE FROM visits WHERE visit_id IN ({format_strings})",
                other_ids
            )
            deleted_count = cursor.rowcount

            logging.info(
                f"Deleted {deleted_count} visits: {other_ids}"
            )

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

        logging.info(f"Merged visits into {main_id}")

        # After DB is consistent
        recalculate_visit_statistics(main_id)

        logging.info(json.dumps({
            "event": "night_merge",
            "main_visit": main_id,
            "merged_visits": other_ids
        }))

    except Exception:
        conn.rollback()
        logging.exception("Merge failed")
        raise

    
    finally:
        cursor.close()
        conn.close()