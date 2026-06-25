"""
fix_workflow_default.py — Recreate tbl_call_workflow with IST default
for action_at, preserving all existing data, correcting historical timestamps.
"""
import os, sys, json, urllib.request

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("ERROR: Set env vars first.")

host = TURSO_URL.replace("libsql://", "").replace("https://", "")
API_URL = f"https://{host}/v2/pipeline"
APPLY = "--apply" in sys.argv

def run_pipeline(stmts):
    requests_list = [{"type": "execute", "stmt": {"sql": s}} for s in stmts]
    requests_list.append({"type": "close"})
    body = json.dumps({"requests": requests_list}).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["results"]

print(f"Mode: {'APPLY' if APPLY else 'DRY RUN'}\n")

stmts = [
    "PRAGMA foreign_keys=OFF;",
    """CREATE TABLE tbl_call_workflow_new (
        workflow_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id         INTEGER NOT NULL REFERENCES tbl_calls(call_id),
        action_by       INTEGER NOT NULL REFERENCES tbl_users(user_id),
        action_type     TEXT NOT NULL,
        action_comment  TEXT,
        from_status     TEXT NOT NULL,
        to_status       TEXT NOT NULL,
        attachment_path TEXT,
        action_at       TEXT DEFAULT (datetime('now','+5 hours','+30 minutes'))
    );""",
    """INSERT INTO tbl_call_workflow_new
        (workflow_id, call_id, action_by, action_type, action_comment,
         from_status, to_status, attachment_path, action_at)
       SELECT workflow_id, call_id, action_by, action_type, action_comment,
              from_status, to_status, attachment_path,
              datetime(action_at, '+5 hours', '+30 minutes')
       FROM tbl_call_workflow;""",
    "DROP TABLE tbl_call_workflow;",
    "ALTER TABLE tbl_call_workflow_new RENAME TO tbl_call_workflow;",
    "PRAGMA foreign_keys=ON;",
]

print("Statements to run:")
for s in stmts:
    print(f"  {s[:80]}...")

if APPLY:
    print("\nApplying...")
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        for e in errs: print(f"  ERROR: {e['error']['message']}")
    else:
        print("  Table recreated with IST default.")
        print("  All existing timestamps corrected to IST (+5:30).")
else:
    print("\nRun with --apply to apply.")
