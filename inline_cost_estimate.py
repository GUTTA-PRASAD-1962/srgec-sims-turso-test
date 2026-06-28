"""
Add inline cost estimation form in _call_detail when action is 'Prepare Cost Estimate'
or 'Forward Cost Estimate to HEAD-UPS'.
SysAdmin can fill costs/supplier directly without going to Spare Parts Indent tab.
"""

with open('pages/common_inbox.py', encoding='utf-8') as f:
    content = f.read()

# Find the action button section and add inline form before it
old = '''    if st.button(f"{sel_action}",type="primary",key=f"usub_{k}"):
        if comment_required and not comment.strip():
            st.error("Comments required for this action.")
            return
        try:
            conn = get_conn()
            new_status = rule["to_status"]'''

new = '''    # Inline cost estimation form for SysAdmin
    if sel_action in ("Prepare Cost Estimate", "Forward Cost Estimate to HEAD-UPS"):
        parts_to_edit = [dict(r) for r in _fa(
            "SELECT * FROM tbl_spare_indent WHERE call_id=? ORDER BY indent_id",
            (call["call_id"],))]
        if parts_to_edit:
            st.markdown("#### Update Cost Estimate")
            st.caption("Fill in costs and supplier details before submitting.")
            updated_parts = []
            for p in parts_to_edit:
                c1,c2,c3,c4 = st.columns(4)
                desc = c1.text_input("Part", value=p["description"],
                                      key=f"ce_desc_{k}_{p['indent_id']}")
                qty  = c2.number_input("Qty", min_value=1, value=int(p["quantity"]),
                                        key=f"ce_qty_{k}_{p['indent_id']}")
                cost = c3.number_input("Unit Cost Rs.", min_value=0.0,
                                        value=float(p["cost_per_unit"]) if float(p["cost_per_unit"]) > 0 else 0.0,
                                        step=100.0, key=f"ce_cost_{k}_{p['indent_id']}")
                src  = c4.text_input("Source/Vendor", value=p.get("source","") or "",
                                      key=f"ce_src_{k}_{p['indent_id']}")
                updated_parts.append({
                    "indent_id": p["indent_id"],
                    "desc": desc, "qty": qty, "cost": cost, "src": src
                })
            total = sum(p["qty"] * p["cost"] for p in updated_parts)
            st.markdown(f"**Grand Total: Rs.{total:,.2f}**")

    if st.button(f"{sel_action}",type="primary",key=f"usub_{k}"):
        if comment_required and not comment.strip():
            st.error("Comments required for this action.")
            return
        # Save cost estimate if applicable
        if sel_action in ("Prepare Cost Estimate", "Forward Cost Estimate to HEAD-UPS"):
            parts_to_save = [dict(r) for r in _fa(
                "SELECT * FROM tbl_spare_indent WHERE call_id=? ORDER BY indent_id",
                (call["call_id"],))]
            if parts_to_save:
                try:
                    conn2 = get_conn()
                    for p in parts_to_save:
                        new_desc = st.session_state.get(f"ce_desc_{k}_{p['indent_id']}", p["description"])
                        new_qty  = st.session_state.get(f"ce_qty_{k}_{p['indent_id']}", p["quantity"])
                        new_cost = st.session_state.get(f"ce_cost_{k}_{p['indent_id']}", p["cost_per_unit"])
                        new_src  = st.session_state.get(f"ce_src_{k}_{p['indent_id']}", p.get("source",""))
                        conn2.execute("""
                            UPDATE tbl_spare_indent
                            SET description=?, quantity=?, cost_per_unit=?, total_cost=?, source=?
                            WHERE indent_id=?
                        """, (new_desc, new_qty, new_cost, new_qty*new_cost, new_src, p["indent_id"]))
                    conn2.commit(); conn2.close()
                except Exception:
                    pass  # Cost save is best-effort
        try:
            conn = get_conn()
            new_status = rule["to_status"]'''

if old in content:
    content = content.replace(old, new, 1)
    with open('pages/common_inbox.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Inline cost estimation form added")
else:
    print("Pattern not found")
    idx = content.find('if st.button(f"{sel_action}"')
    print("Context:", repr(content[idx:idx+100]))
