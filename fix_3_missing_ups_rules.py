"""
fix_3_missing_ups_rules.py — Reactivate + update the 3 UPS rules that
collided with old inactive rows during the full workflow replace.
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
    # Rule [134]: ASSIGNED -> REPAIRED 'Mark as Repaired (No Parts)' -- reactivate
    "UPDATE tbl_workflow_rules SET is_active=1, requires_comment=1, requires_assignee=0, sort_order=5 WHERE rule_id=134;",

    # Rule [8]: REPAIRED -> VERIFIED 'Verify — Working Correctly' -- reactivate, fix roles to Lab-IC only
    "UPDATE tbl_workflow_rules SET is_active=1, allowed_roles='Lab-IC', requires_comment=1, requires_assignee=0, sort_order=18 WHERE rule_id=8;",

    # Rule [11]: OPEN -> REJECTED 'Reject Complaint' -- reactivate, fix roles to HoD,SysAdmin
    "UPDATE tbl_workflow_rules SET is_active=1, allowed_roles='HoD,SysAdmin', requires_comment=1, requires_assignee=0, sort_order=22 WHERE rule_id=11;",
]

print("Statements to run:")
for s in stmts:
    print(f"  {s}")

if APPLY:
    print("\nApplying...")
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        print(f"  {len(errs)} error(s):")
        for e in errs:
            print(f"    - {e['error']['message']}")
    else:
        print("  All 3 rules fixed successfully.")
else:
    print("\nRun again with --apply to apply these changes.")
