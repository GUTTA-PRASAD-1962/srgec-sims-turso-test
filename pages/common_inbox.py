"""
pages/common_inbox.py — Generic Complaint Inbox for ALL modules.
Workflow rules driven entirely from tbl_workflow_rules (no hardcoded statuses).

Usage:
    from pages.common_inbox import show
    show(MODULE_CODE)
"""
import streamlit as st
import pandas as pd
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access
from utils.helpers import format_date, save_scan


STATUS_ICON = {
    "OPEN":"🟡","UNDER REVIEW":"🔵","FORWARDED":"🔵","ASSIGNED":"🟠",
    "UNDER REPAIR":"🔧","PARTS NEEDED":"🟣","PARTS ORDERED":"🟤",
    "REPAIRED":"🟢","VERIFIED":"🟢","CLOSED":"✅","FILE CLOSED":"✅","REJECTED":"❌"
}


def show(module_code):
    role = require_module_access(module_code)
    user = current_user()
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: st.error("Module not found."); return
    mod  = dict(mod)
    mid  = mod["module_id"]

    if st.session_state.get(f"_inbox_msg_{mid}"):
        t, m = st.session_state.pop(f"_inbox_msg_{mid}")
        (st.success if t=="s" else st.error)(m)

    tab1,tab2,tab3,tab4 = st.tabs([
        "Pending My Action",
        "Raise Complaint",
        "Complaint Register",
        "Spare Parts Indent",
    ])
    with tab1: _tab_pending(user, role, mod, mid)
    with tab2: _tab_raise(user, role, mod, mid)
    with tab3: _tab_register(user, role, mod, mid)
    with tab4: _tab_spare_indent(user, role, mod, mid)


# ── helpers ──────────────────────────────────────────────────────
def _get_actions(mid, role, status):
    """Get available actions for role+status from DB rules."""
    rules = [dict(r) for r in _fa("""
        SELECT * FROM tbl_workflow_rules
        WHERE module_id=? AND from_status=? AND is_active=1
        ORDER BY sort_order
    """,(mid, status))]
    return {r["action_label"]: r for r in rules
            if any(r2.strip() == role for r2 in r["allowed_roles"].split(","))
            or role == "SuperAdmin"}


def _get_role_statuses(mid, role):
    if role == "SuperAdmin":
        rows = _fa("SELECT DISTINCT from_status FROM tbl_workflow_rules WHERE module_id=? AND is_active=1",(mid,))
        return list(set(dict(r)["from_status"] for r in rows))
    rows = _fa("""
        SELECT DISTINCT from_status FROM tbl_workflow_rules
        WHERE module_id=? AND is_active=1
          AND (',' || allowed_roles || ',') LIKE ?
    """,(mid, f"%,{role},%"))
    if not rows:
        rows = _fa("""
            SELECT DISTINCT from_status FROM tbl_workflow_rules
            WHERE module_id=? AND is_active=1 AND allowed_roles LIKE ?
        """,(mid, f"%{role}%"))
    return list(set(dict(r)["from_status"] for r in rows))


def _render_table(calls):
    rows = [{
        "Call #":     c["call_number"],
        "Status":     f"{STATUS_ICON.get(c['call_status'],'⚪')} {c['call_status']}",
        "Asset UID":  c.get("unique_item_id","—"),
        "Dept":       c.get("dept_name","—"),
        "Problem":    (c.get("complaint_text","") or "")[:50],
        "Raised By":  c.get("raised_by_name",""),
        "Assignee":   c.get("assignee_name","") or "—",
        "Raised":     str(c.get("created_at",""))[:16],
    } for c in calls]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _load_calls(mid, statuses=None, dept_id=None, assignee_id=None, search=None, limit=200):
    q = """
        SELECT c.*, i.unique_item_id, i.description AS item_desc,
               d.dept_name, l.location_name,
               u.full_name AS raised_by_name,
               u2.full_name AS assignee_name
        FROM tbl_calls c
        LEFT JOIN tbl_items i ON i.item_id=c.item_id
        LEFT JOIN tbl_departments d ON d.dept_id=c.dept_id
        LEFT JOIN tbl_locations l ON l.location_id=c.location_id
        JOIN tbl_users u ON u.user_id=c.raised_by
        LEFT JOIN tbl_users u2 ON u2.user_id=c.current_assignee
        WHERE c.module_id=?
    """
    params = [mid]
    if statuses:
        ph = ",".join("?" * len(statuses))
        q += f" AND c.call_status IN ({ph})"
        params.extend(statuses)
    if dept_id:
        q += " AND c.dept_id=?"; params.append(dept_id)
    if assignee_id:
        q += " AND c.current_assignee=?"; params.append(assignee_id)
    if search:
        q += " AND (c.call_number LIKE ? OR i.unique_item_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    q += f" ORDER BY c.created_at DESC LIMIT {limit}"
    return [dict(r) for r in _fa(q, params)]


# ══ TAB 1 — PENDING MY ACTION ════════════════════════════════════
def _tab_pending(user, role, mod, mid):
    role_statuses = _get_role_statuses(mid, role)
    if not role_statuses:
        st.info(f"No pending actions configured for role '{role}'."); return

    calls = _load_calls(mid, statuses=role_statuses)

    # Filter by dept for non-admins
    if role not in ("SuperAdmin","SysAdmin","Coordinator"):
        dept_id = user.get("dept_id")
        if dept_id: calls = [c for c in calls if c.get("dept_id") == dept_id]
    if role == "Technician":
        calls = [c for c in calls if c.get("current_assignee") == user["user_id"]]

    if not calls:
        st.success("No complaints pending your action."); return

    st.markdown(f"**{len(calls)} complaint(s) awaiting your action**")
    _render_table(calls)
    st.divider()

    opts = {f"{c['call_number']} | {c.get('unique_item_id','—')} | {c['call_status']}": c
            for c in calls[:100]}
    sel  = st.selectbox("Select complaint:", list(opts.keys()), key=f"{mid}_pend_sel")
    _call_detail(opts[sel], user, role, mod, mid, ctx="pend")


# ══ TAB 2 — RAISE COMPLAINT ══════════════════════════════════════
def _tab_raise(user, role, mod, mid):
    st.subheader("Raise New Complaint")

    if st.session_state.get(f"_raise_msg_{mid}"):
        t,m = st.session_state.pop(f"_raise_msg_{mid}")
        (st.success if t=="s" else st.error)(m)

    uid_input = st.text_input("Asset UID *",
                              placeholder=f"e.g. {mod['module_code']}_CSE_06_2026_UPS_00001",
                              key=f"{mid}_raise_uid")
    if not uid_input.strip():
        st.info("Enter the Asset UID to raise a complaint."); return

    item = _fo("""
        SELECT i.*, it.type_name, d.dept_name, l.location_name
        FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        LEFT JOIN tbl_departments d ON d.dept_id=i.dept_id
        LEFT JOIN tbl_locations l ON l.location_id=i.location_id
        WHERE i.unique_item_id=? AND i.module_id=?
    """, (uid_input.strip(), mid))

    if not item: st.error("Asset not found in this module."); return
    item = dict(item)
    st.success(f"{item['type_name']} — {item['description']} | {item.get('dept_name','—')} | Status: `{item['item_status']}`")

    complaint = st.text_area("Nature of Problem *", key=f"{mid}_raise_cmp", height=100,
                             placeholder="Describe the fault in detail...")
    photo = st.file_uploader("Attach Photo (optional)", type=["jpg","jpeg","png"], key=f"{mid}_raise_photo")

    if st.button("Submit Complaint", type="primary", key=f"{mid}_raise_submit"):
        if not complaint.strip(): st.error("Describe the complaint."); return
        try:
            count   = dict(_fo("SELECT COUNT(*) c FROM tbl_calls WHERE module_id=?",(mid,)) or {"c":0})["c"]
            call_no = f"{mod['module_code']}-CALL-{count+1:04d}"
            photo_path = save_scan(photo, call_no) if photo else None
            conn = get_conn()
            conn.execute("""
                INSERT INTO tbl_calls (module_id,call_number,item_id,raised_by,dept_id,
                    location_id,complaint_text,call_status,photo_path)
                VALUES (?,?,?,?,?,?,?,'OPEN',?)
            """,(mid,call_no,item["item_id"],user["user_id"],item.get("dept_id"),
                 item.get("location_id"),complaint.strip(),photo_path))
            call_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("""
                INSERT INTO tbl_call_workflow (call_id,action_by,action_type,action_comment,from_status,to_status)
                VALUES (?,?,'Complaint Raised',?,'NONE','OPEN')
            """,(call_id,user["user_id"],complaint.strip()))
            conn.commit(); conn.close()
            st.session_state[f"_raise_msg_{mid}"] = ("s", f"Complaint {call_no} raised.")
            st.rerun()
        except Exception as ex: st.error(f"Failed: {ex}")


# ══ TAB 3 — COMPLAINT REGISTER ═══════════════════════════════════
def _tab_register(user, role, mod, mid):
    c1,c2 = st.columns(2)
    # Build status list from workflow rules + static closed statuses
    all_statuses = list(set(
        dict(r)["from_status"] for r in _fa(
            "SELECT DISTINCT from_status FROM tbl_workflow_rules WHERE module_id=?",(mid,))
    )) + ["FILE CLOSED","REJECTED"]
    status_f = c1.selectbox("Status",["All"]+sorted(set(all_statuses)),key=f"{mid}_reg_status")
    search   = c2.text_input("Search Call # / Asset UID",key=f"{mid}_reg_search")

    statuses = None if status_f=="All" else [status_f]
    dept_id  = user.get("dept_id") if role not in ("SuperAdmin","SysAdmin","Coordinator") else None
    calls    = _load_calls(mid, statuses=statuses, dept_id=dept_id,
                           search=search.strip() or None)

    st.caption(f"{len(calls)} complaint(s)")
    if not calls: st.info("None found."); return
    _render_table(calls)
    st.divider()

    opts = {f"{c['call_number']} | {c.get('unique_item_id','—')} | {c['call_status']}": c
            for c in calls[:100]}
    sel  = st.selectbox("View details:", list(opts.keys()), key=f"{mid}_reg_sel")
    _call_detail(opts[sel], user, role, mod, mid, ctx="reg")


# ══ TAB 4 — SPARE PARTS INDENT ═══════════════════════════════════
def _tab_spare_indent(user, role, mod, mid):
    st.subheader("Spare Parts Indent")

    if st.session_state.get(f"_indent_msg_{mid}"):
        t,m = st.session_state.pop(f"_indent_msg_{mid}")
        (st.success if t=="s" else st.error)(m)

    sub1,sub2,sub3 = st.tabs(["Raise Indent","Pending Action","All Indents"])

    with sub1: _indent_raise(user, role, mod, mid)
    with sub2: _indent_pending(user, role, mod, mid)
    with sub3: _indent_all(user, role, mod, mid)


def _indent_raise(user, role, mod, mid):
    call_no = st.text_input("Call Number *",key=f"{mid}_ind_cno",
                            placeholder=f"e.g. {mod['module_code']}-CALL-0001")
    if not call_no.strip(): st.info("Enter call number."); return
    call = _fo("SELECT * FROM tbl_calls WHERE call_number=? AND module_id=?",(call_no.strip(),mid))
    if not call: st.error("Call not found."); return
    call = dict(call)
    st.success(f"Call: **{call['call_number']}** | Status: `{call['call_status']}`")
    existing = [dict(r) for r in _fa("SELECT * FROM tbl_spare_indent WHERE call_id=?",(call["call_id"],))]
    if existing:
        df = pd.DataFrame([{"Part":p["description"],"Qty":p["quantity"],
                            "Cost Rs.":p["cost_per_unit"],"Status":p["indent_status"]} for p in existing])
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.info("Indent already raised."); return
    n = st.number_input("Number of parts",min_value=1,max_value=20,value=1,key=f"{mid}_ind_n")
    items = []
    for i in range(int(n)):
        st.markdown(f"**Part {i+1}**")
        p1,p2,p3,p4 = st.columns(4)
        desc=p1.text_input("Part *",key=f"{mid}_ind_d_{i}")
        qty=p2.number_input("Qty",min_value=1,value=1,key=f"{mid}_ind_q_{i}")
        cost=p3.number_input("Unit Cost Rs.",min_value=0.0,step=10.0,key=f"{mid}_ind_c_{i}")
        src=p4.text_input("Source/Vendor",key=f"{mid}_ind_s_{i}")
        items.append({"desc":desc,"qty":qty,"cost":cost,"src":src})
    total = sum(it["qty"]*it["cost"] for it in items)
    st.markdown(f"**Est. Total: Rs.{total:,.2f}**")
    if st.button("Submit Indent",type="primary",key=f"{mid}_ind_submit"):
        errs = [f"Part {i+1}: name required" for i,it in enumerate(items) if not it["desc"].strip()]
        if errs:
            for e in errs: st.error(e); return
        try:
            conn = get_conn()
            for it in items:
                conn.execute("""
                    INSERT INTO tbl_spare_indent (module_id,call_id,prepared_by,description,
                        quantity,cost_per_unit,total_cost,source)
                    VALUES (?,?,?,?,?,?,?,?)
                """,(mid,call["call_id"],user["user_id"],it["desc"].strip(),
                     it["qty"],it["cost"],it["qty"]*it["cost"],it["src"]))
            conn.commit(); conn.close()
            st.session_state[f"_indent_msg_{mid}"] = ("s","Indent submitted.")
            st.rerun()
        except Exception as ex: st.error(f"Failed: {ex}")


def _indent_pending(user, role, mod, mid):
    if role in ("SuperAdmin","SysAdmin","Coordinator"):
        statuses = ["PARTS NEEDED","PARTS ORDERED"]
    elif role in ("HoD",):
        statuses = ["PARTS NEEDED"]
    else:
        st.info("No parts procurement actions for your role."); return

    calls = _load_calls(mid, statuses=statuses)
    if role not in ("SuperAdmin","SysAdmin","Coordinator") and user.get("dept_id"):
        calls = [c for c in calls if c.get("dept_id")==user["dept_id"]]
    if not calls: st.success("No indents pending."); return

    opts = {f"{c['call_number']} | {c.get('unique_item_id','—')} | {c['call_status']}": c for c in calls}
    sel  = st.selectbox("Select:",list(opts.keys()),key=f"{mid}_indp_sel")
    call = opts[sel]

    parts = [dict(r) for r in _fa("SELECT * FROM tbl_spare_indent WHERE call_id=? ORDER BY indent_id",(call["call_id"],))]
    if parts:
        df = pd.DataFrame([{"Part":p["description"],"Qty":p["quantity"],
                            "Unit Rs.":p["cost_per_unit"],"Total Rs.":p["total_cost"],
                            "Source":p.get("source",""),"Status":p["indent_status"]} for p in parts])
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.markdown(f"**Grand Total: Rs.{sum(p['total_cost'] for p in parts):,.2f}**")
    st.divider()

    # Actions based on call status
    status = call["call_status"]
    if role in ("SuperAdmin","SysAdmin") and status=="PARTS NEEDED":
        note = st.text_area("Budget note for HoD *",key=f"{mid}_indp_note",height=80)
        if st.button("Forward to HoD",type="primary",key=f"{mid}_indp_fwd"):
            if not note.strip(): st.error("Note required."); return
            try:
                _update_call_status(call["call_id"],user["user_id"],"PARTS NEEDED",
                                    "Budget Proposal Forwarded to HoD",note.strip())
                st.session_state[f"_indent_msg_{mid}"] = ("s","Forwarded to HoD.")
                st.rerun()
            except Exception as ex: st.error(str(ex))

    elif role in ("HoD",) and status=="PARTS NEEDED":
        dec = st.radio("Decision",[
            "Budget Available — Approve",
            "Budget Not Available — Reject"
        ],key=f"{mid}_indp_dec")
        rem = st.text_area("Remarks *",key=f"{mid}_indp_rem",height=60)
        if st.button("Submit Decision",type="primary",key=f"{mid}_indp_sub"):
            if not rem.strip(): st.error("Remarks required."); return
            if "Approve" in dec:
                new_s = "PARTS ORDERED"
                try:
                    conn=get_conn()
                    conn.execute("UPDATE tbl_spare_indent SET indent_status='AUTHORIZED',authorized_by=?,authorized_at=datetime('now','localtime') WHERE call_id=?",
                                 (user["user_id"],call["call_id"]))
                    conn.commit(); conn.close()
                    _update_call_status(call["call_id"],user["user_id"],"PARTS NEEDED",
                                        "Budget Approved by HoD",rem.strip())
                    conn=get_conn()
                    conn.execute("UPDATE tbl_calls SET call_status='PARTS ORDERED' WHERE call_id=?",(call["call_id"],))
                    conn.commit(); conn.close()
                    st.session_state[f"_indent_msg_{mid}"] = ("s","Budget approved.")
                    st.rerun()
                except Exception as ex: st.error(str(ex))
            else:
                try:
                    conn=get_conn()
                    conn.execute("UPDATE tbl_spare_indent SET indent_status='CANCELLED' WHERE call_id=?",(call["call_id"],))
                    conn.commit(); conn.close()
                    _update_call_status(call["call_id"],user["user_id"],"PARTS NEEDED",
                                        "Budget Rejected",rem.strip())
                    conn=get_conn()
                    conn.execute("UPDATE tbl_calls SET call_status='ASSIGNED' WHERE call_id=?",(call["call_id"],))
                    conn.commit(); conn.close()
                    st.session_state[f"_indent_msg_{mid}"] = ("s","Rejected.")
                    st.rerun()
                except Exception as ex: st.error(str(ex))

    elif role in ("SuperAdmin","SysAdmin") and status=="PARTS ORDERED":
        recv = st.text_area("Receiving note *",key=f"{mid}_indp_recv",height=60)
        if st.button("Parts Received — Hand Over",type="primary",key=f"{mid}_indp_recv_btn"):
            if not recv.strip(): st.error("Note required."); return
            try:
                conn=get_conn()
                conn.execute("UPDATE tbl_spare_indent SET indent_status='PROCURED',procured_at=datetime('now','localtime') WHERE call_id=?",(call["call_id"],))
                conn.execute("UPDATE tbl_calls SET call_status='UNDER REPAIR' WHERE call_id=?",(call["call_id"],))
                conn.commit(); conn.close()
                _update_call_status(call["call_id"],user["user_id"],"PARTS ORDERED",
                                    "Parts Received — Hand Over",recv.strip())
                st.session_state[f"_indent_msg_{mid}"] = ("s","Parts handed over. Status → UNDER REPAIR.")
                st.rerun()
            except Exception as ex: st.error(str(ex))


def _indent_all(user, role, mod, mid):
    rows = [dict(r) for r in _fa("""
        SELECT si.indent_id, si.description, si.quantity, si.cost_per_unit, si.total_cost,
               si.indent_status, si.source, cr.call_number, cr.call_status,
               i.unique_item_id, d.dept_name, u.full_name AS prepared_by
        FROM tbl_spare_indent si
        JOIN tbl_calls cr ON cr.call_id=si.call_id
        LEFT JOIN tbl_items i ON i.item_id=cr.item_id
        LEFT JOIN tbl_departments d ON d.dept_id=cr.dept_id
        LEFT JOIN tbl_users u ON u.user_id=si.prepared_by
        WHERE si.module_id=? ORDER BY si.indent_id DESC
    """,(mid,))]
    if not rows: st.info("No indents."); return
    active = [r for r in rows if r["indent_status"]!="CANCELLED"]
    cancelled = [r for r in rows if r["indent_status"]=="CANCELLED"]
    df = pd.DataFrame([{
        "ID":r["indent_id"],"Call #":r["call_number"],"Part":r["description"],
        "Qty":r["quantity"],"Total Rs.":r["total_cost"],"Status":r["indent_status"],
        "Dept":r.get("dept_name","—"),"Prepared By":r.get("prepared_by",""),
    } for r in rows])
    st.dataframe(df,use_container_width=True,hide_index=True)
    act_tot = sum(r["total_cost"] for r in active if r.get("total_cost"))
    can_tot = sum(r["total_cost"] for r in cancelled if r.get("total_cost"))
    st.markdown(f"**Active Total: Rs.{act_tot:,.2f}** ({len(active)} indent(s))  \n"
                f"*Cancelled: Rs.{can_tot:,.2f} ({len(cancelled)}) — excluded*")


# ══ CALL DETAIL ═══════════════════════════════════════════════════
def _call_detail(call, user, role, mod, mid, ctx=""):
    status = call["call_status"]
    k      = f"{mid}_{ctx}_{call['call_id']}_{status.replace(' ','_')}"

    st.markdown(f"### Call `{call['call_number']}`")
    c1,c2,c3 = st.columns(3)
    c1.markdown(f"**Asset UID:** `{call.get('unique_item_id','—')}`")
    c1.markdown(f"**Description:** {call.get('item_desc','—')}")
    c2.markdown(f"**Department:** {call.get('dept_name','—')}")
    c2.markdown(f"**Raised by:** {call.get('raised_by_name','')}")
    c3.markdown(f"**Status:** `{STATUS_ICON.get(status,'⚪')} {status}`")
    if call.get("assignee_name"):
        c3.markdown(f"**Assignee:** {call['assignee_name']}")
    st.info(f"**Problem:** {call.get('complaint_text','')}")

    # Timeline
    steps = [dict(r) for r in _fa("""
        SELECT wl.*, u.full_name AS actor FROM tbl_call_workflow wl
        LEFT JOIN tbl_users u ON u.user_id=wl.action_by
        WHERE wl.call_id=? ORDER BY wl.action_at ASC
    """,(call["call_id"],))]
    if steps:
        with st.expander("Timeline", expanded=False):
            for s in steps:
                st.markdown(f"**{s['action_at'][:16]}** — **{s['actor']}** "
                            f"`{s['from_status']}` → `{s['to_status']}`  \n"
                            f"*{s.get('action_comment','') or ''}*")

    if status in ("FILE CLOSED","REJECTED"): return
    st.divider()

    # Get available actions
    actions = _get_actions(mid, role, status)
    if not actions:
        st.info(f"No actions available for **{role}** on status **{status}**."); return

    st.markdown("### Take Action")
    sel_action = st.selectbox("Select Action",list(actions.keys()),key=f"ua_{k}")
    rule       = actions[sel_action]
    st.caption(f"`{status}` → `{rule['to_status']}`")
    comment_required = bool(rule.get("requires_comment"))
    comment_label = "Comments *" if comment_required else "Comments (optional)"
    comment = st.text_area(comment_label,key=f"uc_{k}",height=70)

    assignee_id = None
    if rule.get("requires_assignee"):
        # Get technicians for this module
        techs = [dict(r) for r in _fa("""
            SELECT u.user_id, u.full_name FROM tbl_users u
            JOIN tbl_user_module_access a ON a.user_id=u.user_id
            JOIN tbl_modules m ON m.module_id=a.module_id
            WHERE m.module_code=? AND a.role_name='Technician' AND u.is_active=1
        """,(mod["module_code"],))]
        if techs:
            t_opts = {t["full_name"]: t["user_id"] for t in techs}
            pick   = st.selectbox("Assign Technician *",list(t_opts.keys()),key=f"ut_{k}")
            assignee_id = t_opts[pick]

    if st.button(f"{sel_action}",type="primary",key=f"usub_{k}"):
        if comment_required and not comment.strip():
            st.error("Comments required for this action.")
            return
        try:
            conn = get_conn()
            new_status = rule["to_status"]
            conn.execute("""
                UPDATE tbl_calls SET call_status=?,
                    current_assignee=COALESCE(?,current_assignee)
                WHERE call_id=?
            """,(new_status,assignee_id,call["call_id"]))
            conn.execute("""
                INSERT INTO tbl_call_workflow
                    (call_id,action_by,action_type,action_comment,from_status,to_status)
                VALUES (?,?,?,?,?,?)
            """,(call["call_id"],user["user_id"],sel_action,comment.strip(),status,new_status))
            if new_status == "FILE CLOSED":
                conn.execute("UPDATE tbl_items SET item_status='WORKING' WHERE item_id=?",
                             (call.get("item_id"),))
            conn.commit(); conn.close()
            st.session_state[f"_inbox_msg_{mid}"] = ("s",
                f"{sel_action} — Status: **{new_status}**")
            st.rerun()
        except Exception as ex:
            st.error(f"Action failed: {ex}")


def _update_call_status(call_id, user_id, from_status, action_type, comment):
    conn = get_conn()
    conn.execute("""
        INSERT INTO tbl_call_workflow (call_id,action_by,action_type,action_comment,from_status,to_status)
        VALUES (?,?,?,?,?,?)
    """,(call_id,user_id,action_type,comment,from_status,from_status))
    conn.commit(); conn.close()
