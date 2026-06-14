"""
migrate_to_turso.py — Copy a local SQLite database to Turso.

Usage:
    python migrate_to_turso.py

Set these before running (PowerShell):
    $env:TURSO_DATABASE_URL="libsql://your-db.turso.io"
    $env:TURSO_AUTH_TOKEN="your-token"

Edit LOCAL_DB_PATH below to point to your local .db file.
"""
import os
import sqlite3
import libsql_experimental as libsql

LOCAL_DB_PATH = "db/sims_data.db"   # <-- adjust if needed

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit(
        "ERROR: Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment "
        "variables before running this script."
    )

print(f"Reading local DB: {LOCAL_DB_PATH}")
src = sqlite3.connect(LOCAL_DB_PATH)
src.row_factory = sqlite3.Row

print(f"Connecting to Turso: {TURSO_URL}")
dst = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)

# ── 1. Get schema (CREATE TABLE / INDEX statements) from local DB ──
schema_rows = src.execute(
    "SELECT type, name, sql FROM sqlite_master "
    "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
    "ORDER BY (type='table') DESC"  # tables before indexes
).fetchall()

print(f"\nFound {len(schema_rows)} schema objects (tables/indexes).")

for row in schema_rows:
    obj_type, name, sql = row["type"], row["name"], row["sql"]
    try:
        dst.execute(sql)
        print(f"  ✓ Created {obj_type}: {name}")
    except Exception as ex:
        # Likely "already exists" — safe to ignore on re-runs
        print(f"  - Skipped {obj_type} {name}: {ex}")

# ── 2. Copy data table by table ─────────────────────────────────────
tables = [r["name"] for r in schema_rows if r["type"] == "table"]

for table in tables:
    rows = src.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        print(f"  {table}: 0 rows (skipped)")
        continue

    cols = rows[0].keys()
    placeholders = ",".join(["?"] * len(cols))
    col_list = ",".join(cols)
    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    count = 0
    for row in rows:
        try:
            dst.execute(insert_sql, tuple(row))
            count += 1
        except Exception as ex:
            print(f"    ! Row error in {table}: {ex}")

    print(f"  {table}: {count}/{len(rows)} rows copied")

dst.commit() if hasattr(dst, "commit") else None
src.close()
print("\n✅ Migration complete.")
print("Verify by running a query against Turso, e.g.:")
print("  SELECT COUNT(*) FROM tbl_users;")
