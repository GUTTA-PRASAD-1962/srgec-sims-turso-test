"""
fix_user_module_access_constraint.py — Relax the UNIQUE constraint on
tbl_user_module_access from (user_id, module_id) to
(user_id, module_id, role_name), so one user can hold multiple distinct
roles within the same module (e.g. HoD + ECE-HoD for UPS).

SQLite doesn't support ALTER TABLE to drop/modify constraints directly,
so this recreates the table:
  1. Create new table with correct constraint
  2. Copy all data across
  3. Drop old table
  4. Rename new table to original name

Usage (env vars set):
    python fix_user_module_access_constraint.py            # dry run
    python fix_user_module_access_constraint.py --apply    # apply
"""
import os, sys, json, urllib.request

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("ERROR: Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN first.")

host = TURSO_URL.replace("libsql://", "").replace("https://", "")
API_URL = f"https://{host}/v2/pipeline"
APPLY = "--apply" in sys.argv


def run_pipeline(stmts):
    requests_list = [{"type": "execute", "stmt": {"sql": s}} for s in stmts]
    requests_list.append({"type": "close"})
    body = json.dumps({"requests": requests_list}).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["results"]


print(f"Connecting to: {host}")
print(f"Mode: {'APPLY' if APPLY else 'DRY RUN'}\n")

stmts = [
    "PRAGMA foreign_keys=OFF;",

    """CREATE TABLE tbl_user_module_access_new (
        access_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES tbl_users(user_id),
        module_id  INTEGER NOT NULL REFERENCES tbl_modules(module_id),
        role_name  TEXT NOT NULL,
        is_active  INTEGER DEFAULT 1,
        granted_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(user_id, module_id, role_name)
    );""",

    """INSERT INTO tbl_user_module_access_new
        (access_id, user_id, module_id, role_name, is_active, granted_at)
       SELECT access_id, user_id, module_id, role_name, is_active, granted_at
       FROM tbl_user_module_access;""",

    "DROP TABLE tbl_user_module_access;",

    "ALTER TABLE tbl_user_module_access_new RENAME TO tbl_user_module_access;",
]

print("Statements to run:")
for s in stmts:
    print(f"  {s[:80]}...")

if APPLY:
    print("\nApplying...")
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        print(f"  {len(errs)} error(s):")
        for e in errs:
            print(f"    - {e['error']['message']}")
    else:
        print("  Table recreated successfully with new constraint.")
        print("  Users can now hold multiple distinct roles per module.")
else:
    print("\nRun again with --apply to apply these changes.")
