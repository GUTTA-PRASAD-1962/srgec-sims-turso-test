"""
dedupe_workflow_rules_turso.py — Remove duplicate rows from
tbl_workflow_rules in a Turso (SIMS) database, via HTTP API.

Uses ONLY Python stdlib (urllib, json) -- no installs needed.

Usage:
    Set env vars first:
        $env:TURSO_DATABASE_URL = "libsql://srgec-sims-test-....turso.io"
        $env:TURSO_AUTH_TOKEN   = "your-token"
    Then:
        python dedupe_workflow_rules_turso.py            # dry run (report only)
        python dedupe_workflow_rules_turso.py --apply    # delete duplicates
"""
import os, sys, json, urllib.request
from collections import defaultdict

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
print(f"Mode: {'APPLY (delete duplicates)' if APPLY else 'DRY RUN (no changes)'}\n")

rows = query("""
    SELECT rule_id, module_id, from_status, to_status, action_label,
           allowed_roles, requires_comment, requires_assignee, sort_order
    FROM tbl_workflow_rules
    ORDER BY module_id, rule_id
""")

if not rows:
    print("No workflow rules found.")
    sys.exit()

groups = defaultdict(list)
for r in rows:
    key = (r["module_id"], r["from_status"], r["to_status"], r["action_label"])
    groups[key].append(r)

delete_ids = []
for key, group in groups.items():
    if len(group) > 1:
        keep = group[0]
        dupes = group[1:]
        print(f"  DUPLICATE x{len(group)}: module_id={key[0]} {key[1]} -> {key[2]} ({key[3]})")
        print(f"    keeping rule_id={keep['rule_id']}, deleting rule_id(s)="
              f"{[d['rule_id'] for d in dupes]}")
        for d in dupes:
            delete_ids.append(int(d["rule_id"]))

print(f"\n{'='*60}")
print(f"Total rules: {len(rows)} | Unique combinations: {len(groups)}")
print(f"Duplicate rows to delete: {len(delete_ids)}")

if APPLY and delete_ids:
    print("\nDeleting duplicates...")
    del_stmts = [f"DELETE FROM tbl_workflow_rules WHERE rule_id={rid};" for rid in delete_ids]
    results = run_pipeline(del_stmts)
    errs = [r for r in results if r.get("type") == "error"]
    if errs:
        print(f"  {len(errs)} error(s):")
        for e in errs[:5]:
            print(f"    - {e['error']['message']}")
    else:
        print(f"  Deleted {len(delete_ids)} duplicate row(s) successfully.")
elif delete_ids:
    print("\nRun again with --apply to delete these duplicates.")
else:
    print("\nNo duplicates found.")
