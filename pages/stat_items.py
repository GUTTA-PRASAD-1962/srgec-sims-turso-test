"""
pages/stat_items.py — Stationery Item Master Management (SuperAdmin)
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access


def _ist():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")


def show(module_code):
    role = require_module_access(module_code)
    user = current_user()
    mod = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod:
        st.error("Module not found.")
        return
    mod = dict(mod)
    mid = mod["module_id"]

    if role not in ("SuperAdmin", "SysAdmin"):
        st.warning("Item Master is for SuperAdmin / SysAdmin only.")
        return

    st.subheader("Stationery Item Master")

    if st.session_state.get(f"_item_msg_{mid}"):
        t, m = st.session_state.pop(f"_item_msg_{mid}")
        (st.success if t == "s" else st.error)(m)

    with st.expander("All Items", expanded=True):
        items = [dict(r) for r in _fa(
            "SELECT * FROM tbl_stat_items WHERE module_id=? ORDER BY item_name", (mid,)
        )]
        if items:
            df = pd.DataFrame([{
                "ID": it["item_id"], "Item": it["item_name"],
                "Specification": it.get("specification", "-"),
                "Unit": it["unit_of_measure"],
                "Active": "Yes" if it["is_active"] else "No",
            } for it in items])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No items configured yet.")

    with st.expander("Add New Item"):
        c1, c2, c3 = st.columns(3)
        new_name = c1.text_input("Item Name *", key=f"{mid}_new_item_name")
        new_spec = c2.text_input("Specification", key=f"{mid}_new_item_spec")
        new_unit = c3.selectbox("Unit *", ["BOXES", "PACKETS", "NUMBERS", "REELS"],
                                 key=f"{mid}_new_item_unit")
        if st.button("Add Item", type="primary", key=f"{mid}_add_item_btn"):
            if not new_name.strip():
                st.error("Item name is required.")
            else:
                try:
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO tbl_stat_items
                            (module_id, item_name, specification, unit_of_measure, is_active, created_at)
                        VALUES (?, ?, ?, ?, 1, ?)
                    """, (mid, new_name.strip(), new_spec.strip(), new_unit, _ist()))
                    conn.commit()
                    conn.close()
                    st.session_state[f"_item_msg_{mid}"] = ("s", f"Item '{new_name}' added.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed: {ex}")

    with st.expander("Edit / Deactivate Item"):
        if not items:
            st.info("No items to edit.")
        else:
            item_opts = {f"{it['item_name']} ({it.get('specification','-')})": it for it in items}
            sel_label = st.selectbox("Select item", list(item_opts.keys()), key=f"{mid}_edit_item_sel")
            sel_item = item_opts[sel_label]
            c1, c2, c3 = st.columns(3)
            ed_name = c1.text_input("Item Name", value=sel_item["item_name"], key=f"{mid}_ed_name")
            ed_spec = c2.text_input("Specification", value=sel_item.get("specification", "") or "",
                                     key=f"{mid}_ed_spec")
            ed_unit = c3.selectbox("Unit", ["BOXES", "PACKETS", "NUMBERS", "REELS"],
                                    index=["BOXES", "PACKETS", "NUMBERS", "REELS"].index(
                                        sel_item["unit_of_measure"]) if sel_item["unit_of_measure"] in
                                        ["BOXES", "PACKETS", "NUMBERS", "REELS"] else 0,
                                    key=f"{mid}_ed_unit")
            ed_active = st.checkbox("Active", value=bool(sel_item["is_active"]), key=f"{mid}_ed_active")
            if st.button("Save Changes", type="primary", key=f"{mid}_ed_save"):
                try:
                    conn = get_conn()
                    conn.execute("""
                        UPDATE tbl_stat_items
                        SET item_name=?, specification=?, unit_of_measure=?, is_active=?
                        WHERE item_id=?
                    """, (ed_name.strip(), ed_spec.strip(), ed_unit,
                          1 if ed_active else 0, sel_item["item_id"]))
                    conn.commit()
                    conn.close()
                    st.session_state[f"_item_msg_{mid}"] = ("s", f"Item '{ed_name}' updated.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed: {ex}")
