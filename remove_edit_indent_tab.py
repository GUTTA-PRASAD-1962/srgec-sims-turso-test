"""Remove Edit Indent from Spare Parts Indent tab - keep only in My Inbox"""

with open('pages/common_inbox.py', encoding='utf-8') as f:
    content = f.read()

old = '''    # Edit Indent — SysAdmin only, when complaint is at COST ESTIMATED (revised estimate requested)
    if role in ("SuperAdmin","SysAdmin") and call["call_status"] == "COST ESTIMATED" and parts:
        st.divider()
        st.markdown("#### Edit Spare Parts Indent (Revised Estimate)")
        st.caption("Update quantities and costs below, then forward the revised estimate to HEAD-UPS via My Inbox.")
        for p in parts:
            with st.expander(f"Edit: {p['description']}", expanded=True):
                c1,c2,c3,c4 = st.columns(4)
                new_desc = c1.text_input("Part", value=p["description"],
                                          key=f"ei_desc_{p['indent_id']}")
                new_qty  = c2.number_input("Qty", min_value=1, value=int(p["quantity"]),
                                            key=f"ei_qty_{p['indent_id']}")
                new_cost = c3.number_input("Unit Cost Rs.", min_value=0.0,
                                            value=float(p["cost_per_unit"]), step=10.0,
                                            key=f"ei_cost_{p['indent_id']}")
                new_src  = c4.text_input("Source/Vendor", value=p.get("source","") or "",
                                          key=f"ei_src_{p['indent_id']}")
                if st.button(f"Update this item", key=f"ei_save_{p['indent_id']}"):
                    try:
                        from db.connection import get_conn as _gc2
                        conn2 = _gc2()
                        conn2.execute("""
                            UPDATE tbl_spare_indent
                            SET description=?, quantity=?, cost_per_unit=?, total_cost=?, source=?
                            WHERE indent_id=?
                        """, (new_desc.strip(), new_qty, new_cost,
                              new_qty * new_cost, new_src.strip(), p["indent_id"]))
                        conn2.commit(); conn2.close()
                        st.success(f"Updated: {new_desc} x{new_qty} @ Rs.{new_cost}")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Failed: {ex}")

    st.divider()'''

new = '    st.divider()'

if old in content:
    content = content.replace(old, new, 1)
    with open('pages/common_inbox.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Removed Edit Indent from Spare Parts Indent tab")
else:
    print("Pattern not found")
    idx = content.find('Edit Indent')
    print("Context:", repr(content[idx-10:idx+100]))
