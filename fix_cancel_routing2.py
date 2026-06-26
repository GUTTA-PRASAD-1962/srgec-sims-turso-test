"""Add routing for cancel_calls to module_home.py."""

content = open('pages/module_home.py', encoding='utf-8').read()

# Check if routing specifically exists (not just menu entry)
if 'elif subpage == "cancel_calls"' in content:
    print("Routing already exists")
else:
    # Find the complaint_register routing block end
    # It ends with: _tab_register(user, role, mod, mid)\n\n    elif subpage == "raise_complaint"
    marker = '_tab_register(user, role, mod, mid)\n\n    elif subpage == "raise_complaint"'
    if marker in content:
        insert = '_tab_register(user, role, mod, mid)\n    elif subpage == "cancel_calls":\n        from pages.cancel_calls import show as cc_show\n        st.title("\u274c Cancel / Manage Calls")\n        cc_show(module_code)\n\n    elif subpage == "raise_complaint"'
        content = content.replace(marker, insert, 1)
        open('pages/module_home.py', 'w', encoding='utf-8').write(content)
        print("Routing added successfully")
        print("cancel_calls occurrences:", content.count('cancel_calls'))
    else:
        print("ERROR: marker not found")
        idx = content.find('_tab_register(user, role, mod, mid)')
        print("Context:", repr(content[idx:idx+100]))
