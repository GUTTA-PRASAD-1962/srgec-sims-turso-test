"""
fix_closing_steps.py — Combine closing steps for Lab-IC and HoD into single clicks:
1. Lab-IC: REPAIRED → DEPT ACKNOWLEDGED (skip VERIFIED stop)
2. HoD: DEPT ACKNOWLEDGED → HEAD-UPS ACKNOWLEDGED (skip intermediate stop)
Deactivates now-redundant rules 151 and 152.
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
    # 1. Lab-IC: REPAIRED → DEPT ACKNOWLEDGED (was REPAIRED → VERIFIED)
    "UPDATE tbl_workflow_rules SET to_status='DEPT ACKNOWLEDGED', action_label='Verify Working & Forward to Dept HoD' WHERE rule_id=8;",

    # 2. Deactivate old VERIFIED → DEPT ACKNOWLEDGED rule (no longer needed)
    "UPDATE tbl_workflow_rules SET is_active=0 WHERE rule_id=151;",

    # 3. HoD: DEPT ACKNOWLEDGED → HEAD-UPS ACKNOWLEDGED (was DEPT ACKNOWLEDGED → ECE ACKNOWLEDGED via rule 152)
    # Rule 152 already does DEPT ACKNOWLEDGED → HEAD-UPS ACKNOWLEDGED with role HoD
    # Just update the label to be clearer
    "UPDATE tbl_workflow_rules SET action_label='Acknowledge & Forward to HEAD-UPS' WHERE rule_id=152;",

    # 4. Also deactivate old VERIFIED → CLOSED rule (rule 9) if still active
    "UPDATE tbl_workflow_rules SET is_active=0 WHERE rule_id=9 AND is_active=1;",
]

print("Statements:")
for s in stmts:
    print(f"  {s}")

if APPLY:
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        for e in errs: print(f"  ERROR: {e['error']['message']}")
    else:
        print("\n  All closing steps combined successfully.")
        print("  Lab-IC: REPAIRED → DEPT ACKNOWLEDGED (1 click)")
        print("  HoD:    DEPT ACKNOWLEDGED → HEAD-UPS ACKNOWLEDGED (1 click)")
else:
    print("\nRun with --apply to apply.")
