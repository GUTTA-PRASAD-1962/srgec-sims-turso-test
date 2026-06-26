"""
pages/common_admin.py — Administration panel matching IT-IIMS exactly.
Sub-modules: User Management | Dept & Lab Setup | Suppliers | Role Matrix | Audit Log

Usage:
    from pages.common_admin import show
    show(MODULE_CODE)
"""
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
def _ist(): return (datetime.utcnow() + timedelta(hours=5, minutes=30))
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access
from utils.helpers import export_df


# Sub-modules for all SIMS modules
SIMS_SUB_MODULES = [
    "Inventory — Asset Search & Edit",
    "Inventory — Case Sheets",
    "Stock — Central Stock",
    "Stock — Department Stock",
    "Procurement — Forward",
    "Procurement — Pending Approvals",
    "Procurement — Joint Data Entry",
    "Procurement — Log",
    "Procurement — Bulk Upload",
    "Complaints — Raise Complaint",
    "Complaints — My Inbox",
    "Complaints — Complaint Register",
    "Complaints — Spare Parts Indent",
    "Complaints — Closure Report",
    "Warranty — Alerts",
    "Warranty — Expiring Soon",
    "Maintenance — Sheet",
    "Maintenance — Asset Movement",
    "Maintenance — Lab Register",
    "Reports",
    "Administration — User Management",
    "Administration — Dept & Lab Setup",
    "Administration — Suppliers",
    "Administration — Role & Privileges",
    "Administration — Audit Log",
    "Account — Notifications",
    "Account — Change Password",
]

ROLE_DEFAULTS = {
    "SysAdmin":   {s: {"can_view":1,"can_insert":1,"can_update":1,"can_delete":1} for s in SIMS_SUB_MODULES},
    "HoD":        {s: {"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SIMS_SUB_MODULES},
    "HEAD-UPS":   {s: {"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SIMS_SUB_MODULES},
    "Coordinator":{s: {"can_view":1,"can_insert":1,"can_update":1,"can_delete":0} for s in SIMS_SUB_MODULES},
    "Technician": {s: {"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SIMS_SUB_MODULES},
    "Lab-IC":     {s: {"can_view":1,"can_insert":1,"can_update":0,"can_delete":0} for s in SIMS_SUB_MODULES},
    "User":       {s: {"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SIMS_SUB_MODULES},
}

ROLE_VISIBLE = {
    "SysAdmin":   SIMS_SUB_MODULES,
    "HoD":        ["Inventory — Asset Search & Edit","Stock — Central Stock",
                   "Stock — Department Stock","Procurement — Pending Approvals",
                   "Procurement — Log","Complaints — My Inbox",
                   "Complaints — Complaint Register","Complaints — Spare Parts Indent",
                   "Warranty — Alerts","Warranty — Expiring Soon","Reports",
                   "Account — Notifications","Account — Change Password"],
    "Coordinator":["Inventory — Asset Search & Edit","Stock — Central Stock",
                   "Stock — Department Stock","Procurement — Forward",
                   "Procurement — Pending Approvals","Procurement — Joint Data Entry",
                   "Procurement — Log","Procurement — Bulk Upload",
                   "Complaints — My Inbox","Complaints — Complaint Register",
                   "Complaints — Spare Parts Indent","Maintenance — Sheet",
                   "Maintenance — Asset Movement","Warranty — Alerts","Reports",
                   "Account — Notifications","Account — Change Password"],
    "Technician": ["Inventory — Asset Search & Edit","Stock — Department Stock",
                   "Complaints — My Inbox","Complaints — Complaint Register",
                   "Complaints — Spare Parts Indent","Maintenance — Sheet",
                   "Maintenance — Asset Movement","Account — Notifications",
                   "Account — Change Password"],
    "Lab-IC":     ["Inventory — Asset Search & Edit","Stock — Department Stock",
                   "Complaints — Raise Complaint","Complaints — My Inbox",
                   "Complaints — Complaint Register","Warranty — Alerts",
                   "Account — Notifications","Account — Change Password"],
    "User":       ["Inventory — Asset Search & Edit","Stock — Department Stock",
                   "Complaints — Raise Complaint","Complaints — My Inbox",
                   "Account — Notifications","Account — Change Password"],
}


def show(module_code):
    role = require_module_access(module_code)
    if role not in ("SuperAdmin","SysAdmin","Coordinator"):
        st.error("Administration — SysAdmin / Coordinator only."); return

    user = current_user()
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: return
    mod  = dict(mod); mid = mod["module_id"]

    if st.session_state.get(f"_admin_msg_{mid}"):
        t,m = st.session_state.pop(f"_admin_msg_{mid}")
        (st.success if t=="s" else st.error)(m)


def show_users(module_code):
    """👥 User Management — matches IT-IIMS users.py"""
    role = require_module_access(module_code)
    user = current_user()
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: return
    mod  = dict(mod); mid = mod["module_id"]

    if st.session_state.get(f"_admin_msg_{mid}"):
        t,m = st.session_state.pop(f"_admin_msg_{mid}")
        (st.success if t=="s" else st.error)(m)

    # DB Backup at top (SysAdmin only)
    if role in ("SuperAdmin","SysAdmin"):
        with st.expander("🗄️ Database Backup & Statistics"):
            from config import DB_PATH
            from pathlib import Path
            c1,c2 = st.columns(2)
            if c1.button("📥 Download DB Backup", type="primary", key=f"{mid}_db_backup"):
                p = Path(DB_PATH)
                if p.exists():
                    ts = _ist().strftime("%Y%m%d_%H%M%S")
                    st.download_button(
                        f"💾 Save sims_backup_{ts}.db", p.read_bytes(),
                        file_name=f"sims_backup_{ts}.db",
                        mime="application/octet-stream",
                        key=f"{mid}_db_dl")
                else: st.error("DB file not found.")
            if c2.button("📊 DB Statistics", key=f"{mid}_db_stats"):
                tables = [("tbl_items","Assets"),("tbl_invoices","Invoices"),
                          ("tbl_calls","Complaints"),("tbl_maintenance","Maintenance"),
                          ("tbl_users","Users"),("tbl_departments","Departments"),
                          ("tbl_spare_indent","Spare Parts Indents")]
                stats = []
                for tbl,lbl in tables:
                    try:
                        cnt = dict(_fo(f"SELECT COUNT(*) c FROM {tbl}") or {"c":0})["c"]
                        stats.append({"Table":lbl,"Records":cnt})
                    except: pass
                if stats:
                    st.dataframe(pd.DataFrame(stats),use_container_width=True,hide_index=True)

    tab1, tab2 = st.tabs(["👀 All Users", "➕ Create User"])

    with tab1:
        # Show users with module access
        users = [dict(r) for r in _fa("""
            SELECT u.user_id, u.full_name, u.username, u.employee_id,
                   a.role_name, d.dept_name, u.email, u.phone,
                   u.is_active, u.last_login
            FROM tbl_user_module_access a
            JOIN tbl_users u ON u.user_id=a.user_id
            JOIN tbl_modules m ON m.module_id=a.module_id
            LEFT JOIN tbl_departments d ON d.dept_id=u.dept_id
            WHERE m.module_code=? AND a.is_active=1
            ORDER BY u.full_name
        """,(module_code,))]

        if users:
            df = pd.DataFrame([{
                "ID":u["user_id"],"Full Name":u["full_name"],"Username":u["username"],
                "Emp ID":u["employee_id"],"Role":u["role_name"],
                "Department":u.get("dept_name","—"),"Email":u.get("email","—"),
                "Phone":u.get("phone","—"),
                "Active":"Yes" if u["is_active"] else "No",
                "Last Login":str(u.get("last_login",""))[:16],
            } for u in users])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No users assigned to this module yet.")

        st.divider()
        st.subheader("✏️ Edit User")
        all_users = [dict(r) for r in _fa("SELECT user_id,full_name,username FROM tbl_users WHERE is_active=1 ORDER BY full_name")]
        uid_opts  = {f"{u['full_name']} ({u['username']})": u["user_id"] for u in all_users}
        sel_edit  = st.selectbox("Select User to Edit", list(uid_opts.keys()), key=f"{mid}_eu_sel")
        if st.button("Load User", key=f"{mid}_eu_load"):
            st.session_state[f"edit_uid_{mid}"] = uid_opts[sel_edit]

        if f"edit_uid_{mid}" in st.session_state:
            eu = _fo("SELECT u.*, d.dept_name FROM tbl_users u LEFT JOIN tbl_departments d ON d.dept_id=u.dept_id WHERE u.user_id=?",
                     (st.session_state[f"edit_uid_{mid}"],))
            if eu:
                eu = dict(eu)
                depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
                dm    = {"(None)": None}; dm.update({d["dept_name"]: d["dept_id"] for d in depts})

                # Get current module role for this user
                cur_role = _fo("""
                    SELECT role_name FROM tbl_user_module_access a
                    JOIN tbl_modules m ON m.module_id=a.module_id
                    WHERE a.user_id=? AND m.module_code=?
                """,(eu["user_id"], module_code))
                cur_role_name = dict(cur_role)["role_name"] if cur_role else "User"
                role_options = [dict(r)["role_name"] for r in _fa("SELECT role_name FROM tbl_sims_roles ORDER BY is_system DESC, role_name")]

                with st.form(f"edit_user_form_{mid}"):
                    fn   = st.text_input("Full Name",  eu["full_name"])
                    r_sel= st.selectbox("Module Role", role_options,
                                        index=role_options.index(cur_role_name) if cur_role_name in role_options else 6)
                    d_sel= st.selectbox("Department", list(dm.keys()),
                                        index=list(dm.values()).index(eu.get("dept_id")) if eu.get("dept_id") in dm.values() else 0)
                    email= st.text_input("Email",  eu.get("email","") or "")
                    phone= st.text_input("Phone",  eu.get("phone","") or "")
                    act  = st.checkbox("Active", value=bool(eu["is_active"]))
                    npw  = st.text_input("New Password (leave blank to keep)", type="password")
                    if st.form_submit_button("💾 Save", type="primary"):
                        conn = get_conn()
                        try:
                            conn.execute("""
                                UPDATE tbl_users SET full_name=?,dept_id=?,email=?,phone=?,is_active=?
                                WHERE user_id=?
                            """,(fn, dm[d_sel], email, phone, 1 if act else 0, eu["user_id"]))
                            conn.execute("""
                                UPDATE tbl_user_module_access SET role_name=?
                                WHERE user_id=? AND module_id=(SELECT module_id FROM tbl_modules WHERE module_code=?)
                            """,(r_sel, eu["user_id"], module_code))
                            if npw.strip():
                                conn.execute("UPDATE tbl_users SET password_hash=? WHERE user_id=?",
                                             (hashlib.sha256(npw.encode()).hexdigest(), eu["user_id"]))
                            conn.commit(); conn.close()
                            st.success("User updated.")
                            del st.session_state[f"edit_uid_{mid}"]
                            st.rerun()
                        except Exception as ex: st.error(str(ex)); conn.close()

                st.markdown("---")
                st.markdown("#### 🗑 Delete / Deactivate User")
                if eu["user_id"] == user.get("user_id"):
                    st.warning("You cannot delete or deactivate your own account.")
                else:
                    st.caption(
                        "**Deactivate** disables login but keeps history (recommended). "
                        "**Delete** permanently removes the user record and ALL their "
                        "module access — only possible if no audit/asset records "
                        "reference this user."
                    )
                    dcol1, dcol2 = st.columns(2)

                    if eu["is_active"]:
                        if dcol1.button("🚫 Deactivate User", key=f"{mid}_deact_user"):
                            conn = get_conn()
                            conn.execute("UPDATE tbl_users SET is_active=0 WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.commit(); conn.close()
                            st.success(f"User '{eu['username']}' deactivated.")
                            st.rerun()
                    else:
                        if dcol1.button("✅ Reactivate User", key=f"{mid}_react_user"):
                            conn = get_conn()
                            conn.execute("UPDATE tbl_users SET is_active=1 WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.commit(); conn.close()
                            st.success(f"User '{eu['username']}' reactivated.")
                            st.rerun()

                    confirm_del = dcol2.checkbox(
                        f"I confirm permanent deletion of '{eu['username']}'",
                        key=f"{mid}_confirm_del_user"
                    )
                    if dcol2.button("🗑️ Delete Permanently", type="primary",
                                    key=f"{mid}_del_user", disabled=not confirm_del):
                        conn = get_conn()
                        try:
                            conn.execute("DELETE FROM tbl_user_module_access WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.execute("DELETE FROM tbl_users WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.commit(); conn.close()
                            st.success(f"User '{eu['username']}' permanently deleted.")
                            del st.session_state[f"edit_uid_{mid}"]
                            st.rerun()
                        except Exception as ex:
                            conn.close()
                            st.error(
                                f"Cannot delete: {ex}. This user likely has "
                                "linked records (assets, audit logs, complaints). "
                                "Use **Deactivate** instead."
                            )

    with tab2:
        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
        dm    = {"(None)": None}; dm.update({d["dept_name"]: d["dept_id"] for d in depts})

        with st.form(f"create_user_form_{mid}"):
            st.markdown("**New User Details**")
            u1,u2   = st.columns(2)
            username= u1.text_input("Username *")
            password= u2.text_input("Password *", type="password")
            u3,u4   = st.columns(2)
            full_name=u3.text_input("Full Name *")
            emp_id  = u4.text_input("Employee ID *")
            u5,u6   = st.columns(2)
            role_sel= u5.selectbox("Module Role *",
                                    [dict(r)["role_name"] for r in _fa("SELECT role_name FROM tbl_sims_roles WHERE role_name != 'SuperAdmin' ORDER BY is_system DESC, role_name")])
            dept_sel= u6.selectbox("Department", list(dm.keys()))
            u7,u8   = st.columns(2)
            email   = u7.text_input("Email")
            phone   = u8.text_input("Phone")
            submitted = st.form_submit_button("➕ Create User", type="primary",
                                              use_container_width=True)

        if submitted:
            if not all([username.strip(),password.strip(),full_name.strip(),emp_id.strip()]):
                st.error("Username, Password, Full Name and Employee ID are required.")
            else:
                conn = get_conn()
                try:
                    uid = conn.execute("""
                        INSERT INTO tbl_users (username,password_hash,full_name,employee_id,
                            dept_id,email,phone,is_active,created_at)
                        VALUES (?,?,?,?,?,?,?,1,?)
                    """,(username.strip(),hashlib.sha256(password.encode()).hexdigest(),
                         full_name.strip(),emp_id.strip(),dm[dept_sel],email,phone,
                         _ist().strftime("%Y-%m-%d %H:%M:%S"))).lastrowid
                    conn.execute("""
                        INSERT OR REPLACE INTO tbl_user_module_access
                            (user_id,module_id,role_name,is_active,granted_at)
                        VALUES (?,(SELECT module_id FROM tbl_modules WHERE module_code=?),?,1,?)
                    """,(uid,module_code,role_sel,_ist().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit(); conn.close()
                    st.success(f"User '{username}' created with role '{role_sel}'.")
                    st.rerun()
                except Exception as ex: st.error(str(ex)); conn.close()

        st.divider()
        st.markdown("**Grant Module Access to Existing User**")
        g1,g2,g3 = st.columns(3)
        all_u = [dict(r) for r in _fa("SELECT user_id,full_name,username FROM tbl_users WHERE is_active=1 ORDER BY full_name")]
        sel_u = g1.selectbox("User",[f"{u['full_name']} ({u['username']})" for u in all_u],key=f"{mid}_ga_user")
        _ga_roles = [dict(r)["role_name"] for r in _fa("SELECT role_name FROM tbl_sims_roles WHERE role_name != 'SuperAdmin' ORDER BY is_system DESC, role_name")]
        sel_r = g2.selectbox("Role", _ga_roles, key=f"{mid}_ga_role")
        if g3.button("✅ Grant Access", key=f"{mid}_ga_save"):
            idx = [f"{u['full_name']} ({u['username']})" for u in all_u].index(sel_u)
            uid = all_u[idx]["user_id"]
            conn = get_conn()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO tbl_user_module_access
                        (user_id,module_id,role_name,is_active,granted_at)
                    VALUES (?,(SELECT module_id FROM tbl_modules WHERE module_code=?),?,1,?)
                """,(uid,module_code,sel_r,_ist().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit(); st.session_state[f"_admin_msg_{mid}"] = ("s","Access granted successfully."); st.rerun()
            except Exception as ex: st.error(str(ex))
            finally: conn.close()


def show_depts(module_code):
    """🏫 Dept & Lab Setup"""
    from utils.auth import current_user
    user = current_user()
    is_superadmin = bool(int(user.get("is_super_admin") or 0))
 
    depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    if depts:
        st.dataframe(pd.DataFrame([{
            "ID":d["dept_id"],"Name":d["dept_name"],"Code":d["dept_code"]
        } for d in depts]), use_container_width=True, hide_index=True)
    st.divider()
 
    if is_superadmin:
        st.markdown("**Add Department**")
        d1,d2 = st.columns(2)
        dn=d1.text_input("Dept Name *",key="new_dept_n"); dc=d2.text_input("Dept Code *",key="new_dept_c")
        if st.button("➕ Add Dept", key="new_dept_save"):
            if dn and dc:
                conn=get_conn()
                try:
                    conn.execute("INSERT INTO tbl_departments (dept_name,dept_code) VALUES (?,?)",(dn,dc.upper()))
                    conn.commit(); st.success(f"Dept '{dn}' added."); st.rerun()
                except Exception as ex: st.error(str(ex))
                finally: conn.close()
    else:
        st.caption(
            "ℹ️ Departments are managed centrally by SuperAdmin. "
            "Contact SuperAdmin to add or modify departments."
        )
    st.divider()
    st.markdown("**Add Location / Lab**")
    if depts:
        dm = {d["dept_name"]: d["dept_id"] for d in depts}
        l1,l2,l3,l4 = st.columns(4)
        ld=l1.selectbox("Dept *",list(dm.keys()),key="new_loc_dept")
        ln=l2.text_input("Location Name *",key="new_loc_n")
        lc=l3.text_input("Code *",key="new_loc_c")
        lt=l4.selectbox("Type",["LAB","ROOM","FLOOR","BLOCK"],key="new_loc_type")
        if st.button("➕ Add Location", key="new_loc_save"):
            if ln and lc:
                conn=get_conn()
                try:
                    conn.execute("INSERT INTO tbl_locations (dept_id,location_name,location_code,location_type) VALUES (?,?,?,?)",
                                 (dm[ld],ln,lc.upper(),lt))
                    conn.commit(); st.success(f"Location '{ln}' added."); st.rerun()
                except Exception as ex: st.error(str(ex))
                finally: conn.close()

    # Existing locations
    locs = [dict(r) for r in _fa("""
        SELECT l.*, d.dept_name FROM tbl_locations l
        JOIN tbl_departments d ON d.dept_id=l.dept_id
        WHERE l.is_active=1 ORDER BY d.dept_name, l.location_name
    """)]
    if locs:
        st.divider()
        st.markdown("**Existing Locations / Labs:**")
        st.dataframe(pd.DataFrame([{
            "Dept":l["dept_name"],"Location":l["location_name"],
            "Code":l["location_code"],"Type":l["location_type"]
        } for l in locs]), use_container_width=True, hide_index=True)


def show_suppliers(module_code):
    """🏭 Supplier Master — matches IT-IIMS suppliers.py"""
    tab1, tab2 = st.tabs(["📋 All Suppliers", "➕ Add Supplier"])

    with tab1:
        supps = [dict(r) for r in _fa("SELECT * FROM tbl_suppliers ORDER BY supplier_name")]
        if supps:
            df = pd.DataFrame([{
                "ID":s["supplier_id"],"Name":s["supplier_name"],
                "Contact":s.get("contact_person","—"),"Phone":s.get("phone","—"),
                "Email":s.get("email","—"),"Address":s.get("address","—"),
                "Active":"Yes" if s["is_active"] else "No"
            } for s in supps])
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Edit Supplier")
            s_opts = {f"{s['supplier_name']} (#{s['supplier_id']})": s for s in supps}
            sel_s  = st.selectbox("Select Supplier to Edit", list(s_opts.keys()), key="edit_supp_sel")
            if st.button("Load", key="edit_supp_load"):
                st.session_state["edit_supp"] = s_opts[sel_s]["supplier_id"]

            if "edit_supp" in st.session_state:
                sr = next((s for s in supps if s["supplier_id"]==st.session_state["edit_supp"]), None)
                if sr:
                    with st.form("edit_supplier"):
                        name = st.text_input("Name",    sr["supplier_name"])
                        cp   = st.text_input("Contact", sr.get("contact_person","") or "")
                        addr = st.text_area("Address",  sr.get("address","") or "")
                        ph   = st.text_input("Phone",   sr.get("phone","") or "")
                        em   = st.text_input("Email",   sr.get("email","") or "")
                        act  = st.checkbox("Active",    value=bool(sr.get("is_active",1)))
                        if st.form_submit_button("💾 Save"):
                            conn=get_conn()
                            conn.execute("""
                                UPDATE tbl_suppliers SET supplier_name=?,contact_person=?,
                                address=?,phone=?,email=?,is_active=? WHERE supplier_id=?
                            """,(name,cp,addr,ph,em,1 if act else 0,sr["supplier_id"]))
                            conn.commit(); conn.close()
                            st.success("Supplier updated.")
                            del st.session_state["edit_supp"]
                            st.rerun()
        else:
            st.info("No suppliers yet.")

    with tab2:
        with st.form("add_supplier"):
            name = st.text_input("Supplier Name *")
            cp   = st.text_input("Contact Person")
            addr = st.text_area("Address")
            ph   = st.text_input("Phone")
            em   = st.text_input("Email")
            if st.form_submit_button("➕ Add Supplier", type="primary"):
                if name.strip():
                    conn=get_conn()
                    try:
                        conn.execute("INSERT INTO tbl_suppliers (supplier_name,contact_person,address,phone,email) VALUES (?,?,?,?,?)",
                                     (name.strip(),cp,addr,ph,em))
                        conn.commit(); conn.close()
                        st.success(f"Supplier '{name}' added."); st.rerun()
                    except Exception as ex: st.error(str(ex))
                else: st.error("Supplier name is required.")


def show_role_matrix(module_code):
    """🔐 Role & Privileges Matrix — assign VIEW/EDIT/DELETE/APPROVE per role per sub-module"""
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: return
    mod  = dict(mod); mid = mod["module_id"]

    st.info(
        "Define what each role can do in each sub-module. "
        "This matrix controls VIEW, ADD, EDIT, DELETE, and APPROVE privileges."
    )

    # Sub-modules list
    sub_modules = [
        "Central Stock", "Department Stock", "Procurement-Forward",
        "Procurement-Entry", "Procurement-Approvals", "Complaint-Raise",
        "Complaint-Inbox", "Complaint-Register", "Spare Parts Indent",
        "Maintenance Sheet", "Asset Movement", "Lab Maintenance",
        "Warranty Alerts", "Reports", "User Management",
        "Dept & Lab Setup", "Suppliers", "Audit Log",
    ]
    roles_list = ["SysAdmin","HoD","HEAD-UPS","Coordinator","Technician","Lab-IC","User"]
    privs      = ["VIEW","ADD","EDIT","DELETE","APPROVE"]

    # Load existing matrix from DB
    matrix_rows = [dict(r) for r in _fa("""
        SELECT * FROM tbl_role_privileges WHERE module_id=?
    """,(mid,))]
    # Build lookup: {role: {sub_module: {priv: bool}}}
    matrix = {}
    for r in matrix_rows:
        matrix.setdefault(r["role_name"],{}).setdefault(r["sub_module"],{})[r["privilege"]] = bool(r["is_allowed"])

    tab1, tab2 = st.tabs(["📋 View Matrix","✏️ Edit Privileges"])

    with tab1:
        st.markdown("**Current Role Privileges Matrix**")
        # Build display table
        rows = []
        for sub in sub_modules:
            row = {"Sub-Module": sub}
            for role in roles_list:
                perms = matrix.get(role,{}).get(sub,{})
                icons = ""
                if perms.get("VIEW",True):    icons += "👁 "
                if perms.get("ADD",False):    icons += "➕ "
                if perms.get("EDIT",False):   icons += "✏️ "
                if perms.get("DELETE",False): icons += "🗑 "
                if perms.get("APPROVE",False):icons += "✅ "
                row[role] = icons.strip() or "—"
            rows.append(row)
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        export_df(df, f"{module_code}_Role_Matrix.xlsx")

    with tab2:
        st.markdown("**Edit Role Privileges**")
        c1,c2 = st.columns(2)
        sel_role = c1.selectbox("Role", roles_list, key=f"{mid}_rm_role")
        sel_sub  = c2.selectbox("Sub-Module", sub_modules, key=f"{mid}_rm_sub")

        # Current privileges
        cur = matrix.get(sel_role,{}).get(sel_sub,{})
        st.markdown(f"**Privileges for `{sel_role}` on `{sel_sub}`:**")
        p1,p2,p3,p4,p5 = st.columns(5)
        v_view   = p1.checkbox("VIEW",   value=cur.get("VIEW",   True),  key=f"{mid}_rm_view")
        v_add    = p2.checkbox("ADD",    value=cur.get("ADD",    False), key=f"{mid}_rm_add")
        v_edit   = p3.checkbox("EDIT",   value=cur.get("EDIT",   False), key=f"{mid}_rm_edit")
        v_del    = p4.checkbox("DELETE", value=cur.get("DELETE", False), key=f"{mid}_rm_del")
        v_appr   = p5.checkbox("APPROVE",value=cur.get("APPROVE",False), key=f"{mid}_rm_appr")

        if st.button("💾 Save Privileges", type="primary", key=f"{mid}_rm_save"):
            try:
                conn = get_conn()
                # Ensure table exists

                for priv, val in [("VIEW",v_view),("ADD",v_add),("EDIT",v_edit),
                                   ("DELETE",v_del),("APPROVE",v_appr)]:
                    conn.execute("""
                        INSERT OR REPLACE INTO tbl_role_privileges
                            (module_id,role_name,sub_module,privilege,is_allowed,updated_at)
                        VALUES (?,?,?,?,?,?)
                    """,(mid,sel_role,sel_sub,priv,1 if val else 0,
                         _ist().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit(); conn.close()
                st.success(f"Privileges saved for {sel_role} on {sel_sub}.")
                st.rerun()
            except Exception as ex: st.error(f"Failed: {ex}")

        st.divider()
        st.markdown("**Quick Setup — Apply Default Privileges for All Roles**")
        st.caption("Sets sensible defaults based on role. You can customize above afterwards.")

        defaults = {
            "SysAdmin":   {"VIEW":True,"ADD":True,"EDIT":True,"DELETE":True,"APPROVE":True},
            "HoD":        {"VIEW":True,"ADD":False,"EDIT":False,"DELETE":False,"APPROVE":True},
            "Coordinator":{"VIEW":True,"ADD":True,"EDIT":True,"DELETE":False,"APPROVE":True},
            "Technician": {"VIEW":True,"ADD":False,"EDIT":False,"DELETE":False,"APPROVE":False},
            "Lab-IC":     {"VIEW":True,"ADD":True,"EDIT":False,"DELETE":False,"APPROVE":False},
            "User":       {"VIEW":True,"ADD":False,"EDIT":False,"DELETE":False,"APPROVE":False},
        }

        if st.button("⚡ Apply Default Matrix for All Roles & Sub-Modules",
                     key=f"{mid}_rm_defaults"):
            try:
                conn = get_conn()

                count = 0
                for sub in sub_modules:
                    for role_n, privs_d in defaults.items():
                        for priv, val in privs_d.items():
                            conn.execute("""
                                INSERT OR REPLACE INTO tbl_role_privileges
                                    (module_id,role_name,sub_module,privilege,is_allowed,updated_at)
                                VALUES (?,?,?,?,?,?)
                            """,(mid,role_n,sub,priv,1 if val else 0,
                                 _ist().strftime("%Y-%m-%d %H:%M:%S")))
                            count += 1
                conn.commit(); conn.close()
                st.success(f"Default matrix applied — {count} privilege records saved.")
                st.rerun()
            except Exception as ex: st.error(f"Failed: {ex}")


def show_audit(module_code):
    """📜 Audit Log"""
    mod = _fo("SELECT module_id FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: return
    mid = dict(mod)["module_id"]

    rows = [dict(r) for r in _fa("""
        SELECT a.*, u.full_name AS user_name
        FROM tbl_audit a
        LEFT JOIN tbl_users u ON u.user_id=a.user_id
        WHERE a.module_id=? ORDER BY a.created_at DESC LIMIT 200
    """,(mid,))]
    if not rows: st.info("No audit records yet."); return
    df = pd.DataFrame([{
        "Time":str(r.get("created_at",""))[:16],"User":r.get("user_name","—"),
        "Action":r["action"],"Table":r.get("table_name","—"),
        "Details":(r.get("details","") or "")[:80],
    } for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)
    export_df(df, f"{module_code}_Audit_Log.xlsx")


def show_role_matrix(module_code):
    """🔐 Role & Privileges Matrix for SRGEC-SIMS module."""
    from utils.auth import current_user
    user = current_user()
    is_superadmin = bool(int(user.get("is_super_admin") or 0))
 
    mod = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: return
    mod = dict(mod)
    st.info(
        "Define default privileges per role for this module. "
        "These apply to all users with that role unless overridden individually."
    )
    roles_list = list(ROLE_DEFAULTS.keys())
 
    if not is_superadmin:
        st.warning(
            "⛔ Role & Privileges are managed centrally by SuperAdmin. "
            "You can view the current matrix below, but editing is restricted."
        )
        rows_db = [dict(r) for r in _fa(
            "SELECT * FROM tbl_role_module_privileges WHERE module_code=? ORDER BY role_name,sub_module",
            (module_code,))]
        if not rows_db:
            st.info("No role privileges defined yet. Contact SuperAdmin to configure.")
            return
        lookup = {(r["role_name"],r["sub_module"]): r for r in rows_db}
        rows = []
        for sub in SIMS_SUB_MODULES:
            row = {"Sub-Module": sub}
            for role_n in roles_list:
                r = lookup.get((role_n, sub), {})
                if not r.get("is_visible", 1):
                    row[role_n] = "🚫"
                else:
                    icons = ""
                    if r.get("can_view",1):    icons += "👁 "
                    if r.get("can_add",0):     icons += "➕ "
                    if r.get("can_edit",0):    icons += "✏️ "
                    if r.get("can_delete",0):  icons += "🗑 "
                    if r.get("can_approve",0): icons += "✅ "
                    row[role_n] = icons.strip() or "👁"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return
 
    sub1, sub2 = st.tabs(["📋 View Matrix", "✏️ Edit Role Privileges"])

    with sub1:
        rows_db = [dict(r) for r in _fa(
            "SELECT * FROM tbl_role_module_privileges WHERE module_code=? ORDER BY role_name,sub_module",
            (module_code,))]
        if not rows_db:
            st.info("No role privileges defined yet.")
            if st.button("⚡ Apply Default Role Privileges", type="primary",
                         key=f"apply_def_{module_code}"):
                _apply_role_defaults(module_code)
                st.success("Default privileges applied."); st.rerun()
            return

        lookup = {(r["role_name"],r["sub_module"]): r for r in rows_db}
        rows = []
        for sub in SIMS_SUB_MODULES:
            row = {"Sub-Module": sub}
            for role_n in roles_list:
                r = lookup.get((role_n, sub), {})
                if not r.get("is_visible", 1):
                    row[role_n] = "🚫"
                else:
                    icons = ""
                    if r.get("can_view",1):    icons += "👁 "
                    if r.get("can_add",0):     icons += "➕ "
                    if r.get("can_edit",0):    icons += "✏️ "
                    if r.get("can_delete",0):  icons += "🗑 "
                    if r.get("can_approve",0): icons += "✅ "
                    row[role_n] = icons.strip() or "👁"
            rows.append(row)
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        c1,c2 = st.columns(2)
        if c1.button("⚡ Re-apply Defaults", key=f"reapply_{module_code}"):
            _apply_role_defaults(module_code)
            st.success("Defaults re-applied."); st.rerun()
        import io
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        c2.download_button("📥 Export Matrix", buf.getvalue(),
                           f"{module_code}_Role_Matrix.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with sub2:
        col1, col2 = st.columns(2)
        sel_role = col1.selectbox("Role", roles_list, key=f"rm_role_{module_code}")
        sel_sub  = col2.selectbox("Sub-Module", SIMS_SUB_MODULES, key=f"rm_sub_{module_code}")

        cur = _fo("SELECT * FROM tbl_role_module_privileges WHERE module_code=? AND role_name=? AND sub_module=?",
                  (module_code, sel_role, sel_sub))
        cur = dict(cur) if cur else {}

        p1,p2,p3,p4,p5,p6 = st.columns(6)
        v_vis  = p1.checkbox("Visible", value=bool(cur.get("is_visible",1)),  key=f"rm_vis_{module_code}")
        v_view = p2.checkbox("VIEW",    value=bool(cur.get("can_view",1)),    key=f"rm_view_{module_code}")
        v_add  = p3.checkbox("ADD",     value=bool(cur.get("can_add",0)),     key=f"rm_add_{module_code}")
        v_edit = p4.checkbox("EDIT",    value=bool(cur.get("can_edit",0)),    key=f"rm_edit_{module_code}")
        v_del  = p5.checkbox("DELETE",  value=bool(cur.get("can_delete",0)),  key=f"rm_del_{module_code}")
        v_appr = p6.checkbox("APPROVE", value=bool(cur.get("can_approve",0)), key=f"rm_appr_{module_code}")

        if st.button("💾 Save Role Privilege", type="primary", key=f"rm_save_{module_code}"):
            conn = get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO tbl_role_module_privileges
                    (module_code,role_name,sub_module,can_view,can_add,can_edit,
                     can_delete,can_approve,is_visible,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """,(module_code,sel_role,sel_sub,
                 1 if v_view else 0, 1 if v_add else 0, 1 if v_edit else 0,
                 1 if v_del else 0, 1 if v_appr else 0, 1 if v_vis else 0,
                 _ist().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
            st.success(f"Saved: {sel_role} → {sel_sub}"); st.rerun()


def show_user_privileges(module_code):
    """👤 User-level privilege overrides."""
    st.info(
        "Override privileges for a specific user. "
        "User overrides take priority over role defaults."
    )
    all_users = [dict(r) for r in _fa("""
        SELECT u.user_id, u.full_name, u.username, a.role_name
        FROM tbl_user_module_access a
        JOIN tbl_users u ON u.user_id=a.user_id
        JOIN tbl_modules m ON m.module_id=a.module_id
        WHERE m.module_code=? AND a.is_active=1 AND u.is_active=1
        ORDER BY u.full_name
    """,(module_code,))]
    if not all_users: st.info("No users assigned to this module."); return

    u_opts = {f"{u['full_name']} ({u['username']} / {u['role_name']})": u for u in all_users}

    tab1, tab2, tab3 = st.tabs(["👁 View Access","✏️ Edit Override","🔄 Copy Role Defaults"])

    with tab1:
        sel_u = st.selectbox("Select User", list(u_opts.keys()), key=f"up_view1_{module_code}")
        u_row = u_opts[sel_u]
        uid   = u_row["user_id"]
        user_privs = {dict(r)["sub_module"]: dict(r) for r in _fa(
            "SELECT * FROM tbl_user_module_privileges WHERE user_id=? AND module_code=?",
            (uid, module_code))}
        role_privs = {dict(r)["sub_module"]: dict(r) for r in _fa(
            "SELECT * FROM tbl_role_module_privileges WHERE module_code=? AND role_name=?",
            (module_code, u_row["role_name"]))}
        rows = []
        for sub in SIMS_SUB_MODULES:
            p = user_privs.get(sub) or role_privs.get(sub) or {}
            source = "👤 User Override" if sub in user_privs else "🔖 Role Default"
            icons = ""
            if p.get("can_view",1):    icons += "👁 "
            if p.get("can_add",0):     icons += "➕ "
            if p.get("can_edit",0):    icons += "✏️ "
            if p.get("can_delete",0):  icons += "🗑 "
            if p.get("can_approve",0): icons += "✅ "
            rows.append({"Sub-Module":sub,
                         "Visible":"✅" if p.get("is_visible",1) else "🚫",
                         "Privileges":icons.strip() or "👁","Source":source})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab2:
        sel_u2  = st.selectbox("Select User", list(u_opts.keys()), key=f"up_edit1_{module_code}")
        u_row2  = u_opts[sel_u2]
        uid2    = u_row2["user_id"]
        sel_sub = st.selectbox("Sub-Module", SIMS_SUB_MODULES, key=f"up_sub2_{module_code}")
        cur = _fo("SELECT * FROM tbl_user_module_privileges WHERE user_id=? AND module_code=? AND sub_module=?",
                  (uid2, module_code, sel_sub))
        cur = dict(cur) if cur else {}
        if not cur:
            role_cur = _fo("SELECT * FROM tbl_role_module_privileges WHERE module_code=? AND role_name=? AND sub_module=?",
                           (module_code, u_row2["role_name"], sel_sub))
            if role_cur: cur = dict(role_cur)

        p1,p2,p3,p4,p5,p6 = st.columns(6)
        v_vis  = p1.checkbox("Visible", value=bool(cur.get("is_visible",1)),  key=f"up_vis2_{module_code}")
        v_view = p2.checkbox("VIEW",    value=bool(cur.get("can_view",1)),    key=f"up_view2_{module_code}")
        v_add  = p3.checkbox("ADD",     value=bool(cur.get("can_add",0)),     key=f"up_add2_{module_code}")
        v_edit = p4.checkbox("EDIT",    value=bool(cur.get("can_edit",0)),    key=f"up_edit3_{module_code}")
        v_del  = p5.checkbox("DELETE",  value=bool(cur.get("can_delete",0)),  key=f"up_del2_{module_code}")
        v_appr = p6.checkbox("APPROVE", value=bool(cur.get("can_approve",0)), key=f"up_appr2_{module_code}")

        c1,c2 = st.columns(2)
        if c1.button("💾 Save Override", type="primary", key=f"up_save2_{module_code}"):
            user_obj = current_user()
            conn = get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO tbl_user_module_privileges
                    (user_id,module_code,sub_module,can_view,can_add,can_edit,
                     can_delete,can_approve,is_visible,granted_by,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,(uid2,module_code,sel_sub,
                 1 if v_view else 0, 1 if v_add else 0, 1 if v_edit else 0,
                 1 if v_del else 0, 1 if v_appr else 0, 1 if v_vis else 0,
                 user_obj.get("user_id"),_ist().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
            st.success(f"Override saved for {u_row2['full_name']} → {sel_sub}"); st.rerun()
        if c2.button("🗑 Remove Override", key=f"up_rem2_{module_code}"):
            conn = get_conn()
            conn.execute("DELETE FROM tbl_user_module_privileges WHERE user_id=? AND module_code=? AND sub_module=?",
                         (uid2, module_code, sel_sub))
            conn.commit(); conn.close()
            st.success("Override removed."); st.rerun()

    with tab3:
        sel_u3 = st.selectbox("Select User", list(u_opts.keys()), key=f"up_copy3_{module_code}")
        u_row3 = u_opts[sel_u3]
        if st.button(f"🔄 Copy {u_row3['role_name']} defaults to {u_row3['full_name']}",
                     type="primary", key=f"up_copybtn_{module_code}"):
            role_privs3 = [dict(r) for r in _fa(
                "SELECT * FROM tbl_role_module_privileges WHERE module_code=? AND role_name=?",
                (module_code, u_row3["role_name"]))]
            if not role_privs3:
                st.warning("No role privileges defined. Apply role defaults first."); return
            user_obj = current_user()
            conn = get_conn()
            for rp in role_privs3:
                conn.execute("""
                    INSERT OR REPLACE INTO tbl_user_module_privileges
                        (user_id,module_code,sub_module,can_view,can_add,can_edit,
                         can_delete,can_approve,is_visible,granted_by,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,(u_row3["user_id"],module_code,rp["sub_module"],
                     rp["can_view"],rp["can_add"],rp["can_edit"],rp["can_delete"],
                     rp["can_approve"],rp["is_visible"],
                     user_obj.get("user_id"),_ist().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
            st.success(f"Defaults copied to {u_row3['full_name']}."); st.rerun()


def _apply_role_defaults(module_code):
    """Apply default role privileges for all roles and sub-modules."""
    conn = get_conn()
    now  = _ist().strftime("%Y-%m-%d %H:%M:%S")
    for role_n, defaults in ROLE_DEFAULTS.items():
        visible_subs = ROLE_VISIBLE.get(role_n, [])
        for sub in SIMS_SUB_MODULES:
            is_vis = 1 if sub in visible_subs else 0
            conn.execute("""
                INSERT OR REPLACE INTO tbl_role_module_privileges
                    (module_code,role_name,sub_module,can_view,can_add,can_edit,
                     can_delete,can_approve,is_visible,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """,(module_code,role_n,sub,
                 defaults["can_view"] if is_vis else 0,
                 defaults["can_add"]  if is_vis else 0,
                 defaults["can_edit"] if is_vis else 0,
                 defaults["can_delete"]  if is_vis else 0,
                 defaults["can_approve"] if is_vis else 0,
                 is_vis, now))
    conn.commit(); conn.close()
