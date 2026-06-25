"""
pages/common_inbox.py - Generic Complaint Inbox for ALL modules.
Workflow rules driven entirely from tbl_workflow_rules (no hardcoded statuses).
Usage:
    from pages.common_inbox import show
    show(MODULE_CODE)
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access
from utils.helpers import format_date, save_scan

STATUS_ICON = {
    "OPEN":"🟡","UNDER REVIEW":"🔵","FORWARDED":"🔵","ASSIGNED":"🟠",
    "UNDER REPAIR":"🔧","PARTS NEEDED":"🟣","PARTS ORDERED":"🟤",
    "REPAIRED":"🟢","VERIFIED":"🟢","CLOSED":"✅","FILE CLOSED":"✅","REJECTED":"❌"
}

def _ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

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

def _get_actions(mid, role, status, user=None, call=None):
    rules = [dict(r) for r in _fa("""
        SELECT * FROM tbl_workflow_rules
        WHERE module_id=? AND from_status=? AND is_active=1
        ORDER BY sort_order
    """,(mid, status))]
    call_dept_id = None
    if call:
        raiser = _fo("SELECT dept_id FROM tbl_users WHERE user_id=?",
                      (call.get("raised_by"),))
        if raiser:
            call_dept_id = dict(raiser).get("dept_id")
    user_dept_id = user.get("dept_id") if user else None
    result = {}
    for r in rules:
        allowed = [r2.strip() for r2 in r["allowed_roles"].split(",")]
        if role == "SuperAdmin":
            result[r["action_label"]] = r
            continue
        if role not in allowed:
            continue
        if role == "HoD":
            if call_dept_id is not None and user_dept_id is not None \
               and call_dept_id != user_dept_id:
                continue
        result[r["action_label"]] = r
    return result

def _get_role_statuses(mid, role):
    if role == "SuperAdmin":
        rows = _fa(
            "SELECT DISTINCT from_status FROM tbl_workflow_rules "
            "WHERE module_id=? AND is_active=1",
            (mid,)
        )
        return list(set(dict(r)["from_status"] for r in rows))
    rows = _fa(
        "SELECT DISTINCT from_status FROM tbl_workflow_rules "
        "WHERE module_id=? AND is_active=1 "
        "AND (',' || allowed_roles || ',') LIKE ?",
        (mid, f"%,{role},%")
    )
    return list(set(dict(r)["from_status"] for r in rows))

def _load_calls(mid, statuses=None, dept_id=None, search=None):
    q = """
        SELECT c.*, i.unique_item_id, i.description AS item_desc,
               u.full_name AS raised_by_name, u.dept_id AS dept_id,
               d.dept_name,
               au.full_name AS assignee_name
        FROM tbl_calls c
        LEFT JOIN tbl_items i ON i.item_id = c.item_id
        LEFT JOIN tbl_users u ON u.user_id = c.raised_by
        LEFT JOIN tbl_departments d ON d.dept_id = u.dept_id
        LEFT JOIN tbl_users au ON au.user_id = c.current_assignee
        WHERE c.module_id = ?
    """
    params = [mid]
    if statuses:
        placeholders = ",".join(["?"] * len(statuses))
        q += f" AND c.call_status IN ({placeholders})"
        params.extend(statuses)
    if dept_id:
        q += " AND u.dept_id = ?"
        params.append(dept_id)
    if search:
        q += " AND (c.call_number LIKE ? OR i.unique_item_id LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s])
    q += " ORDER BY c.call_id DESC"
    rows = _fa(q, tuple(params))
    return [dict(r) for r in rows]

def _render_table(calls):
    if not calls:
        st.info("No complaints to display.")
        return
    df = pd.DataFrame([{
        "Call #": c.get("call_number", ""),
        "Asset UID": c.get("unique_item_id", "-"),
        "Department": c.get("dept_name", "-"),
        "Status": c.get("call_status", ""),
        "Raised By": c.get("raised_by_name", "-"),
        "Assignee": c.get("assignee_name", "-"),
    } for c in calls])
    st.dataframe(df, use_container_width=True, hide_index=True)

def _tab_pending(user, role, mod, mid):
    role_statuses = _get_role_statuses(mid, role)
    if not role_statuses:
        st.info(f"No pending actions configured for role '{role}'."); return
    calls = _load_calls(mid, statuses=role_statuses)
    if role == "HoD":
        dept_id = user.get("dept_id")
        if dept_id: calls = [c for c in calls if c.get("dept_id") == dept_id]
    if role == "Technician":
        calls = [c for c in calls if c.get("current_assignee") == user["user_id"]]
    if not calls:
        st.success("No complaints pending your action."); return
    st.markdown(f"**{len(calls)} complaint(s) awaiting your action**")
    _render_table(calls)
    st.divider()
    opts = {f"{c['call_number']} | {c.get('unique_item_id','-')} | {c['call_status']}": c
            for c in calls[:100]}
    sel  = st.selectbox("Select complaint:", list(opts.keys()), key=f"{mid}_pend_sel")
    _call_detail(opts[sel], user, role, mod, mid, ctx="pend")

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
    st.success(f"{item['type_name']} - {item['description']} | {item.get('dept_name','-')} | Status: {item['item_status']}")
    # Check for existing active complaint on this asset
    active_call = _fo("""
        SELECT call_number, call_status FROM tbl_calls
        WHERE item_id=? AND module_id=?
        AND call_status NOT IN ('FILE CLOSED','REJECTED')
    """, (item["item_id"], mid))
    st.write(f"DEBUG active_call: {active_call}")
    if active_call:
        active_call = dict(active_call)
        st.error(
            f"Active complaint {active_call['call_number']} already exists "
            f"for this asset (Status: {active_call['call_status']}). "
            f"Please close or resolve it before raising a new one."
        )
        return
    complaint = st.text_area("Nature of Problem *", key=f"{mid}_raise_cmp", height=100,
                             placeholder="Describe the fault in detail...")
    photo = st.file_uploader("Attach Photo (optional)", type=["jpg","jpeg","png"], key=f"{mid}_raise_photo")
    if st.button("Submit Complaint", type="primary", key=f"{mid}_raise_submit"):
        if not complaint.strip(): st.error("Describe the complaint."); return
        try:
            count   = dict(_fo("SELECT COUNT(*) c FROM tbl_calls WHERE module_id=?",(mid,)) or {"c":0})["c"]
            call_no = f"{mod['module_code']}-CALL-{count+1:04d}"
            photo_path = save_scan(photo, call_no) if photo else None
            _now = _ist().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_conn()
            conn.execute("""
                INSERT INTO tbl_calls (module_id,call_number,item_id,raised_by,dept_id,
                    location_id,complaint_text,call_status,photo_path)
                VALUES (?,?,?,?,?,?,?,'DEPT REVIEW',?)
            """,(mid,call_no,item["item_id"],user["user_id"],item.get("dept_id"),
                 item.get("location_id"),complaint.strip(),photo_path))
            call_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("""
                INSERT INTO tbl_call_workflow (call_id,action_by,action_type,action_comment,from_status,to_status,action_at)
                VALUES (?,?,'Complaint Raised',?,'NONE','OPEN',?)
            """,(call_id,user["user_id"],complaint.strip(),_now))
            conn.execute("""
                INSERT INTO tbl_call_workflow (call_id,action_by,action_type,action_comment,from_status,to_status,action_at)
                VALUES (?,?,'Forward to Dept HoD',?,'OPEN','DEPT REVIEW',?)
            """,(call_id,user["user_id"],complaint.strip(),_now))
            conn.commit(); conn.close()
            st.session_state[f"_raise_msg_{mid}"] = ("s", f"Complaint {call_no} raised.")
            st.rerun()
        except Exception as ex: st.error(f"Failed: {ex}")

def _tab_register(user, role, mod, mid):
    c1,c2 = st.columns(2)
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
    opts = {f"{c['call_number']} | {c.get('unique_item_id','-')} | {c['call_status']}": c
            for c in calls[:100]}
    sel  = st.selectbox("View details:", list(opts.keys()), key=f"{mid}_reg_sel")
    _call_detail(opts[sel], user, role, mod, mid, ctx="reg")

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
    """Read-only view of spare parts indents.
    All workflow actions are via Complaints -> My Inbox -> Pending My Action.
    """
    spare_statuses = [
        "PARTS NEEDED", "COST ESTIMATED", "HEAD-UPS BUDGET REVIEW",
        "BUDGET REVIEW", "BUDGET APPROVED", "ON HOLD", "PO RAISED", "UNDER REPAIR"
    ]
    calls = _load_calls(mid, statuses=spare_statuses)
    if role == "HoD":
        if user.get("dept_id"):
            calls = [c for c in calls if c.get("dept_id") == user.get("dept_id")]
    if not calls:
        st.info("No active spare parts indents."); return
    opts = {f"{c['call_number']} | {c.get('unique_item_id','-')} | {c['call_status']}": c
            for c in calls}
    sel  = st.selectbox("Select complaint:", list(opts.keys()), key=f"{mid}_indp_sel")
    call = opts[sel]
    st.markdown(f"**Call:** `{call['call_number']}` | **Status:** `{call['call_status']}`")
    parts = [dict(r) for r in _fa(
        "SELECT * FROM tbl_spare_indent WHERE call_id=? ORDER BY indent_id",
        (call["call_id"],))]
    if parts:
        df = pd.DataFrame([{
            "Part":        p["description"],
            "Qty":         p["quantity"],
            "Unit Rs.":    p["cost_per_unit"],
            "Total Rs.":   p["total_cost"],
            "Source":      p.get("source", ""),
            "Status":      p["indent_status"],
        } for p in parts])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown(f"**Grand Total: Rs.{sum(p['total_cost'] for p in parts):,.2f}**")
    else:
        st.info("No spare parts items raised for this complaint yet.")
    st.divider()
    st.info(
        "To take action on this complaint, go to Complaints -> My Inbox -> Pending My Action."
    )

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
        "Dept":r.get("dept_name","-"),"Prepared By":r.get("prepared_by",""),
    } for r in rows])
    st.dataframe(df,use_container_width=True,hide_index=True)
    act_tot = sum(r["total_cost"] for r in active if r.get("total_cost"))
    can_tot = sum(r["total_cost"] for r in cancelled if r.get("total_cost"))
    st.markdown(f"**Active Total: Rs.{act_tot:,.2f}** ({len(active)} indent(s))")

def _call_detail(call, user, role, mod, mid, ctx=""):
    status = call["call_status"]
    k      = f"{mid}_{ctx}_{call['call_id']}_{status.replace(' ','_')}"
    st.markdown(f"### Call `{call['call_number']}`")
    c1,c2,c3 = st.columns(3)
    c1.markdown(f"**Asset UID:** `{call.get('unique_item_id','-')}`")
    c1.markdown(f"**Description:** {call.get('item_desc','-')}")
    c2.markdown(f"**Department:** {call.get('dept_name','-')}")
    c2.markdown(f"**Raised by:** {call.get('raised_by_name','')}")
    c3.markdown(f"**Status:** `{STATUS_ICON.get(status,'?')} {status}`")
    if call.get("assignee_name"):
        c3.markdown(f"**Assignee:** {call['assignee_name']}")
    st.info(f"**Problem:** {call.get('complaint_text','')}")
    spare_statuses = [
        "PARTS NEEDED","COST ESTIMATED","HEAD-UPS BUDGET REVIEW",
        "BUDGET REVIEW","BUDGET APPROVED","ON HOLD","PO RAISED","UNDER REPAIR"
    ]
    if status in spare_statuses:
        parts = [dict(r) for r in _fa(
            "SELECT * FROM tbl_spare_indent WHERE call_id=? ORDER BY indent_id",
            (call["call_id"],))]
        if parts:
            st.divider()
            st.markdown("#### Spare Parts Indent")
            df_parts = pd.DataFrame([{
                "Part":        p["description"],
                "Qty":         p["quantity"],
                "Unit Rs.":    p["cost_per_unit"],
                "Total Rs.":   p["total_cost"],
                "Source":      p.get("source", "-"),
                "Status":      p["indent_status"],
            } for p in parts])
            st.dataframe(df_parts, use_container_width=True, hide_index=True)
            st.markdown(f"**Grand Total: Rs.{sum(p['total_cost'] for p in parts):,.2f}**")
    steps = [dict(r) for r in _fa("""
        SELECT wl.*, u.full_name AS actor FROM tbl_call_workflow wl
        LEFT JOIN tbl_users u ON u.user_id=wl.action_by
        WHERE wl.call_id=? ORDER BY wl.action_at ASC
    """,(call["call_id"],))]
    if steps:
        with st.expander("Timeline", expanded=False):
            for s in steps:
                st.markdown(f"**{s['action_at'][:16]}** - **{s['actor']}** "
                            f"`{s['from_status']}` -> `{s['to_status']}`  \n"
                            f"*{s.get('action_comment','') or ''}*")
    if status in ("FILE CLOSED","REJECTED"): return
    st.divider()
    actions = _get_actions(mid, role, status, user=user, call=call)
    if not actions:
        st.info(f"No actions available for **{role}** on status **{status}**."); return
    st.markdown("### Take Action")
    sel_action = st.selectbox("Select Action",list(actions.keys()),key=f"ua_{k}")
    rule       = actions[sel_action]
    st.caption(f"`{status}` -> `{rule['to_status']}`")
    comment_required = bool(rule.get("requires_comment"))
    comment_label = "Comments *" if comment_required else "Comments (optional)"
    comment = st.text_area(comment_label,key=f"uc_{k}",height=70)
    assignee_id = None
    if rule.get("requires_assignee"):
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
            _now = _ist().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                INSERT INTO tbl_call_workflow
                    (call_id,action_by,action_type,action_comment,from_status,to_status,action_at)
                VALUES (?,?,?,?,?,?,?)
            """,(call["call_id"],user["user_id"],sel_action,comment.strip(),status,new_status,_now))
            if new_status == "FILE CLOSED":
                conn.execute("UPDATE tbl_items SET item_status='WORKING' WHERE item_id=?",
                             (call.get("item_id"),))
            conn.commit(); conn.close()
            st.session_state[f"_inbox_msg_{mid}"] = ("s",
                f"{sel_action} - Status: **{new_status}**")
            st.rerun()
        except Exception as ex:
            st.error(f"Action failed: {ex}")

def _update_call_status(call_id, user_id, from_status, action_type, comment):
    _now = _ist().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("""
        INSERT INTO tbl_call_workflow (call_id,action_by,action_type,action_comment,from_status,to_status,action_at)
        VALUES (?,?,?,?,?,?,?)
    """,(call_id,user_id,action_type,comment,from_status,from_status,_now))
    conn.commit(); conn.close()
