"""Add action_at column to tbl_call_workflow with IST default."""
import os, json, urllib.request

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("ERROR: Set env vars first.")

host = TURSO_URL.replace("libsql://", "").replace("https://", "")
API_URL = f"https://{host}/v2/pipeline"

def run(sql):
    body = json.dumps({"requests":[{"type":"execute","stmt":{"sql":sql}},{"type":"close"}]}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req).read())
    return r["results"][0]

# Add action_at column with IST default
sql = "ALTER TABLE tbl_call_workflow ADD COLUMN action_at TEXT DEFAULT (datetime('now','+5 hours','+30 minutes'));"
result = run(sql)
if result.get("type") == "error":
    msg = result["error"]["message"]
    if "duplicate column" in msg.lower():
        print("Column already exists — safe to ignore.")
    else:
        print(f"ERROR: {msg}")
else:
    print("action_at column added successfully with IST default.")

# Verify
verify = run("PRAGMA table_info(tbl_call_workflow);")
cols = [r[0] for r in verify["response"]["result"]["rows"]]
print(f"Columns now: {[c.get('value','?') for c in [row[1] for row in verify['response']['result']['rows']]]}")
