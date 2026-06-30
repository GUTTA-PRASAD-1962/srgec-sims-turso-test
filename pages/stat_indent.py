"""
pages/stat_indent.py — Stationery Indent Management for SRGEC-SIMS
Workflow: Junior Assistant raises indent (table form) -> HoD -> Office Superintendent
-> Stationery In-charge (stock check) -> OS (remarks) -> Principal (approve/reduce/reject)
-> Junior Assistant confirms -> OS informs -> Stationery In-charge issues -> JA acknowledges
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db.connection import fetchall as _fa, fetchone as _fo, get_conn, execute as _ex
from utils.auth import current_user, require_module_access


def _ist():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")


def _generate_indent_number(dept_code, mid):
    """Generate per-department sequential indent number: STAT_ECE_IND_0001"""
    count = dict(_fo(
        "SELECT COUNT(*) c FROM tbl_stat_indents WHERE indent_number LIKE ?",
        (f"STAT_{dept_code}_IND_%",)
    ) or {"c": 0})["c"]
    return f"STAT_{dept_code}_IND_{count+1:04d}"


def show(module_code):
    role = require_module_access(module_code)
    user = current_user()
    mod = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod:
        st.error("Module not found.")
        return
    mod = dict(mod)
    mid = mod["module_id"]

    tab1, tab2, tab3 = st.tabs(["Raise Indent", "My Inbox", "Indent Register"])
    with tab1:
        _tab_raise(user, role, mod, mid)
    with tab2:
        _tab_pending(user, role, mod, mid)
    with tab3:
        _tab_register(user, role, mod, mid)


# ───────────────────────────── RAISE INDENT ─────────────────────────────
def _tab_raise(user, role, mod, mid):
    st.subheader("Raise Stationery Indent")

    if role != "JuniorAssistant" and role not in ("SuperAdmin",):
        st.info("Only Junior Assistant can raise a new indent.")
        return

    if st.session_state.get(f"_indent_msg_{mid}"):
        t, m = st.session_state.pop(f"_indent_msg_{mid}")
        (st.success if t == "s" else st.error)(m)

    dept_id = user.get("dept_id")
    if not dept_id and role != "SuperAdmin":
        st.warning("Your account has no department assigned.")
        return

    items = [dict(r) for r in _fa(
        "SELECT * FROM tbl_stat_items WHERE module_id=? AND is_active=1 ORDER BY item_name",
        (mid,)
    )]
    if not items:
        st.info("No stationery items configured. Contact SuperAdmin.")
        return

    st.caption("Check the items you need, enter quantity, and add remarks if needed.")

    with st.form(f"{mid}_raise_indent_form"):
        selections = []
        for it in items:
            c1, c2, c3, c4, c5 = st.columns([0.5, 2.5, 2, 1, 2])
            checked = c1.checkbox("", key=f"chk_{it['item_id']}")
            c2.markdown(f"**{it['item_name']}**")
            c3.markdown(f"_{it.get('specification','-')}_")
            qty = c4.number_input("Qty", min_value=0.0, step=1.0,
                                   key=f"qty_{it['item_id']}", label_visibility="collapsed")
            remarks = c5.text_input("Remarks", key=f"rem_{it['item_id']}",
                                     label_visibility="collapsed", placeholder="remarks (optional)")
            selections.append({
                "item_id": it["item_id"],
                "item_name": it["item_name"],
                "unit": it["unit_of_measure"],
                "checked": checked,
                "qty": qty,
                "remarks": remarks
            })

        submitted = st.form_submit_button("Submit Indent", type="primary", use_container_width=True)

    if submitted:
        selected = [s for s in selections if s["checked"] and s["qty"] > 0]
        if not selected:
            st.error("Select at least one item with a quantity greater than 0.")
            return
        try:
            depts = _fo("SELECT dept_code FROM tbl_departments WHERE dept_id=?", (dept_id,))
            dept_code = dict(depts)["dept_code"] if depts else "GEN"
            indent_no = _generate_indent_number(dept_code, mid)

            conn = get_conn()
            cur = conn.execute("""
                INSERT INTO tbl_stat_indents (indent_number, dept_id, raised_by, indent_status, created_at)
                VALUES (?, ?, ?, 'DEPT REVIEW', ?)
            """, (indent_no, dept_id, user["user_id"], _ist()))
            indent_id = cur.lastrowid if hasattr(cur, "lastrowid") else \
                conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            for s in selected:
                conn.execute("""
                    INSERT INTO tbl_stat_indent_items
                        (indent_id, item_id, requested_qty, unit, remarks, line_status)
                    VALUES (?, ?, ?, ?, ?, 'PENDING')
                """, (indent_id, s["item_id"], s["qty"], s["unit"], s["remarks"]))

            conn.execute("""
                INSERT INTO tbl_stat_indent_workflow
                    (indent_id, action_by, action_type, action_comment, from_status, to_status, action_at)
                VALUES (?, ?, 'Indent Raised', ?, 'NONE', 'DEPT REVIEW', ?)
            """, (indent_id, user["user_id"], f"{len(selected)} item(s) requested", _ist()))

            conn.commit()
            conn.close()

            st.session_state[f"_indent_msg_{mid}"] = (
                "s", f"Indent {indent_no} submitted with {len(selected)} item(s)."
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Failed to submit indent: {ex}")


# ───────────────────────────── MY INBOX (PENDING ACTIONS) ─────────────────────────────
def _get_role_statuses(role):
    """Map role to the indent statuses they need to act on."""
    mapping = {
        "HoD": ["DEPT REVIEW"],
        "OS": ["OS REVIEW", "PRINCIPAL REVIEW"],
        "StatIncharge": ["STOCK CHECK", "ISSUE PENDING"],
        "Principal": ["PRINCIPAL DECISION"],
        "JuniorAssistant": ["JA CONFIRMATION", "RECEIVED PENDING"],
        "SuperAdmin": ["DEPT REVIEW", "OS REVIEW", "STOCK CHECK", "PRINCIPAL REVIEW",
                       "PRINCIPAL DECISION", "JA CONFIRMATION", "ISSUE PENDING", "RECEIVED PENDING"],
    }
    return mapping.get(role, [])


def _load_indents(mid, statuses=None, dept_id=None):
    q = """
        SELECT i.*, d.dept_name, u.full_name AS raised_by_name
        FROM tbl_stat_indents i
        LEFT JOIN tbl_departments d ON d.dept_id = i.dept_id
        LEFT JOIN tbl_users u ON u.user_id = i.raised_by
        WHERE 1=1
    """
    params = []
    if statuses:
        ph = ",".join(["?"] * len(statuses))
        q += f" AND i.indent_status IN ({ph})"
        params.extend(statuses)
    if dept_id:
        q += " AND i.dept_id = ?"
        params.append(dept_id)
    q += " ORDER BY i.created_at DESC"
    return [dict(r) for r in _fa(q, tuple(params))]


def _tab_pending(user, role, mod, mid):
    if st.session_state.get(f"_indent_act_msg_{mid}"):
        t, m = st.session_state.pop(f"_indent_act_msg_{mid}")
        (st.success if t == "s" else st.error)(m)

    statuses = _get_role_statuses(role)
    if not statuses:
        st.info(f"No pending actions configured for role '{role}'.")
        return

    dept_filter = None
    if role in ("HoD", "JuniorAssistant"):
        dept_filter = user.get("dept_id")

    indents = _load_indents(mid, statuses=statuses, dept_id=dept_filter)
    if not indents:
        st.success("No indents pending your action.")
        return

    st.markdown(f"**{len(indents)} indent(s) awaiting your action**")
    df = pd.DataFrame([{
        "Indent #": i["indent_number"],
        "Dept": i.get("dept_name", "-"),
        "Status": i["indent_status"],
        "Raised By": i.get("raised_by_name", "-"),
        "Date": str(i.get("created_at", ""))[:16],
    } for i in indents])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    opts = {f"{i['indent_number']} | {i.get('dept_name','-')} | {i['indent_status']}": i
            for i in indents[:100]}
    sel = st.selectbox("Select Indent:", list(opts.keys()), key=f"{mid}_pend_sel")
    _indent_detail(opts[sel], user, role, mod, mid)


# ───────────────────────────── INDENT DETAIL + ACTIONS ─────────────────────────────
def _indent_detail(indent, user, role, mod, mid):
    indent_id = indent["indent_id"]
    status = indent["indent_status"]

    st.markdown(f"### Indent `{indent['indent_number']}`")
    c1, c2 = st.columns(2)
    c1.markdown(f"**Department:** {indent.get('dept_name','-')}")
    c1.markdown(f"**Raised by:** {indent.get('raised_by_name','-')}")
    c2.markdown(f"**Status:** `{status}`")
    c2.markdown(f"**Date:** {str(indent.get('created_at',''))[:16]}")

    # Show last action prominently
    last_action = _fo("""
        SELECT action_type, action_comment, action_at, u.full_name AS actor
        FROM tbl_stat_indent_workflow wl
        LEFT JOIN tbl_users u ON u.user_id = wl.action_by
        WHERE wl.indent_id=? ORDER BY wl.action_at DESC LIMIT 1
    """, (indent_id,))
    if last_action:
        la = dict(last_action)
        st.info(
            f"**Last Action:** `{la['action_type']}` by **{la.get('actor','-')}** "
            f"on {str(la.get('action_at',''))[:16]}" +
            (f"  \n> {la['action_comment']}" if la.get("action_comment") else "")
        )

    # Line items
    lines = [dict(r) for r in _fa("""
        SELECT li.*, it.item_name, it.specification
        FROM tbl_stat_indent_items li
        JOIN tbl_stat_items it ON it.item_id = li.item_id
        WHERE li.indent_id=? ORDER BY li.line_id
    """, (indent_id,))]

    st.markdown("#### Indent Items")

    # Editable table for stock check (StatIncharge) and principal decision stages
    editable_stock = (role == "StatIncharge" and status == "STOCK CHECK")
    editable_principal = (role == "Principal" and status == "PRINCIPAL DECISION")
    editable_ja_confirm = (role == "JuniorAssistant" and status == "JA CONFIRMATION")

    if editable_stock:
        st.caption("Enter the quantity AVAILABLE in central stock for each item.")
        for ln in lines:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.markdown(f"**{ln['item_name']}** ({ln.get('specification','-')})")
            c2.markdown(f"Requested: {ln['requested_qty']} {ln['unit']}")
            avail = c3.number_input("Available", min_value=0.0,
                                     value=float(ln.get("available_qty") or 0),
                                     key=f"avail_{ln['line_id']}")
            c4.markdown(f"Remarks: {ln.get('remarks','-')}")

    elif editable_principal:
        st.caption("Approve, reduce quantity, or reject each item based on availability.")
        for ln in lines:
            c1, c2, c3, c4 = st.columns([3, 1.5, 1, 1.5])
            c1.markdown(f"**{ln['item_name']}**")
            c2.markdown(f"Requested: {ln['requested_qty']} | Available: {ln.get('available_qty', 0)}")
            max_q = float(ln.get("available_qty") or ln["requested_qty"])
            approved = c3.number_input("Approve Qty", min_value=0.0, max_value=max(max_q, ln["requested_qty"]),
                                       value=float(ln.get("approved_qty") or min(max_q, ln["requested_qty"])),
                                       key=f"appr_{ln['line_id']}")
            c4.markdown(f"Unit: {ln['unit']}")

    elif editable_ja_confirm:
        st.caption("Review the approved quantities. Confirm to proceed with issuing.")
        df_confirm = pd.DataFrame([{
            "Item": ln["item_name"],
            "Requested": ln["requested_qty"],
            "Approved": ln.get("approved_qty", 0),
            "Unit": ln["unit"],
        } for ln in lines])
        st.dataframe(df_confirm, use_container_width=True, hide_index=True)

    else:
        df_view = pd.DataFrame([{
            "Item": ln["item_name"],
            "Spec": ln.get("specification", "-"),
            "Requested": ln["requested_qty"],
            "Available": ln.get("available_qty", "-"),
            "Approved": ln.get("approved_qty", "-"),
            "Issued": ln.get("issued_qty", 0),
            "Unit": ln["unit"],
            "Status": ln.get("line_status", "-"),
            "Remarks": ln.get("remarks", "-"),
        } for ln in lines])
        st.dataframe(df_view, use_container_width=True, hide_index=True)

    st.divider()

    # ───── Actions ─────
    actions = _get_indent_actions(status, role)
    if not actions:
        st.info("No actions available for you at this stage.")
        return

    st.markdown("### Take Action")
    sel_action = st.selectbox("Select Action", list(actions.keys()), key=f"ia_{indent_id}_{status}")
    next_status = actions[sel_action]
    comment_required = sel_action in ("Reject Indent", "Send Back for Revision")
    comment_label = "Comments *" if comment_required else "Comments (optional)"
    comment = st.text_area(comment_label, key=f"ic_{indent_id}_{status}", height=70)

    if st.button(sel_action, type="primary", key=f"isub_{indent_id}_{status}"):
        if comment_required and not comment.strip():
            st.error("Comments are required for this action.")
            return
        try:
            conn = get_conn()

            # Save line-item edits based on stage
            if editable_stock:
                for ln in lines:
                    avail = st.session_state.get(f"avail_{ln['line_id']}", 0)
                    line_status = "AVAILABLE" if avail >= ln["requested_qty"] else \
                                  ("PARTIAL" if avail > 0 else "PENDING PROCUREMENT")
                    conn.execute("""
                        UPDATE tbl_stat_indent_items SET available_qty=?, line_status=?
                        WHERE line_id=?
                    """, (avail, line_status, ln["line_id"]))

            if editable_principal:
                for ln in lines:
                    appr = st.session_state.get(f"appr_{ln['line_id']}", 0)
                    conn.execute("""
                        UPDATE tbl_stat_indent_items SET approved_qty=? WHERE line_id=?
                    """, (appr, ln["line_id"]))

            conn.execute(
                "UPDATE tbl_stat_indents SET indent_status=? WHERE indent_id=?",
                (next_status, indent_id)
            )
            conn.execute("""
                INSERT INTO tbl_stat_indent_workflow
                    (indent_id, action_by, action_type, action_comment, from_status, to_status, action_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (indent_id, user["user_id"], sel_action, comment.strip(), status, next_status, _ist()))

            # On final receipt acknowledgement, move stock into dept stock
            if next_status == "INDENT CLOSED":
                for ln in lines:
                    issued = ln.get("approved_qty") or ln["requested_qty"]
                    conn.execute("""
                        UPDATE tbl_stat_indent_items SET issued_qty=?, line_status='ISSUED'
                        WHERE line_id=?
                    """, (issued, ln["line_id"]))

            conn.commit()
            conn.close()

            st.session_state[f"_indent_act_msg_{mid}"] = (
                "s", f"{sel_action} — Status: **{next_status}**"
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Action failed: {ex}")


def _get_indent_actions(status, role):
    """Returns dict of {action_label: next_status} for given status+role."""
    rules = {
        ("DEPT REVIEW", "HoD"): {
            "Approve & Forward to Office Superintendent": "OS REVIEW",
            "Reject Indent": "REJECTED",
        },
        ("OS REVIEW", "OS"): {
            "Forward to Stationery In-charge for Stock Check": "STOCK CHECK",
        },
        ("STOCK CHECK", "StatIncharge"): {
            "Submit Availability & Forward to OS": "PRINCIPAL REVIEW",
        },
        ("PRINCIPAL REVIEW", "OS"): {
            "Forward to Principal with Remarks": "PRINCIPAL DECISION",
        },
        ("PRINCIPAL DECISION", "Principal"): {
            "Approve (Full or Partial)": "JA CONFIRMATION",
            "Reject Indent": "REJECTED",
            "Send Back for Revision": "DEPT REVIEW",
        },
        ("JA CONFIRMATION", "JuniorAssistant"): {
            "Confirm Approved Quantities": "ISSUE PENDING",
        },
        ("ISSUE PENDING", "StatIncharge"): {
            "Issue Items to Department": "RECEIVED PENDING",
        },
        ("RECEIVED PENDING", "JuniorAssistant"): {
            "Acknowledge Receipt": "INDENT CLOSED",
        },
    }
    if role == "SuperAdmin":
        # SuperAdmin can act at any stage with the same options as the assigned role
        for (st_, r_), acts in rules.items():
            if st_ == status:
                return acts
        return {}
    return rules.get((status, role), {})


# ───────────────────────────── INDENT REGISTER ─────────────────────────────
def _tab_register(user, role, mod, mid):
    st.subheader("Indent Register")

    dept_filter = None
    if role in ("HoD", "JuniorAssistant"):
        dept_filter = user.get("dept_id")

    indents = _load_indents(mid, dept_id=dept_filter)
    if not indents:
        st.info("No indents found.")
        return

    df = pd.DataFrame([{
        "Indent #": i["indent_number"],
        "Dept": i.get("dept_name", "-"),
        "Status": i["indent_status"],
        "Raised By": i.get("raised_by_name", "-"),
        "Date": str(i.get("created_at", ""))[:16],
    } for i in indents])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    opts = {f"{i['indent_number']} | {i.get('dept_name','-')} | {i['indent_status']}": i
            for i in indents[:100]}
    sel = st.selectbox("View Indent Detail:", list(opts.keys()), key=f"{mid}_reg_sel")
    selected_indent = opts[sel]

    # Read-only detail view
    st.markdown(f"### Indent `{selected_indent['indent_number']}`")
    lines = [dict(r) for r in _fa("""
        SELECT li.*, it.item_name, it.specification
        FROM tbl_stat_indent_items li
        JOIN tbl_stat_items it ON it.item_id = li.item_id
        WHERE li.indent_id=? ORDER BY li.line_id
    """, (selected_indent["indent_id"],))]
    df_lines = pd.DataFrame([{
        "Item": ln["item_name"], "Requested": ln["requested_qty"],
        "Available": ln.get("available_qty", "-"), "Approved": ln.get("approved_qty", "-"),
        "Issued": ln.get("issued_qty", 0), "Unit": ln["unit"], "Status": ln.get("line_status", "-"),
    } for ln in lines])
    st.dataframe(df_lines, use_container_width=True, hide_index=True)

    steps = [dict(r) for r in _fa("""
        SELECT wl.*, u.full_name AS actor FROM tbl_stat_indent_workflow wl
        LEFT JOIN tbl_users u ON u.user_id = wl.action_by
        WHERE wl.indent_id=? ORDER BY wl.action_at ASC
    """, (selected_indent["indent_id"],))]
    if steps:
        st.markdown("#### Timeline")
        for s in steps:
            st.markdown(
                f"**{str(s['action_at'])[:16]}** - **{s['actor']}** "
                f"`{s['from_status']}` -> `{s['to_status']}`  \n"
                f"_{s.get('action_comment','') or ''}_"
            )
