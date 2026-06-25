import os, json, urllib.request
TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("ERROR: Set env vars first.")
host = TURSO_URL.replace("libsql://", "").replace("https://", "")
API_URL = f"https://{host}/v2/pipeline"
sql = "UPDATE tbl_workflow_rules SET action_label='Repair Complete - Ready for Verification' WHERE rule_id=150;"
body = json.dumps({"requests":[{"type":"execute","stmt":{"sql":sql}},{"type":"close"}]}).encode()
req = urllib.request.Request(API_URL, data=body, method="POST",
    headers={"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"})
r = json.loads(urllib.request.urlopen(req).read())
print("OK" if r["results"][0]["type"] != "error" else r["results"][0]["error"])
