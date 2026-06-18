"""
fix_ece_hod_labels.py — Update stale 'Forward to ECE HoD' action_label
text to 'Forward to HEAD-UPS' for rules where allowed_roles=HoD (the
button HoD clicks to forward institute-wide UPS oversight role).
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
    "UPDATE tbl_workflow_rules SET action_label='Forward to HEAD-UPS' WHERE rule_id=136;",
    "UPDATE tbl_workflow_rules SET action_label='Forward to HEAD-UPS' WHERE rule_id=141;",
    "UPDATE tbl_workflow_rules SET action_label='Forward to HEAD-UPS' WHERE rule_id=152;",
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
        print("  All 3 labels updated successfully.")
else:
    print("\nRun again with --apply to apply these changes.")
