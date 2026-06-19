"""
rename_ece_statuses.py — Rename status labels containing 'ECE' to 'HEAD-UPS'
across tbl_workflow_rules (from_status/to_status), tbl_calls (call_status),
and tbl_call_workflow (from_status/to_status), for full consistency with
the renamed HEAD-UPS role.

Renames:
  ECE REVIEW        -> HEAD-UPS REVIEW
  ECE BUDGET REVIEW -> HEAD-UPS BUDGET REVIEW
  ECE ACKNOWLEDGED  -> HEAD-UPS ACKNOWLEDGED

Usage (env vars set):
    python rename_ece_statuses.py            # dry run
    python rename_ece_statuses.py --apply    # apply
"""
import os, sys, json, urllib.request

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("ERROR: Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN first.")

host = TURSO_URL.replace("libsql://", "").replace("https://", "")
API_URL = f"https://{host}/v2/pipeline"
APPLY = "--apply" in sys.argv

RENAMES = [
    ("ECE BUDGET REVIEW", "HEAD-UPS BUDGET REVIEW"),  # longer string first!
    ("ECE ACKNOWLEDGED",  "HEAD-UPS ACKNOWLEDGED"),
    ("ECE REVIEW",        "HEAD-UPS REVIEW"),
]


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


def query(sql):
    results = run_pipeline([sql])
    r = results[0]
    if r["type"] == "error":
        raise RuntimeError(r["error"]["message"])
    cols = [c["name"] for c in r["response"]["result"]["cols"]]
    rows = []
    for row in r["response"]["result"]["rows"]:
        vals = [cell.get("value") for cell in row]
        rows.append(dict(zip(cols, vals)))
    return rows


print(f"Connecting to: {host}")
print(f"Mode: {'APPLY' if APPLY else 'DRY RUN'}\n")

# Preview affected rows
for old, new in RENAMES:
    rules = query(f"SELECT rule_id, from_status, to_status FROM tbl_workflow_rules WHERE from_status='{old}' OR to_status='{old}'")
    calls = query(f"SELECT call_id, call_status FROM tbl_calls WHERE call_status='{old}'")
    wf    = query(f"SELECT call_id, from_status, to_status FROM tbl_call_workflow WHERE from_status='{old}' OR to_status='{old}'")
    print(f"'{old}' -> '{new}':")
    print(f"  workflow_rules: {len(rules)} row(s)")
    print(f"  calls: {len(calls)} row(s)")
    print(f"  call_workflow: {len(wf)} row(s)")

stmts = []
for old, new in RENAMES:
    stmts.append(f"UPDATE tbl_workflow_rules SET from_status='{new}' WHERE from_status='{old}';")
    stmts.append(f"UPDATE tbl_workflow_rules SET to_status='{new}' WHERE to_status='{old}';")
    stmts.append(f"UPDATE tbl_calls SET call_status='{new}' WHERE call_status='{old}';")
    stmts.append(f"UPDATE tbl_call_workflow SET from_status='{new}' WHERE from_status='{old}';")
    stmts.append(f"UPDATE tbl_call_workflow SET to_status='{new}' WHERE to_status='{old}';")

print(f"\n{'='*60}")
print(f"Total statements: {len(stmts)}")

if APPLY:
    print("\nApplying...")
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        print(f"  {len(errs)} error(s):")
        for e in errs:
            print(f"    - {e['error']['message']}")
    else:
        print("  All renames applied successfully.")
else:
    print("\nRun again with --apply to apply these changes.")
