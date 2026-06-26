"""
pages/module_home.py — Generic module home page with full sidebar navigation.
This is the landing page when any module is opened.
All sub-modules route through here.

Usage:
    from pages.module_home import show
    show(MODULE_CODE)
"""
import streamlit as st
from db.connection import fetchone as _fo, fetchall as _fa
from utils.auth import current_user, require_module_access, get_user_module_role
from config import MODULES


def show(module_code):
    role = require_module_access(module_code)
    user = current_user()
    mod  = _fo("SELECT * FROM tbl_modules WHERE module_code=?", (module_code,))
    if not mod: st.error(f"Module '{module_code}' not found."); return
    mod  = dict(mod); mid = mod["module_id"]

    # Store current module in session
    st.session_state["sims_module"] = module_code

    # Get subpage — default to dashboard
    subpage = st.session_state.get(f"sub_{module_code}", "dashboard")

    # Render module sidebar
    _render_module_sidebar(module_code, mod, role)

    # Route to subpage
    _route(subpage, module_code, mod, role, user)


def _render_module_sidebar(module_code, mod, role):
    """Render module-specific sidebar with privilege-aware navigation."""
    mc    = mod["module_code"]
    info  = MODULES.get(mc, {})
    color = info.get("color", "#1B4F9A")
    user  = current_user()

    # Import privilege checker
    from components.header import _can_see

    with st.sidebar:
        # Module header
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,{color}CC,{color});
                    padding:10px 14px;border-radius:8px;
                    border-bottom:3px solid #F0A500;margin-bottom:12px">
          <p style="color:#FFFFFF;font-weight:900;font-size:0.9rem;margin:0">
            {mod['module_icon']} {mod['module_name']}</p>
          <p style="color:#FFE0B2;font-size:0.72rem;margin:3px 0 0 0">
            Role: {role}</p>
        </div>
        """, unsafe_allow_html=True)

        def nav(label, sub):
            if st.button(label, use_container_width=True, key=f"snb_{mc}_{sub}"):
                st.session_state[f"sub_{mc}"] = sub
                st.rerun()

        def pnav(label, sub, priv_key):
            """Privilege-aware nav — only shows if user can see it."""
            if _can_see(user, mc, priv_key):
                nav(label, sub)

        def sec(icon, title, color="#F0A500"):
            st.markdown(
                f'<div style="background:linear-gradient(90deg,#0D2B5E,#1B4F9A);'
                f'padding:5px 10px;border-radius:5px;margin:8px 0 3px;'
                f'border-left:3px solid {color}">'
                f'<span style="color:{color};font-size:0.75rem;font-weight:800">'
                f'{icon} {title.upper()}</span></div>',
                unsafe_allow_html=True)

        # Dashboard
        if st.button("🏠  Module Dashboard", type="primary",
                     use_container_width=True, key=f"snb_{mc}_dash"):
            st.session_state[f"sub_{mc}"] = "dashboard"; st.rerun()

        # Back to Portal
        if st.button("◀  Back to Portal", use_container_width=True, key=f"snb_{mc}_back"):
            st.session_state["sims_module"] = ""
            st.session_state["page"] = "dashboard"; st.rerun()

        sec("🔍", "Inventory", "#4FC3F7")
        pnav("📋  Asset Search & Edit",   "asset_search",  "Inventory — Asset Search & Edit")
        pnav("📄  Case Sheets",           "case_sheets",   "Inventory — Case Sheets")

        sec("📊", "Stock Registers", "#81C784")
        pnav("🏛  Central Stock",         "central_stock", "Stock — Central Stock")
        pnav("🏢  Department Stock",      "dept_stock",    "Stock — Department Stock")

        sec("🛒", "Procurement", "#FFB74D")
        pnav("📤  Forward Procurement",   "proc_forward",  "Procurement — Forward")
        pnav("✅  Pending Approvals",     "proc_approvals","Procurement — Pending Approvals")
        pnav("✏️  Joint Data Entry",      "proc_entry",    "Procurement — Joint Data Entry")
        pnav("📋  Procurement Log",       "proc_log",      "Procurement — Log")
        pnav("📥  Bulk Upload",           "bulk_upload",   "Procurement — Bulk Upload")

        sec("🔧", "Complaints", "#EF9A9A")
        pnav("🆕  Raise Complaint",       "raise_complaint","Complaints — Raise Complaint")
        pnav("📥  My Inbox",              "my_inbox",      "Complaints — My Inbox")
        pnav("📂  Complaint Register",    "complaint_register","Complaints — Complaint Register")
        pnav("❌  Cancel / Manage Calls", "cancel_calls",     "Complaints — Cancel / Manage")
        pnav("🔩  Spare Parts Indent",    "spare_indent",  "Complaints — Spare Parts Indent")
        pnav("📄  Closure Report",        "closure_report","Complaints — Closure Report")

        sec("🔒", "Warranty", "#CE93D8")
        pnav("⚠️  Warranty Alerts",       "warranty_alerts","Warranty — Alerts")
        pnav("📅  Expiring Soon",         "warranty_expiring","Warranty — Expiring Soon")

        if mod.get("has_maintenance", 1):
            sec("🛠", "Maintenance", "#80DEEA")
            pnav("🔧  Maintenance Sheet",     "maintenance_sheet","Maintenance — Sheet")
            pnav("🚚  Asset Movement",        "asset_movement","Maintenance — Asset Movement")
            pnav("🏭  Lab Maint. Register",   "lab_maint",     "Maintenance — Lab Register")

        sec("📈", "Reports", "#A5D6A7")
        pnav("📊  Reports & Export",      "reports",       "Reports")

        if role in ("SuperAdmin","SysAdmin","Coordinator"):
            sec("⚙️", "Administration", "#F48FB1")
            pnav("👥  User Management",       "admin_users",   "Administration — User Management")
            pnav("🏫  Dept & Lab Setup",      "admin_depts",   "Administration — Dept & Lab Setup")
            pnav("🏭  Suppliers",             "admin_suppliers","Administration — Suppliers")
            pnav("🔐  Role & Privileges",     "admin_matrix",  "Administration — Role & Privileges")
            pnav("✏️  Rename Roles",          "role_rename",   "Administration — Rename Roles")
            pnav("📜  Audit Log",             "admin_audit",   "Administration — Audit Log")
            if user.get("is_super_admin"):
                pnav("🆔  Asset UID Format",      "admin_uidfmt",  "Administration — UID Format")

        sec("👤", "Account", "#B0BEC5")
        pnav("🔔  Notifications",         "notifications", "Account — Notifications")
        pnav("🔑  Change Password",       "change_password","Account — Change Password")


def _route(subpage, module_code, mod, role, user):
    """Route to correct page — each sub-module opens its own dedicated page."""
    mc  = module_code
    mid = mod["module_id"]
    icon = mod.get("module_icon","📦")
    name = mod.get("module_name","")

    if subpage == "dashboard":
        _module_dashboard(mod, role)

    # ── Stock Register sub-pages ───────────────────────────────────
    elif subpage in ("central_stock","asset_search","case_sheets","new_entry","issue_to_dept"):
        # Central Stock — full page with tabs matching IT-IIMS Central Stock
        from pages.common_stock import _new_entry, _issue_to_dept, _view_stock, _asset_search, _edit_delete, _dept_view, _get_module
        m = _get_module(mc)
        st.title(f"{icon} {name} — Central Stock")
        if st.session_state.get("_stock_msg"):
            t, msg = st.session_state.pop("_stock_msg")
            (st.success if t == "s" else st.error)(msg)
        is_admin = role in ("SuperAdmin","SysAdmin","Coordinator")
        if is_admin:
            tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
                "➕ New Procurement Entry",
                "📥 Bulk Upload",
                "🔀 Issue to Department",
                "📋 View Central Stock",
                "🔍 Asset Detail Search",
                "✏️ Edit / Delete Entries",
                "🏢 Dept-wise View",
            ])
            with tab1: _new_entry(user, role, m)
            with tab2: _bulk_upload(m, m["module_id"], user)
            with tab3: _issue_to_dept(user, role, m)
            with tab4: _view_stock(m)
            with tab5: _asset_search(m)
            with tab6: _edit_delete(user, m)
            with tab7: _dept_view(m)
        else:
            tab1,tab2 = st.tabs(["📋 View Central Stock","🔍 Asset Search"])
            with tab1: _view_stock(m)
            with tab2: _asset_search(m)

    elif subpage == "dept_stock":
        from pages.common_stock import _dept_stock, _dept_view, _new_dept_entry, _get_module
        m = _get_module(mc)
        st.title(f"{icon} {name} — Department Stock")
        if st.session_state.get("_stock_msg"):
            t, msg = st.session_state.pop("_stock_msg")
            (st.success if t == "s" else st.error)(msg)
        tab1,tab2,tab3,tab4,tab5 = st.tabs([
            "📋 Stock Register",
            "📦 All Assets in Dept",
            "📊 Category Summary",
            "➕ Manual Department Entry",
            "🏷 Assign to Lab",
        ])
        with tab1: _dept_stock(m)
        with tab2: _dept_view(m)
        with tab3: _category_summary(m, mid)
        with tab4: _new_dept_entry(user, role, m)
        with tab5: _assign_to_lab_sims(m, mid, user, role)

    # ── Procurement — each sidebar item = dedicated page like IT-IIMS
    elif subpage == "proc_forward":
        from pages.common_procurement import _forward
        st.title("📤 Forward Procurement to Lab Faculty")
        if st.session_state.get(f"_proc_msg_{mid}"):
            t, msg = st.session_state.pop(f"_proc_msg_{mid}")
            (st.success if t == "s" else st.error)(msg)
        _forward(user, role, mod, mid)

    elif subpage == "proc_entry":
        from pages.common_procurement import _joint_entry
        st.title("✏️ Procurement Data Entry (Joint)")
        if st.session_state.get(f"_proc_msg_{mid}"):
            t, msg = st.session_state.pop(f"_proc_msg_{mid}")
            (st.success if t == "s" else st.error)(msg)
        _joint_entry(user, role, mod, mid)

    elif subpage == "proc_approvals":
        from pages.common_procurement import _approvals
        st.title("✅ Procurement Pending Approvals")
        _approvals(user, role, mod, mid)

    elif subpage == "proc_log":
        from pages.common_procurement import _log
        st.title(f"{icon} {name} — Procurement Log")
        _log(user, role, mod, mid)

    elif subpage == "bulk_upload":
        st.title(f"{icon} {name} — Bulk Upload")
        _bulk_upload(mod, mid, user)

    # ── Complaints — each sidebar item opens its own page ─────────
    elif subpage == "my_inbox":
        from pages.common_inbox import _tab_pending, _tab_register
        st.title("📥 Complaint Inbox")
        if st.session_state.get(f"_inbox_msg_{mid}"):
            t, msg = st.session_state.pop(f"_inbox_msg_{mid}")
            (st.success if t == "s" else st.error)(msg)
        itab1, itab2 = st.tabs([
            "⏳ Pending My Action",
            "📋 All My Complaints",
        ])
        with itab1: _tab_pending(user, role, mod, mid)
        with itab2: _tab_register(user, role, mod, mid)
    elif subpage == "cancel_calls":
        from pages.cancel_calls import show as cc_show
        st.title("❌ Cancel / Manage Calls")
        cc_show(module_code)

    elif subpage == "raise_complaint":
        st.title("🆕 Raise Complaint Call")
        if st.session_state.get(f"_raise_msg_{mid}"):
            t, msg = st.session_state.pop(f"_raise_msg_{mid}")
            (st.success if t == "s" else st.error)(msg)
        from pages.common_inbox import _tab_raise
        _tab_raise(user, role, mod, mid)

    elif subpage == "complaint_register":
        from pages.common_inbox import _tab_register
        st.title("📂 Complaint Register")
        _tab_register(user, role, mod, mid)

    elif subpage == "spare_indent":
        from pages.common_inbox import _tab_spare_indent
        st.title("🔩 Spare Parts Indent")
        if st.session_state.get(f"_indent_msg_{mid}"):
            t, msg = st.session_state.pop(f"_indent_msg_{mid}")
            (st.success if t == "s" else st.error)(msg)
        _tab_spare_indent(user, role, mod, mid)

    elif subpage == "closure_report":
        from pages.call_report import show as cr_show
        cr_show(module_code)
    elif subpage == "warranty_alerts":
        from pages.common_warranty import _alerts
        st.title(f"{icon} {name} — Warranty Alerts")
        _alerts(mod, mid)

    elif subpage == "warranty_expiring":
        from pages.common_warranty import _expiring
        st.title(f"{icon} {name} — Expiring Soon")
        _expiring(mod, mid)

    # ── Maintenance sub-pages ──────────────────────────────────────
    elif subpage == "maintenance_sheet":
        from pages.common_maintenance import _maint_sheet
        st.title(f"{icon} {name} — Maintenance Sheet")
        _maint_sheet(user, role, mod, mid)

    elif subpage == "asset_movement":
        from pages.common_maintenance import _asset_movement
        st.title(f"{icon} {name} — Asset Movement")
        _asset_movement(user, role, mod, mid)

    elif subpage == "lab_maint":
        from pages.common_maintenance import _lab_maint
        st.title(f"{icon} {name} — Lab Maintenance Register")
        _lab_maint(user, role, mod, mid)

    # ── Inventory — Asset Search / Case Sheets ─────────────────────
    elif subpage == "asset_search":
        from pages.common_stock import _asset_search, _get_module
        m = _get_module(mc)
        st.title(f"{icon} {name} — Asset Search & Edit")
        _asset_search(m)

    elif subpage == "case_sheets":
        from pages.common_stock import _asset_search, _get_module
        m = _get_module(mc)
        st.title(f"{icon} {name} — Case Sheets")
        _asset_search(m)

    # ── Reports ────────────────────────────────────────────────────
    elif subpage == "reports":
        from pages.common_reports import show as rep_show
        rep_show(mc)

    # ── Administration sub-pages ───────────────────────────────────
    elif subpage == "admin_users":
        from pages.common_admin import show_users
        st.title("👥 User Management")
        show_users(mc)

    elif subpage == "admin_depts":
        from pages.common_admin import show_depts
        st.title("🏫 Dept & Lab Setup")
        show_depts(mc)

    elif subpage == "admin_suppliers":
        from pages.common_admin import show_suppliers
        st.title("🏭 Supplier Master")
        show_suppliers(mc)

    elif subpage == "admin_matrix":
        from pages.sims_role_permissions import show as rp_show
        rp_show(mc)
    elif subpage == "role_rename":
        from pages.role_rename_tool import show as rr_show
        st.title("✏️ Rename Roles")
        rr_show(module_code)

    elif subpage == "admin_audit":
        from pages.common_admin import show_audit
        st.title("📜 Audit Log")
        show_audit(mc)

    elif subpage == "admin_uidfmt":
        from pages.uid_format import show as uidfmt_show
        uidfmt_show(mc)

    # ── Account ────────────────────────────────────────────────────
    elif subpage == "notifications":
        from pages.common_notifications import show as notif_show
        st.title("🔔 Notifications")
        notif_show()

    elif subpage == "change_password":
        from pages.common_account import show as acct_show
        st.title("🔑 Change Password")
        acct_show()

    else:
        _module_dashboard(mod, role)


def _assign_to_lab_sims(mod, mid, user, role):
    """Assign unassigned dept assets to specific locations — SRGEC-SIMS version."""
    from db.connection import get_conn, fetchall as _fa
    from collections import defaultdict
    import pandas as pd

    st.subheader("🏷 Assign Assets to Location / Lab")
    st.info(
        "Assets issued from **Central Stock** to this department appear here as "
        "**Unassigned** until the coordinator distributes them to specific locations."
    )

    if role not in ("SuperAdmin","SysAdmin","Coordinator","HoD"):
        st.warning("Only SysAdmin / Coordinator / HoD can assign assets to locations.")
        # Read-only view
        unassigned = [dict(r) for r in _fa("""
            SELECT i.unique_item_id, it.type_name, i.description, i.item_status
            FROM tbl_items i JOIN tbl_item_types it ON it.type_id=i.type_id
            WHERE i.module_id=? AND i.dept_id IS NOT NULL
              AND i.location_id IS NULL AND i.is_deleted=0
            ORDER BY it.type_name, i.item_id
        """,(mid,))]
        if unassigned:
            st.warning(f"{len(unassigned)} unassigned asset(s):")
            st.dataframe(pd.DataFrame(unassigned), use_container_width=True, hide_index=True)
        return

    # Get unassigned assets (dept assigned, no location)
    unassigned = [dict(r) for r in _fa("""
        SELECT i.item_id, i.unique_item_id, i.description,
               i.item_status, it.type_name, it.type_id,
               d.dept_id, d.dept_name
        FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        JOIN tbl_departments d ON d.dept_id=i.dept_id
        WHERE i.module_id=? AND i.dept_id IS NOT NULL
          AND i.location_id IS NULL AND i.is_deleted=0
        ORDER BY it.type_name, i.item_id
    """,(mid,))]

    if not unassigned:
        st.success("✅ All assets are assigned to locations.")
        _show_location_summary(mid)
        return

    by_type = defaultdict(list)
    for a in unassigned: by_type[a["type_name"]].append(a)

    # Get unique depts in unassigned
    depts_in = list(set(a["dept_name"] for a in unassigned))
    dept_ids_in = list(set(a["dept_id"] for a in unassigned))

    st.markdown(
        f"<div style='background:#fff3cd;padding:10px;border-radius:6px;"
        f"border-left:4px solid #ffc107'>"
        f"<b>⚠️ {len(unassigned)} asset(s) unassigned</b> across: "
        f"{', '.join(depts_in)}</div>", unsafe_allow_html=True
    )
    st.markdown("")
    for tn, assets in by_type.items():
        st.markdown(f"  - **{tn}**: {len(assets)} unit(s)")

    st.divider()

    # Get all locations across relevant depts
    all_locs = []
    for did in dept_ids_in:
        locs = [dict(r) for r in _fa(
            "SELECT location_id, location_name, dept_id FROM tbl_locations WHERE dept_id=? AND is_active=1",(did,))]
        all_locs.extend(locs)

    if not all_locs:
        st.error("No locations configured. Add locations in Administration → Dept & Lab Setup.")
        return

    loc_map = {f"{l['location_name']}": l["location_id"] for l in all_locs}

    if st.session_state.get(f"_asgn_msg_{mid}"):
        t,m = st.session_state.pop(f"_asgn_msg_{mid}")
        (st.success if t=="s" else st.error)(m)

    # Option A — Bulk by type
    st.markdown("#### Option A — Assign by Asset Type (Bulk)")
    with st.expander("Assign all units of a type to one location", expanded=True):
        c1,c2,c3 = st.columns(3)
        sel_type = c1.selectbox("Asset Type *", list(by_type.keys()), key=f"asl_type_{mid}")
        avail    = by_type[sel_type]
        max_qty  = len(avail)
        qty_asgn = c2.number_input(f"Quantity (max {max_qty})",
                                   min_value=1, max_value=max_qty, value=max_qty,
                                   key=f"asl_qty_{mid}")
        sel_loc  = c3.selectbox("Assign to Location *", list(loc_map.keys()),
                                key=f"asl_loc_{mid}")
        st.markdown(f"Will assign **{qty_asgn}** `{sel_type}` → **{sel_loc}**")

        if st.button("✅ Assign to Location", type="primary", key=f"asl_submit_{mid}"):
            to_assign = avail[:int(qty_asgn)]
            loc_id    = loc_map[sel_loc]
            try:
                conn = get_conn()
                for a in to_assign:
                    conn.execute("UPDATE tbl_items SET location_id=? WHERE item_id=?",
                                 (loc_id, a["item_id"]))
                conn.commit(); conn.close()
                st.session_state[f"_asgn_msg_{mid}"] = (
                    "s", f"{qty_asgn} {sel_type}(s) assigned to **{sel_loc}**.")
                st.rerun()
            except Exception as ex: st.error(f"Failed: {ex}")

    st.markdown("---")

    # Option B — Individual UIDs
    st.markdown("#### Option B — Assign Individual Assets by UID")
    with st.expander("Select specific asset UIDs"):
        df_un = pd.DataFrame([{
            "UID":r["unique_item_id"],"Type":r["type_name"],
            "Description":r["description"],"Dept":r["dept_name"],
        } for r in unassigned])
        st.dataframe(df_un, use_container_width=True, hide_index=True)
        uid_input = st.text_area("Asset UIDs (one per line or comma-separated)",
                                 key=f"asl_uids_{mid}", height=80)
        sel_loc2  = st.selectbox("Assign to Location *", list(loc_map.keys()),
                                 key=f"asl_loc2_{mid}")
        if st.button("✅ Assign Selected", type="primary", key=f"asl_uid_{mid}"):
            if not uid_input.strip(): st.error("Enter at least one UID."); return
            uids = [u.strip() for u in uid_input.replace(",","\n").split("\n") if u.strip()]
            loc_id2 = loc_map[sel_loc2]
            ok = []; not_found = []
            conn = get_conn()
            for uid in uids:
                item = conn.execute(
                    "SELECT item_id FROM tbl_items WHERE unique_item_id=? AND module_id=?",
                    (uid,mid)).fetchone()
                if not item: not_found.append(uid); continue
                conn.execute("UPDATE tbl_items SET location_id=? WHERE item_id=?",
                             (loc_id2,dict(item)["item_id"]))
                ok.append(uid)
            conn.commit(); conn.close()
            if ok: st.success(f"{len(ok)} asset(s) assigned to {sel_loc2}.")
            if not_found: st.warning(f"Not found: {', '.join(not_found)}")
            if ok: st.rerun()

    st.divider()
    _show_location_summary(mid)


def _show_location_summary(mid):
    from db.connection import fetchall as _fa
    import pandas as pd
    st.markdown("#### 📊 Current Location-wise Distribution")
    rows = [dict(r) for r in _fa("""
        SELECT d.dept_name, l.location_name, it.type_name, COUNT(*) AS total
        FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        JOIN tbl_departments d ON d.dept_id=i.dept_id
        JOIN tbl_locations l ON l.location_id=i.location_id
        WHERE i.module_id=? AND i.location_id IS NOT NULL AND i.is_deleted=0
        GROUP BY i.dept_id, i.location_id, i.type_id
        ORDER BY d.dept_name, l.location_name
    """,(mid,))]
    if not rows: st.info("No assets assigned to locations yet."); return
    df = pd.DataFrame(rows)
    pivot = df.pivot_table(index=["dept_name","location_name"],
                           columns="type_name", values="total",
                           aggfunc="sum", fill_value=0)
    pivot["TOTAL"] = pivot.sum(axis=1)
    st.dataframe(pivot, use_container_width=True)


def _bulk_upload(mod, mid, user):
    """Bulk upload assets from Excel template — mirrors IT-IIMS bulk upload."""
    import pandas as pd
    st.subheader("Bulk Upload Assets")

    # Download template
    template_cols = [
        "description","type_code","make","model","serial_number",
        "cost_per_unit","purchase_date","warranty_from","warranty_to",
        "invoice_number","supplier_name"
    ]
    import io
    buf = io.BytesIO()
    pd.DataFrame(columns=template_cols).to_excel(buf, index=False, engine="openpyxl")
    st.download_button(
        "📥 Download Excel Template",
        buf.getvalue(),
        file_name=f"{mod['module_code']}_bulk_upload_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{mid}_bu_template"
    )
    st.caption("Fill in the template and upload below. One row = one asset unit.")
    st.divider()

    # Upload
    uploaded = st.file_uploader("Choose Excel (.xlsx)", type=["xlsx"], key=f"{mid}_bu_file")
    if not uploaded:
        st.info("Download template above, fill it in, then upload here.")
        return

    try:
        df = pd.read_excel(uploaded, dtype=str)
        df = df.fillna("")
        st.success(f"{len(df)} rows found")
        st.dataframe(df.head(5), use_container_width=True, hide_index=True)
        st.caption(f"Preview showing first 5 of {len(df)} rows")
    except Exception as ex:
        st.error(f"Could not read file: {ex}"); return

    # Validation
    required = ["description","type_code","cost_per_unit","purchase_date"]
    missing  = [col for col in required if col not in df.columns]
    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}"); return

    depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    dm    = {"Central Stock (no dept)": None}
    dm.update({d["dept_name"]: d["dept_id"] for d in depts})
    target_dept = st.selectbox("Assign all to department", list(dm.keys()), key=f"{mid}_bu_dept")

    if st.button("Upload & Register All", type="primary", key=f"{mid}_bu_submit"):
        from db.connection import get_conn
        from utils.helpers import generate_item_id
        conn = get_conn()
        ok = fail = 0
        errors = []
        for idx, row in df.iterrows():
            try:
                type_code = str(row.get("type_code","")).strip().upper()
                ti = conn.execute(
                    "SELECT * FROM tbl_item_types WHERE module_id=? AND type_code=?",
                    (mid, type_code)).fetchone()
                if not ti:
                    errors.append(f"Row {idx+2}: type_code '{type_code}' not found")
                    fail += 1; continue
                ti = dict(ti)
                dept_id = dm[target_dept]
                uid = generate_item_id(
                    mod["module_code"],
                    "CS" if not dept_id else target_dept[:4].upper(),
                    ti["id_prefix"], str(row.get("purchase_date",""))[:10] or "2026-01-01"
                )
                conn.execute("""
                    INSERT INTO tbl_items (module_id,type_id,unique_item_id,
                        description,make,model,serial_number,cost_per_unit,
                        purchase_date,warranty_from,warranty_to,
                        dept_id,item_status,created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,(mid, ti["type_id"], uid,
                     str(row.get("description","")).strip(),
                     str(row.get("make","")).strip(),
                     str(row.get("model","")).strip(),
                     str(row.get("serial_number","")).strip(),
                     float(row.get("cost_per_unit",0) or 0),
                     str(row.get("purchase_date",""))[:10],
                     str(row.get("warranty_from",""))[:10] or None,
                     str(row.get("warranty_to",""))[:10] or None,
                     dept_id, "WORKING", user["user_id"]))
                ok += 1
            except Exception as ex:
                errors.append(f"Row {idx+2}: {ex}"); fail += 1
        conn.commit(); conn.close()
        st.success(f"Uploaded: {ok} assets registered.")
        if fail: st.warning(f"{fail} rows failed:")
        for e in errors[:10]: st.caption(e)


def _raise_complaint_page(user, role, mod, mid):
    """Raise complaint — matches IT-IIMS raise_call.py exactly."""
    from db.connection import get_conn
    from utils.helpers import save_scan

    # Dept lock for Lab-IC / Technician
    if user.get("dept_id"):
        dept_id   = user["dept_id"]
        dept_name = user.get("dept_name","")
        st.info(f"Department: **{dept_name}**")
    else:
        depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
        dm    = {d["dept_name"]: d["dept_id"] for d in depts}
        dept_name = st.selectbox("Department", list(dm.keys()), key=f"{mid}_rc_dept")
        dept_id   = dm[dept_name]

    # Location
    locs = [dict(r) for r in _fa("SELECT * FROM tbl_locations WHERE dept_id=? AND is_active=1",(dept_id,))]
    if locs:
        lm    = {l["location_name"]: l["location_id"] for l in locs}
        if user.get("location_id") and user.get("location_id") in lm.values():
            location_id = user["location_id"]
            st.info(f"Lab / Location: **{next(k for k,v in lm.items() if v==location_id)}**")
        else:
            loc_name    = st.selectbox("Laboratory / Location", list(lm.keys()), key=f"{mid}_rc_loc")
            location_id = lm[loc_name]
    else:
        location_id = None

    # Asset selection
    st.markdown("### Select Asset")
    uid_input = st.text_input(
        "Enter Unique Asset ID *",
        placeholder=f"e.g. {mod['module_code']}_CSE_06_2026_UPS_00001",
        key=f"{mid}_rc_uid"
    )

    asset = None
    if uid_input.strip():
        asset = _fo("""
            SELECT i.*, it.type_name, s.supplier_name,
                   s.contact_person, s.phone AS supplier_phone
            FROM tbl_items i
            JOIN tbl_item_types it ON it.type_id=i.type_id
            LEFT JOIN tbl_suppliers s ON s.supplier_id=i.supplier_id
            WHERE i.unique_item_id=? AND i.module_id=?
        """,(uid_input.strip(), mid))

        if not asset:
            st.error("Asset not found. Check the Asset UID.")
        else:
            asset = dict(asset)
            st.success(
                f"**{asset['type_name']}** — {asset['description']} | "
                f"{asset.get('make','')} | Status: `{asset['item_status']}`"
            )

            # ── WARRANTY CHECK ────────────────────────────────────────────
            from datetime import date as _date
            wto = asset.get("warranty_to","")
            if wto and str(wto)[:10] >= str(_date.today()):
                msg = (
                    "WARRANTY ALERT — THIS ASSET IS UNDER WARRANTY  \n"
                    f"Warranty Valid Until: {wto[:10]}  \n"
                    f"Supplier: {asset.get('supplier_name','—')} | "
                    f"{asset.get('contact_person','—')} | {asset.get('supplier_phone','—')}  \n"
                    "Do NOT repair locally. This call will be routed to System Administrator."
                )
                st.error(msg)
            elif not wto:
                st.warning(
                    "Warranty date not recorded for this asset. "
                    "System Administrator will verify warranty status."
                )

    st.divider()
    st.markdown("### Complaint Details")
    complaint_text = st.text_area(
        "Nature of Complaint *",
        placeholder="Describe the fault in detail...",
        key=f"{mid}_rc_complaint",
        height=120
    )
    photo = st.file_uploader(
        "Attach Photo (optional)",
        type=["jpg","jpeg","png"],
        key=f"{mid}_rc_photo"
    )

    if st.button("Submit Complaint", type="primary",
                 use_container_width=True, key=f"{mid}_rc_submit"):
        if not asset:
            st.error("Please enter a valid Asset UID."); return
        if not complaint_text.strip():
            st.error("Please describe the complaint."); return
        if not location_id and locs:
            st.error("Please select a laboratory/location."); return
        try:
            count   = dict(_fo("SELECT COUNT(*) c FROM tbl_calls WHERE module_id=?",(mid,)) or {"c":0})["c"]
            call_no = f"{mod['module_code']}-CALL-{count+1:04d}"
            photo_path = save_scan(photo, call_no) if photo else None

            conn = get_conn()
            conn.execute("""
                INSERT INTO tbl_calls (module_id,call_number,item_id,raised_by,
                    dept_id,location_id,complaint_text,call_status,photo_path)
                VALUES (?,?,?,?,?,?,?,'OPEN',?)
            """,(mid,call_no,asset["item_id"],user["user_id"],
                 dept_id,location_id,complaint_text.strip(),photo_path))
            call_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("""
                INSERT INTO tbl_call_workflow
                    (call_id,action_by,action_type,action_comment,from_status,to_status)
                VALUES (?,?,'Complaint Raised',?,'NONE','OPEN')
            """,(call_id,user["user_id"],complaint_text.strip()))
            conn.commit(); conn.close()

            st.success(
                f"Complaint submitted! Call ID: {call_no}. "
                "Your complaint has been registered."
            )
        except Exception as ex:
            st.error(f"Failed to submit complaint: {ex}")


def _category_summary(mod, mid):
    """Category-wise summary for dept stock."""
    import pandas as pd
    from db.connection import fetchall as _fa
    st.subheader("Category Summary")
    depts = [dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    if not depts: st.info("No departments."); return
    dm   = {d["dept_name"]: d["dept_id"] for d in depts}
    sel  = st.selectbox("Department", list(dm.keys()), key=f"cs_dept_{mid}")
    rows = [dict(r) for r in _fa("""
        SELECT it.type_name,
               COUNT(*) AS total,
               SUM(CASE WHEN i.item_status="WORKING" THEN 1 ELSE 0 END) AS working,
               SUM(CASE WHEN i.item_status!="WORKING" THEN 1 ELSE 0 END) AS faulty,
               SUM(i.cost_per_unit) AS total_value
        FROM tbl_items i
        JOIN tbl_item_types it ON it.type_id=i.type_id
        WHERE i.module_id=? AND i.dept_id=? AND i.is_deleted=0
        GROUP BY i.type_id ORDER BY total DESC
    """,(mid, dm[sel]))]
    if not rows: st.info(f"No assets in {sel}."); return
    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    m1,m2,m3 = st.columns(3)
    m1.metric("Total Assets", sum(r["total"] for r in rows))
    m2.metric("Working", sum(r["working"] for r in rows))
    m3.metric("Faulty", sum(r["faulty"] for r in rows))


def _module_dashboard(mod, role):
    """Module-specific dashboard with metrics."""
    mid = mod["module_id"]
    mc  = mod["module_code"]

    st.title(f"{mod['module_icon']} {mod['module_name']} — Dashboard")
    st.caption(f"Your role: **{role}**")

    # Metrics
    try:
        total   = dict(_fo("SELECT COUNT(*) c FROM tbl_items WHERE module_id=? AND is_deleted=0",(mid,)) or {"c":0})["c"]
        central = dict(_fo("SELECT COUNT(*) c FROM tbl_items WHERE module_id=? AND dept_id IS NULL AND is_deleted=0",(mid,)) or {"c":0})["c"]
        open_c  = dict(_fo("SELECT COUNT(*) c FROM tbl_calls WHERE module_id=? AND call_status='OPEN'",(mid,)) or {"c":0})["c"]
        working = dict(_fo("SELECT COUNT(*) c FROM tbl_items WHERE module_id=? AND item_status='WORKING' AND is_deleted=0",(mid,)) or {"c":0})["c"]
        faulty  = total - working

        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("Total Assets",   total)
        m2.metric("Central Stock",  central)
        m3.metric("Open Complaints",open_c)
        m4.metric("Working",        working)
        m5.metric("Faulty",         faulty)
    except Exception: pass

    st.divider()

    # Quick actions
    user = current_user()
    col2,col3 = st.columns(2)

    with col2:
        st.markdown("#### Recent Complaints")
        try:
            calls = [dict(r) for r in _fa("""
                SELECT c.call_number, c.call_status, c.created_at,
                       i.unique_item_id, d.dept_name
                FROM tbl_calls c
                LEFT JOIN tbl_items i ON i.item_id=c.item_id
                LEFT JOIN tbl_departments d ON d.dept_id=c.dept_id
                WHERE c.module_id=? ORDER BY c.created_at DESC LIMIT 5
            """,(mid,))]
            for c in calls:
                st.markdown(
                    f"**{c['call_number']}** `{c['call_status']}`  \n"
                    f"{c.get('unique_item_id','—')} | {c.get('dept_name','—')}"
                )
        except Exception: pass

    with col3:
        st.markdown("#### Warranty Expiring (30 days)")
        try:
            from datetime import date, timedelta
            threshold = str(date.today() + timedelta(days=30))
            today     = str(date.today())
            expiring  = [dict(r) for r in _fa("""
                SELECT i.unique_item_id, i.description, i.warranty_to
                FROM tbl_items i
                WHERE i.module_id=? AND i.is_deleted=0
                  AND i.warranty_to >= ? AND i.warranty_to <= ?
                ORDER BY i.warranty_to ASC LIMIT 5
            """,(mid,today,threshold))]
            if expiring:
                for e in expiring:
                    st.warning(f"`{e['unique_item_id']}` — expires {e['warranty_to'][:10]}")
            else:
                st.success("No warranties expiring in 30 days.")
        except Exception: pass
