"""
pages/stat_stock.py v2 — Quantity-based Stock Register for Stationery (SRGEC-SIMS)

CENTRAL STOCK (SysAdmin/SuperAdmin/OS/Principal/StatIncharge can VIEW):
  - New Procurement Entry (SysAdmin/StatIncharge)
  - Bulk Upload (SysAdmin/StatIncharge) — pre-filled template
  - View Central Stock (all authorized)
  - Item Detail Search with dropdown
  - Edit/Delete Entries (SysAdmin only) — shows existing qty
  NOTE: Issue to Department removed — issuing happens via indent only

DEPARTMENT STOCK (Junior Assistant — own dept only):
  - View Department Stock
  - Category Summary
  - Record Consumption (items issued/used → deducts from dept stock)
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user


def _ist():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")


def _get_module(module_code):
    return dict(_fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,)))


def _get_central_stock_map(mid):
    """Returns {item_id: {qty, unit, stock_id}} for all central stock items."""
    rows = [dict(r) for r in _fa("""
        SELECT cs.stock_id, cs.item_id, cs.quantity, cs.unit
        FROM tbl_stat_central_stock cs
        WHERE cs.item_id IN (SELECT item_id FROM tbl_stat_items WHERE module_id=?)
    """, (mid,))]
    return {r["item_id"]: r for r in rows}


def _get_dept_stock_map(dept_id):
    """Returns {item_id: {qty, unit, dept_stock_id}} for a department's stock."""
    rows = [dict(r) for r in _fa("""
        SELECT dept_stock_id, item_id, quantity, unit
        FROM tbl_stat_dept_stock WHERE dept_id=?
    """, (dept_id,))]
    return {r["item_id"]: r for r in rows}


# ═══════════════════════════ CENTRAL STOCK ═══════════════════════════
def show_central_stock(module_code):
    from utils.auth import require_module_access
    role = require_module_access(module_code)
    user = current_user()
    mod = _get_module(module_code)
    mid = mod["module_id"]

    can_edit = role in ("SuperAdmin", "SysAdmin", "StatIncharge")
    can_view = role in ("SuperAdmin", "SysAdmin", "StatIncharge", "OS", "Principal")

    if not can_view:
        st.warning("Central Stock is restricted to authorized roles only.")
        return

    st.title(f"{mod['module_icon']} {mod['module_name']} — Central Stock")

    if st.session_state.get(f"_cstock_msg_{mid}"):
        t, m = st.session_state.pop(f"_cstock_msg_{mid}")
        (st.success if t == "s" else st.error)(m)

    if can_edit:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "New Procurement Entry", "Bulk Upload",
            "View Central Stock", "Item Detail Search", "Edit / Delete Entries"
        ])
        with tab1: _new_procurement(user, mid)
        with tab2: _bulk_upload(user, mid)
        with tab3: _view_central_stock(mid)
        with tab4: _item_search(mid)
        with tab5: _edit_delete_stock(user, mid)
    else:
        # OS/Principal can only view
        tab1, tab2 = st.tabs(["View Central Stock", "Item Detail Search"])
        with tab1: _view_central_stock(mid)
        with tab2: _item_search(mid)


def _new_procurement(user, mid):
    st.subheader("New Procurement Entry")
    items = [dict(r) for r in _fa(
        "SELECT * FROM tbl_stat_items WHERE module_id=? AND is_active=1 ORDER BY item_name", (mid,)
    )]
    if not items:
        st.info("No items configured. Add items via Item Master first.")
        return

    item_opts = {f"{it['item_name']} ({it.get('specification','-')}) — {it['unit_of_measure']}": it
                 for it in items}
    c1, c2, c3 = st.columns(3)
    sel_label = c1.selectbox("Item *", list(item_opts.keys()), key=f"{mid}_proc_item")
    sel_item = item_opts[sel_label]
    
    # Show current stock
    current = _fo("SELECT quantity FROM tbl_stat_central_stock WHERE item_id=?", (sel_item["item_id"],))
    current_qty = dict(current)["quantity"] if current else 0
    c2.metric("Current Stock", f"{current_qty} {sel_item['unit_of_measure']}")
    
    qty = c3.number_input(f"Quantity to Add ({sel_item['unit_of_measure']}) *",
                           min_value=0.0, step=1.0, key=f"{mid}_proc_qty")
    remarks = st.text_input("Remarks / Invoice Ref", key=f"{mid}_proc_remarks")

    if st.button("Add to Central Stock", type="primary", key=f"{mid}_proc_submit"):
        if qty <= 0:
            st.error("Quantity must be greater than 0.")
            return
        try:
            conn = get_conn()
            if current:
                conn.execute(
                    "UPDATE tbl_stat_central_stock SET quantity=quantity+?, unit=?, updated_at=? WHERE item_id=?",
                    (qty, sel_item["unit_of_measure"], _ist(), sel_item["item_id"])
                )
            else:
                conn.execute("""
                    INSERT INTO tbl_stat_central_stock (item_id, quantity, unit, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (sel_item["item_id"], qty, sel_item["unit_of_measure"], _ist()))
            conn.execute("""
                INSERT INTO tbl_stat_stock_movements
                    (item_id, movement_type, quantity, remarks, created_by, created_at)
                VALUES (?, 'PROCUREMENT', ?, ?, ?, ?)
            """, (sel_item["item_id"], qty, remarks.strip(), user["user_id"], _ist()))
            conn.commit(); conn.close()
            st.session_state[f"_cstock_msg_{mid}"] = (
                "s", f"{qty} {sel_item['unit_of_measure']} of {sel_item['item_name']} added. "
                     f"New total: {current_qty + qty}"
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Failed: {ex}")


def _bulk_upload(user, mid):
    st.subheader("Bulk Upload Procurement")
    st.caption("Download the pre-filled template, enter quantities only, upload to add stock.")
    
    items = [dict(r) for r in _fa(
        "SELECT item_name, specification, unit_of_measure, item_id FROM tbl_stat_items WHERE module_id=? AND is_active=1 ORDER BY item_name",
        (mid,)
    )]
    stock_map = _get_central_stock_map(mid)
    
    if items:
        df_template = pd.DataFrame([{
            "item_name": it["item_name"],
            "specification": it.get("specification", ""),
            "unit": it["unit_of_measure"],
            "current_stock": stock_map.get(it["item_id"], {}).get("quantity", 0),
            "quantity_to_add": "",
            "remarks": ""
        } for it in items])
    else:
        df_template = pd.DataFrame(columns=["item_name","specification","unit","current_stock","quantity_to_add","remarks"])
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_template.to_excel(writer, index=False, sheet_name="Procurement")
        worksheet = writer.sheets["Procurement"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col) + 4
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len, 40)
    
    st.download_button(
        "Download Pre-filled Template", buf.getvalue(),
        file_name="stat_bulk_upload_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{mid}_bulk_template"
    )
    st.info(f"Template has {len(items)} items pre-filled with current stock. Enter 'quantity_to_add' only.")

    uploaded = st.file_uploader("Choose filled Excel (.xlsx)", type=["xlsx"], key=f"{mid}_bulk_file")
    if not uploaded:
        return
    try:
        df = pd.read_excel(uploaded, dtype=str).fillna("")
        st.success(f"{len(df)} row(s) found.")
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)
    except Exception as ex:
        st.error(f"Could not read file: {ex}"); return

    if st.button("Upload & Add All", type="primary", key=f"{mid}_bulk_submit"):
        items_by_name = {dict(r)["item_name"]: dict(r) for r in _fa(
            "SELECT * FROM tbl_stat_items WHERE module_id=?", (mid,)
        )}
        conn = get_conn(); ok = fail = 0; errors = []
        for idx, row in df.iterrows():
            try:
                item_name = str(row.get("item_name", "")).strip()
                qty_raw = str(row.get("quantity_to_add", "")).strip()
                if not qty_raw or qty_raw in ("nan", ""):
                    continue
                qty = float(qty_raw)
                if qty <= 0:
                    continue
                remarks = str(row.get("remarks", "")).strip()
                item = items_by_name.get(item_name)
                if not item:
                    errors.append(f"Row {idx+2}: item '{item_name}' not found")
                    fail += 1; continue
                existing = conn.execute(
                    "SELECT stock_id FROM tbl_stat_central_stock WHERE item_id=?", (item["item_id"],)
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE tbl_stat_central_stock SET quantity=quantity+?, unit=?, updated_at=? WHERE item_id=?",
                        (qty, item["unit_of_measure"], _ist(), item["item_id"])
                    )
                else:
                    conn.execute("""
                        INSERT INTO tbl_stat_central_stock (item_id, quantity, unit, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (item["item_id"], qty, item["unit_of_measure"], _ist()))
                conn.execute("""
                    INSERT INTO tbl_stat_stock_movements
                        (item_id, movement_type, quantity, remarks, created_by, created_at)
                    VALUES (?, 'PROCUREMENT', ?, ?, ?, ?)
                """, (item["item_id"], qty, remarks, user["user_id"], _ist()))
                ok += 1
            except Exception as ex:
                errors.append(f"Row {idx+2}: {ex}"); fail += 1
        conn.commit(); conn.close()
        st.success(f"Uploaded: {ok} item(s) updated.")
        if fail:
            st.warning(f"{fail} row(s) failed:")
            for e in errors[:10]: st.caption(e)


def _view_central_stock(mid):
    st.subheader("Central Stock Register")
    stock = [dict(r) for r in _fa("""
        SELECT cs.stock_id, cs.item_id, cs.quantity, cs.unit, cs.updated_at,
               it.item_name, it.specification
        FROM tbl_stat_central_stock cs
        JOIN tbl_stat_items it ON it.item_id = cs.item_id
        ORDER BY it.item_name
    """, ())]
    if not stock:
        st.info("No stock entries yet. Use Bulk Upload or New Procurement Entry.")
        return
    df = pd.DataFrame([{
        "Item": s["item_name"], "Specification": s.get("specification", "-"),
        "Quantity": s["quantity"], "Unit": s.get("unit", "-"),
        "Last Updated": str(s.get("updated_at", ""))[:16],
    } for s in stock])
    st.dataframe(df, use_container_width=True, hide_index=True)
    total_items = len(stock)
    low_stock = [s for s in stock if s["quantity"] < 10]
    m1, m2 = st.columns(2)
    m1.metric("Total Item Types in Stock", total_items)
    m2.metric("Low Stock Items (< 10)", len(low_stock))
    if low_stock:
        st.warning("Low stock: " + ", ".join(f"{s['item_name']} ({s['quantity']})" for s in low_stock))


def _item_search(mid):
    st.subheader("Item Detail Search")
    stock = [dict(r) for r in _fa("""
        SELECT cs.stock_id, cs.item_id, cs.quantity, cs.unit, cs.updated_at,
               it.item_name, it.specification
        FROM tbl_stat_central_stock cs
        JOIN tbl_stat_items it ON it.item_id = cs.item_id
        ORDER BY it.item_name
    """, ())]
    if not stock:
        st.info("No stock entries found.")
        return
    opts = {f"{s['item_name']} ({s.get('specification','-')}) — {s['quantity']} {s.get('unit','')}": s
            for s in stock}
    sel_label = st.selectbox("Select Item", list(opts.keys()), key=f"{mid}_isearch_sel")
    s = opts[sel_label]
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Stock", f"{s['quantity']} {s.get('unit','')}")
    c2.markdown(f"**Specification:** {s.get('specification','-')}")
    c3.markdown(f"**Last Updated:** {str(s.get('updated_at',''))[:16]}")
    
    movements = [dict(m) for m in _fa("""
        SELECT mv.*, u.full_name AS by_name
        FROM tbl_stat_stock_movements mv
        LEFT JOIN tbl_users u ON u.user_id = mv.created_by
        WHERE mv.item_id=? ORDER BY mv.created_at DESC LIMIT 10
    """, (s["item_id"],))]
    if movements:
        st.markdown("**Recent Movements:**")
        df_mv = pd.DataFrame([{
            "Type": m["movement_type"], "Qty": m["quantity"],
            "By": m.get("by_name","-"), "Date": str(m.get("created_at",""))[:16],
            "Remarks": m.get("remarks","-")
        } for m in movements])
        st.dataframe(df_mv, use_container_width=True, hide_index=True)


def _edit_delete_stock(user, mid):
    st.subheader("Edit / Delete Stock Entries")
    stock = [dict(r) for r in _fa("""
        SELECT cs.stock_id, cs.item_id, cs.quantity, cs.unit,
               it.item_name, it.specification
        FROM tbl_stat_central_stock cs
        JOIN tbl_stat_items it ON it.item_id = cs.item_id
        ORDER BY it.item_name
    """, ())]
    if not stock:
        st.info("No entries to edit.")
        return
    opts = {f"{s['item_name']} ({s.get('specification','-')})": s for s in stock}
    sel_label = st.selectbox("Select Item", list(opts.keys()), key=f"{mid}_ed_sel")
    sel = opts[sel_label]
    
    st.info(f"Current quantity: **{sel['quantity']} {sel.get('unit','')}**")
    new_qty = st.number_input(
        f"New Quantity ({sel.get('unit','')})",
        min_value=0.0, value=float(sel["quantity"]),
        key=f"{mid}_ed_qty"
    )
    reason = st.text_input("Reason for change *", key=f"{mid}_ed_reason",
                            placeholder="e.g. Physical count correction, damaged items removed")
    
    c1, c2 = st.columns(2)
    if c1.button("Save Change", type="primary", key=f"{mid}_ed_save"):
        if not reason.strip():
            st.error("Please provide a reason for the change.")
            return
        try:
            diff = new_qty - sel["quantity"]
            conn = get_conn()
            conn.execute(
                "UPDATE tbl_stat_central_stock SET quantity=?, unit=?, updated_at=? WHERE stock_id=?",
                (new_qty, sel.get("unit","NUMBERS"), _ist(), sel["stock_id"])
            )
            conn.execute("""
                INSERT INTO tbl_stat_stock_movements
                    (item_id, movement_type, quantity, remarks, created_by, created_at)
                VALUES (?, 'MANUAL_CORRECTION', ?, ?, ?, ?)
            """, (sel["item_id"], diff, reason.strip(), user["user_id"], _ist()))
            conn.commit(); conn.close()
            st.session_state[f"_cstock_msg_{mid}"] = ("s", f"Updated to {new_qty} {sel.get('unit','')}.")
            st.rerun()
        except Exception as ex:
            st.error(f"Failed: {ex}")
    
    confirm_del = c2.checkbox(f"Confirm delete '{sel['item_name']}' entry", key=f"{mid}_ed_del_chk")
    if c2.button("Delete Entry", key=f"{mid}_ed_del", disabled=not confirm_del):
        try:
            conn = get_conn()
            conn.execute("DELETE FROM tbl_stat_central_stock WHERE stock_id=?", (sel["stock_id"],))
            conn.commit(); conn.close()
            st.session_state[f"_cstock_msg_{mid}"] = ("s", f"Entry for '{sel['item_name']}' deleted.")
            st.rerun()
        except Exception as ex:
            st.error(f"Failed: {ex}")


# ═══════════════════════════ DEPARTMENT STOCK ═══════════════════════════
def show_dept_stock(module_code):
    from utils.auth import require_module_access
    role = require_module_access(module_code)
    user = current_user()
    mod = _get_module(module_code)
    mid = mod["module_id"]

    dept_id = user.get("dept_id")
    if not dept_id and role not in ("SuperAdmin", "SysAdmin"):
        st.warning("Your account has no department assigned.")
        return

    st.title(f"{mod['module_icon']} {mod['module_name']} — Department Stock")

    tab1, tab2, tab3 = st.tabs(["View Department Stock", "Category Summary", "Record Consumption"])
    with tab1: _view_dept_stock(dept_id, mid)
    with tab2: _category_summary(dept_id)
    with tab3: _record_consumption(user, dept_id, mid)


def _view_dept_stock(dept_id, mid=None):
    st.subheader("Department Stock Register")
    if not dept_id:
        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
        dm = {d["dept_name"]: d["dept_id"] for d in depts}
        sel = st.selectbox("Department", list(dm.keys()), key="dv_dept_sel")
        dept_id = dm[sel]

    stock = [dict(r) for r in _fa("""
        SELECT ds.dept_stock_id, ds.quantity, ds.unit, ds.updated_at,
               it.item_name, it.specification, it.item_id
        FROM tbl_stat_dept_stock ds
        JOIN tbl_stat_items it ON it.item_id = ds.item_id
        WHERE ds.dept_id=? ORDER BY it.item_name
    """, (dept_id,))]
    if not stock:
        st.info("No stock in your department yet. Stock is added when indent items are issued.")
        return
    df = pd.DataFrame([{
        "Item": s["item_name"], "Specification": s.get("specification", "-"),
        "Quantity": s["quantity"], "Unit": s.get("unit", "-"),
        "Last Updated": str(s.get("updated_at", ""))[:16],
    } for s in stock])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _category_summary(dept_id):
    st.subheader("Category Summary")
    if not dept_id:
        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
        dm = {d["dept_name"]: d["dept_id"] for d in depts}
        sel = st.selectbox("Department", list(dm.keys()), key="cs_dept_sel")
        dept_id = dm[sel]

    stock = [dict(r) for r in _fa("""
        SELECT ds.quantity, ds.unit, it.item_name
        FROM tbl_stat_dept_stock ds
        JOIN tbl_stat_items it ON it.item_id = ds.item_id
        WHERE ds.dept_id=?
    """, (dept_id,))]
    if not stock:
        st.info("No stock to summarize.")
        return
    total_qty = sum(s["quantity"] for s in stock)
    m1, m2 = st.columns(2)
    m1.metric("Total Item Types", len(stock))
    m2.metric("Total Units (combined)", f"{total_qty:.0f}")
    df = pd.DataFrame([{"Item": s["item_name"], "Quantity": s["quantity"], "Unit": s["unit"]}
                       for s in stock])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _record_consumption(user, dept_id, mid):
    """Junior Assistant records items consumed/issued to teaching staff — deducts from dept stock."""
    st.subheader("Record Consumption")
    st.caption("Record items issued to teaching staff or consumed. This will deduct from your department stock.")

    if not dept_id:
        st.warning("Department not assigned to your account.")
        return

    stock = [dict(r) for r in _fa("""
        SELECT ds.dept_stock_id, ds.quantity, ds.unit, ds.item_id,
               it.item_name, it.specification
        FROM tbl_stat_dept_stock ds
        JOIN tbl_stat_items it ON it.item_id = ds.item_id
        WHERE ds.dept_id=? AND ds.quantity > 0 ORDER BY it.item_name
    """, (dept_id,))]
    if not stock:
        st.info("No stock available in your department to record consumption against.")
        return

    if st.session_state.get(f"_cons_msg_{dept_id}"):
        t, m = st.session_state.pop(f"_cons_msg_{dept_id}")
        (st.success if t == "s" else st.error)(m)

    opts = {f"{s['item_name']} (Available: {s['quantity']} {s.get('unit','')})": s for s in stock}
    c1, c2, c3 = st.columns(3)
    sel_label = c1.selectbox("Item *", list(opts.keys()), key=f"cons_item_{dept_id}")
    sel = opts[sel_label]
    qty = c2.number_input(
        f"Quantity Consumed ({sel.get('unit','')})",
        min_value=0.0, max_value=float(sel["quantity"]), step=1.0,
        key=f"cons_qty_{dept_id}"
    )
    remarks = c3.text_input("Issued to / Remarks", key=f"cons_rem_{dept_id}",
                             placeholder="e.g. Issued to Dr. Rajasekhar for exam duty")

    if st.button("Record Consumption", type="primary", key=f"cons_submit_{dept_id}"):
        if qty <= 0:
            st.error("Quantity must be greater than 0.")
            return
        try:
            conn = get_conn()
            conn.execute(
                "UPDATE tbl_stat_dept_stock SET quantity=quantity-?, updated_at=? WHERE dept_stock_id=?",
                (qty, _ist(), sel["dept_stock_id"])
            )
            conn.execute("""
                INSERT INTO tbl_stat_stock_movements
                    (item_id, movement_type, quantity, dept_id, remarks, created_by, created_at)
                VALUES (?, 'CONSUMPTION', ?, ?, ?, ?, ?)
            """, (sel["item_id"], qty, dept_id, remarks.strip(), user["user_id"], _ist()))
            conn.commit(); conn.close()
            st.session_state[f"_cons_msg_{dept_id}"] = (
                "s", f"Recorded: {qty} {sel.get('unit','')} of {sel['item_name']} consumed. "
                     f"Remaining: {sel['quantity'] - qty}"
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Failed: {ex}")


# ═══════════════════════════ STOCK MOVEMENT UTILITIES ═══════════════════════════
def deduct_central_stock(item_id, qty, dept_id, indent_id, user_id, remarks=""):
    """Deduct from central stock when indent items are issued to department."""
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE tbl_stat_central_stock SET quantity=quantity-?, updated_at=? WHERE item_id=?",
            (qty, _ist(), item_id)
        )
        conn.execute("""
            INSERT INTO tbl_stat_stock_movements
                (item_id, movement_type, quantity, dept_id, indent_id, remarks, created_by, created_at)
            VALUES (?, 'ISSUE_TO_DEPT', ?, ?, ?, ?, ?, ?)
        """, (item_id, qty, dept_id, indent_id, remarks, user_id, _ist()))
        conn.commit(); conn.close()
    except Exception:
        pass


def add_dept_stock(item_id, dept_id, qty, unit, indent_id, user_id):
    """Add to department stock when indent items are received."""
    try:
        conn = get_conn()
        existing = conn.execute(
            "SELECT dept_stock_id FROM tbl_stat_dept_stock WHERE dept_id=? AND item_id=?",
            (dept_id, item_id)
        ).fetchone()
        if existing:
            dsid = existing[0] if not hasattr(existing, "keys") else dict(existing)["dept_stock_id"]
            conn.execute(
                "UPDATE tbl_stat_dept_stock SET quantity=quantity+?, unit=?, updated_at=? WHERE dept_stock_id=?",
                (qty, unit, _ist(), dsid)
            )
        else:
            conn.execute("""
                INSERT INTO tbl_stat_dept_stock (dept_id, item_id, quantity, unit, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (dept_id, item_id, qty, unit, _ist()))
        conn.execute("""
            INSERT INTO tbl_stat_stock_movements
                (item_id, movement_type, quantity, dept_id, indent_id, created_by, created_at)
            VALUES (?, 'DEPT_RECEIPT', ?, ?, ?, ?, ?)
        """, (item_id, qty, dept_id, indent_id, user_id, _ist()))
        conn.commit(); conn.close()
    except Exception:
        pass
