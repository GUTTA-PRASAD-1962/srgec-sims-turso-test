"""
fix_label_and_timezone.py — Two fixes:
1. Update action_label for rule 141 (COST ESTIMATED → HEAD-UPS BUDGET REVIEW)
   from 'Forward to HEAD-UPS' to 'Forward to Dept HoD for Budget Approval'
2. Update action_label for rule 152 (DEPT ACKNOWLEDGED → HEAD-UPS ACKNOWLEDGED)
   from 'Forward to HEAD-UPS' to 'Forward to HEAD-UPS for Acknowledgement'
   (to distinguish from rule 136 which also says 'Forward to HEAD-UPS')
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
    # Rule 141: HEAD-UPS forwards budget to Dept HoD
    "UPDATE tbl_workflow_rules SET action_label='Forward to Dept HoD for Budget Approval' WHERE rule_id=141;",
    # Rule 152: HoD forwards acknowledgement to HEAD-UPS
    "UPDATE tbl_workflow_rules SET action_label='Forward to HEAD-UPS for Final Acknowledgement' WHERE rule_id=152;",
]

print("Statements:")
for s in stmts:
    print(f"  {s}")

if APPLY:
    print("\nApplying...")
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        for e in errs:
            print(f"  ERROR: {e['error']['message']}")
    else:
        print("  Labels updated successfully.")
else:
    print("\nRun again with --apply to apply.")
