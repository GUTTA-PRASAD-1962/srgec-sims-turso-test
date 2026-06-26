"""
Rebuild show_users() in common_admin.py with clean expander-based UI.
No tabs, no emojis in section headers, no Create User.
Sections: Users List, Edit User, Grant Module Access, DB Backup (SysAdmin only)
"""

content = open('pages/common_admin.py', encoding='utf-8').read()

# Find show_users function boundaries
start = content.find('\ndef show_users(module_code):')
end = content.find('\ndef show_depts(', start)

print(f"show_users: {start} to {end}")

new_show_users = '''
def show_users(module_code):
    """User Management - expander-based UI"""
    role = require_module_access(module_code)
    user = current_user()
    is_super = bool(int(user.get("is_super_admin") or 0))
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: return
    mod  = dict(mod); mid = mod["module_id"]
    if st.session_state.get(f"_admin_msg_{mid}"):
        t,m = st.session_state.pop(f"_admin_msg_{mid}")
        (st.success if t=="s" else st.error)(m)

    # -- DB Backup (SysAdmin only) --
    if role in ("SuperAdmin","SysAdmin") and is_super:
        with st.expander("Database Backup & Statistics"):
            from config import DB_PATH
            from pathlib import Path
            c1,c2 = st.columns(2)
            if c1.button("Download DB Backup", type="primary", key=f"{mid}_db_backup"):
                p = Path(DB_PATH)
                if p.exists():
                    ts = _ist().strftime("%Y%m%d_%H%M%S")
                    st.download_button(
                        f"Save sims_backup_{ts}.db", p.read_bytes(),
                        file_name=f"sims_backup_{ts}.db",
                        mime="application/octet-stream",
                        key=f"{mid}_db_dl")
                else: st.error("DB file not found.")
            if c2.button("DB Statistics", key=f"{mid}_db_stats"):
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

    # -- Users List --
    with st.expander("All Users in this Module", expanded=True):
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
                "Department":u.get("dept_name","-"),"Email":u.get("email","-"),
                "Active":"Yes" if u["is_active"] else "No",
                "Last Login":str(u.get("last_login",""))[:16],
            } for u in users])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No users assigned to this module yet.")

    # -- Edit User --
    with st.expander("Edit User"):
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
                                        index=role_options.index(cur_role_name) if cur_role_name in role_options else 0)
                    d_sel= st.selectbox("Department", list(dm.keys()),
                                        index=list(dm.values()).index(eu.get("dept_id")) if eu.get("dept_id") in dm.values() else 0)
                    email= st.text_input("Email",  eu.get("email","") or "")
                    phone= st.text_input("Phone",  eu.get("phone","") or "")
                    act  = st.checkbox("Active", value=bool(eu["is_active"]))
                    npw  = st.text_input("New Password (leave blank to keep)", type="password")
                    if st.form_submit_button("Save", type="primary"):
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
                            st.session_state[f"_admin_msg_{mid}"] = ("s","User updated.")
                            del st.session_state[f"edit_uid_{mid}"]
                            st.rerun()
                        except Exception as ex: st.error(str(ex)); conn.close()
                st.divider()
                st.markdown("#### Delete / Deactivate User")
                if eu["user_id"] == user.get("user_id"):
                    st.warning("You cannot delete or deactivate your own account.")
                else:
                    st.caption(
                        "Deactivate disables login but keeps history (recommended). "
                        "Delete permanently removes the user record."
                    )
                    dcol1, dcol2 = st.columns(2)
                    if eu["is_active"]:
                        if dcol1.button("Deactivate User", key=f"{mid}_deact_user"):
                            conn = get_conn()
                            conn.execute("UPDATE tbl_users SET is_active=0 WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.commit(); conn.close()
                            st.session_state[f"_admin_msg_{mid}"] = ("s",f"User '{eu['username']}' deactivated.")
                            st.rerun()
                    else:
                        if dcol1.button("Reactivate User", key=f"{mid}_react_user"):
                            conn = get_conn()
                            conn.execute("UPDATE tbl_users SET is_active=1 WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.commit(); conn.close()
                            st.session_state[f"_admin_msg_{mid}"] = ("s",f"User '{eu['username']}' reactivated.")
                            st.rerun()
                    confirm_del = dcol2.checkbox(
                        f"Confirm permanent deletion of '{eu['username']}'",
                        key=f"{mid}_confirm_del_user"
                    )
                    if dcol2.button("Delete Permanently", type="primary",
                                    key=f"{mid}_del_user", disabled=not confirm_del):
                        conn = get_conn()
                        try:
                            conn.execute("DELETE FROM tbl_user_module_access WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.execute("DELETE FROM tbl_users WHERE user_id=?",
                                         (eu["user_id"],))
                            conn.commit(); conn.close()
                            st.session_state[f"_admin_msg_{mid}"] = ("s",f"User '{eu['username']}' permanently deleted.")
                            del st.session_state[f"edit_uid_{mid}"]
                            st.rerun()
                        except Exception as ex:
                            conn.close()
                            st.error(
                                f"Cannot delete: {ex}. This user likely has "
                                "linked records. Use Deactivate instead."
                            )

    # -- Grant Module Access --
    with st.expander("Grant Module Access to Existing User"):
        st.caption("Assign an existing system user to this module with a specific role.")
        g1,g2,g3 = st.columns(3)
        all_u = [dict(r) for r in _fa("SELECT user_id,full_name,username FROM tbl_users WHERE is_active=1 ORDER BY full_name")]
        sel_u = g1.selectbox("User",[f"{u['full_name']} ({u['username']})" for u in all_u],key=f"{mid}_ga_user")
        _ga_roles = [dict(r)["role_name"] for r in _fa("SELECT role_name FROM tbl_sims_roles WHERE role_name != 'SuperAdmin' ORDER BY is_system DESC, role_name")]
        sel_r = g2.selectbox("Role", _ga_roles, key=f"{mid}_ga_role")
        if g3.button("Grant Access", key=f"{mid}_ga_save"):
            idx = [f"{u['full_name']} ({u['username']})" for u in all_u].index(sel_u)
            uid = all_u[idx]["user_id"]
            conn = get_conn()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO tbl_user_module_access
                        (user_id,module_id,role_name,is_active,granted_at)
                    VALUES (?,(SELECT module_id FROM tbl_modules WHERE module_code=?),?,1,?)
                """,(uid,module_code,sel_r,_ist().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit(); conn.close()
                st.session_state[f"_admin_msg_{mid}"] = ("s","Access granted successfully.")
                st.rerun()
            except Exception as ex: st.error(str(ex)); conn.close()

'''

# Replace the old show_users function
new_content = content[:start] + new_show_users + content[end:]
open('pages/common_admin.py', 'w', encoding='utf-8').write(new_content)
print(f"Done. New length: {len(new_content)}")
