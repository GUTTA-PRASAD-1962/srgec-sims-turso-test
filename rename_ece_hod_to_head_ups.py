"""
rename_ece_hod_to_head_ups.py — Rename role 'ECE-HoD' to 'HEAD-UPS'
across tbl_workflow_rules.allowed_roles and tbl_user_module_access.role_name.

Usage (env vars set):
    python rename_ece_hod_to_head_ups.py            # dry run
    python rename_ece_hod_to_head_ups.py --apply    # apply
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

# 1. Show affected workflow rules
rules = query("SELECT rule_id, allowed_roles FROM tbl_workflow_rules WHERE allowed_roles LIKE '%ECE-HoD%'")
print(f"Workflow rules containing 'ECE-HoD': {len(rules)}")
for r in rules:
    print(f"  [{r['rule_id']}] {r['allowed_roles']}")

# 2. Show affected user_module_access rows
access = query("SELECT access_id, user_id, module_id, role_name FROM tbl_user_module_access WHERE role_name='ECE-HoD'")
print(f"\nUser module access rows with role_name='ECE-HoD': {len(access)}")
for a in access:
    print(f"  [{a['access_id']}] user_id={a['user_id']} module_id={a['module_id']}")

stmts = [
    "UPDATE tbl_workflow_rules SET allowed_roles = REPLACE(allowed_roles, 'ECE-HoD', 'HEAD-UPS') WHERE allowed_roles LIKE '%ECE-HoD%';",
    "UPDATE tbl_user_module_access SET role_name = 'HEAD-UPS' WHERE role_name = 'ECE-HoD';",
]

print(f"\n{'='*60}")
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
        print("  Rename applied successfully.")
else:
    print("\nRun again with --apply to apply this rename.")
