"""
pages/call_report.py — Complaint Closure Final Report Generator (SIMS)
Module-agnostic: works for any SIMS module's workflow (UPS, IT, CIVIL, etc.)
by rendering the actual chronological tbl_call_workflow timeline, rather
than hardcoding specific status names.
"""
import streamlit as st
import json, subprocess, os, tempfile, shutil
from pathlib import Path
from db.connection import fetchall as _fa, fetchone as _fo
from utils.auth import current_user


def show(module_code):
    st.title("📄 Complaint Closure Report")
    st.info(
        "Generate the official **Complaint Closure Final Report** for a closed complaint. "
        "All fields are auto-filled from the system. Download as Word (.docx) for printing and signatures."
    )
    user = current_user()
    role = user.get("role") or user.get("role_name") or ""

    mod = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod:
        st.error("Module not found."); return
    mod = dict(mod)
    mid = mod["module_id"]

    # ── Search ────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    search        = c1.text_input("Search by Call Number / Asset UID",
                                   placeholder="e.g. UPS-CALL-0001", key="rpt_search")
    status_filter = c2.selectbox("Filter by Status",
                                  ["FILE CLOSED","REJECTED","All Closed"], key="rpt_status")
    statuses = (["FILE CLOSED"] if status_filter == "FILE CLOSED"
                else ["REJECTED"] if status_filter == "REJECTED"
                else ["FILE CLOSED","REJECTED"])
    ph = ",".join("?" * len(statuses))

    q = f"""
        SELECT c.*, i.unique_item_id, i.description AS item_desc,
               i.item_status AS final_item_status,
               u.full_name AS raised_by_name, u.dept_id AS dept_id,
               d.dept_name,
               au.full_name AS assignee_name
        FROM tbl_calls c
        LEFT JOIN tbl_items i ON i.item_id = c.item_id
        LEFT JOIN tbl_users u ON u.user_id = c.raised_by
        LEFT JOIN tbl_departments d ON d.dept_id = u.dept_id
        LEFT JOIN tbl_users au ON au.user_id = c.current_assignee
        WHERE c.module_id = ? AND c.call_status IN ({ph})
        ORDER BY c.call_id DESC
    """
    try:
        rows = [dict(r) for r in _fa(q, tuple([mid] + statuses))]
    except Exception as ex:
        st.error(f"Cannot load calls: {ex}"); return

    if role not in ("SuperAdmin", "SysAdmin", "Coordinator", "HEAD-UPS"):
        rows = [r for r in rows if r.get("dept_id") == user.get("dept_id")]

    if search.strip():
        s = search.lower()
        rows = [r for r in rows
                if s in (r.get("call_number") or "").lower()
                or s in (r.get("unique_item_id") or "").lower()]

    if not rows:
        st.info("No closed complaints found."); return

    import pandas as pd
    df = pd.DataFrame([{
        "Call #":     r["call_number"],
        "Status":     r["call_status"],
        "Asset UID":  r.get("unique_item_id", "—"),
        "Department": r.get("dept_name", "—"),
        "Raised":     str(r.get("created_at", ""))[:16],
    } for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    opts = {f"{r['call_number']} | {r.get('unique_item_id','')} | {r['call_status']}": r
            for r in rows[:100]}
    sel_label = st.selectbox("Select complaint to generate report:", list(opts.keys()), key="rpt_sel")
    call = opts[sel_label]

    st.markdown(
        f"**Call:** `{call['call_number']}` | "
        f"**Asset:** `{call.get('unique_item_id','')}` | "
        f"**Dept:** {call.get('dept_name','')} | "
        f"**Status:** `{call['call_status']}`"
    )

    if st.button("📄 Generate Closure Report", type="primary", key="rpt_gen"):
        with st.spinner("Generating report..."):
            data   = _build_report_data(call, mod)
            result = _generate_docx(data)
            if result:
                fname = f"Closure_Report_{call['call_number'].replace('/','_')}.docx"
                st.download_button(
                    f"📥 Download — {fname}", result,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="rpt_dl"
                )
                st.success("✅ Report ready. Click above to download and print.")


def _build_report_data(call, mod):
    """
    Module-agnostic: builds report data from the actual chronological
    tbl_call_workflow timeline, with no hardcoded status names. Works
    identically regardless of how many steps or what they're called.
    """
    call_id = call["call_id"]

    try:
        workflow = [dict(r) for r in _fa("""
            SELECT wl.action_type, wl.action_comment, wl.action_at,
                   u.full_name AS actor_name, wl.from_status, wl.to_status
            FROM tbl_call_workflow wl
            LEFT JOIN tbl_users u ON u.user_id = wl.action_by
            WHERE wl.call_id = ? ORDER BY wl.action_at ASC
        """, (call_id,))]
    except Exception:
        workflow = []

    try:
        parts = [dict(r) for r in _fa("""
            SELECT description, quantity, cost_per_unit, total_cost,
                   source, indent_status, authorized_at
            FROM tbl_spare_indent
            WHERE call_id = ?
        """, (call_id,))]
    except Exception:
        parts = []

    def ts(w):  return str(w.get("action_at", ""))[:16] if w else "—"
    def rem(w): return (w.get("action_comment") or "—") if w else "—"
    def act(w): return (w.get("actor_name") or "—") if w else "—"

    # Build the dynamic, chronological step list -- this is what makes
    # the report module-agnostic. Each step is exactly one row in
    # tbl_call_workflow, rendered in order, regardless of module.
    steps = []
    for w in workflow:
        steps.append({
            "step_label": f"{w.get('from_status','—')} → {w.get('to_status','—')}",
            "action":     w.get("action_type", "—"),
            "by":         act(w),
            "on":         ts(w),
            "remarks":    rem(w),
        })

    parts_desc   = "; ".join(
        f"{p['description']} x{p['quantity']} @ Rs.{p['cost_per_unit']}"
        for p in parts) if parts else "Not Required"
    parts_budget = f"Rs.{sum(p['total_cost'] for p in parts):,.2f}" if parts else "—"

    # Downtime: first step (raise) to last step (closure)
    downtime = "—"
    try:
        from datetime import datetime
        if workflow:
            start = datetime.strptime(str(call.get("created_at",""))[:19], "%Y-%m-%d %H:%M:%S")
            end_str = str(workflow[-1].get("action_at",""))[:19]
            if end_str:
                end = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                diff = end - start
                downtime = f"{diff.days} day(s) {diff.seconds//3600} hour(s)"
    except Exception:
        pass

    return {
        "module_name":        mod.get("module_name", ""),
        "call_number":        call.get("call_number", ""),
        "raised_at":          str(call.get("created_at", ""))[:16],
        "unique_item_id":     call.get("unique_item_id", ""),
        "item_desc":          call.get("item_desc", ""),
        "dept_name":          call.get("dept_name", ""),
        "complaint_text":     call.get("complaint_text", ""),
        "raised_by_name":     call.get("raised_by_name", ""),
        "final_status":       call.get("call_status", ""),
        "final_item_status":  call.get("final_item_status", "WORKING"),
        "parts_description":  parts_desc,
        "parts_budget":       parts_budget,
        "downtime":           downtime,
        "steps":              steps,   # dynamic timeline -- the core of this report
    }


def _generate_docx(data):
    tmp_dir    = Path(tempfile.gettempdir())
    tmp_data   = tmp_dir / "sims_report_data.json"
    tmp_out    = tmp_dir / "sims_complaint_report.docx"
    tmp_script = tmp_dir / "sims_generate_report_run.js"

    base   = Path(__file__).parent.parent
    script = base / "generate_report.js"
    if not script.exists():
        st.error(f"generate_report.js not found in {base}"); return None

    js = script.read_text(encoding="utf-8")
    js = js.replace(
        "fs.readFileSync('/tmp/sims_report_data.json'",
        f"fs.readFileSync({json.dumps(str(tmp_data))}"
    ).replace(
        "fs.writeFileSync('/tmp/sims_complaint_report.docx'",
        f"fs.writeFileSync({json.dumps(str(tmp_out))}"
    )
    tmp_script.write_text(js, encoding="utf-8")

    src_modules = base / "node_modules"
    dst_modules = tmp_dir / "node_modules"
    if src_modules.exists() and not dst_modules.exists():
        try: shutil.copytree(str(src_modules), str(dst_modules))
        except Exception: pass

    tmp_data.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    node = shutil.which("node")
    if not node:
        for candidate in [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
        ]:
            if Path(candidate).exists():
                node = candidate; break
    if not node:
        st.error("Node.js not found. Install from nodejs.org and restart Streamlit, "
                  "or ensure Node.js buildpack is configured on Render.")
        return None

    try:
        result = subprocess.run(
            [node, str(tmp_script)],
            capture_output=True, text=True, timeout=30,
            cwd=str(base)
        )
        if result.returncode == 0 and tmp_out.exists():
            return tmp_out.read_bytes()
        st.error(f"Generation error: {result.stderr[:400] or result.stdout[:400]}")
        return None
    except Exception as ex:
        st.error(f"Failed: {ex}")
        return None
