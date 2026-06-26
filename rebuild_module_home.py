"""
rebuild_module_home.py
Rebuilds pages/module_home.py from the original clean source at C:/SRGEC_SIMS/
and applies ALL required fixes in one shot:
1. Route raise_complaint to _tab_raise (duplicate prevention)
2. Fix closure_report routing to use call_report.show
3. Add cancel_calls menu entry and routing
"""

import os

# Read from original clean source
src = 'C:/SRGEC_SIMS/pages/module_home.py'
dst = 'pages/module_home.py'

if not os.path.exists(src):
    print(f"ERROR: Source not found: {src}")
    exit()

content = open(src, encoding='utf-8').read()
print(f"Source length: {len(content)}")

# Verify emojis are intact
if '🏠' in content:
    print("Emojis OK")
else:
    print("WARNING: Emojis not found in source")

changes = 0

# Fix 1: Route raise_complaint to _tab_raise
old1 = '        _raise_complaint_page(user, role, mod, mid)'
new1 = '        from pages.common_inbox import _tab_raise\n        _tab_raise(user, role, mod, mid)'
if old1 in content:
    content = content.replace(old1, new1, 1)
    print("Fix 1 applied: raise_complaint routed to _tab_raise")
    changes += 1
else:
    print("Fix 1: pattern not found - checking alternative...")
    idx = content.find('raise_complaint_page')
    if idx != -1:
        print("Context:", repr(content[idx-20:idx+60]))

# Fix 2: Fix closure_report routing
old2_marker = 'elif subpage == "closure_report":'
if old2_marker in content:
    start = content.find('    ' + old2_marker)
    end = content.find('\n    elif subpage == "warranty', start)
    if end == -1:
        end = content.find('\n    # ', start)
    old2_block = content[start:end]
    new2_block = '    elif subpage == "closure_report":\n        from pages.call_report import show as cr_show\n        cr_show(module_code)'
    content = content[:start] + new2_block + content[end:]
    print("Fix 2 applied: closure_report routing fixed")
    changes += 1
else:
    # Add it — find complaint_register routing block end
    marker = '_tab_register(user, role, mod, mid)\n\n    elif subpage == "spare_indent"'
    if marker in content:
        insert = '_tab_register(user, role, mod, mid)\n    elif subpage == "closure_report":\n        from pages.call_report import show as cr_show\n        cr_show(module_code)\n\n    elif subpage == "spare_indent"'
        content = content.replace(marker, insert, 1)
        print("Fix 2 applied: closure_report routing added")
        changes += 1
    else:
        print("Fix 2: Could not add closure_report routing")

# Fix 3: Add cancel_calls menu entry
if 'cancel_calls' not in content:
    old3 = 'pnav("📂  Complaint Register",    "complaint_register","Complaints — Complaint Register")'
    new3 = old3 + '\n        pnav("❌  Cancel / Manage Calls", "cancel_calls",     "Complaints — Cancel / Manage")'
    if old3 in content:
        content = content.replace(old3, new3, 1)
        print("Fix 3a applied: cancel_calls menu entry added")
        changes += 1
    else:
        print("Fix 3a: menu pattern not found")

    # Add cancel_calls routing
    route_marker = '_tab_register(user, role, mod, mid)\n\n    elif subpage == "raise_complaint"'
    if route_marker in content:
        new_route = '_tab_register(user, role, mod, mid)\n    elif subpage == "cancel_calls":\n        from pages.cancel_calls import show as cc_show\n        st.title("❌ Cancel / Manage Calls")\n        cc_show(module_code)\n\n    elif subpage == "raise_complaint"'
        content = content.replace(route_marker, new_route, 1)
        print("Fix 3b applied: cancel_calls routing added")
        changes += 1
    else:
        print("Fix 3b: routing pattern not found")
        idx = content.find('raise_complaint')
        print("Context:", repr(content[idx-100:idx+50]))
else:
    print("Fix 3: cancel_calls already present")
    changes += 1

print(f"\nTotal changes applied: {changes}")
print(f"cancel_calls occurrences: {content.count('cancel_calls')}")
print(f"closure_report occurrences: {content.count('closure_report')}")
print(f"_tab_raise occurrences: {content.count('_tab_raise')}")

# Write output
open(dst, 'w', encoding='utf-8').write(content)
print(f"\nWritten to {dst} ({len(content)} bytes)")
