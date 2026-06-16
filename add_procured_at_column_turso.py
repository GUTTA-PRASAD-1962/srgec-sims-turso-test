"""
add_procured_at_column_turso.py — Add missing procured_at column to
tbl_spare_indent in Turso.

Usage (env vars set):
    python add_procured_at_column_turso.py            # dry run
    python add_procured_at_column_turso.py --apply    # apply
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

stmt = "ALTER TABLE tbl_spare_indent ADD COLUMN procured_at TEXT;"
print(f"Statement: {stmt}")

if APPLY:
    results = run_pipeline([stmt])
    r = results[0]
    if r["type"] == "error":
        print(f"\nERROR: {r['error']['message']}")
        if "duplicate column" in r['error']['message'].lower():
            print("(Column already exists -- safe to ignore.)")
    else:
        print("\nColumn added successfully.")
else:
    print("\nRun again with --apply to add this column.")
