import os
from dotenv import load_dotenv

load_dotenv(override=True)

USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() == "true"
DB_DEBUG = os.getenv("DB_DEBUG", "false").lower() == "true"


# =========================================================
# SQLITE MODE
# =========================================================
if USE_SQLITE:
    import sqlite3

    SQLITE_DB = os.path.join(os.path.dirname(__file__), "local.db")

    def get_conn():
        conn = sqlite3.connect(SQLITE_DB)
        conn.row_factory = sqlite3.Row
        return conn

    def cursor(conn):
        return conn.cursor()


# =========================================================
# MARIA MODE
# =========================================================
else:
    import mysql.connector
    from mysql.connector import pooling

    DB_CONFIG = {
        "host": os.getenv("DB_HOST"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "autocommit": True
    }

    _pool = None

    def get_pool():
        global _pool
        if _pool is None:
            _pool = pooling.MySQLConnectionPool(
                pool_name="ajax_pool",
                pool_size=5,
                **DB_CONFIG
            )
        return _pool

    def get_conn():
        return get_pool().get_connection()

    def cursor(conn):
        return conn.cursor(dictionary=True)


# =========================================================
# QUERY COMPILATION (KEY FIX)
# =========================================================
def compile_query(query):
    if USE_SQLITE:
        return query
    return query.replace("?", "%s")


# =========================================================
# NORMALIZATION (KEY FIX)
# =========================================================
def normalize(row):
    if row is None:
        return None
    try:
        return dict(row)
    except Exception:
        return row


def normalize_all(rows):
    return [normalize(r) for r in rows]


# =========================================================
# CORE DB OPS
# =========================================================
def fetch_one(query, params=None):
    conn = get_conn()
    cur = cursor(conn)

    compiled = compile_query(query)

    if DB_DEBUG:
        print("SQL:", compiled, params)

    cur.execute(compiled, params or ())
    row = cur.fetchone()

    cur.close()
    conn.close()

    return normalize(row)


def fetch_all(query, params=None):
    conn = get_conn()
    cur = cursor(conn)

    compiled = compile_query(query)

    if DB_DEBUG:
        print("SQL:", compiled, params)

    cur.execute(compiled, params or ())
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return normalize_all(rows)


def execute(query, params=None):
    conn = get_conn()
    cur = cursor(conn)

    compiled = compile_query(query)

    if DB_DEBUG:
        print("SQL:", compiled, params)

    cur.execute(compiled, params or ())
    conn.commit()

    cur.close()
    conn.close()

def create_template(name, layout_json, created_by):
    execute(
        "INSERT INTO templates (name, layout_json, created_by) VALUES (?, ?, ?)",
        (name, layout_json, created_by)
    )

def get_templates():
    return fetch_all("SELECT * FROM templates ORDER BY created_at DESC")