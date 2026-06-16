"""
pages/sims_role_permissions.py
==============================
Role Permissions Manager for SRGEC-SIMS.
Works for ALL 8 modules — pass module_code to scope permissions.
Matrix view: Roles × Sub-Modules × Actions (View/Insert/Update/Delete)
"""
import streamlit as st
import pandas as pd
from datetime import datetime

SUB_MODULES = [
    "Inventory — Asset Search & Edit",
    "Inventory — Case Sheets",
    "Stock — Central Stock",
    "Stock — Department Stock",
    "Procurement — Forward",
    "Procurement — Pending Approvals",
    "Procurement — Joint Data Entry",
    "Procurement — Log",
    "Procurement — Bulk Upload",
    "Complaints — Raise Complaint",
    "Complaints — My Inbox",
    "Complaints — Complaint Register",
    "Complaints — Spare Parts Indent",
    "Complaints — Closure Report",
    "Warranty — Alerts",
    "Warranty — Expiring Soon",
    "Maintenance — Sheet",
    "Maintenance — Asset Movement",
    "Maintenance — Lab Register",
    "Reports",
    "Administration — User Management",
    "Administration — Dept & Lab Setup",
    "Administration — Suppliers",
    "Administration — Role & Privileges",
    "Administration — Audit Log",
    "Account — Notifications",
    "Account — Change Password",
]

ACTIONS = ["can_view","can_insert","can_update","can_delete"]
ACTION_LABELS = {
    "can_view":   "👁 View",
    "can_insert": "➕ Insert",
    "can_update": "✏️ Update",
    "can_delete": "🗑 Delete",
}

SUB_MODULE_GROUPS = {
    "📦 Inventory":       ["Inventory — Asset Search & Edit","Inventory — Case Sheets"],
    "📊 Stock Registers": ["Stock — Central Stock","Stock — Department Stock"],
    "🛒 Procurement":     ["Procurement — Forward","Procurement — Pending Approvals",
                           "Procurement — Joint Data Entry","Procurement — Log",
                           "Procurement — Bulk Upload"],
    "🔧 Complaints":      ["Complaints — Raise Complaint","Complaints — My Inbox",
                           "Complaints — Complaint Register","Complaints — Spare Parts Indent",
                           "Complaints — Closure Report"],
    "🔒 Warranty":        ["Warranty — Alerts","Warranty — Expiring Soon"],
    "🛠 Maintenance":     ["Maintenance — Sheet","Maintenance — Asset Movement",
                           "Maintenance — Lab Register"],
    "📈 Reports":         ["Reports"],
    "⚙️ Administration":  ["Administration — User Management","Administration — Dept & Lab Setup",
                           "Administration — Suppliers","Administration — Role & Privileges",
                           "Administration — Audit Log"],
    "👤 Account":         ["Account — Notifications","Account — Change Password"],
}

ROLE_DEFAULTS = {
    "SysAdmin":   {s: {"can_view":1,"can_insert":1,"can_update":1,"can_delete":1} for s in SUB_MODULES},
    "HoD":        {s: {"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SUB_MODULES},
    "Coordinator":{s: {"can_view":1,"can_insert":1,"can_update":1,"can_delete":0} for s in SUB_MODULES},
    "Technician": {s: {"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SUB_MODULES},
    "Lab-IC":     {s: {"can_view":1,"can_insert":1,"can_update":0,"can_delete":0} for s in SUB_MODULES},
    "User":       {s: {"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SUB_MODULES},
}

# Restrict admin-only sub-modules for non-admins
RESTRICTED = {
    "HoD":        ["Administration — User Management","Administration — Dept & Lab Setup",
                   "Administration — Suppliers","Administration — Role & Privileges",
                   "Administration — Audit Log","Procurement — Bulk Upload"],
    "Coordinator":["Administration — User Management","Administration — Role & Privileges",
                   "Administration — Audit Log"],
    "Technician": ["Administration — User Management","Administration — Dept & Lab Setup",
                   "Administration — Suppliers","Administration — Role & Privileges",
                   "Administration — Audit Log","Procurement — Forward",
                   "Procurement — Pending Approvals","Procurement — Joint Data Entry",
                   "Procurement — Bulk Upload","Stock — Central Stock"],
    "Lab-IC":     ["Administration — User Management","Administration — Dept & Lab Setup",
                   "Administration — Suppliers","Administration — Role & Privileges",
                   "Administration — Audit Log","Procurement — Bulk Upload",
                   "Stock — Central Stock"],
    "User":       ["Administration — User Management","Administration — Dept & Lab Setup",
                   "Administration — Suppliers","Administration — Role & Privileges",
                   "Administration — Audit Log","Procurement — Forward",
                   "Procurement — Pending Approvals","Procurement — Joint Data Entry",
                   "Procurement — Bulk Upload","Stock — Central Stock",
                   "Maintenance — Sheet","Maintenance — Asset Movement",
                   "Maintenance — Lab Register"],
}


def show(module_code):
    """Entry point — called from module_home for admin_matrix subpage."""
    from db.connection import fetchall as fetchall, fetchone as fetchone, execute as execute
    from utils.auth import current_user, require_module_access
    role = require_module_access(module_code)
    if role not in ("SuperAdmin","SysAdmin"):
        st.error("🔒 Access denied."); return
    user = current_user()
    is_superadmin = bool(int(user.get("is_super_admin") or 0))

    st.title(f"🔐 Role Permissions Manager")
    st.caption(f"Module: **{module_code}** — Define what each role can do. Changes take effect immediately.")

    if not is_superadmin:
        st.warning(
            "⛔ Role & Privileges are managed centrally by SuperAdmin. "
            "You can view the current matrix below, but editing is restricted."
        )
        _permission_matrix(module_code, fetchall)
        return

    tab1, tab2, tab3 = st.tabs([
        "📋 Permission Matrix",
        "🎯 Edit by Role",
        "👤 Edit by Module",
    ])
    with tab1: _permission_matrix(module_code, fetchall)
    with tab2: _edit_by_role(module_code, user, fetchall, fetchone, execute)
    with tab3: _edit_by_module(module_code, user, fetchall, fetchone, execute)

# ══════════════════════════════════════════════════════════════════
# TAB 1 — Full matrix overview
# ══════════════════════════════════════════════════════════════════
def _permission_matrix(module_code, fetchall):
    st.subheader("📋 Full Permission Matrix")
    st.caption("✅ = allowed  ❌ = denied  Click **Edit by Role** tab to change.")

    role_names = list(ROLE_DEFAULTS.keys())

    perms = fetchall("""
        SELECT * FROM tbl_sims_role_permissions WHERE module_code=?
    """,(module_code,))
    perm_map = {(p["role_name"],p["sub_module"]): p for p in perms}

    if not perms:
        st.info("No permissions defined yet. Use **Edit by Role** tab or click below to apply defaults.")
        if st.button("⚡ Apply All Default Permissions", type="primary", key=f"pm_apply_{module_code}"):
            _apply_all_defaults(module_code, role_names, fetchall)
            st.success("Default permissions applied."); st.rerun()
        return

    for group_label, subs in SUB_MODULE_GROUPS.items():
        st.markdown(f"### {group_label}")
        rows = []
        for sub in subs:
            for action in ACTIONS:
                row = {"Sub-Module": sub, "Action": ACTION_LABELS[action]}
                for rn in role_names:
                    p = perm_map.get((rn, sub), {})
                    row[rn] = "✅" if p.get(action, 0) else "❌"
                rows.append(row)
        df = pd.DataFrame(rows)
        st.dataframe(
            df.set_index(["Sub-Module","Action"]),
            use_container_width=True,
            height=min(len(rows)*38+40, 500)
        )

    # Export
    import io
    all_rows = []
    for sub in SUB_MODULES:
        for action in ACTIONS:
            row = {"Sub-Module":sub, "Action":ACTION_LABELS[action]}
            for rn in role_names:
                p = perm_map.get((rn,sub),{})
                row[rn] = "Yes" if p.get(action,0) else "No"
            all_rows.append(row)
    df_all = pd.DataFrame(all_rows)
    buf = io.BytesIO()
    df_all.to_excel(buf, index=False, engine="openpyxl")
    st.download_button("📥 Export Full Matrix",buf.getvalue(),
                       f"{module_code}_Permission_Matrix.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ══════════════════════════════════════════════════════════════════
# TAB 2 — Edit by Role
# ══════════════════════════════════════════════════════════════════
def _edit_by_role(module_code, user, fetchall, fetchone, execute):
    st.subheader("🎯 Edit Permissions by Role")

    # Always show all standard roles so permissions can be pre-configured
    # before any user with that role exists.
    role_names = [r for r in ROLE_DEFAULTS.keys() if r != "SysAdmin"]

    sel_role    = st.selectbox("Select Role", role_names, key=f"ebr_role_{module_code}")
    is_sysadmin = sel_role in ("SuperAdmin","SysAdmin")

    if is_sysadmin:
        st.info("ℹ️ SysAdmin always has full access. Permissions cannot be restricted.")

    # Load current
    perms   = fetchall("SELECT * FROM tbl_sims_role_permissions WHERE module_code=? AND role_name=?",
                       (module_code, sel_role))
    perm_map= {p["sub_module"]: p for p in perms}

    st.markdown("---")
    st.markdown("Check actions to **allow** for each sub-module:")

    new_values = {}
    for group_label, subs in SUB_MODULE_GROUPS.items():
        st.markdown(f"#### {group_label}")
        hcols = st.columns([4,1,1,1,1])
        hcols[0].markdown("**Sub-Module**")
        for i,a in enumerate(ACTIONS):
            hcols[i+1].markdown(f"**{ACTION_LABELS[a]}**")

        for sub in subs:
            p    = perm_map.get(sub, {})
            cols = st.columns([4,1,1,1,1])
            cols[0].markdown(f"&nbsp;&nbsp;{sub}")
            vals = {}
            for i,action in enumerate(ACTIONS):
                current = bool(p.get(action, 0))
                if is_sysadmin:
                    cols[i+1].checkbox("", value=True,
                                       key=f"ebr_{module_code}_{sel_role}_{sub}_{action}",
                                       disabled=True)
                    vals[action] = 1
                else:
                    vals[action] = 1 if cols[i+1].checkbox(
                        "", value=current,
                        key=f"ebr_{module_code}_{sel_role}_{sub}_{action}"
                    ) else 0
            new_values[sub] = vals
        st.markdown("---")

    if not is_sysadmin:
        c1,c2 = st.columns(2)
        if c1.button("💾 Save All Permissions", type="primary", key=f"ebr_save_{module_code}"):
            _save_permissions(module_code, sel_role, new_values, execute)
            st.success(f"✅ Permissions saved for **{sel_role}**."); st.rerun()

        if c2.button("🔄 Reset to Defaults", key=f"ebr_reset_{module_code}"):
            st.session_state[f"ebr_confirm_{module_code}"] = True

        if st.session_state.get(f"ebr_confirm_{module_code}"):
            st.warning(f"Reset all permissions for **{sel_role}** to defaults?")
            rc1,rc2 = st.columns(2)
            if rc1.button("✅ Yes, Reset", key=f"ebr_yes_{module_code}"):
                _reset_defaults(module_code, sel_role, execute)
                st.session_state[f"ebr_confirm_{module_code}"] = False
                st.success("✅ Reset to defaults."); st.rerun()
            if rc2.button("❌ Cancel", key=f"ebr_no_{module_code}"):
                st.session_state[f"ebr_confirm_{module_code}"] = False; st.rerun()


# ══════════════════════════════════════════════════════════════════
# TAB 3 — Edit by Sub-Module
# ══════════════════════════════════════════════════════════════════
def _edit_by_module(module_code, user, fetchall, fetchone, execute):
    st.subheader("👤 Edit Permissions by Sub-Module")
    st.caption("See all roles' permissions for one sub-module and edit together.")

    sel_sub = st.selectbox("Select Sub-Module", SUB_MODULES, key=f"ebm_sub_{module_code}")

    role_names = list(ROLE_DEFAULTS.keys())

    perms    = fetchall("SELECT * FROM tbl_sims_role_permissions WHERE module_code=? AND sub_module=?",
                        (module_code, sel_sub))
    perm_map = {p["role_name"]: p for p in perms}

    st.markdown("---")
    hcols = st.columns([3,1,1,1,1])
    hcols[0].markdown("**Role**")
    for i,a in enumerate(ACTIONS):
        hcols[i+1].markdown(f"**{ACTION_LABELS[a]}**")

    new_values = {}
    for rn in role_names:
        p           = perm_map.get(rn, {})
        is_sysadmin = rn in ("SuperAdmin","SysAdmin")
        cols        = st.columns([3,1,1,1,1])
        cols[0].markdown(f"**{rn}**")
        vals = {}
        for i,action in enumerate(ACTIONS):
            current = bool(p.get(action, 0))
            if is_sysadmin:
                cols[i+1].checkbox("", value=True,
                                   key=f"ebm_{module_code}_{rn}_{sel_sub}_{action}",
                                   disabled=True)
                vals[action] = 1
            else:
                vals[action] = 1 if cols[i+1].checkbox(
                    "", value=current,
                    key=f"ebm_{module_code}_{rn}_{sel_sub}_{action}"
                ) else 0
        new_values[rn] = vals

    st.markdown("---")
    if st.button("💾 Save Sub-Module Permissions", type="primary", key=f"ebm_save_{module_code}"):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        for rn, vals in new_values.items():
            if rn in ("SuperAdmin","SysAdmin"): continue
            conn.execute("""
                INSERT INTO tbl_sims_role_permissions
                    (module_code,role_name,sub_module,can_view,can_insert,can_update,can_delete,updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(module_code,role_name,sub_module) DO UPDATE SET
                    can_view=excluded.can_view, can_insert=excluded.can_insert,
                    can_update=excluded.can_update, can_delete=excluded.can_delete,
                    updated_at=excluded.updated_at
            """,(module_code,rn,sel_sub,
                 vals["can_view"],vals["can_insert"],
                 vals["can_update"],vals["can_delete"],now))
        conn.commit(); conn.close()
        st.success(f"✅ Permissions saved for **{sel_sub}**."); st.rerun()


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════
def _save_permissions(module_code, role_name, new_values, execute):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for sub, vals in new_values.items():
        execute("""
            INSERT INTO tbl_sims_role_permissions
                (module_code,role_name,sub_module,can_view,can_insert,can_update,can_delete,updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(module_code,role_name,sub_module) DO UPDATE SET
                can_view=excluded.can_view, can_insert=excluded.can_insert,
                can_update=excluded.can_update, can_delete=excluded.can_delete,
                updated_at=excluded.updated_at
        """,(module_code,role_name,sub,
             vals["can_view"],vals["can_insert"],
             vals["can_update"],vals["can_delete"],now))


def _reset_defaults(module_code, role_name, execute):
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    defaults = ROLE_DEFAULTS.get(role_name, {s:{"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SUB_MODULES})
    restricted = RESTRICTED.get(role_name, [])
    none_ = {"can_view":0,"can_insert":0,"can_update":0,"can_delete":0}
    for sub in SUB_MODULES:
        vals = none_ if sub in restricted else defaults.get(sub, none_)
        execute("""
            INSERT INTO tbl_sims_role_permissions
                (module_code,role_name,sub_module,can_view,can_insert,can_update,can_delete,updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(module_code,role_name,sub_module) DO UPDATE SET
                can_view=excluded.can_view, can_insert=excluded.can_insert,
                can_update=excluded.can_update, can_delete=excluded.can_delete,
                updated_at=excluded.updated_at
        """,(module_code,role_name,sub,
             vals["can_view"],vals["can_insert"],
             vals["can_update"],vals["can_delete"],now))


def _apply_all_defaults(module_code, role_names, fetchall):
    import sqlite3
    from config import DB_PATH
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    none_= {"can_view":0,"can_insert":0,"can_update":0,"can_delete":0}
    conn = sqlite3.connect(DB_PATH)
    for rn in role_names:
        if rn in ("SuperAdmin","SysAdmin"): continue
        defaults   = ROLE_DEFAULTS.get(rn, {s:{"can_view":1,"can_insert":0,"can_update":0,"can_delete":0} for s in SUB_MODULES})
        restricted = RESTRICTED.get(rn, [])
        for sub in SUB_MODULES:
            vals = none_ if sub in restricted else defaults.get(sub, none_)
            conn.execute("""
                INSERT INTO tbl_sims_role_permissions
                    (module_code,role_name,sub_module,can_view,can_insert,can_update,can_delete,updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(module_code,role_name,sub_module) DO UPDATE SET
                    can_view=excluded.can_view, can_insert=excluded.can_insert,
                    can_update=excluded.can_update, can_delete=excluded.can_delete,
                    updated_at=excluded.updated_at
            """,(module_code,rn,sub,
                 vals["can_view"],vals["can_insert"],
                 vals["can_update"],vals["can_delete"],now))
    conn.commit(); conn.close()


def get_permission(module_code, role_name, sub_module, action):
    """Helper — check permission from anywhere in SIMS."""
    if role_name in ("SuperAdmin","SysAdmin"): return True
    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT * FROM tbl_sims_role_permissions
        WHERE module_code=? AND role_name=? AND sub_module=?
    """,(module_code, role_name, sub_module)).fetchone()
    conn.close()
    if not row: return True  # no record = allow by default
    return bool(dict(row).get(action, 0))
