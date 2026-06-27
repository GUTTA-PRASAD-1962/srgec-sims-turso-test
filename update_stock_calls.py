"""Update module_home.py calls to pass user/role to stock functions"""

with open('pages/module_home.py', encoding='utf-8') as f:
    content = f.read()

count = 0
fixes = [
    # Central Stock tab calls
    ('            with tab4: _view_stock(m)\n            with tab5: _asset_search(m)\n            with tab6: _edit_delete(user, m)\n            with tab7: _dept_view(m)',
     '            with tab4: _view_stock(m, user, role)\n            with tab5: _asset_search(m, user, role)\n            with tab6: _edit_delete(user, m)\n            with tab7: _dept_view(m, user, role)'),
    # Non-admin Central Stock calls
    ('            with tab1: _view_stock(m)\n            with tab2: _asset_search(m)',
     '            with tab1: _view_stock(m, user, role)\n            with tab2: _asset_search(m, user, role)'),
    # Dept Stock tab calls
    ('        with tab1: _dept_stock(m)\n        with tab2: _dept_view(m)',
     '        with tab1: _dept_stock(m, user, role)\n        with tab2: _dept_view(m, user, role)'),
    # Asset search standalone calls
    ('        from pages.common_stock import _asset_search, _get_module\n        m = _get_module(mc)\n        st.title(f"{icon} {name} \u2014 Asset Search & Edit")\n        _asset_search(m)',
     '        from pages.common_stock import _asset_search, _get_module\n        m = _get_module(mc)\n        st.title(f"{icon} {name} \u2014 Asset Search & Edit")\n        _asset_search(m, user, role)'),
    ('        from pages.common_stock import _asset_search, _get_module\n        m = _get_module(mc)\n        st.title(f"{icon} {name} \u2014 Case Sheets")\n        _asset_search(m)',
     '        from pages.common_stock import _asset_search, _get_module\n        m = _get_module(mc)\n        st.title(f"{icon} {name} \u2014 Case Sheets")\n        _asset_search(m, user, role)'),
]

for old, new in fixes:
    if old in content:
        content = content.replace(old, new, 1)
        print(f"Fixed: {old[:60]}...")
        count += 1
    else:
        print(f"Not found: {old[:60]}...")

with open('pages/module_home.py', 'w', encoding='utf-8') as f:
    f.write(content)
print(f"\nTotal: {count} fixes applied")
