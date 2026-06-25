"""pages/mod_stat.py — Stationery module (indent only, no maintenance)"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
def _ist(): return (datetime.utcnow() + timedelta(hours=5, minutes=30))
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access
from utils.helpers import export_df
from components.header import render_portal_sidebar

MODULE_CODE = "STAT"

def show_module():
    role = require_module_access(MODULE_CODE)
    user = current_user()
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (MODULE_CODE,))
    if not mod: return
    mod  = dict(mod)

    st.session_state["sims_module"] = MODULE_CODE

    # Sidebar for stationery
    with st.sidebar:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#00838F,#006064);
                    padding:10px 14px;border-radius:8px;
                    border-bottom:3px solid #F0A500;margin-bottom:12px">
          <p style="color:#FFFFFF;font-weight:900;font-size:0.9rem;margin:0">
            📝 Stationery Management</p>
          <p style="color:#B2EBF2;font-size:0.72rem;margin:3px 0 0 0">
            Indent only — no maintenance</p>
        </div>
        """, unsafe_allow_html=True)

        def nav(label, sub):
            if st.button(label, use_container_width=True, key=f"stat_{sub}"):
                st.session_state["stat_sub"] = sub; st.rerun()

        if st.button("◀  Back to Portal", use_container_width=True, key="stat_back"):
            st.session_state["sims_module"] = ""; st.session_state["page"] = "dashboard"; st.rerun()

        nav("📋  Raise Indent",       "raise")
        nav("⏳  Pending Approval",   "pending")
        nav("✅  Approved Indents",   "approved")
        nav("📊  All Indents",        "all")
        if role in ("SuperAdmin","SysAdmin","HoD","Coordinator"):
            nav("📈  Summary Report", "report")

    if st.session_state.get("_stat_msg"):
        t,m = st.session_state.pop("_stat_msg")
        (st.success if t=="s" else st.error)(m)

    sub = st.session_state.get("stat_sub","raise")
    st.title(f"📝 Stationery Management")

    if sub == "raise":   _raise(user, role)
    elif sub == "pending": _pending(user, role)
    elif sub == "approved": _approved(user, role)
    elif sub == "report":  _report()
    else: _all(user, role)


def _raise(user, role):
    st.subheader("Raise Stationery Indent")
    count = dict(_fo("SELECT COUNT(*) c FROM tbl_stationery_indent") or {"c":0})["c"]
    indent_no = f"STAT-{_ist().strftime('%Y%m')}-{count+1:04d}"

    depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    if not depts: st.warning("No departments configured."); return
    dm = {d["dept_name"]: d["dept_id"] for d in depts}

    dept = st.selectbox("Department *", list(dm.keys()), key="si_dept")
    c1,c2 = st.columns(2)
    item = c1.text_input("Item Name *", placeholder="e.g. A4 Paper Ream 500 sheets", key="si_item")
    c3,c4,c5 = st.columns(3)
    qty  = c3.number_input("Quantity *", min_value=1, value=1, key="si_qty")
    unit = c4.selectbox("Unit", ["Nos","Reams","Boxes","Packets","Pens","Kg","Litre"], key="si_unit")
    purp = c5.text_input("Purpose *", placeholder="e.g. Exam Hall use", key="si_purp")
    rem  = st.text_input("Remarks", key="si_rem")

    st.markdown(f"**Indent No: `{indent_no}`**")

    if st.button("Submit Indent", type="primary", use_container_width=True, key="si_submit"):
        if not item.strip() or not purp.strip():
            st.error("Item and Purpose are required."); return
        try:
            conn = get_conn()
            conn.execute("""
                INSERT INTO tbl_stationery_indent
                    (indent_number,raised_by,dept_id,item_name,quantity,unit,purpose,indent_status,remarks)
                VALUES (?,?,?,?,?,?,?,'PENDING',?)
            """,(indent_no,user["user_id"],dm[dept],item.strip(),qty,unit,purp.strip(),rem))
            conn.commit(); conn.close()
            st.session_state["_stat_msg"] = ("s", f"Indent {indent_no} submitted for approval.")
            st.rerun()
        except Exception as ex: st.error(f"Failed: {ex}")


def _pending(user, role):
    st.subheader("Pending Approval")
    if role in ("SuperAdmin","SysAdmin","HoD","Coordinator"):
        rows = [dict(r) for r in _fa("""
            SELECT si.*, d.dept_name, u.full_name AS raised_by_name
            FROM tbl_stationery_indent si
            JOIN tbl_departments d ON d.dept_id=si.dept_id
            JOIN tbl_users u ON u.user_id=si.raised_by
            WHERE si.indent_status='PENDING' ORDER BY si.created_at ASC
        """)]
    else:
        rows = [dict(r) for r in _fa("""
            SELECT si.*, d.dept_name, u.full_name AS raised_by_name
            FROM tbl_stationery_indent si
            JOIN tbl_departments d ON d.dept_id=si.dept_id
            JOIN tbl_users u ON u.user_id=si.raised_by
            WHERE si.indent_status='PENDING' AND si.raised_by=?
        """,(user["user_id"],))]

    if not rows: st.success("No pending indents."); return
    st.markdown(f"**{len(rows)} indent(s) pending:**")

    for r in rows:
        with st.expander(f"{r['indent_number']} | {r['item_name']} x{r['quantity']} {r['unit']} | {r['dept_name']}"):
            st.markdown(f"**Purpose:** {r['purpose']}  \n**Raised by:** {r['raised_by_name']}  \n**Date:** {str(r.get('created_at',''))[:16]}")
            if r.get("remarks"): st.caption(f"Remarks: {r['remarks']}")
            if role in ("SuperAdmin","SysAdmin","HoD","Coordinator"):
                c1,c2,c3 = st.columns(3)
                appr_rem = c3.text_input("Approval Remarks",key=f"apr_rem_{r['indent_id']}")
                if c1.button("✅ Approve & Issue",type="primary",key=f"apr_{r['indent_id']}"):
                    conn=get_conn()
                    conn.execute("""UPDATE tbl_stationery_indent SET indent_status='ISSUED',
                        approved_by=?,approved_at=?,issued_by=?,issued_at=?,remarks=COALESCE(?,remarks)
                        WHERE indent_id=?""",
                        (user["user_id"],_ist().strftime("%Y-%m-%d %H:%M:%S"),
                         user["user_id"],_ist().strftime("%Y-%m-%d %H:%M:%S"),
                         appr_rem or None,r["indent_id"]))
                    conn.commit(); conn.close()
                    st.session_state["_stat_msg"] = ("s","Approved and issued."); st.rerun()
                if c2.button("❌ Reject",key=f"rej_{r['indent_id']}"):
                    conn=get_conn()
                    conn.execute("""UPDATE tbl_stationery_indent SET indent_status='REJECTED',
                        approved_by=?,approved_at=? WHERE indent_id=?""",
                        (user["user_id"],_ist().strftime("%Y-%m-%d %H:%M:%S"),r["indent_id"]))
                    conn.commit(); conn.close()
                    st.session_state["_stat_msg"] = ("s","Rejected."); st.rerun()


def _approved(user, role):
    st.subheader("Approved / Issued Indents")
    rows = [dict(r) for r in _fa("""
        SELECT si.*, d.dept_name, u.full_name AS raised_by_name, u2.full_name AS approved_by_name
        FROM tbl_stationery_indent si
        JOIN tbl_departments d ON d.dept_id=si.dept_id
        JOIN tbl_users u ON u.user_id=si.raised_by
        LEFT JOIN tbl_users u2 ON u2.user_id=si.approved_by
        WHERE si.indent_status IN ('APPROVED','ISSUED') ORDER BY si.approved_at DESC
    """)]
    if not rows: st.info("No approved indents."); return
    df = pd.DataFrame([{
        "Indent #":r["indent_number"],"Item":r["item_name"],"Qty":r["quantity"],
        "Unit":r["unit"],"Dept":r["dept_name"],"Status":r["indent_status"],
        "Approved By":r.get("approved_by_name","—"),"Issued On":str(r.get("issued_at",""))[:16],
    } for r in rows])
    st.dataframe(df,use_container_width=True,hide_index=True)
    export_df(df,"Stationery_Issued.xlsx")


def _all(user, role):
    st.subheader("All Stationery Indents")
    c1,c2 = st.columns(2)
    status_f = c1.selectbox("Status",["All","PENDING","APPROVED","ISSUED","REJECTED"],key="stat_all_s")
    search   = c2.text_input("Search Item / Dept",key="stat_all_srch")

    q = """
        SELECT si.*, d.dept_name, u.full_name AS raised_by_name,
               u2.full_name AS approved_by_name
        FROM tbl_stationery_indent si
        JOIN tbl_departments d ON d.dept_id=si.dept_id
        JOIN tbl_users u ON u.user_id=si.raised_by
        LEFT JOIN tbl_users u2 ON u2.user_id=si.approved_by
    """
    params = []
    if status_f != "All":
        q += " WHERE si.indent_status=?"; params.append(status_f)
    q += " ORDER BY si.created_at DESC"
    rows = [dict(r) for r in _fa(q, params)]

    if search.strip():
        s = search.lower()
        rows = [r for r in rows if s in r.get("item_name","").lower()
                or s in r.get("dept_name","").lower()]

    if not rows: st.info("No indents found."); return
    df = pd.DataFrame([{
        "Indent #":r["indent_number"],"Item":r["item_name"],"Qty":r["quantity"],
        "Unit":r["unit"],"Dept":r["dept_name"],"Purpose":r.get("purpose",""),
        "Status":r["indent_status"],"Raised By":r["raised_by_name"],
        "Approved By":r.get("approved_by_name","—"),
        "Date":str(r.get("created_at",""))[:16],
    } for r in rows])
    st.dataframe(df,use_container_width=True,hide_index=True)
    export_df(df,"Stationery_All_Indents.xlsx")


def _report(user=None):
    st.subheader("Stationery Summary Report")
    # By status
    by_status = [dict(r) for r in _fa("""
        SELECT indent_status, COUNT(*) AS count FROM tbl_stationery_indent GROUP BY indent_status
    """)]
    if by_status:
        m_cols = st.columns(len(by_status))
        for i,s in enumerate(by_status):
            m_cols[i].metric(s["indent_status"],s["count"])
    # By dept
    by_dept = [dict(r) for r in _fa("""
        SELECT d.dept_name, COUNT(*) AS indents, SUM(si.quantity) AS total_qty
        FROM tbl_stationery_indent si
        JOIN tbl_departments d ON d.dept_id=si.dept_id
        GROUP BY si.dept_id ORDER BY indents DESC
    """)]
    if by_dept:
        st.markdown("**By Department:**")
        df = pd.DataFrame(by_dept)
        st.dataframe(df,use_container_width=True,hide_index=True)
        export_df(df,"Stationery_Dept_Summary.xlsx")
