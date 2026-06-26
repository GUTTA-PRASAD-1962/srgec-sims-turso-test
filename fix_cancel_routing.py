"""Add routing for cancel_calls to module_home.py."""

content = open('pages/module_home.py', encoding='utf-8').read()

# Find the exact context after complaint_register routing
idx = content.find('_tab_register(user, role, m')
if idx == -1:
    print("ERROR: _tab_register call not found")
else:
    print("Context:", repr(content[idx:idx+120]))
    # Find end of this elif block
    line_end = content.find('\n', idx)
    next_elif = content.find('\n    elif', line_end)
    print("Block end context:", repr(content[line_end:next_elif+20]))
    
    # Insert cancel_calls routing after the complaint_register block
    insert = '\n    elif subpage == "cancel_calls":\n        from pages.cancel_calls import show as cc_show\n        st.title("\u274c Cancel / Manage Calls")\n        cc_show(module_code)'
    
    if 'cancel_calls' in content:
        print("cancel_calls routing already exists")
    else:
        content = content[:next_elif] + insert + content[next_elif:]
        open('pages/module_home.py', 'w', encoding='utf-8').write(content)
        print("Routing added successfully")
        print("cancel_calls occurrences:", content.count('cancel_calls'))
