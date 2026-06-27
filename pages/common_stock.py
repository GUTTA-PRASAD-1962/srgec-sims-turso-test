"""
pages/common_stock.py — Generic Stock Register for ALL modules.

Usage:
    from pages.common_stock import show
    show(MODULE_CODE)

Provides all IT-IIMS Central Stock tabs:
  Tab 1: New Procurement Entry
  Tab 2: Issue to Department
  Tab 3: View Central Stock
  Tab 4: Department Stock Register
  Tab 5: Asset Search & Edit
  Tab 6: Edit / Delete
  Tab 7: Dept-wise View
"""
import streamlit as st
import pandas as pd
from datetime import date
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access
from utils.helpers import (generate_item_id, save_scan, show_scan,
                            export_df, format_date, format_currency,
                            get_dynamic_fields, render_dynamic_fields,
                            save_field_values)


def show(module_code):
    role = require_module_access(module_code)
    user = current_user()
    mod  = _get_module(module_code)
    if not mod: st.error(f"Module '{module_code}' not found."); return

    st.title(f"{mod['module_icon']} {mod['module_name']} — Stock Register")
    st.caption(f"Your role: **{role}**")

    if st.session_state.get("_stock_msg"):
        t, m = st.session_state.pop("_stock_msg")
        (st.success if t == "s" else st.error)(m)

    is_admin = role in ("SuperAdmin","SysAdmin","Coordinator")

    if is_admin:
        tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
            "New Entry",
            "Issue to Dept",
            "View Central Stock",
            "Dept Stock Register",
            "Asset Search",
            "Edit / Delete",
            "Dept-wise View",
        ])
        with tab1: _new_entry(user, role, mod)
        with tab2: _issue_to_dept(user, role, mod)
        with tab3: _view_stock(mod)
        with tab4: _dept_stock(mod)
        with tab5: _asset_search(mod)
        with tab6: _edit_delete(user, mod)
        with tab7: _dept_view(mod)
    else:
        tab1,tab2 = st.tabs(["View Stock","Asset Search"])
        with tab1: _view_stock(mod)
        with tab2: _asset_search(mod)


# ── helpers ───────────────────────────────────────────────────────
def _get_module(code):
    r = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (code,))
    return dict(r) if r else None


def _get_mid(code):
    r = _fo("SELECT module_id FROM tbl_modules WHERE module_code=?", (code,))
    return dict(r)["module_id"] if r else None


def _flash():
    if st.session_state.get("_stock_msg"):
        t, m = st.session_state.pop("_stock_msg")
        (st.success if t == "s" else st.error)(m)


# ══ TAB 1 — NEW ENTRY ════════════════════════════════════════════
def _new_entry(user, role, mod):
    _flash()
    st.subheader("New Procurement Entry")
    st.info("Register newly received assets into Central Stock.")
    mid = mod["module_id"]

    types = [dict(r) for r in _fa(
        "SELECT * FROM tbl_item_types WHERE module_id=? AND is_active=1 ORDER BY type_name",(mid,))]
    if not types: st.warning("No item types configured. Add them via SuperAdmin."); return

    # Supplier
    st.markdown("#### Step 1 — Supplier")
    supps   = [dict(r) for r in _fa("SELECT * FROM tbl_suppliers WHERE is_active=1 ORDER BY supplier_name")]
    s_opts  = {"— select —": None}
    s_opts.update({s["supplier_name"]: s["supplier_id"] for s in supps})
    new_s = st.checkbox("Add New Supplier", key=f"{mid}_new_s")
    if new_s:
        a1,a2,a3 = st.columns(3)
        sn=a1.text_input("Name *",key=f"{mid}_sn"); sp=a2.text_input("Phone",key=f"{mid}_sp"); se=a3.text_input("Email",key=f"{mid}_se")
        sa=st.text_input("Address",key=f"{mid}_sa")
        if st.button("Save Supplier",key=f"{mid}_ss"):
            if sn.strip():
                c=get_conn(); c.execute("INSERT INTO tbl_suppliers (supplier_name,phone,email,address) VALUES (?,?,?,?)",(sn.strip(),sp,se,sa)); c.commit(); c.close()
                st.success(f"Supplier '{sn}' saved."); st.rerun()
        return
    sel_s = st.selectbox("Supplier *",list(s_opts.keys()),key=f"{mid}_supp")
    sup_id = s_opts[sel_s]

    st.markdown("#### Step 2 — Invoice")
    c1,c2,c3 = st.columns(3)
    inv_no  = c1.text_input("Invoice No *",placeholder="INV/2026/001",key=f"{mid}_ino")
    inv_dt  = c2.date_input("Invoice Date",value=date.today(),key=f"{mid}_idt")
    rec_dt  = c3.date_input("Receipt Date",value=date.today(),key=f"{mid}_rdt")
    c4,c5   = st.columns(2)
    inv_amt = c4.number_input("Total Amount (Rs.)",min_value=0.0,step=100.0,key=f"{mid}_iamt")
    inv_rem = c5.text_input("Remarks",key=f"{mid}_irem")
    inv_scan= st.file_uploader("Invoice Scan (PDF/Image)",type=["pdf","jpg","jpeg","png"],key=f"{mid}_iscan")

    st.markdown("#### Step 3 — Assets (go to Central Stock)")
    type_map = {t["type_name"]: t for t in types}
    n_types  = st.number_input("Number of asset types",min_value=1,max_value=30,value=1,key=f"{mid}_nt")

    rows = []
    for i in range(int(n_types)):
        st.markdown(f"---\n**Asset Type {i+1}**")
        r1,r2,r3,r4 = st.columns([2,1,2,2])
        atype  = r1.selectbox("Type *",list(type_map.keys()),key=f"{mid}_at_{i}")
        qty    = r2.number_input("Qty *",min_value=1,value=1,key=f"{mid}_q_{i}")
        desc   = r3.text_input("Description *",key=f"{mid}_d_{i}")
        make   = r4.text_input("Make/Brand",key=f"{mid}_mk_{i}")
        r5,r6,r7,r8 = st.columns(4)
        model  = r5.text_input("Model",key=f"{mid}_mo_{i}")
        serial = r6.text_input("Serial No (1st unit)",key=f"{mid}_sn_{i}")
        cost   = r7.number_input("Cost/Unit (Rs.) *",min_value=0.0,step=100.0,key=f"{mid}_c_{i}")
        pdate  = r8.text_input("Purchase Date",value=str(date.today()),key=f"{mid}_pd_{i}")
        w1,w2  = st.columns(2)
        wf = w1.text_input("Warranty From",key=f"{mid}_wf_{i}")
        wt = w2.text_input("Warranty To",key=f"{mid}_wto_{i}")
        # Dynamic fields
        tinfo  = type_map[atype]
        fields = get_dynamic_fields(tinfo["type_id"])
        cfg    = render_dynamic_fields(fields, key_prefix=f"{mid}_f{i}") if fields else {}
        if cost>0 and qty>0:
            st.caption(f"Subtotal: Rs.{qty*cost:,.2f}")
        rows.append({"tinfo":tinfo,"qty":int(qty),"desc":desc,"make":make,"model":model,
                     "serial":serial,"cost":float(cost),"pdate":pdate,"wf":wf,"wt":wt,"cfg":cfg})

    grand = sum(r["qty"]*r["cost"] for r in rows)
    st.markdown(f"**Grand Total: Rs.{grand:,.2f}**")

    if st.button("Register All Assets",type="primary",use_container_width=True,key=f"{mid}_reg"):
        errs = []
        if not sel_s or sel_s=="— select —": errs.append("Select supplier.")
        if not inv_no.strip(): errs.append("Invoice number required.")
        for i,r in enumerate(rows):
            if not r["desc"].strip(): errs.append(f"Type {i+1}: Description required.")
            if r["cost"]<=0: errs.append(f"Type {i+1}: Cost must be > 0.")
        if errs:
            for e in errs: st.error(e)
            return
        try:
            conn = get_conn()
            inv_id = conn.execute("""
                INSERT INTO tbl_invoices (module_id,invoice_number,invoice_date,supplier_id,
                    total_amount,received_date,received_by,remarks)
                VALUES (?,?,?,?,?,?,?,?)
            """,(mid,inv_no.strip(),str(inv_dt),sup_id,inv_amt or grand,str(rec_dt),user["user_id"],inv_rem)).lastrowid
            conn.commit()
            scan_path = save_scan(inv_scan, inv_no.strip()) if inv_scan else None
            if scan_path:
                conn.execute("UPDATE tbl_invoices SET invoice_scan_path=? WHERE invoice_id=?",(scan_path,inv_id))
                conn.commit()
            created = []
            for r in rows:
                ti = r["tinfo"]
                for u in range(r["qty"]):
                    serial = f"{r['serial']}-{u+1:03d}" if r["qty"]>1 and r["serial"] else r["serial"]
                    uid = generate_item_id(mod["module_code"],"CS",ti["id_prefix"],r["pdate"])
                    item_id = conn.execute("""
                        INSERT INTO tbl_items (module_id,type_id,unique_item_id,invoice_id,supplier_id,
                            description,make,model,serial_number,cost_per_unit,purchase_date,
                            warranty_from,warranty_to,item_status,created_by)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,(mid,ti["type_id"],uid,inv_id,sup_id,r["desc"],r["make"],r["model"],serial,
                         r["cost"],r["pdate"],r["wf"] or None,r["wt"] or None,"WORKING",user["user_id"])).lastrowid
                    conn.commit()
                    if r["cfg"]: save_field_values(conn,item_id,ti["type_id"],r["cfg"])
                    created.append(uid)
                conn.execute("""
                    INSERT INTO tbl_stock_register (module_id,invoice_id,type_id,description,
                        qty_received,cost_per_unit,remarks)
                    VALUES (?,?,?,?,?,?,?)
                """,(mid,inv_id,ti["type_id"],r["desc"],r["qty"],r["cost"],inv_rem))
                conn.commit()
            conn.close()
            st.session_state["_stock_msg"] = ("s",
                f"{sum(r['qty'] for r in rows)} asset(s) registered. IDs: {', '.join(created[:5])}{'...' if len(created)>5 else ''}")
            st.rerun()
        except Exception as ex:
            st.error(f"Registration failed: {ex}")


# ══ TAB 2 — ISSUE TO DEPT ════════════════════════════════════════
def _issue_to_dept(user, role, mod):
    _flash()
    from collections import defaultdict
    mid = mod["module_id"]
    st.subheader("Issue Assets to Department")

    if st.session_state.get("_issue_msg"):
        st.success(st.session_state.pop("_issue_msg"))

    orphans = [dict(r) for r in _fa("""
        SELECT i.item_id, i.unique_item_id, i.description, i.item_status,
               it.type_name, it.type_id
        FROM tbl_items i JOIN tbl_item_types it ON it.type_id=i.type_id
        WHERE i.module_id=? AND i.dept_id IS NULL AND i.is_deleted=0
        ORDER BY it.type_name, i.item_id
    """,(mid,))]

    if not orphans: st.success("All assets have been issued to departments."); return

    by_type = defaultdict(list)
    for a in orphans: by_type[a["type_name"]].append(a)
    for tn, assets in by_type.items():
        st.markdown(f"  - **{tn}**: {len(assets)} unit(s)")

    st.divider()
    type_sel = st.selectbox("Asset Type to Issue",list(by_type.keys()),key=f"{mid}_it_type")
    avail    = by_type[type_sel]

    depts   = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    dm      = {d["dept_name"]: d for d in depts}
    to_dept = st.selectbox("Issue to Department *",list(dm.keys()),key=f"{mid}_it_dept")
    dept    = dm[to_dept]

    locs    = [dict(r) for r in _fa("SELECT * FROM tbl_locations WHERE dept_id=? AND is_active=1",(dept["dept_id"],))]
    lm      = {"— No specific location —": None}
    lm.update({l["location_name"]: l["location_id"] for l in locs})
    to_loc  = st.selectbox("Location (optional)",list(lm.keys()),key=f"{mid}_it_loc")

    qty_i   = st.number_input("Quantity to Issue *",min_value=1,max_value=len(avail),value=1,key=f"{mid}_it_qty")
    rem_i   = st.text_area("Remarks",key=f"{mid}_it_rem",height=60)

    if st.button("Issue to Department",type="primary",key=f"{mid}_it_btn"):
        try:
            conn = get_conn()
            to_issue = avail[:int(qty_i)]
            for a in to_issue:
                conn.execute("UPDATE tbl_items SET dept_id=?,location_id=? WHERE item_id=?",
                             (dept["dept_id"],lm[to_loc],a["item_id"]))
            # DSR entry
            ti_row = to_issue[0]
            conn.execute("""
                INSERT INTO tbl_dept_stock (module_id,dept_id,type_id,description,qty_received,remarks)
                VALUES (?,?,?,?,?,?)
            """,(mid,dept["dept_id"],ti_row["type_id"],ti_row["description"],qty_i,rem_i))
            conn.commit(); conn.close()
            st.session_state["_issue_msg"] = f"{qty_i} {type_sel}(s) issued to {to_dept}."
            st.rerun()
        except Exception as ex: st.error(f"Failed: {ex}")


# ══ TAB 3 — VIEW CENTRAL STOCK ═══════════════════════════════════
def _view_stock(mod, user=None, role=None):
    _flash()
    mid = mod["module_id"]
    st.subheader("Central Stock Register")

    # Metrics
    try:
        total   = dict(_fo("SELECT COUNT(*) c FROM tbl_items WHERE module_id=? AND is_deleted=0",(mid,)))["c"]
        central = dict(_fo("SELECT COUNT(*) c FROM tbl_items WHERE module_id=? AND dept_id IS NULL AND is_deleted=0",(mid,)))["c"]
        issued  = total - central
        working = dict(_fo("SELECT COUNT(*) c FROM tbl_items WHERE module_id=? AND item_status='WORKING' AND is_deleted=0",(mid,)))["c"]
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total Assets",total)
        m2.metric("Central Stock",central)
        m3.metric("Issued to Depts",issued)
        m4.metric("Working",working)
    except Exception: pass

    # Invoice scan viewer
    with st.expander("View Invoice Scan"):
        scans = [dict(r) for r in _fa(
            "SELECT invoice_number, invoice_scan_path FROM tbl_invoices WHERE module_id=? AND invoice_scan_path IS NOT NULL ORDER BY invoice_id DESC",(mid,))]
        if scans:
            sc1,sc2 = st.columns([2,3])
            srch = sc1.text_input("Search Invoice No",key=f"{mid}_inv_srch")
            fl   = [s for s in scans if srch.lower() in s["invoice_number"].lower()] if srch.strip() else scans
            if fl:
                sel = sc2.selectbox("Select Invoice",[s["invoice_number"] for s in fl],key=f"{mid}_inv_sel")
                show_scan(next(s["invoice_scan_path"] for s in fl if s["invoice_number"]==sel))
        else:
            st.info("No invoice scans uploaded yet.")

    # Dept distribution
    _restricted_r = ("HoD","Lab-IC","Technician")
    _udept = (user or {}).get("dept_id")
    st.markdown("#### Department-wise Distribution")
    try:
        dist = [dict(r) for r in _fa("""
            SELECT d.dept_name, it.type_name, COUNT(*) AS total
            FROM tbl_items i
            JOIN tbl_departments d ON d.dept_id=i.dept_id
            JOIN tbl_item_types it ON it.type_id=i.type_id
            WHERE i.module_id=? AND i.dept_id IS NOT NULL AND i.is_deleted=0
            GROUP BY i.dept_id, i.type_id ORDER BY d.dept_name
        """,(mid,))]
        if dist:
            df = pd.DataFrame(dist)
            pivot = df.pivot_table(index="dept_name",columns="type_name",values="total",aggfunc="sum",fill_value=0)
            pivot["TOTAL"] = pivot.sum(axis=1)
            st.dataframe(pivot.sort_values("TOTAL",ascending=False),use_container_width=True)
            st.bar_chart(pivot["TOTAL"].sort_values(ascending=True),use_container_width=True,height=300)
    except Exception as ex: st.warning(f"Could not load distribution: {ex}")

    # Full register
    st.markdown("#### Full Register")
    rows = [dict(r) for r in _fa("""
        SELECT i.unique_item_id, it.type_name, i.description, i.make, i.model,
               i.serial_number, i.cost_per_unit, i.purchase_date, i.warranty_to,
               i.item_status, d.dept_name, l.location_name,
               s.supplier_name, inv.invoice_number
        FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        LEFT JOIN tbl_departments d ON d.dept_id=i.dept_id
        LEFT JOIN tbl_locations l ON l.location_id=i.location_id
        LEFT JOIN tbl_suppliers s ON s.supplier_id=i.supplier_id
        LEFT JOIN tbl_invoices inv ON inv.invoice_id=i.invoice_id
        WHERE i.module_id=? AND i.is_deleted=0 ORDER BY it.type_name, i.item_id
    """,(mid,))]
    if rows:
        df = pd.DataFrame([{
            "UID":r["unique_item_id"],"Type":r["type_name"],"Description":r["description"],
            "Make":r.get("make","—"),"Model":r.get("model","—"),"Serial":r.get("serial_number","—"),
            "Cost Rs.":r["cost_per_unit"],"Invoice":r.get("invoice_number","—"),
            "Department":r.get("dept_name","Central Stock"),"Location":r.get("location_name","—"),
            "Status":r["item_status"],"Warranty To":r.get("warranty_to","—"),
        } for r in rows])
        st.dataframe(df,use_container_width=True,hide_index=True)
        export_df(df,f"{mod['module_code']}_Central_Stock.xlsx")
    else:
        st.info("No assets registered yet.")


# ══ TAB 4 — DEPT STOCK REGISTER ══════════════════════════════════
def _dept_stock(mod, user=None, role=None):
    _flash()
    mid = mod["module_id"]
    st.subheader("Department Stock Register")
    # Department filter based on role
    _restricted_roles = ("HoD","Lab-IC","Technician")
    _dept_id = (user or {}).get("dept_id") if role in _restricted_roles else None
    if _dept_id:
        rows = [dict(r) for r in _fa("""
            SELECT ds.*, d.dept_name, it.type_name, inv.invoice_number
            FROM tbl_dept_stock ds
            JOIN tbl_departments d ON d.dept_id=ds.dept_id
            JOIN tbl_item_types it ON it.type_id=ds.type_id
            LEFT JOIN tbl_invoices inv ON inv.invoice_id=ds.invoice_id
            WHERE ds.module_id=? AND ds.dept_id=? ORDER BY ds.entry_date DESC
        """,(mid, _dept_id))]
    else:
        rows = [dict(r) for r in _fa("""
            SELECT ds.*, d.dept_name, it.type_name, inv.invoice_number
            FROM tbl_dept_stock ds
            JOIN tbl_departments d ON d.dept_id=ds.dept_id
            JOIN tbl_item_types it ON it.type_id=ds.type_id
            LEFT JOIN tbl_invoices inv ON inv.invoice_id=ds.invoice_id
            WHERE ds.module_id=? ORDER BY ds.entry_date DESC
        """,(mid,))]
    if not rows: st.info("No DSR entries."); return
    df = pd.DataFrame([{
        "Dept":r["dept_name"],"Type":r["type_name"],"Description":r["description"],
        "Qty":r["qty_received"],"Cost Rs.":r["cost_per_unit"],
        "Invoice":r.get("invoice_number","—"),"Date":r.get("entry_date","")[:10],
        "Remarks":r.get("remarks",""),
    } for r in rows])
    st.dataframe(df,use_container_width=True,hide_index=True)
    export_df(df,f"{mod['module_code']}_Dept_Stock.xlsx")


# ══ TAB 5 — ASSET SEARCH ═════════════════════════════════════════
def _asset_search(mod, user=None, role=None):
    _flash()
    mid = mod["module_id"]
    st.subheader("Asset Search")
    srch = st.text_input("Search UID / Description / Serial / Department",key=f"{mid}_srch")
    if not srch.strip(): st.info("Enter search term."); return
    s = f"%{srch}%"
    items = [dict(r) for r in _fa("""
        SELECT i.*, it.type_name, d.dept_name, l.location_name,
               s.supplier_name, inv.invoice_number, inv.invoice_scan_path
        FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        LEFT JOIN tbl_departments d ON d.dept_id=i.dept_id
        LEFT JOIN tbl_locations l ON l.location_id=i.location_id
        LEFT JOIN tbl_suppliers s ON s.supplier_id=i.supplier_id
        LEFT JOIN tbl_invoices inv ON inv.invoice_id=i.invoice_id
        WHERE i.module_id=? AND i.is_deleted=0
          AND (i.unique_item_id LIKE ? OR i.description LIKE ?
               OR i.serial_number LIKE ? OR d.dept_name LIKE ?)
        ORDER BY i.item_id DESC LIMIT 50
    """,(mid,s,s,s,s))]
    if not items: st.info("No assets found."); return
    opts = {f"{a['unique_item_id']} | {a['description']} | {a.get('dept_name','Central Stock')}": a
            for a in items}
    sel = st.selectbox("Select asset:",list(opts.keys()),key=f"{mid}_srch_sel")
    a   = opts[sel]
    # Display
    c1,c2,c3 = st.columns(3)
    c1.markdown(f"**UID:** `{a['unique_item_id']}`")
    c1.markdown(f"**Type:** {a['type_name']}")
    c1.markdown(f"**Description:** {a['description']}")
    c2.markdown(f"**Make/Model:** {a.get('make','—')} / {a.get('model','—')}")
    c2.markdown(f"**Serial:** {a.get('serial_number','—')}")
    c2.markdown(f"**Cost:** {format_currency(a.get('cost_per_unit'))}")
    c3.markdown(f"**Department:** {a.get('dept_name','Central Stock')}")
    c3.markdown(f"**Location:** {a.get('location_name','—')}")
    c3.markdown(f"**Status:** `{a['item_status']}`")
    st.markdown(f"**Invoice:** {a.get('invoice_number','—')} | **Supplier:** {a.get('supplier_name','—')} | "
                f"**Purchased:** {a.get('purchase_date','—')} | **Warranty To:** {a.get('warranty_to','—')}")
    # Dynamic fields
    fvals = [dict(r) for r in _fa("""
        SELECT fd.field_label, fv.field_value
        FROM tbl_item_field_values fv JOIN tbl_field_defs fd ON fd.field_id=fv.field_id
        WHERE fv.item_id=? ORDER BY fd.sort_order
    """,(a["item_id"],))]
    if fvals:
        st.markdown("**Technical Configuration:**")
        cols = st.columns(3)
        for i,f in enumerate(fvals):
            cols[i%3].markdown(f"**{f['field_label']}:** {f['field_value'] or '—'}")
    if a.get("invoice_scan_path"):
        with st.expander(f"View Invoice Scan — {a.get('invoice_number','')}"):
            show_scan(a["invoice_scan_path"])


# ══ TAB 6 — EDIT / DELETE ════════════════════════════════════════
def _edit_delete(user, mod):
    _flash()
    mid = mod["module_id"]
    st.subheader("Edit / Delete Assets")
    srch = st.text_input("Search asset (UID / Description)",key=f"{mid}_ed_srch")
    if not srch.strip(): st.info("Enter search term."); return
    s = f"%{srch}%"
    items = [dict(r) for r in _fa("""
        SELECT i.*, it.type_name FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        WHERE i.module_id=? AND i.is_deleted=0
          AND (i.unique_item_id LIKE ? OR i.description LIKE ?) LIMIT 20
    """,(mid,s,s))]
    if not items: st.info("Not found."); return
    opts = {f"{a['unique_item_id']} | {a['description']}": a for a in items}
    sel  = st.selectbox("Select:",list(opts.keys()),key=f"{mid}_ed_sel")
    a    = opts[sel]
    t1,t2 = st.tabs(["Edit","Delete"])
    with t1:
        with st.form(f"{mid}_edit_form"):
            e1,e2 = st.columns(2)
            nd=e1.text_input("Description",a["description"]); nm=e2.text_input("Make",a.get("make","") or "")
            e3,e4 = st.columns(2)
            no=e3.text_input("Model",a.get("model","") or ""); ns=e4.text_input("Serial",a.get("serial_number","") or "")
            sts=["WORKING","NOT WORKING","UNDER REPAIR","UNDER MAINTENANCE","CONDEMNED","DISPOSED"]
            ci = sts.index(a["item_status"]) if a["item_status"] in sts else 0
            nst=st.selectbox("Status",sts,index=ci); nw=st.text_input("Warranty To",a.get("warranty_to","") or "")
            if st.form_submit_button("Save Changes",type="primary"):
                conn=get_conn()
                conn.execute("UPDATE tbl_items SET description=?,make=?,model=?,serial_number=?,item_status=?,warranty_to=? WHERE item_id=?",
                             (nd,nm,no,ns,nst,nw,a["item_id"])); conn.commit(); conn.close()
                st.success("Updated."); st.rerun()
    with t2:
        if st.checkbox("Confirm delete",key=f"{mid}_del_chk"):
            if st.button("Delete Asset",type="primary",key=f"{mid}_del_btn"):
                conn=get_conn()
                conn.execute("UPDATE tbl_items SET is_deleted=1 WHERE item_id=?",(a["item_id"],)); conn.commit(); conn.close()
                st.success("Deleted."); st.rerun()


# ══ TAB 7 — DEPT-WISE VIEW ════════════════════════════════════════
def _dept_view(mod, user=None, role=None):
    _flash()
    mid = mod["module_id"]
    st.subheader("Department-wise Asset View")
    _restricted = ("HoD","Lab-IC","Technician")
    _user_dept_id = (user or {}).get("dept_id")
    if role in _restricted and _user_dept_id:
        # Lock to user's own department
        dept_row = _fo("SELECT dept_name FROM tbl_departments WHERE dept_id=?", (_user_dept_id,))
        dept_name = dict(dept_row)["dept_name"] if dept_row else "Your Department"
        st.info(f"Showing assets for: **{dept_name}**")
        dept_id = _user_dept_id
    else:
        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
        if not depts: st.info("No departments."); return
        dm      = {d["dept_name"]: d["dept_id"] for d in depts}
        sel_d   = st.selectbox("Department",list(dm.keys()),key=f"{mid}_dv_dept")
        dept_id = dm[sel_d]
    items   = [dict(r) for r in _fa("""
        SELECT i.unique_item_id, it.type_name, i.description, i.make, i.model,
               i.serial_number, i.item_status, l.location_name, i.warranty_to
        FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        LEFT JOIN tbl_locations l ON l.location_id=i.location_id
        WHERE i.module_id=? AND i.dept_id=? AND i.is_deleted=0
        ORDER BY it.type_name, i.item_id
    """,(mid,dept_id))]
    if not items: st.info(f"No assets in {sel_d}."); return
    df = pd.DataFrame([{
        "UID":r["unique_item_id"],"Type":r["type_name"],"Description":r["description"],
        "Make":r.get("make","—"),"Serial":r.get("serial_number","—"),
        "Location":r.get("location_name","—"),"Status":r["item_status"],"Warranty":r.get("warranty_to","—"),
    } for r in items])
    st.markdown(f"**{len(items)} asset(s) in {sel_d}**")
    st.dataframe(df,use_container_width=True,hide_index=True)
    export_df(df,f"{mod['module_code']}_{sel_d}_Assets.xlsx")


# ══ MANUAL DEPT ENTRY ═════════════════════════════════════════════
def _new_dept_entry(user, role, mod):
    """Manual entry directly into department stock (occasional dept purchases)."""
    _flash()
    mid = mod["module_id"]
    st.subheader("Manual Department Entry")
    st.info(
        "Use this for occasional direct department purchases. "
        "For major procurement use the Procurement module."
    )

    types = [dict(r) for r in _fa(
        "SELECT * FROM tbl_item_types WHERE module_id=? AND is_active=1 ORDER BY type_name",(mid,))]
    if not types: st.warning("No item types configured."); return
    type_map = {t["type_name"]: t for t in types}

    depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    dm    = {d["dept_name"]: d for d in depts}
    supps = [dict(r) for r in _fa("SELECT * FROM tbl_suppliers WHERE is_active=1 ORDER BY supplier_name")]
    s_opts = {"— select —": None}
    s_opts.update({s["supplier_name"]: s["supplier_id"] for s in supps})

    c1,c2 = st.columns(2)
    dept_name = c1.selectbox("Department *", list(dm.keys()), key=f"{mid}_mde_dept")
    sel_s     = c2.selectbox("Supplier", list(s_opts.keys()), key=f"{mid}_mde_supp")
    dept = dm[dept_name]

    locs  = [dict(r) for r in _fa("SELECT * FROM tbl_locations WHERE dept_id=? AND is_active=1",(dept["dept_id"],))]
    lm    = {"— No specific location —": None}
    lm.update({l["location_name"]: l["location_id"] for l in locs})
    to_loc = st.selectbox("Location", list(lm.keys()), key=f"{mid}_mde_loc")

    c3,c4 = st.columns(2)
    bill_no  = c3.text_input("Bill / Invoice No", key=f"{mid}_mde_bill")
    bill_date= c4.date_input("Bill Date", key=f"{mid}_mde_date")

    # Invoice scan upload (outside form)
    inv_scan = st.file_uploader("Upload Bill / Invoice Scan",
                                type=["pdf","jpg","jpeg","png"], key=f"{mid}_mde_scan")

    st.markdown("---")
    st.markdown("**Item Details**")
    r1,r2,r3,r4 = st.columns([2,1,2,2])
    atype = r1.selectbox("Type *", list(type_map.keys()), key=f"{mid}_mde_type")
    qty   = r2.number_input("Qty *", min_value=1, value=1, key=f"{mid}_mde_qty")
    desc  = r3.text_input("Description *", key=f"{mid}_mde_desc")
    make  = r4.text_input("Make/Brand", key=f"{mid}_mde_make")
    r5,r6 = st.columns(2)
    cost  = r5.number_input("Cost/Unit (Rs.) *", min_value=0.0, step=100.0, key=f"{mid}_mde_cost")
    serial= r6.text_input("Serial No", key=f"{mid}_mde_serial")
    rem   = st.text_input("Remarks", key=f"{mid}_mde_rem")

    if cost > 0 and qty > 0:
        st.caption(f"Subtotal: Rs.{qty*cost:,.2f}")

    if st.button("Save Entry", type="primary", use_container_width=True, key=f"{mid}_mde_save"):
        if not desc.strip(): st.error("Description required."); return
        if cost <= 0: st.error("Cost must be > 0."); return
        try:
            conn = get_conn()
            ti    = type_map[atype]
            sup_id= s_opts[sel_s]

            # Create invoice if bill number given
            inv_id = None
            if bill_no.strip() and sup_id:
                inv_id = conn.execute("""
                    INSERT INTO tbl_invoices (module_id,invoice_number,invoice_date,supplier_id,
                        total_amount,received_by,remarks)
                    VALUES (?,?,?,?,?,?,?)
                """,(mid,bill_no.strip(),str(bill_date),sup_id,qty*cost,user["user_id"],rem)).lastrowid
                conn.commit()
                # Save scan
                scan_path = save_scan(inv_scan, bill_no.strip()) if inv_scan else None
                if scan_path:
                    conn.execute("UPDATE tbl_invoices SET invoice_scan_path=? WHERE invoice_id=?",
                                 (scan_path, inv_id))

            # Create asset(s)
            created = []
            from datetime import date as _date
            for u in range(int(qty)):
                ser = f"{serial}-{u+1:03d}" if qty>1 and serial else serial
                uid = generate_item_id(mod["module_code"], dept["dept_code"], ti["id_prefix"], str(bill_date))
                item_id = conn.execute("""
                    INSERT INTO tbl_items (module_id,type_id,unique_item_id,invoice_id,supplier_id,
                        description,make,serial_number,cost_per_unit,purchase_date,
                        dept_id,location_id,item_status,created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,(mid,ti["type_id"],uid,inv_id,sup_id,desc.strip(),make,ser,
                     cost,str(bill_date),dept["dept_id"],lm[to_loc],"WORKING",user["user_id"])).lastrowid
                created.append(uid)

            # DSR entry
            conn.execute("""
                INSERT INTO tbl_dept_stock
                    (module_id,dept_id,invoice_id,type_id,description,qty_received,cost_per_unit,remarks)
                VALUES (?,?,?,?,?,?,?,?)
            """,(mid,dept["dept_id"],inv_id,ti["type_id"],desc.strip(),qty,cost,rem))
            conn.commit(); conn.close()

            st.session_state["_stock_msg"] = ("s",
                f"{qty} asset(s) added to {dept_name}. IDs: {', '.join(created)}")
            st.rerun()
        except Exception as ex: st.error(f"Failed: {ex}")
