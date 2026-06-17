"""
check_ups_rules.py — List current UPS workflow rules (active only) so we
can verify which of the intended 21 new rules are actually present.
"""
import os, sys, json, urllib.request

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("ERROR: Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN first.")

host = TURSO_URL.replace("libsql://", "").replace("https://", "")
API_URL = f"https://{host}/v2/pipeline"


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


mod_row = query("SELECT module_id FROM tbl_modules WHERE module_code='UPS'")
mid = int(mod_row[0]["module_id"])
print(f"UPS module_id = {mid}\n")

rules = query(f"""
    SELECT rule_id, from_status, to_status, action_label, allowed_roles, is_active
    FROM tbl_workflow_rules WHERE module_id={mid}
    ORDER BY is_active DESC, sort_order
""")

active = [r for r in rules if int(r["is_active"])]
inactive = [r for r in rules if not int(r["is_active"])]

print(f"ACTIVE rules ({len(active)}):")
for r in active:
    print(f"  [{r['rule_id']}] {r['from_status']} -> {r['to_status']}  '{r['action_label']}'  ({r['allowed_roles']})")

print(f"\nINACTIVE rules ({len(inactive)}):")
for r in inactive:
    print(f"  [{r['rule_id']}] {r['from_status']} -> {r['to_status']}  '{r['action_label']}'  ({r['allowed_roles']})")
