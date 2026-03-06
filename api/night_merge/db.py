import os
from mysql.connector.pooling import MySQLConnectionPool
from contextlib import contextmanager

db_pool = MySQLConnectionPool(
    pool_name="night_merge_pool",
    pool_size=5,
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    database=os.environ["DB_NAME"],
    unix_socket=f"/cloudsql/{os.environ['INSTANCE_CONNECTION_NAME']}"
)

def get_connection():
    return db_pool.get_connection()

@contextmanager
def db_cursor():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield conn, cursor
    finally:
        cursor.close()
        conn.close()