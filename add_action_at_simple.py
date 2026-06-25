"""Add action_at column to tbl_call_workflow (no default - Python will always provide it)."""
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

# Add action_at column without default
result = run("ALTER TABLE tbl_call_workflow ADD COLUMN action_at TEXT;")
if result.get("type") == "error":
    msg = result["error"]["message"]
    if "duplicate column" in msg.lower() or "already exists" in msg.lower():
        print("Column already exists.")
    else:
        print(f"ERROR: {msg}")
else:
    print("action_at column added successfully.")
