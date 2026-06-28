"""Add inline spare parts form when Technician clicks 'Raise Spare Parts Indent' in My Inbox"""

with open('pages/common_inbox.py', encoding='utf-8') as f:
    content = f.read()

# Add inline spare parts form alongside the cost estimate form
old = '''    # Inline cost estimation form for SysAdmin
    if sel_action in ("Prepare Cost Estimate", "Forward Cost Estimate to HEAD-UPS"):'''

new = '''    # Inline spare parts form for Technician
    if sel_action == "Raise Spare Parts Indent":
        st.markdown("#### Spare Parts Required")
        st.caption("Enter the parts needed for repair. This will be sent to the coordinator for cost estimation.")
        n_parts = st.number_input("Number of parts required", min_value=1, max_value=20, value=1,
                                   key=f"sp_n_{k}")
        sp_items = []
        for i in range(int(n_parts)):
            st.markdown(f"**Part {i+1}**")
            sp1,sp2,sp3 = st.columns(3)
            sp_desc = sp1.text_input("Part Description *", key=f"sp_desc_{k}_{i}",
                                      placeholder="e.g. Battery 12V 7Ah")
            sp_qty  = sp2.number_input("Quantity", min_value=1, value=1, key=f"sp_qty_{k}_{i}")
            sp_src  = sp3.text_input("Source/Vendor", key=f"sp_src_{k}_{i}",
                                      placeholder="e.g. Local market")
            sp_items.append({"desc": sp_desc, "qty": sp_qty, "src": sp_src})

    # Inline cost estimation form for SysAdmin
    if sel_action in ("Prepare Cost Estimate", "Forward Cost Estimate to HEAD-UPS"):'''

if old in content:
    content = content.replace(old, new, 1)
    print("Fix 1 applied: inline spare parts form added")
else:
    print("Fix 1: pattern not found")

# Now add the save logic in the submit handler
old2 = '''        # Save cost estimate if applicable
        if sel_action in ("Prepare Cost Estimate", "Forward Cost Estimate to HEAD-UPS"):'''

new2 = '''        # Save spare parts indent if applicable
        if sel_action == "Raise Spare Parts Indent":
            sp_items_to_save = []
            n = st.session_state.get(f"sp_n_{k}", 1)
            for i in range(int(n)):
                desc = st.session_state.get(f"sp_desc_{k}_{i}", "").strip()
                qty  = st.session_state.get(f"sp_qty_{k}_{i}", 1)
                src  = st.session_state.get(f"sp_src_{k}_{i}", "").strip()
                if desc:
                    sp_items_to_save.append({"desc": desc, "qty": qty, "src": src})
            if not sp_items_to_save:
                st.error("Please enter at least one part description.")
                return
            try:
                conn3 = get_conn()
                for it in sp_items_to_save:
                    conn3.execute("""
                        INSERT INTO tbl_spare_indent
                            (module_id, call_id, prepared_by, description, quantity,
                             cost_per_unit, total_cost, source, indent_status)
                        VALUES (?, ?, ?, ?, ?, 0, 0, ?, 'PENDING')
                    """, (mid, call["call_id"], user["user_id"],
                          it["desc"], it["qty"], it["src"]))
                conn3.commit(); conn3.close()
            except Exception as ex:
                st.error(f"Failed to save parts: {ex}")
                return

        # Save cost estimate if applicable
        if sel_action in ("Prepare Cost Estimate", "Forward Cost Estimate to HEAD-UPS"):'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("Fix 2 applied: spare parts save logic added")
else:
    print("Fix 2: pattern not found")
    idx = content.find('Save cost estimate')
    print("Context:", repr(content[idx-20:idx+100]))

with open('pages/common_inbox.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
