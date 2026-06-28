"""
pages/common_circulars.py — Circulars Board for SRGEC-SIMS
Post and read circulars/announcements within a module.
Who can post: SuperAdmin, SysAdmin, HoD, HEAD-UPS, Coordinator
Who can read: All users in the module
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db.connection import fetchall as _fa, fetchone as _fo, execute as _ex, get_conn
from utils.auth import current_user, require_module_access


def _ist():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")


def show(module_code):
    role = require_module_access(module_code)
    user = current_user()
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: st.error("Module not found."); return
    mod  = dict(mod)
    mid  = mod["module_id"]
    uid  = user.get("user_id")

    can_post = role in ("SuperAdmin","SysAdmin","HoD","HEAD-UPS","Coordinator")

    # Count unread
    unread = dict(_fo("""
        SELECT COUNT(*) c FROM tbl_circulars c
        WHERE c.module_id=? AND c.is_active=1
        AND c.circular_id NOT IN (
            SELECT circular_id FROM tbl_circular_reads WHERE user_id=?
        )
    """, (mid, uid)) or {"c":0})["c"]

    st.markdown(f"### Circulars & Announcements")
    if unread:
        st.warning(f"You have **{unread}** unread circular(s).")

    # Post new circular
    if can_post:
        with st.expander("Post New Circular", expanded=False):
            title = st.text_input("Title *", key=f"{mid}_circ_title",
                                   placeholder="e.g. UPS Maintenance Schedule — July 2026")
            message = st.text_area("Message *", key=f"{mid}_circ_msg", height=120,
                                    placeholder="Enter the circular details here...")
            priority = st.selectbox("Priority", ["NORMAL","HIGH","URGENT"],
                                     key=f"{mid}_circ_pri")
            if st.button("Post Circular", type="primary", key=f"{mid}_circ_post"):
                if not title.strip() or not message.strip():
                    st.error("Title and message are required.")
                else:
                    try:
                        _ex("""
                            INSERT INTO tbl_circulars
                                (module_id, posted_by, title, message, priority, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (mid, uid, title.strip(), message.strip(), priority, _ist()))
                        st.success("Circular posted successfully.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Failed: {ex}")

    st.divider()

    # Load all circulars for this module
    circulars = [dict(r) for r in _fa("""
        SELECT c.circular_id, c.title, c.message, c.priority,
               c.created_at, u.full_name AS posted_by_name,
               u.user_id AS poster_id
        FROM tbl_circulars c
        JOIN tbl_users u ON u.user_id=c.posted_by
        WHERE c.module_id=? AND c.is_active=1
        ORDER BY c.created_at DESC
    """, (mid,))]

    if not circulars:
        st.info("No circulars posted yet.")
        return

    # Get read circular IDs for this user
    read_ids = set(dict(r)["circular_id"] for r in _fa(
        "SELECT circular_id FROM tbl_circular_reads WHERE user_id=?", (uid,)
    ))

    for c in circulars:
        cid = c["circular_id"]
        is_read = cid in read_ids
        priority_color = {"URGENT":"🔴","HIGH":"🟡","NORMAL":"🔵"}.get(c["priority"],"🔵")
        unread_badge = "" if is_read else " 🆕"

        with st.expander(
            f"{priority_color} {c['title']}{unread_badge} — {str(c['created_at'])[:16]} | {c['posted_by_name']}",
            expanded=not is_read
        ):
            st.markdown(c["message"])
            st.caption(f"Posted by **{c['posted_by_name']}** on {str(c['created_at'])[:16]} | Priority: {c['priority']}")

            col1, col2 = st.columns([1,4])
            if not is_read:
                if col1.button("Mark as Read", key=f"circ_read_{cid}"):
                    try:
                        _ex("""
                            INSERT OR IGNORE INTO tbl_circular_reads (circular_id, user_id, read_at)
                            VALUES (?, ?, ?)
                        """, (cid, uid, _ist()))
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Failed: {ex}")

            # Delete option for poster or SysAdmin/SuperAdmin
            if role in ("SuperAdmin","SysAdmin") or c["poster_id"] == uid:
                if col2.button("Delete Circular", key=f"circ_del_{cid}"):
                    try:
                        _ex("UPDATE tbl_circulars SET is_active=0 WHERE circular_id=?", (cid,))
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Failed: {ex}")
