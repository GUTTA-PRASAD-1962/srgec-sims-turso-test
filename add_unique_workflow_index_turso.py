"""
add_unique_workflow_index_turso.py — Add a UNIQUE index on
tbl_workflow_rules(module_id, from_status, to_status, action_label) so that
future re-seeding (e.g. on app restart) cannot insert duplicate rows --
INSERTs that would duplicate an existing combination will fail/be ignored.

IMPORTANT: Run dedupe_workflow_rules_turso.py --apply FIRST, or this index
creation will fail (UNIQUE constraint cannot be added while duplicates exist).

Usage (env vars set):
    python add_unique_workflow_index_turso.py            # dry run
    python add_unique_workflow_index_turso.py --apply    # create index
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

stmt = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_rules_unique "
    "ON tbl_workflow_rules(module_id, from_status, to_status, action_label);"
)
print(f"Statement: {stmt}")

if APPLY:
    results = run_pipeline([stmt])
    r = results[0]
    if r["type"] == "error":
        print(f"\nERROR: {r['error']['message']}")
        print("\nIf this says duplicates still exist, run "
              "dedupe_workflow_rules_turso.py --apply first.")
    else:
        print("\nUnique index created successfully.")
        print("Future duplicate INSERTs (same module_id+from_status+to_status+action_label) "
              "will now fail/be ignored automatically.")
else:
    print("\nRun again with --apply to create this index.")
