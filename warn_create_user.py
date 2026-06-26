"""Add warning to Create User tab directing users to SuperAdmin panel"""

content = open('pages/common_admin.py', encoding='utf-8').read()

# Find start of tab2 content
old = '    with tab2:\n        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]'
new = '    with tab2:\n        st.warning(\n            "Creating users here also creates them system-wide. "\n            "It is recommended to create users in the **Super Admin Panel** "\n            "(accessible from the main dashboard) and then use **Grant Module Access** below "\n            "to assign them to this module. This avoids duplicate user errors."\n        )\n        st.divider()\n        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]'

if old in content:
    content = content.replace(old, new, 1)
    open('pages/common_admin.py', 'w', encoding='utf-8').write(content)
    print("Warning added to Create User tab")
else:
    print("Pattern not found")
    idx = content.find('with tab2:')
    print("Context:", repr(content[idx:idx+120]))
