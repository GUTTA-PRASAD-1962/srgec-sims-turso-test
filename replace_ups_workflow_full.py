"""
replace_ups_workflow_full.py — Replace UPS module's workflow rules entirely
with the new 26-rule, two-path flow (Path 1: no spares, Path 2: with spares
and budget approval/revision/hold/reject), including the new ECE-HoD role
concept (role name used directly in allowed_roles).

This DEACTIVATES all existing UPS rules (does not delete, for history) and
INSERTS the new 26 rules fresh.

Usage (env vars set):
    python replace_ups_workflow_full.py            # dry run
    python replace_ups_workflow_full.py --apply    # apply
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

mod_row = query("SELECT module_id FROM tbl_modules WHERE module_code='UPS'")
if not mod_row:
    raise SystemExit("UPS module not found!")
mid = int(mod_row[0]["module_id"])
print(f"UPS module_id = {mid}\n")

# ── New rule definitions ────────────────────────────────────────────
# (from_status, action_label, to_status, allowed_roles, requires_comment, requires_assignee)
NEW_RULES = [
    # Shared start
    ("OPEN", "Forward to Dept HoD", "DEPT REVIEW", "Lab-IC", 1, 0),
    ("DEPT REVIEW", "Forward to ECE HoD", "ECE REVIEW", "HoD", 1, 0),
    ("ECE REVIEW", "Forward to UPS Coordinator", "COORDINATOR REVIEW", "ECE-HoD", 1, 0),
    ("COORDINATOR REVIEW", "Assign to Technician", "ASSIGNED", "SysAdmin", 1, 1),

    # Path 1 fork - no spares
    ("ASSIGNED", "Mark as Repaired (No Parts)", "REPAIRED", "Technician", 1, 0),

    # Path 2 fork - spares needed
    ("ASSIGNED", "Raise Spare Parts Indent", "PARTS NEEDED", "Technician", 1, 0),
    ("PARTS NEEDED", "Prepare Cost Estimate", "COST ESTIMATED", "SysAdmin", 1, 0),
    ("COST ESTIMATED", "Forward to ECE HoD", "ECE BUDGET REVIEW", "ECE-HoD", 1, 0),
    ("ECE BUDGET REVIEW", "Forward for Budget Approval", "BUDGET REVIEW", "HoD", 1, 0),
    ("BUDGET REVIEW", "Approve Budget", "BUDGET APPROVED", "HoD", 1, 0),
    ("BUDGET REVIEW", "Request Revised Estimate", "COST ESTIMATED", "HoD", 1, 0),
    ("BUDGET REVIEW", "Reject Budget", "REJECTED", "HoD", 1, 0),
    ("BUDGET REVIEW", "Hold for Now", "ON HOLD", "HoD", 1, 0),
    ("ON HOLD", "Resume Review", "BUDGET REVIEW", "HoD", 0, 0),
    ("BUDGET APPROVED", "Raise Purchase Order", "PO RAISED", "SysAdmin", 1, 0),
    ("PO RAISED", "Parts Received — Hand Over", "UNDER REPAIR", "SysAdmin", 1, 0),
    ("UNDER REPAIR", "Fix & Mark Ready", "REPAIRED", "Technician", 1, 0),

    # Shared end (both paths converge at REPAIRED)
    ("REPAIRED", "Verify — Working Correctly", "VERIFIED", "Lab-IC", 1, 0),
    ("VERIFIED", "Forward to Dept HoD", "DEPT ACKNOWLEDGED", "Lab-IC", 1, 0),
    ("DEPT ACKNOWLEDGED", "Forward to ECE HoD", "ECE ACKNOWLEDGED", "HoD", 1, 0),
    ("ECE ACKNOWLEDGED", "Generate Final Report & Close", "FILE CLOSED", "ECE-HoD,SysAdmin", 1, 0),

    # Reject path from the very start
    ("OPEN", "Reject Complaint", "REJECTED", "HoD,SysAdmin", 1, 0),
]

print(f"New rules to insert: {len(NEW_RULES)}\n")
for i, r in enumerate(NEW_RULES, 1):
    print(f"  {i:2d}. {r[0]} -> {r[2]}  '{r[1]}'  ({r[3]})")

stmts = []
# Deactivate ALL existing UPS rules first
stmts.append(f"UPDATE tbl_workflow_rules SET is_active=0 WHERE module_id={mid};")

# Insert new rules
for i, (fs, label, ts, roles, req_c, req_a) in enumerate(NEW_RULES):
    label_e = label.replace("'", "''")
    stmts.append(f"""
        INSERT INTO tbl_workflow_rules
            (module_id, from_status, to_status, action_label, allowed_roles,
             requires_comment, requires_assignee, sort_order, is_active)
        VALUES ({mid}, '{fs}', '{ts}', '{label_e}', '{roles}',
                {req_c}, {req_a}, {i}, 1);
    """)

print(f"\n{'='*60}")
print(f"Total statements: {len(stmts)}")

if APPLY:
    print("\nApplying changes...")
    results = run_pipeline(stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        print(f"  {len(errs)} error(s):")
        for e in errs[:10]:
            print(f"    - {e['error']['message']}")
    else:
        print(f"  All {len(stmts)} statement(s) applied successfully.")
        print(f"\n  UPS now has {len(NEW_RULES)} active rules (old rules deactivated, kept for history).")
else:
    print("\nRun again with --apply to apply these changes.")
