"""
init_turso_db.py — Initialize a Turso database with SIMS schema + seed data.

Run this ONCE against a fresh Turso database (e.g. srgec-sims-test) to
create all tables and seed default roles/superadmin, BEFORE first use.

Usage (with Turso env vars set):
    python init_turso_db.py

Safe to re-run: CREATE TABLE IF NOT EXISTS and duplicate-insert errors
are caught and skipped.
"""
import os, hashlib
from datetime import datetime

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("ERROR: Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN first.")

import libsql
conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)

# ── 1. Create schema ────────────────────────────────────────────────
from db.schema import SCHEMA
print("Creating schema...")
for stmt in SCHEMA.split(";"):
    stmt = stmt.strip()
    if not stmt:
        continue
    try:
        conn.execute(stmt + ";")
    except Exception as ex:
        print(f"  - skip: {ex}")
conn.commit()
print("Schema created ✓")

# ── 2. Seed roles, modules, default superadmin (same as setup_sims.py) ─
def h(p): return hashlib.sha256(p.encode()).hexdigest()

def ins(sql, params):
    try:
        conn.execute(sql, params)
        conn.commit()
        return True
    except Exception as ex:
        print(f"  - skip insert: {ex}")
        return False

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print("\nSeeding roles...")
for r in [("SuperAdmin","Super Administrator",1),("SysAdmin","System Administrator",0),
          ("HoD","Head of Department",0),("Coordinator","Module Coordinator",0),
          ("Technician","Technician / Engineer",0),("Lab-IC","Lab In-Charge",0),
          ("User","Regular User",0)]:
    ins("INSERT INTO tbl_roles (role_name,role_label,is_super_admin) VALUES (?,?,?)", r)

print("Seeding default superadmin user...")
ins("""INSERT INTO tbl_users (username,password_hash,full_name,employee_id,
        is_super_admin,is_active,created_at)
        VALUES (?,?,?,?,?,?,?)""",
    ("superadmin", h("admin@sims123"), "Super Administrator", "SA001", 1, 1, now))

print("\n✅ Turso database initialized.")
print("Login with: superadmin / admin@sims123")
