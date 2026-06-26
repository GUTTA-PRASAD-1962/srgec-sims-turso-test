"""
Remove Create User tab from module User Management.
Keep only All Users tab (with Edit/Deactivate/Delete) and Grant Access section.
Simple approach: change 2 tabs to 1 tab, move Grant Access into tab1.
"""

content = open('pages/common_admin.py', encoding='utf-8').read()

# Find the exact positions
tab_def_idx = content.find('    tab1, tab2 = st.tabs(')
tab1_with_idx = content.find('\n    with tab1:')
tab2_with_idx = content.find('\n    with tab2:')
next_def_idx = content.find('\ndef show_depts', tab2_with_idx)

print(f"tab_def at: {tab_def_idx}")
print(f"with tab1: at: {tab1_with_idx}")
print(f"with tab2: at: {tab2_with_idx}")
print(f"next def at: {next_def_idx}")

# Extract grant access section from tab2
tab2_block = content[tab2_with_idx:next_def_idx]
grant_start = tab2_block.find('\n        st.divider()\n        st.markdown("**Grant Module Access')
if grant_start == -1:
    # Try without warning
    grant_start = tab2_block.find('\n        st.markdown("**Grant Module Access')
    
print(f"Grant access start in tab2: {grant_start}")
grant_section = tab2_block[grant_start:]
print(f"Grant section length: {len(grant_section)}")
print(f"Grant section preview: {repr(grant_section[:80])}")

# Build new content:
# 1. Everything before tab_def line
tab_def_line_start = content.rfind('\n', 0, tab_def_idx)
before_tabs = content[:tab_def_line_start]

# 2. tab1 content only (no tab wrapper needed, already indented correctly)
tab1_block = content[tab1_with_idx:tab2_with_idx]
# Replace 'with tab1:' header line - remove it, keep content
tab1_content_lines = tab1_block.split('\n')
# Remove first two lines: empty line + "    with tab1:"
tab1_content = '\n'.join(tab1_content_lines[2:])

# 3. Grant access section (remove 4 spaces of tab2 indentation)
grant_lines = grant_section.split('\n')
grant_dedented = '\n'.join(
    line[4:] if line.startswith('        ') else line
    for line in grant_lines
)

# 4. Everything after tab2 block
after = content[next_def_idx:]

new_content = before_tabs + '\n' + tab1_content + grant_dedented + after

open('pages/common_admin.py', 'w', encoding='utf-8').write(new_content)
print(f"\nDone. New length: {len(new_content)} (was {len(content)})")
