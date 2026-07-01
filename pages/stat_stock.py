"""
pages/stat_stock.py — Quantity-based Stock Register for Stationery (SRGEC-SIMS)

CENTRAL STOCK (SysAdmin/SuperAdmin only):
  - New Procurement Entry
  - Bulk Upload
  - Issue to Departments
  - View Central Stock
  - Item Detail Search
  - Edit/Delete Entries

DEPARTMENT STOCK (Junior Assistant only, own dept):
  - View Department Stock
  - Category Summary
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


# ═══════════════════════════ CENTRAL STOCK ═══════════════════════════
def show_central_stock(module_code):
    user = current_user()
    role = st.session_state.get("role") or (current_user() or {}).get("role")
    from utils.auth import require_module_access
    role = require_module_access(module_code)
    mod = _get_module(module_code)
    mid = mod["module_id"]

    if role not in ("SuperAdmin", "SysAdmin"):
        st.warning("Central Stock is for SuperAdmin / SysAdmin only.")
        return

    st.title(f"{mod['module_icon']} {mod['module_name']} — Central Stock")

    if st.session_state.get(f"_cstock_msg_{mid}"):
        t, m = st.session_state.pop(f"_cstock_msg_{mid}")
        (st.success if t == "s" else st.error)(m)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "New Procurement Entry", "Bulk Upload", "Issue to Departments",
        "View Central Stock", "Item Detail Search", "Edit / Delete Entries"
    ])
    with tab1: _new_procurement(user, mid)
    with tab2: _bulk_upload(user, mid)
    with tab3: _issue_to_dept(user, mid)
    with tab4: _view_central_stock(mid)
    with tab5: _item_search(mid)
    with tab6: _edit_delete_stock(user, mid)


def _new_procurement(user, mid):
    st.subheader("New Procurement Entry")
    items = [dict(r) for r in _fa(
        "SELECT * FROM tbl_stat_items WHERE module_id=? AND is_active=1 ORDER BY item_name", (mid,)
    )]
    if not items:
        st.info("No items configured. Add items via Item Master first.")
        return

    item_opts = {f"{it['item_name']} ({it.get('specification','-')})": it for it in items}
    c1, c2, c3 = st.columns(3)
    sel_label = c1.selectbox("Item *", list(item_opts.keys()), key=f"{mid}_proc_item")
    sel_item = item_opts[sel_label]
    qty = c2.number_input(f"Quantity ({sel_item['unit_of_measure']}) *", min_value=0.0, step=1.0,
                           key=f"{mid}_proc_qty")
    remarks = c3.text_input("Remarks / Invoice Ref", key=f"{mid}_proc_remarks")

    if st.button("Add to Central Stock", type="primary", key=f"{mid}_proc_submit"):
        if qty <= 0:
            st.error("Quantity must be greater than 0.")
            return
        try:
            conn = get_conn()
            existing = conn.execute(
                "SELECT stock_id, quantity FROM tbl_stat_central_stock WHERE item_id=?",
                (sel_item["item_id"],)
            ).fetchone()
            if existing:
                ex = dict(existing) if not isinstance(existing, dict) else existing
                new_qty = (ex.get("quantity") if isinstance(ex, dict) else ex[1]) + qty
                stock_id = ex.get("stock_id") if isinstance(ex, dict) else ex[0]
                conn.execute(
                    "UPDATE tbl_stat_central_stock SET quantity=?, updated_at=? WHERE stock_id=?",
                    (new_qty, _ist(), stock_id)
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
            conn.commit()
            conn.close()
            st.session_state[f"_cstock_msg_{mid}"] = (
                "s", f"{qty} {sel_item['unit_of_measure']} of {sel_item['item_name']} added to central stock."
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Failed: {ex}")


def _bulk_upload(user, mid):
    st.subheader("Bulk Upload Procurement")
    st.caption("Download the pre-filled template, enter quantities only, upload to add stock.")
    
    # Generate template with all items pre-filled from database
    items = [dict(r) for r in _fa(
        "SELECT item_name, specification, unit_of_measure FROM tbl_stat_items WHERE module_id=? AND is_active=1 ORDER BY item_name",
        (mid,)
    )]
    if items:
        df_template = pd.DataFrame([{
            "item_name": it["item_name"],
            "specification": it.get("specification", ""),
            "unit": it["unit_of_measure"],
            "quantity": "",
            "remarks": ""
        } for it in items])
    else:
        df_template = pd.DataFrame(columns=["item_name","specification","unit","quantity","remarks"])
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_template.to_excel(writer, index=False, sheet_name="Procurement")
        # Auto-fit column widths
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
    st.info(f"Template has {len(items)} items pre-filled. Enter quantity for items received, leave blank to skip.")

    uploaded = st.file_uploader("Choose Excel (.xlsx)", type=["xlsx"], key=f"{mid}_bulk_file")
    if not uploaded:
        return
    try:
        df = pd.read_excel(uploaded, dtype=str).fillna("")
        st.success(f"{len(df)} row(s) found.")
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)
    except Exception as ex:
        st.error(f"Could not read file: {ex}")
        return

    if st.button("Upload & Add All", type="primary", key=f"{mid}_bulk_submit"):
        items_by_name = {dict(r)["item_name"]: dict(r) for r in _fa(
            "SELECT * FROM tbl_stat_items WHERE module_id=?", (mid,)
        )}
        conn = get_conn()
        ok = fail = 0
        errors = []
        for idx, row in df.iterrows():
            try:
                item_name = str(row.get("item_name", "")).strip()
                qty_raw = str(row.get("quantity", "")).strip()
                if not qty_raw or qty_raw == "nan":
                    continue  # Skip blank rows (pre-filled template rows left empty)
                qty = float(qty_raw)
                remarks = str(row.get("remarks", "")).strip()
                item = items_by_name.get(item_name)
                if not item:
                    errors.append(f"Row {idx+2}: item '{item_name}' not found in Item Master")
                    fail += 1
                    continue
                if qty <= 0:
                    continue  # Skip zero quantities silently
                existing = conn.execute(
                    "SELECT stock_id, quantity FROM tbl_stat_central_stock WHERE item_id=?",
                    (item["item_id"],)
                ).fetchone()
                if existing:
                    ex_row = dict(existing) if hasattr(existing, "keys") else \
                              {"stock_id": existing[0], "quantity": existing[1]}
                    conn.execute(
                        "UPDATE tbl_stat_central_stock SET quantity=quantity+?, updated_at=? WHERE stock_id=?",
                        (qty, _ist(), ex_row["stock_id"])
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
                errors.append(f"Row {idx+2}: {ex}")
                fail += 1
        conn.commit()
        conn.close()
        st.success(f"Uploaded: {ok} row(s) added.")
        if fail:
            st.warning(f"{fail} row(s) failed:")
            for e in errors[:10]:
                st.caption(e)


def _issue_to_dept(user, mid):
    st.subheader("Issue Stock to Department")
    st.caption("Use this to issue stock directly (outside the indent workflow), e.g. corrections or manual issues.")

    stock = [dict(r) for r in _fa("""
        SELECT cs.*, it.item_name, it.specification
        FROM tbl_stat_central_stock cs
        JOIN tbl_stat_items it ON it.item_id = cs.item_id
        WHERE cs.quantity > 0 ORDER BY it.item_name
    """, ())]
    if not stock:
        st.info("No stock available in central stock.")
        return

    depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    if not depts:
        st.info("No departments configured.")
        return
    dm = {d["dept_name"]: d["dept_id"] for d in depts}

    item_opts = {f"{s['item_name']} (Available: {s['quantity']} {s['unit']})": s for s in stock}
    c1, c2, c3 = st.columns(3)
    sel_label = c1.selectbox("Item *", list(item_opts.keys()), key=f"{mid}_issue_item")
    sel_stock = item_opts[sel_label]
    to_dept = c2.selectbox("Issue to Department *", list(dm.keys()), key=f"{mid}_issue_dept")
    qty = c3.number_input(f"Quantity ({sel_stock['unit']}) *", min_value=0.0,
                           max_value=float(sel_stock["quantity"]), step=1.0, key=f"{mid}_issue_qty")

    if st.button("Issue to Department", type="primary", key=f"{mid}_issue_btn"):
        if qty <= 0:
            st.error("Quantity must be greater than 0.")
            return
        try:
            conn = get_conn()
            conn.execute(
                "UPDATE tbl_stat_central_stock SET quantity=quantity-?, updated_at=? WHERE stock_id=?",
                (qty, _ist(), sel_stock["stock_id"])
            )
            dept_existing = conn.execute(
                "SELECT dept_stock_id, quantity FROM tbl_stat_dept_stock WHERE dept_id=? AND item_id=?",
                (dm[to_dept], sel_stock["item_id"])
            ).fetchone()
            if dept_existing:
                de = dict(dept_existing) if hasattr(dept_existing, "keys") else \
                     {"dept_stock_id": dept_existing[0], "quantity": dept_existing[1]}
                conn.execute(
                    "UPDATE tbl_stat_dept_stock SET quantity=quantity+?, updated_at=? WHERE dept_stock_id=?",
                    (qty, _ist(), de["dept_stock_id"])
                )
            else:
                conn.execute("""
                    INSERT INTO tbl_stat_dept_stock (dept_id, item_id, quantity, unit, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (dm[to_dept], sel_stock["item_id"], qty, sel_stock["unit"], _ist()))
            conn.execute("""
                INSERT INTO tbl_stat_stock_movements
                    (item_id, movement_type, quantity, dept_id, remarks, created_by, created_at)
                VALUES (?, 'MANUAL_ISSUE', ?, ?, ?, ?, ?)
            """, (sel_stock["item_id"], qty, dm[to_dept], "Manual issue", user["user_id"], _ist()))
            conn.commit()
            conn.close()
            st.session_state[f"_cstock_msg_{mid}"] = (
                "s", f"{qty} {sel_stock['unit']} of {sel_stock['item_name']} issued to {to_dept}."
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Failed: {ex}")


def _view_central_stock(mid):
    st.subheader("Central Stock Register")
    stock = [dict(r) for r in _fa("""
        SELECT cs.*, it.item_name, it.specification
        FROM tbl_stat_central_stock cs
        JOIN tbl_stat_items it ON it.item_id = cs.item_id
        ORDER BY it.item_name
    """, ())]
    if not stock:
        st.info("No stock entries yet.")
        return
    df = pd.DataFrame([{
        "Item": s["item_name"], "Specification": s.get("specification", "-"),
        "Quantity": s["quantity"], "Unit": s["unit"],
        "Last Updated": str(s.get("updated_at", ""))[:16],
    } for s in stock])
    st.dataframe(df, use_container_width=True, hide_index=True)
    total_items = len(stock)
    low_stock = [s for s in stock if s["quantity"] < 10]
    m1, m2 = st.columns(2)
    m1.metric("Total Item Types", total_items)
    m2.metric("Low Stock Items (< 10)", len(low_stock))
    if low_stock:
        st.warning("Low stock items: " + ", ".join(s["item_name"] for s in low_stock))


def _item_search(mid):
    st.subheader("Item Detail Search")
    srch = st.text_input("Search item name / specification", key=f"{mid}_isearch")
    if not srch.strip():
        st.info("Enter a search term.")
        return
    s = f"%{srch}%"
    results = [dict(r) for r in _fa("""
        SELECT cs.*, it.item_name, it.specification
        FROM tbl_stat_central_stock cs
        JOIN tbl_stat_items it ON it.item_id = cs.item_id
        WHERE it.item_name LIKE ? OR it.specification LIKE ?
        ORDER BY it.item_name
    """, (s, s))]
    if not results:
        st.info("No matching items found.")
        return
    for r in results:
        st.markdown(f"**{r['item_name']}** ({r.get('specification','-')}) — "
                    f"{r['quantity']} {r['unit']} in central stock")
        movements = [dict(m) for m in _fa("""
            SELECT * FROM tbl_stat_stock_movements WHERE item_id=? ORDER BY created_at DESC LIMIT 5
        """, (r["item_id"],))]
        if movements:
            with st.expander("Recent movements"):
                df_mv = pd.DataFrame([{
                    "Type": m["movement_type"], "Qty": m["quantity"],
                    "Date": str(m.get("created_at",""))[:16], "Remarks": m.get("remarks","-")
                } for m in movements])
                st.dataframe(df_mv, use_container_width=True, hide_index=True)


def _edit_delete_stock(user, mid):
    st.subheader("Edit / Delete Stock Entries")
    stock = [dict(r) for r in _fa("""
        SELECT cs.*, it.item_name FROM tbl_stat_central_stock cs
        JOIN tbl_stat_items it ON it.item_id = cs.item_id ORDER BY it.item_name
    """, ())]
    if not stock:
        st.info("No entries to edit.")
        return
    opts = {f"{s['item_name']} ({s['quantity']} {s['unit']})": s for s in stock}
    sel_label = st.selectbox("Select entry", list(opts.keys()), key=f"{mid}_ed_sel")
    sel = opts[sel_label]
    new_qty = st.number_input(f"Quantity ({sel['unit']})", min_value=0.0, value=float(sel["quantity"]),
                               key=f"{mid}_ed_qty")
    c1, c2 = st.columns(2)
    if c1.button("Save Change", type="primary", key=f"{mid}_ed_save"):
        try:
            conn = get_conn()
            conn.execute(
                "UPDATE tbl_stat_central_stock SET quantity=?, updated_at=? WHERE stock_id=?",
                (new_qty, _ist(), sel["stock_id"])
            )
            conn.execute("""
                INSERT INTO tbl_stat_stock_movements
                    (item_id, movement_type, quantity, remarks, created_by, created_at)
                VALUES (?, 'MANUAL_CORRECTION', ?, ?, ?, ?)
            """, (sel["item_id"], new_qty - sel["quantity"], "Manual correction", user["user_id"], _ist()))
            conn.commit()
            conn.close()
            st.success("Updated.")
            st.rerun()
        except Exception as ex:
            st.error(f"Failed: {ex}")
    if c2.button("Delete Entry", key=f"{mid}_ed_del"):
        try:
            conn = get_conn()
            conn.execute("DELETE FROM tbl_stat_central_stock WHERE stock_id=?", (sel["stock_id"],))
            conn.commit()
            conn.close()
            st.success("Deleted.")
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

    if role not in ("JuniorAssistant", "SuperAdmin"):
        st.warning("Department Stock is for Junior Assistant only.")
        return

    dept_id = user.get("dept_id")
    if not dept_id and role != "SuperAdmin":
        st.warning("Your account has no department assigned.")
        return

    st.title(f"{mod['module_icon']} {mod['module_name']} — Department Stock")

    tab1, tab2 = st.tabs(["View Department Stock", "Category Summary"])
    with tab1:
        _view_dept_stock(dept_id)
    with tab2:
        _category_summary(dept_id)


def _view_dept_stock(dept_id):
    st.subheader("Department Stock Register")
    if not dept_id:
        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
        dm = {d["dept_name"]: d["dept_id"] for d in depts}
        sel = st.selectbox("Department", list(dm.keys()), key="dv_dept_sel")
        dept_id = dm[sel]

    stock = [dict(r) for r in _fa("""
        SELECT ds.*, it.item_name, it.specification
        FROM tbl_stat_dept_stock ds
        JOIN tbl_stat_items it ON it.item_id = ds.item_id
        WHERE ds.dept_id=? ORDER BY it.item_name
    """, (dept_id,))]
    if not stock:
        st.info("No stock entries for your department yet.")
        return
    df = pd.DataFrame([{
        "Item": s["item_name"], "Specification": s.get("specification", "-"),
        "Quantity": s["quantity"], "Unit": s["unit"],
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
    m2.metric("Total Quantity (all units combined)", f"{total_qty:.0f}")
    df = pd.DataFrame([{"Item": s["item_name"], "Quantity": s["quantity"], "Unit": s["unit"]} for s in stock])
    st.dataframe(df, use_container_width=True, hide_index=True)
