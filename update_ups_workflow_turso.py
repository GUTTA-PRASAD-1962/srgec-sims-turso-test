"""
update_ups_workflow_turso.py — Apply the new two-path (with/without spares)
workflow for UPS Management directly to tbl_workflow_rules in Turso.

Uses ONLY Python stdlib (urllib, json) -- no installs needed.

Usage:
    Set env vars first:
        $env:TURSO_DATABASE_URL = "libsql://srgec-sims-test-....turso.io"
        $env:TURSO_AUTH_TOKEN   = "your-token"
    Then:
        python update_ups_workflow_turso.py            # dry run (report only)
        python update_ups_workflow_turso.py --apply    # apply changes
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
        headers={
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json",
        }
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["results"]


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
print(f"Mode: {'APPLY' if APPLY else 'DRY RUN (no changes)'}\n")

# Get UPS module_id
mod_row = query("SELECT module_id FROM tbl_modules WHERE module_code='UPS'")
if not mod_row:
    raise SystemExit("UPS module not found!")
mid = int(mod_row[0]["module_id"])
print(f"UPS module_id = {mid}\n")

# Show current rules for UPS
current = query(f"""
    SELECT rule_id, from_status, to_status, action_label, allowed_roles
    FROM tbl_workflow_rules WHERE module_id={mid} ORDER BY rule_id
""")
print("Current UPS rules:")
for r in current:
    print(f"  [{r['rule_id']}] {r['from_status']} -> {r['to_status']} "
          f"'{r['action_label']}' ({r['allowed_roles']})")

stmts = []

def find_rule_id(from_s, to_s, label_contains):
    for r in current:
        if r["from_status"] == from_s and r["to_status"] == to_s and label_contains in r["action_label"]:
            return int(r["rule_id"])
    return None

# ── EDIT 1: OPEN -> UNDER REVIEW "Forward to Coordinator" -> "Forward to System Admin", roles HoD
rid = find_rule_id("OPEN", "UNDER REVIEW", "Forward")
if rid:
    stmts.append(
        f"UPDATE tbl_workflow_rules SET action_label='Forward to System Admin', "
        f"allowed_roles='HoD' WHERE rule_id={rid};"
    )
    print(f"\nEdit rule {rid}: OPEN->UNDER REVIEW -> 'Forward to System Admin', roles=HoD")

# ── EDIT 2: UNDER REVIEW -> ASSIGNED "Assign to Technician", roles -> SysAdmin
rid = find_rule_id("UNDER REVIEW", "ASSIGNED", "Assign")
if rid:
    stmts.append(
        f"UPDATE tbl_workflow_rules SET allowed_roles='SysAdmin' WHERE rule_id={rid};"
    )
    print(f"Edit rule {rid}: UNDER REVIEW->ASSIGNED roles=SysAdmin")

# ── EDIT 3: PARTS NEEDED -> PARTS ORDERED "Authorise & Order Parts"
#    becomes BUDGET APPROVAL -> PARTS ORDERED "Approve Budget", roles HoD
rid = find_rule_id("PARTS NEEDED", "PARTS ORDERED", "Authorise")
if rid:
    stmts.append(
        f"UPDATE tbl_workflow_rules SET from_status='BUDGET APPROVAL', "
        f"action_label='Approve Budget', allowed_roles='HoD' WHERE rule_id={rid};"
    )
    print(f"Edit rule {rid}: -> BUDGET APPROVAL->PARTS ORDERED 'Approve Budget', roles=HoD")

# ── DEACTIVATE: ASSIGNED -> UNDER REPAIR "Start Repair / Service"
rid = find_rule_id("ASSIGNED", "UNDER REPAIR", "Start Repair")
if rid:
    stmts.append(
        f"UPDATE tbl_workflow_rules SET is_active=0 WHERE rule_id={rid};"
    )
    print(f"Deactivate rule {rid}: ASSIGNED->UNDER REPAIR 'Start Repair / Service'")

# ── ADD NEW: PARTS NEEDED -> BUDGET APPROVAL "Forward for Budget Approval", SysAdmin
stmts.append(f"""
    INSERT INTO tbl_workflow_rules
        (module_id, from_status, to_status, action_label, allowed_roles,
         requires_comment, requires_assignee, sort_order, is_active)
    VALUES ({mid}, 'PARTS NEEDED', 'BUDGET APPROVAL', 'Forward for Budget Approval',
            'SysAdmin', 1, 0, 50, 1);
""")
print("Add new rule: PARTS NEEDED -> BUDGET APPROVAL 'Forward for Budget Approval' (SysAdmin)")

# ── ADD NEW: ASSIGNED -> REPAIRED "Mark as Repaired (No Parts)", Technician
stmts.append(f"""
    INSERT INTO tbl_workflow_rules
        (module_id, from_status, to_status, action_label, allowed_roles,
         requires_comment, requires_assignee, sort_order, is_active)
    VALUES ({mid}, 'ASSIGNED', 'REPAIRED', 'Mark as Repaired (No Parts)',
            'Technician', 1, 0, 51, 1);
""")
print("Add new rule: ASSIGNED -> REPAIRED 'Mark as Repaired (No Parts)' (Technician)")

print(f"\n{'='*60}")
print(f"Total statements to run: {len(stmts)}")

if APPLY:
    print("\nApplying changes...")
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        print(f"  {len(errs)} error(s):")
        for e in errs:
            print(f"    - {e['error']['message']}")
    else:
        print(f"  All {len(stmts)} statement(s) applied successfully.")

    # Show final state
    final = query(f"""
        SELECT rule_id, from_status, to_status, action_label, allowed_roles, is_active
        FROM tbl_workflow_rules WHERE module_id={mid} ORDER BY from_status, rule_id
    """)
    print("\nFinal UPS rules:")
    for r in final:
        status = "ACTIVE" if int(r["is_active"]) else "inactive"
        print(f"  [{status}] {r['from_status']} -> {r['to_status']} "
              f"'{r['action_label']}' ({r['allowed_roles']})")
else:
    print("\nRun again with --apply to apply these changes.")
