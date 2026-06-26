"""Wire cancel_calls into module_home.py navigation and routing."""

content = open('pages/module_home.py', encoding='utf-8').read()
original_len = len(content)

# Find the exact complaint register pnav line
import re

# Add menu entry after complaint_register pnav
if 'cancel_calls' in content:
    print("cancel_calls already wired - no changes needed")
else:
    # Find complaint register pnav line
    idx = content.find('"complaint_register","Complaints')
    if idx == -1:
        print("ERROR: complaint_register pnav not found")
        print("Searching for alternatives...")
        idx2 = content.find('complaint_register')
        print(f"Found 'complaint_register' at: {idx2}")
        print("Context:", repr(content[idx2-20:idx2+100]))
    else:
        # Find end of this line
        line_end = content.find('\n', idx)
        menu_insert = '\n        pnav("\u274c  Cancel / Manage Calls", "cancel_calls", "Complaints \u2014 Cancel / Manage")'
        content = content[:line_end] + menu_insert + content[line_end:]
        print("Menu entry added")

    # Add routing after complaint_register elif block
    route_marker = '_tab_register(user, role, mod, mid)\n    elif subpage == "spare_indent"'
    if route_marker in content:
        new_route = '_tab_register(user, role, mod, mid)\n    elif subpage == "cancel_calls":\n        from pages.cancel_calls import show as cc_show\n        st.title("\u274c Cancel / Manage Calls")\n        cc_show(module_code)\n    elif subpage == "spare_indent"'
        content = content.replace(route_marker, new_route, 1)
        print("Routing added")
    else:
        print("ERROR: route marker not found")
        idx3 = content.find('spare_indent')
        print("Context around spare_indent:", repr(content[idx3-100:idx3+50]))

    open('pages/module_home.py', 'w', encoding='utf-8').write(content)
    print(f"Done. File size: {original_len} -> {len(content)}")
    print("cancel_calls occurrences:", content.count('cancel_calls'))
