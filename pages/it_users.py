"""pages/users.py — User Management + Role & Privileges Matrix (SysAdmin only)."""
import streamlit as st
import bcrypt
import pandas as pd
from datetime import datetime, timedelta
def _ist(): return (datetime.utcnow() + timedelta(hours=5, minutes=30))
from db import repository as repo
from db.connection import get_conn, fetchall as _fa, fetchone as _fo
from utils.auth import current_user, require_role
from utils.helpers import rows_to_df
from config import DB_PATH
from pathlib import Path


# ── Sub-modules list (all IT-IIMS pages) ──────────────────────────
IT_SUB_MODULES = [
    "Dashboard",
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

# Default privileges per role
ROLE_DEFAULTS = {
    "SysAdmin":  dict(can_view=1,can_add=1,can_edit=1,can_delete=1,can_approve=1,is_visible=1),
    "CSE-HoD":   dict(can_view=1,can_add=0,can_edit=0,can_delete=0,can_approve=1,is_visible=1),
    "HoD":       dict(can_view=1,can_add=0,can_edit=0,can_delete=0,can_approve=1,is_visible=1),
    "HW-Coord":  dict(can_view=1,can_add=1,can_edit=1,can_delete=0,can_approve=0,is_visible=1),
    "LAN-Staff": dict(can_view=1,can_add=1,can_edit=0,can_delete=0,can_approve=0,is_visible=1),
    "Lab-IC":    dict(can_view=1,can_add=1,can_edit=0,can_delete=0,can_approve=0,is_visible=1),
}

# Sub-modules visible per role by default
ROLE_VISIBLE = {
    "SysAdmin":  IT_SUB_MODULES,  # all
    "CSE-HoD":   ["Dashboard","Inventory — Asset Search & Edit","Stock — Central Stock",
                  "Stock — Department Stock","Procurement — Pending Approvals",
                  "Procurement — Log","Complaints — My Inbox","Complaints — Complaint Register",
                  "Complaints — Spare Parts Indent","Warranty — Alerts","Warranty — Expiring Soon",
                  "Reports","Account — Notifications","Account — Change Password"],
    "HoD":       ["Dashboard","Inventory — Asset Search & Edit","Stock — Department Stock",
                  "Procurement — Pending Approvals","Procurement — Log",
                  "Complaints — My Inbox","Complaints — Complaint Register",
                  "Complaints — Spare Parts Indent","Warranty — Alerts",
                  "Reports","Account — Notifications","Account — Change Password"],
    "HW-Coord":  ["Dashboard","Inventory — Asset Search & Edit","Stock — Central Stock",
                  "Stock — Department Stock","Procurement — Forward","Procurement — Joint Data Entry",
                  "Procurement — Log","Complaints — My Inbox","Complaints — Complaint Register",
                  "Complaints — Spare Parts Indent","Maintenance — Sheet",
                  "Maintenance — Asset Movement","Reports",
                  "Account — Notifications","Account — Change Password"],
    "LAN-Staff": ["Dashboard","Inventory — Asset Search & Edit","Stock — Department Stock",
                  "Complaints — Raise Complaint","Complaints — My Inbox",
                  "Complaints — Complaint Register","Complaints — Spare Parts Indent",
                  "Maintenance — Sheet","Account — Notifications","Account — Change Password"],
    "Lab-IC":    ["Dashboard","Inventory — Asset Search & Edit","Stock — Department Stock",
                  "Complaints — Raise Complaint","Complaints — My Inbox",
                  "Complaints — Complaint Register","Warranty — Alerts",
                  "Account — Notifications","Account — Change Password"],
}


def show():
    require_role("SysAdmin")
    user = current_user()

    # DB Backup expander
    with st.expander("🗄️ Database Backup & Statistics"):
        c1,c2 = st.columns(2)
        if c1.button("📥 Download DB Backup", type="primary", key="dl_db"):
            p = Path(DB_PATH)
            if p.exists():
                ts = _ist().strftime("%Y%m%d_%H%M%S")
                fname = f"iims_backup_{ts}.db"
                st.download_button(f"💾 Save {fname}", p.read_bytes(),
                                   file_name=fname,
                                   mime="application/octet-stream",
                                   key="dl_db_save")
                st.success(f"Ready — {p.stat().st_size//1024:.1f} KB")
            else:
                st.error("DB not found.")
        if c2.button("📊 DB Statistics", key="db_stats"):
            tables = [("tbl_assets","Assets"),("tbl_invoices","Invoices"),
                      ("tbl_central_stock_register","Central Stock"),
                      ("tbl_dept_stock_register","Dept Stock"),
                      ("tbl_call_register","Complaints"),
                      ("tbl_spare_parts_indent","Spare Parts"),
                      ("tbl_users","Users")]
            stats = []
            for tbl,lbl in tables:
                try:
                    cnt = _fo(f"SELECT COUNT(*) c FROM {tbl}")
                    stats.append({"Table":lbl,"Records":dict(cnt)["c"]})
                except: pass
            if stats:
                st.dataframe(pd.DataFrame(stats),use_container_width=True,hide_index=True)

    st.title("👥 User Management")

    tab1,tab2,tab3,tab4 = st.tabs([
        "👀 All Users",
        "➕ Create User",
        "🔐 Role Privileges Matrix",
        "👤 User Privileges",
    ])

    with tab1: _tab_all_users(user)
    with tab2: _tab_create_user(user)
    with tab3: _tab_role_matrix(user)
    with tab4: _tab_user_privileges(user)


# ══ TAB 1 — ALL USERS ════════════════════════════════════════════
def _tab_all_users(user):
    users = repo.get_all_users(include_inactive=True)
    df    = rows_to_df(users)
    if not df.empty:
        disp = ["user_id","full_name","username","employee_id",
                "role_name","dept_name","lab_name","email","phone","is_active","last_login"]
        st.dataframe(df[[c for c in disp if c in df.columns]],use_container_width=True)

    st.divider()
    st.subheader("✏️ Edit User")
    uid_edit = st.number_input("User ID to edit", min_value=1, step=1, key="eu_id")
    if st.button("Load User", key="eu_load"):
        st.session_state["edit_user_id"] = int(uid_edit)

    if "edit_user_id" in st.session_state:
        u = repo.get_user_by_id(st.session_state["edit_user_id"])
        if u:
            d      = dict(u)
            roles  = repo.get_roles()
            r_opts = {r["role_name"]: r["role_id"] for r in roles}
            depts  = repo.get_departments()
            d_opts = {"(None)": None}
            d_opts.update({d2["dept_name"]: d2["dept_id"] for d2 in depts})
            labs   = repo.get_labs()
            l_opts = {"(None)": None}
            l_opts.update({l["lab_name"]: l["lab_id"] for l in labs})

            with st.form("edit_user_form"):
                full_name = st.text_input("Full Name",  d["full_name"])
                role_sel  = st.selectbox("Role", list(r_opts.keys()),
                                         index=list(r_opts.values()).index(d["role_id"])
                                         if d["role_id"] in r_opts.values() else 0)
                dept_sel  = st.selectbox("Department", list(d_opts.keys()))
                lab_sel   = st.selectbox("Laboratory",  list(l_opts.keys()))
                email     = st.text_input("Email",  d.get("email","") or "")
                phone     = st.text_input("Phone",  d.get("phone","") or "")
                is_active = st.checkbox("Active",   value=bool(d["is_active"]))
                new_pw    = st.text_input("New Password (leave blank to keep)",type="password")
                if st.form_submit_button("💾 Save", type="primary"):
                    repo.update_user(d["user_id"],full_name,r_opts[role_sel],
                                     d_opts[dept_sel],l_opts[lab_sel],
                                     email,phone,1 if is_active else 0,
                                     user.get("user_id"))
                    if new_pw.strip():
                        h = bcrypt.hashpw(new_pw.encode(),bcrypt.gensalt()).decode()
                        repo.update_password(d["user_id"],h)
                    st.success("User updated.")
                    del st.session_state["edit_user_id"]
                    st.rerun()


# ══ TAB 2 — CREATE USER ══════════════════════════════════════════
def _tab_create_user(user):
    roles  = repo.get_roles()
    r_opts = {r["role_name"]: r["role_id"] for r in roles}
    depts  = repo.get_departments()
    d_opts = {"(None)": None}
    d_opts.update({d2["dept_name"]: d2["dept_id"] for d2 in depts})
    labs   = repo.get_labs()
    l_opts = {"(None)": None}
    l_opts.update({l["lab_name"]: l["lab_id"] for l in labs})

    with st.form("create_user_form"):
        username  = st.text_input("Username *")
        password  = st.text_input("Password *", type="password")
        full_name = st.text_input("Full Name *")
        emp_id    = st.text_input("Employee ID *")
        role_sel  = st.selectbox("Role *",        list(r_opts.keys()))
        dept_sel  = st.selectbox("Department",    list(d_opts.keys()))
        lab_sel   = st.selectbox("Laboratory",    list(l_opts.keys()))
        email     = st.text_input("Email")
        phone     = st.text_input("Phone")
        submitted = st.form_submit_button("➕ Create User", type="primary",
                                          use_container_width=True)

    if submitted:
        if not all([username.strip(),password.strip(),full_name.strip(),emp_id.strip()]):
            st.error("Username, Password, Full Name and Employee ID are required.")
        else:
            pw_hash = bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()
            try:
                new_id = repo.create_user(
                    username.strip(), pw_hash, full_name.strip(), emp_id.strip(),
                    r_opts[role_sel], d_opts[dept_sel], l_opts[lab_sel],
                    email or None, phone or None, user.get("user_id")
                )
                # Apply default role privileges for this new user
                _apply_role_defaults_to_user(new_id, role_sel)
                st.success(
                    f"User '{username}' created (ID: {new_id}). "
                    f"Default privileges for role '{role_sel}' applied."
                )
            except Exception as e:
                st.error(f"Error creating user: {e}")


# ══ TAB 3 — ROLE PRIVILEGES MATRIX ═══════════════════════════════
def _tab_role_matrix(user):
    st.info(
        "Define default privileges for each **Role**. "
        "These apply to all users with that role unless overridden individually in Tab 4."
    )

    roles_list = list(ROLE_DEFAULTS.keys())

    sub1, sub2 = st.tabs(["📋 View Matrix","✏️ Edit Role Privileges"])

    with sub1:
        # Load matrix
        matrix_rows = [dict(r) for r in _fa(
            "SELECT * FROM tbl_role_privileges ORDER BY role_name, sub_module")]
        if not matrix_rows:
            st.info("No role privileges defined yet. Use 'Edit Role Privileges' or apply defaults.")
            if st.button("⚡ Apply All Default Role Privileges", type="primary", key="apply_all_defaults"):
                _apply_all_role_defaults()
                st.success("Default role privileges applied for all roles.")
                st.rerun()
            return

        # Build pivot table
        rows = []
        lookup = {(r["role_name"],r["sub_module"]): r for r in matrix_rows}
        for sub in IT_SUB_MODULES:
            row = {"Sub-Module": sub}
            for role_n in roles_list:
                r = lookup.get((role_n,sub),{})
                if not r.get("is_visible",1):
                    row[role_n] = "🚫 Hidden"
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

        col1,col2 = st.columns(2)
        if col1.button("⚡ Re-apply All Defaults", key="reapply_defaults"):
            _apply_all_role_defaults()
            st.success("Defaults re-applied."); st.rerun()

        # Export
        import io
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        col2.download_button("📥 Export Matrix",buf.getvalue(),
                             "IT_IIMS_Role_Matrix.xlsx",
                             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with sub2:
        c1,c2 = st.columns(2)
        sel_role = c1.selectbox("Role", roles_list, key="rm_role")
        sel_sub  = c2.selectbox("Sub-Module", IT_SUB_MODULES, key="rm_sub")

        # Load current
        cur = _fo("SELECT * FROM tbl_role_privileges WHERE role_name=? AND sub_module=?",
                  (sel_role, sel_sub))
        cur = dict(cur) if cur else {}

        st.markdown(f"**Privileges for role `{sel_role}` on `{sel_sub}`:**")
        p1,p2,p3,p4,p5,p6 = st.columns(6)
        v_vis  = p1.checkbox("Visible",  value=bool(cur.get("is_visible",1)),  key="rm_vis")
        v_view = p2.checkbox("VIEW",     value=bool(cur.get("can_view",1)),    key="rm_view")
        v_add  = p3.checkbox("ADD",      value=bool(cur.get("can_add",0)),     key="rm_add")
        v_edit = p4.checkbox("EDIT",     value=bool(cur.get("can_edit",0)),    key="rm_edit")
        v_del  = p5.checkbox("DELETE",   value=bool(cur.get("can_delete",0)),  key="rm_del")
        v_appr = p6.checkbox("APPROVE",  value=bool(cur.get("can_approve",0)), key="rm_appr")

        if st.button("💾 Save Role Privilege", type="primary", key="rm_save"):
            conn = get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO tbl_role_privileges
                    (role_name,sub_module,can_view,can_add,can_edit,
                     can_delete,can_approve,is_visible,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """,(sel_role,sel_sub,
                 1 if v_view else 0, 1 if v_add else 0, 1 if v_edit else 0,
                 1 if v_del else 0, 1 if v_appr else 0, 1 if v_vis else 0,
                 _ist().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
            st.success(f"Privileges saved for {sel_role} → {sel_sub}.")
            st.rerun()


# ══ TAB 4 — USER PRIVILEGES (individual override) ════════════════
def _tab_user_privileges(user):
    st.info(
        "Override privileges for a **specific user** — overrides the role defaults. "
        "If no override exists, the user gets their role's default privileges."
    )

    all_users = repo.get_all_users(include_inactive=False)
    if not all_users: st.info("No users."); return

    u_opts = {f"{u['full_name']} ({u['username']} / {u['role_name']})": u
              for u in [dict(u) for u in all_users]}

    sub1,sub2,sub3 = st.tabs([
        "👁 View User Access",
        "✏️ Edit User Privileges",
        "🔄 Copy Role Defaults to User",
    ])

    with sub1:
        sel_u = st.selectbox("Select User", list(u_opts.keys()), key="up_view_sel")
        u_row = u_opts[sel_u]
        uid   = u_row["user_id"]

        # Show user's effective privileges
        user_privs = {dict(r)["sub_module"]: dict(r) for r in _fa(
            "SELECT * FROM tbl_user_privileges WHERE user_id=?", (uid,))}
        role_privs = {dict(r)["sub_module"]: dict(r) for r in _fa(
            "SELECT * FROM tbl_role_privileges WHERE role_name=?", (u_row["role_name"],))}

        rows = []
        for sub in IT_SUB_MODULES:
            # User override takes priority
            p = user_privs.get(sub) or role_privs.get(sub) or {}
            source = "👤 User Override" if sub in user_privs else "🔖 Role Default"
            visible = bool(p.get("is_visible",1))
            icons = ""
            if bool(p.get("can_view",1)):    icons += "👁 "
            if bool(p.get("can_add",0)):     icons += "➕ "
            if bool(p.get("can_edit",0)):    icons += "✏️ "
            if bool(p.get("can_delete",0)):  icons += "🗑 "
            if bool(p.get("can_approve",0)): icons += "✅ "
            rows.append({
                "Sub-Module":sub,
                "Visible":"✅" if visible else "🚫",
                "Privileges":icons.strip() or "👁",
                "Source":source,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with sub2:
        sel_u2 = st.selectbox("Select User", list(u_opts.keys()), key="up_edit_sel")
        u_row2 = u_opts[sel_u2]
        uid2   = u_row2["user_id"]

        sel_sub = st.selectbox("Sub-Module", IT_SUB_MODULES, key="up_sub")
        cur = _fo("SELECT * FROM tbl_user_privileges WHERE user_id=? AND sub_module=?",
                  (uid2, sel_sub))
        cur = dict(cur) if cur else {}

        # Fall back to role defaults if no user override
        if not cur:
            role_cur = _fo("SELECT * FROM tbl_role_privileges WHERE role_name=? AND sub_module=?",
                           (u_row2["role_name"], sel_sub))
            if role_cur: cur = dict(role_cur)

        st.markdown(f"**Override for `{u_row2['full_name']}` on `{sel_sub}`:**")
        p1,p2,p3,p4,p5,p6 = st.columns(6)
        v_vis  = p1.checkbox("Visible", value=bool(cur.get("is_visible",1)),  key="up_vis")
        v_view = p2.checkbox("VIEW",    value=bool(cur.get("can_view",1)),    key="up_view")
        v_add  = p3.checkbox("ADD",     value=bool(cur.get("can_add",0)),     key="up_add")
        v_edit = p4.checkbox("EDIT",    value=bool(cur.get("can_edit",0)),    key="up_edit")
        v_del  = p5.checkbox("DELETE",  value=bool(cur.get("can_delete",0)),  key="up_del")
        v_appr = p6.checkbox("APPROVE", value=bool(cur.get("can_approve",0)), key="up_appr")

        col1,col2 = st.columns(2)
        if col1.button("💾 Save Override", type="primary", key="up_save"):
            conn = get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO tbl_user_privileges
                    (user_id,role_name,sub_module,can_view,can_add,can_edit,
                     can_delete,can_approve,is_visible,granted_by,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,(uid2, u_row2["role_name"], sel_sub,
                 1 if v_view else 0, 1 if v_add else 0, 1 if v_edit else 0,
                 1 if v_del else 0, 1 if v_appr else 0, 1 if v_vis else 0,
                 user["user_id"], _ist().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
            st.success(f"Override saved for {u_row2['full_name']} → {sel_sub}.")
            st.rerun()

        if col2.button("🗑 Remove Override (use role default)", key="up_del_override"):
            conn = get_conn()
            conn.execute("DELETE FROM tbl_user_privileges WHERE user_id=? AND sub_module=?",
                         (uid2, sel_sub))
            conn.commit(); conn.close()
            st.success("Override removed. Role default will apply.")
            st.rerun()

    with sub3:
        st.info("Copies the role's default privileges to a specific user as overrides.")
        sel_u3 = st.selectbox("Select User", list(u_opts.keys()), key="up_copy_sel")
        u_row3 = u_opts[sel_u3]
        uid3   = u_row3["user_id"]
        role3  = u_row3["role_name"]

        st.markdown(f"Will copy **{role3}** role defaults to **{u_row3['full_name']}**")

        if st.button(f"🔄 Copy {role3} Defaults to {u_row3['full_name']}",
                     type="primary", key="up_copy_btn"):
            role_privs3 = [dict(r) for r in _fa(
                "SELECT * FROM tbl_role_privileges WHERE role_name=?", (role3,))]
            if not role_privs3:
                st.warning(f"No role privileges defined for '{role3}'. Apply role defaults first."); return
            conn = get_conn()
            count = 0
            for rp in role_privs3:
                conn.execute("""
                    INSERT OR REPLACE INTO tbl_user_privileges
                        (user_id,role_name,sub_module,can_view,can_add,can_edit,
                         can_delete,can_approve,is_visible,granted_by,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,(uid3,role3,rp["sub_module"],rp["can_view"],rp["can_add"],
                     rp["can_edit"],rp["can_delete"],rp["can_approve"],rp["is_visible"],
                     user["user_id"],_ist().strftime("%Y-%m-%d %H:%M:%S")))
                count += 1
            conn.commit(); conn.close()
            st.success(f"{count} privileges copied to {u_row3['full_name']}.")
            st.rerun()


# ── Helpers ───────────────────────────────────────────────────────
def _apply_all_role_defaults():
    """Apply default role privileges for all roles and all sub-modules."""
    conn = get_conn()
    now  = _ist().strftime("%Y-%m-%d %H:%M:%S")
    for role_n, defaults in ROLE_DEFAULTS.items():
        visible_subs = ROLE_VISIBLE.get(role_n, [])
        for sub in IT_SUB_MODULES:
            is_vis = 1 if sub in visible_subs else 0
            conn.execute("""
                INSERT OR REPLACE INTO tbl_role_privileges
                    (role_name,sub_module,can_view,can_add,can_edit,
                     can_delete,can_approve,is_visible,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """,(role_n, sub,
                 defaults["can_view"] if is_vis else 0,
                 defaults["can_add"]  if is_vis else 0,
                 defaults["can_edit"] if is_vis else 0,
                 defaults["can_delete"]  if is_vis else 0,
                 defaults["can_approve"] if is_vis else 0,
                 is_vis, now))
    conn.commit(); conn.close()


def _apply_role_defaults_to_user(user_id, role_name):
    """Apply role defaults to a newly created user."""
    role_privs = [dict(r) for r in _fa(
        "SELECT * FROM tbl_role_privileges WHERE role_name=?", (role_name,))]
    if not role_privs: return
    conn = get_conn()
    now  = _ist().strftime("%Y-%m-%d %H:%M:%S")
    for rp in role_privs:
        conn.execute("""
            INSERT OR REPLACE INTO tbl_user_privileges
                (user_id,role_name,sub_module,can_view,can_add,can_edit,
                 can_delete,can_approve,is_visible,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """,(user_id,role_name,rp["sub_module"],rp["can_view"],rp["can_add"],
             rp["can_edit"],rp["can_delete"],rp["can_approve"],rp["is_visible"],now))
    conn.commit(); conn.close()
