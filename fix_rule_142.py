"""Fix rule 142: HEAD-UPS BUDGET REVIEW → BUDGET REVIEW should be HEAD-UPS role, not HoD"""
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
    # Rule 142: HEAD-UPS BUDGET REVIEW → BUDGET REVIEW
    # HEAD-UPS reviews cost estimate and forwards to Dept HoD for budget approval
    "UPDATE tbl_workflow_rules SET allowed_roles='HEAD-UPS', action_label='Forward to Dept HoD for Budget Approval' WHERE rule_id=142;",
    # Also fix rule 141 - this was the label we already fixed, but also ensure role is correct
    # Rule 141: COST ESTIMATED → HEAD-UPS BUDGET REVIEW, should be ECE-HoD/SysAdmin forwarding to HEAD-UPS
    # Let's check - who should forward cost estimate to HEAD-UPS? SysAdmin (coordinator)
    "UPDATE tbl_workflow_rules SET allowed_roles='SysAdmin', action_label='Forward Cost Estimate to HEAD-UPS' WHERE rule_id=141;",
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
        print("\n  Rules fixed successfully.")
else:
    print("\nRun with --apply to apply.")
