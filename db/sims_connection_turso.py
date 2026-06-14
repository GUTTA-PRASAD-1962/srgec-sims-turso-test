"""
db/connection.py — Turso (libSQL) backed, with local SQLite fallback.

If env vars TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are set, connects
to the remote Turso database (data persists across Render restarts).
Otherwise falls back to local SQLite file (for local development).
"""
import os
import sqlite3

try:
    from config import DB_PATH
except Exception:
    DB_PATH = "db/sims_data.db"

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)

if USE_TURSO:
    import libsql_experimental as libsql


def get_conn():
    if USE_TURSO:
        conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _as_row(cur, row):
    """Wrap a raw tuple as a dict-like sqlite3.Row using cursor description."""
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def fetchall(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        if USE_TURSO:
            return [_as_row(cur, r) for r in rows]
        return rows
    finally:
        conn.close()


def fetchone(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        if USE_TURSO:
            return _as_row(cur, row)
        return row
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid if hasattr(cur, "lastrowid") else None
    finally:
        conn.close()
