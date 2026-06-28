"""Update common_admin.py and superadmin.py to use tbl_sims_roles"""

# Fix common_admin.py - load roles from tbl_sims_roles
content = open('pages/common_admin.py', encoding='utf-8').read()
count = 0

# Fix 1: Edit User role dropdown
old1 = '                _fixed = ["SuperAdmin","SysAdmin","HoD","HEAD-UPS","Coordinator","Technician","Lab-IC","User"]\n                _dyn = [dict(r)["role_name"] for r in _fa("SELECT DISTINCT role_name FROM tbl_user_module_access ORDER BY role_name")]\n                role_options = _fixed + [r for r in _dyn if r not in _fixed]'
new1 = '                role_options = [dict(r)["role_name"] for r in _fa("SELECT role_name FROM tbl_sims_roles ORDER BY is_system DESC, role_name")]'
if old1 in content:
    content = content.replace(old1, new1, 1)
    print("Fix 1 applied: Edit User dropdown uses tbl_sims_roles")
    count += 1

# Fix 2: Grant Access role dropdown
old2 = '        _ga_base = ["SysAdmin","HoD","HEAD-UPS","Coordinator","Technician","Lab-IC","User"]\n        _ga_dyn = [dict(r)["role_name"] for r in _fa("SELECT DISTINCT role_name FROM tbl_user_module_access ORDER BY role_name")]\n        sel_r = g2.selectbox("Role", _ga_base + [r for r in _ga_dyn if r not in _ga_base], key=f"{mid}_ga_role")'
new2 = '        _ga_roles = [dict(r)["role_name"] for r in _fa("SELECT role_name FROM tbl_sims_roles WHERE role_name != \'SuperAdmin\' ORDER BY is_system DESC, role_name")]\n        sel_r = g2.selectbox("Role", _ga_roles, key=f"{mid}_ga_role")'
if old2 in content:
    content = content.replace(old2, new2, 1)
    print("Fix 2 applied: Grant Access dropdown uses tbl_sims_roles")
    count += 1

# Fix 3: Create User role dropdown
old3 = '                                    (lambda f,d: f+[r for r in d if r not in f])(["SysAdmin","HoD","HEAD-UPS","Coordinator","Technician","Lab-IC","User"],[dict(r)["role_name"] for r in _fa("SELECT DISTINCT role_name FROM tbl_user_module_access ORDER BY role_name")]))'
new3 = '                                    [dict(r)["role_name"] for r in _fa("SELECT role_name FROM tbl_sims_roles WHERE role_name != \'SuperAdmin\' ORDER BY is_system DESC, role_name")])'
if old3 in content:
    content = content.replace(old3, new3, 1)
    print("Fix 3 applied: Create User dropdown uses tbl_sims_roles")
    count += 1

open('pages/common_admin.py', 'w', encoding='utf-8').write(content)
print(f"common_admin.py: {count} fixes applied")

# Fix superadmin.py - Register New Role saves to tbl_sims_roles
content2 = open('pages/superadmin.py', encoding='utf-8').read()

old4 = '''    if st.button("Register Role", type="primary", key="sa_nr_submit"):
        if not new_role_name.strip():
            st.error("Role name is required.")
        elif new_role_name.strip() in all_roles:
            st.warning(f"Role \'{new_role_name.strip()}\' already exists in the system.")
        else:
            new_r = new_role_name.strip()
            st.success(f"Role name **\'{new_r}\'** is ready to use.")
            st.info(
                f"Next steps to activate **\'{new_r}\'**:\\n"
                f"1. Go to **Administration → User Management** → Edit a user → set their Module Role to **\'{new_r}\'**\\n"
                f"2. Go to **Super Admin → Workflow Rules** → add **\'{new_r}\'** to the allowed_roles of relevant workflow steps\\n"
                f"3. Optionally go to **Administration → Role & Privileges** → configure what this role can see"
            )'''

new4 = '''    if st.button("Register Role", type="primary", key="sa_nr_submit"):
        if not new_role_name.strip():
            st.error("Role name is required.")
        elif new_role_name.strip() in all_roles:
            st.warning(f"Role \'{new_role_name.strip()}\' already exists in the system.")
        else:
            new_r = new_role_name.strip()
            try:
                conn = get_conn()
                conn.execute("INSERT OR IGNORE INTO tbl_sims_roles (role_name, is_system) VALUES (?, 0)", (new_r,))
                conn.commit(); conn.close()
                st.success(f"Role **\'{new_r}\'** registered successfully.")
                st.info(
                    f"Next steps to activate **\'{new_r}\'**:\\n"
                    f"1. Go to **Administration → User Management** → assign this role to a user\\n"
                    f"2. Go to **Super Admin → Workflow Rules** → add **\'{new_r}\'** to relevant workflow steps\\n"
                    f"3. Optionally configure Role & Privileges for this role"
                )
                st.rerun()
            except Exception as ex:
                st.error(f"Failed: {ex}")'''

if old4 in content2:
    content2 = content2.replace(old4, new4, 1)
    open('pages/superadmin.py', 'w', encoding='utf-8').write(content2)
    print("superadmin.py: Register Role now saves to tbl_sims_roles")
else:
    print("superadmin.py: pattern not found")
    idx = content2.find('Register Role')
    print("Context:", repr(content2[idx:idx+100]))
