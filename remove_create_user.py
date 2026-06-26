"""Remove Create User tab from module User Management, keep Grant Access in tab1"""

content = open('pages/common_admin.py', encoding='utf-8').read()

# Step 1: Change tabs definition from 2 tabs to 1 tab
old_tabs = '    tab1, tab2 = st.tabs(["'
# Find the exact line
idx = content.find('    tab1, tab2 = st.tabs(["\U0001f440 All Users"')
if idx == -1:
    idx = content.find('tab1, tab2 = st.tabs(')
    # Find end of this line
    line_end = content.find('\n', idx)
    old_tab_line = content[idx:line_end]
    print("Found tab line:", repr(old_tab_line))
    new_tab_line = '    with True:'  # placeholder
else:
    print("Found exact tab line")

# Let's just do a targeted replacement
# Change: tab1, tab2 = st.tabs([...])  with tab1: ... with tab2: ...
# To: just the content without tabs wrapping

# Find start of tab1 and tab2 blocks
tab1_start = content.find('\n    with tab1:')
tab2_start = content.find('\n    with tab2:')
# Find end of tab2 block (next def at same indentation level)
next_def = content.find('\ndef show_depts', tab2_start)

tab1_content = content[tab1_start:tab2_start]
tab2_content = content[tab2_start:next_def]

print("tab1 length:", len(tab1_content))
print("tab2 length:", len(tab2_content))
print("tab2 preview:", repr(tab2_content[:100]))

# Extract: from tab2, only keep Grant Access section (not Create User form)
grant_access_start = tab2_content.find('\n        st.divider()\n        st.markdown("**Grant Module Access')
if grant_access_start == -1:
    print("ERROR: Grant Access section not found in tab2")
else:
    grant_access_content = tab2_content[grant_access_start:]
    print("Grant Access content found, length:", len(grant_access_content))
    
    # Remove the tabs wrapper and merge
    # tab line to remove
    tab_line_start = content.rfind('\n    tab1, tab2 = st.tabs(', 0, tab1_start)
    tab_line_end = content.find('\n', tab_line_start + 1)
    
    # Build new content:
    # 1. Everything before the tab line
    # 2. tab1 content (dedented by 4 spaces)  
    # 3. Grant Access section (dedented by 4 spaces)
    # 4. Everything after tab2 block
    
    before = content[:tab_line_start]
    
    # Dedent tab1 content (remove leading 4 spaces per line)
    tab1_dedented = '\n'.join(
        line[4:] if line.startswith('    ') else line 
        for line in tab1_content.split('\n')
    )
    
    # Dedent grant access content
    grant_dedented = '\n'.join(
        line[4:] if line.startswith('    ') else line
        for line in grant_access_content.split('\n')
    )
    
    after = content[next_def:]
    
    new_content = before + tab1_dedented + grant_dedented + after
    
    open('pages/common_admin.py', 'w', encoding='utf-8').write(new_content)
    print("Done - file written")
    print("New length:", len(new_content))
