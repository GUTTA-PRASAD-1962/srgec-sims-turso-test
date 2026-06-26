"""
pages/cancel_calls.py — Manage / Cancel Calls for SRGEC-SIMS.
Adapted from IT-IIMS all_calls.py _manage_calls() function.

Who can cancel:
- Lab-IC  : their own DEPT REVIEW complaints only
- HoD     : DEPT REVIEW complaints for their department
- SysAdmin: any complaint at any stage
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access


def _ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def show(module_code):
    role = require_module_access(module_code)
    user = current_user()
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: st.error("Module not found."); return
    mod  = dict(mod)
    mid  = mod["module_id"]

    st.subheader("Cancel / Manage Calls")

    if st.session_state.get(f"_cancel_msg_{mid}"):
        t, m = st.session_state.pop(f"_cancel_msg_{mid}")
        (st.success if t == "s" else st.error)(m)

    st.info(
        "**Who can cancel a call:**\n"
        "- **Lab-IC** - can cancel their own complaints at DEPT REVIEW stage\n"
        "- **HoD** - can cancel DEPT REVIEW complaints for their department\n"
        "- **SysAdmin** - can cancel any complaint at any stage with reason\n\n"
        "Cancelled calls are marked **REJECTED** and kept for audit. "
        "All linked spare parts indents are also cancelled automatically."
    )

    # Determine which statuses this role can cancel
    if role == "SuperAdmin":
        cancelable_statuses = None  # all
    elif role == "SysAdmin":
        cancelable_statuses = None  # all
    elif role == "HoD":
        cancelable_statuses = ["DEPT REVIEW"]
    elif role == "Lab-IC":
        cancelable_statuses = ["DEPT REVIEW"]
    else:
        st.warning("You do not have permission to cancel complaints.")
        return

    # Search
    c1, c2 = st.columns(2)
    search        = c1.text_input("Call Number / Asset UID", key=f"{mid}_cancel_search",
                                   placeholder="e.g. UPS-CALL-0001")
    status_filter = c2.selectbox("Filter by Status",
        ["All active", "DEPT REVIEW", "HEAD-UPS REVIEW", "COORDINATOR REVIEW",
         "ASSIGNED", "PARTS NEEDED", "COST ESTIMATED", "HEAD-UPS BUDGET REVIEW",
         "BUDGET REVIEW", "BUDGET APPROVED", "PO RAISED", "UNDER REPAIR",
         "REPAIRED", "REJECTED"],
        key=f"{mid}_cancel_status_f"
    )

    # Build query
    q = """
        SELECT c.call_id, c.call_number, c.call_status, c.created_at,
               c.raised_by, c.complaint_text,
               i.unique_item_id, i.description AS item_desc,
               d.dept_name,
               u.full_name AS raised_by_name, u.dept_id AS raiser_dept_id,
               au.full_name AS assignee_name
        FROM tbl_calls c
        LEFT JOIN tbl_items i ON i.item_id = c.item_id
        LEFT JOIN tbl_users u ON u.user_id = c.raised_by
        LEFT JOIN tbl_departments d ON d.dept_id = u.dept_id
        LEFT JOIN tbl_users au ON au.user_id = c.current_assignee
        WHERE c.module_id = ?
        AND c.call_status NOT IN ('FILE CLOSED')
    """
    params = [mid]

    if status_filter != "All active":
        q += " AND c.call_status = ?"
        params.append(status_filter)

    if cancelable_statuses:
        ph = ",".join(["?"] * len(cancelable_statuses))
        q += f" AND c.call_status IN ({ph})"
        params.extend(cancelable_statuses)

    q += " ORDER BY c.created_at DESC"

    try:
        rows = [dict(r) for r in _fa(q, tuple(params))]
    except Exception as ex:
        st.error(f"Cannot load calls: {ex}"); return

    # Role-based filtering
    if role == "HoD":
        rows = [r for r in rows if r.get("raiser_dept_id") == user.get("dept_id")]
    elif role == "Lab-IC":
        rows = [r for r in rows if r.get("raised_by") == user.get("user_id")]

    # Search filter
    if search.strip():
        s = search.lower()
        rows = [r for r in rows
                if s in (r.get("call_number") or "").lower()
                or s in (r.get("unique_item_id") or "").lower()]

    if not rows:
        st.info("No cancellable complaints found."); return

    df = pd.DataFrame([{
        "Call #":    r["call_number"],
        "Status":    r["call_status"],
        "Asset UID": r.get("unique_item_id", "-"),
        "Dept":      r.get("dept_name", "-"),
        "Raised By": r.get("raised_by_name", "-"),
        "Raised":    str(r.get("created_at", ""))[:16],
    } for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    opts = {
        f"{r['call_number']} | {r.get('unique_item_id','')} | {r['call_status']}": r
        for r in rows[:100]
    }
    sel_label = st.selectbox("Select Call to Cancel", list(opts.keys()),
                             key=f"{mid}_cancel_sel")
    sel = opts[sel_label]

    st.markdown(
        f"**Call:** `{sel['call_number']}` | "
        f"**Asset:** `{sel.get('unique_item_id','')}` | "
        f"**Status:** `{sel['call_status']}` | "
        f"**Raised by:** {sel.get('raised_by_name','')} on "
        f"{str(sel.get('created_at',''))[:16]}"
    )
    st.markdown(f"**Complaint:** {sel.get('complaint_text','')}")
    st.divider()

    # Show linked indents
    try:
        linked = [dict(r) for r in _fa(
            "SELECT indent_id, description, indent_status FROM tbl_spare_indent WHERE call_id=?",
            (sel["call_id"],)
        )]
        active_indents = [i for i in linked
                         if i["indent_status"] not in ("CANCELLED", "PROCURED")]
        if active_indents:
            st.warning(
                f"This call has **{len(active_indents)} active spare parts indent(s)** "
                f"that will also be cancelled:"
            )
            for i in active_indents:
                st.markdown(f"  - {i['description']} | Status: {i['indent_status']}")
    except Exception:
        active_indents = []

    st.markdown("### Cancel This Call")
    cancel_reason = st.text_area(
        "Reason for cancellation *",
        key=f"{mid}_cancel_reason", height=80,
        placeholder="e.g. Raised by mistake - asset is working\n"
                    "OR: Duplicate complaint - already registered\n"
                    "OR: Problem resolved before technician visit"
    )

    confirm = st.checkbox(
        f"I confirm cancellation of **{sel['call_number']}** "
        f"and all linked indents",
        key=f"{mid}_cancel_confirm"
    )

    if st.button("Cancel This Call", type="primary",
                 key=f"{mid}_cancel_btn",
                 disabled=not confirm):
        if not cancel_reason.strip():
            st.error("Reason for cancellation is required."); return
        try:
            _now = _ist().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_conn()

            # Cancel linked indents
            if active_indents:
                for i in active_indents:
                    conn.execute(
                        "UPDATE tbl_spare_indent SET indent_status='CANCELLED' WHERE indent_id=?",
                        (i["indent_id"],)
                    )

            # Update call status to REJECTED
            conn.execute(
                "UPDATE tbl_calls SET call_status='REJECTED' WHERE call_id=?",
                (sel["call_id"],)
            )

            # Log the cancellation in workflow
            conn.execute("""
                INSERT INTO tbl_call_workflow
                    (call_id, action_by, action_type, action_comment, from_status, to_status, action_at)
                VALUES (?, ?, 'Call Cancelled', ?, ?, 'REJECTED', ?)
            """, (sel["call_id"], user["user_id"], cancel_reason.strip(),
                  sel["call_status"], _now))

            conn.commit(); conn.close()

            n = len(active_indents)
            st.session_state[f"_cancel_msg_{mid}"] = ("s",
                f"{sel['call_number']} cancelled (REJECTED). "
                f"{f'{n} indent(s) also cancelled.' if n else ''}"
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Cancellation failed: {ex}")
