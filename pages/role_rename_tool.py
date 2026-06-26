"""
pages/role_rename_tool.py — System-wide role name renaming utility.
SuperAdmin only. Updates role names across all tables simultaneously.
"""
import streamlit as st
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access


def show(module_code):
    user = current_user()
    is_super = bool(int(user.get("is_super_admin") or 0))
    if not is_super:
        st.error("SuperAdmin only."); return

    st.subheader("System-wide Role Name Management")
    st.info(
        "Rename a role across ALL tables: user access, workflow rules, and privileges. "
        "This affects every module simultaneously."
    )

    # Get all current role names in use
    roles_access = [dict(r)["role_name"] for r in _fa(
        "SELECT DISTINCT role_name FROM tbl_user_module_access ORDER BY role_name")]
    roles_rules  = set()
    for r in _fa("SELECT DISTINCT allowed_roles FROM tbl_workflow_rules"):
        for role in dict(r)["allowed_roles"].split(","):
            roles_rules.add(role.strip())
    roles_privs  = [dict(r)["role_name"] for r in _fa(
        "SELECT DISTINCT role_name FROM tbl_role_module_privileges ORDER BY role_name")]

    all_roles = sorted(set(roles_access) | roles_rules | set(roles_privs))

    if not all_roles:
        st.info("No roles found in the system."); return

    st.markdown("#### Current Roles in System")
    col1, col2, col3 = st.columns(3)
    col1.markdown("**User Access**\n" + "\n".join(f"- {r}" for r in roles_access))
    col2.markdown("**Workflow Rules**\n" + "\n".join(f"- {r}" for r in sorted(roles_rules)))
    col3.markdown("**Privileges**\n" + "\n".join(f"- {r}" for r in roles_privs))

    st.divider()
    st.markdown("#### Rename a Role")

    old_role = st.selectbox("Select role to rename", all_roles, key="rr_old")
    new_role = st.text_input("New role name *", key="rr_new",
                             placeholder="e.g. UPS Technician")

    if not new_role.strip():
        st.info("Enter the new role name above."); return

    if new_role.strip() == old_role:
        st.warning("New name is the same as the old name."); return

    # Preview impact
    affected_users = [dict(r) for r in _fa("""
        SELECT u.full_name, u.username, m.module_name
        FROM tbl_user_module_access a
        JOIN tbl_users u ON u.user_id=a.user_id
        JOIN tbl_modules m ON m.module_id=a.module_id
        WHERE a.role_name=?
    """, (old_role,))]

    affected_rules = [dict(r) for r in _fa("""
        SELECT rule_id, module_id, from_status, to_status, allowed_roles
        FROM tbl_workflow_rules
        WHERE (',' || allowed_roles || ',') LIKE ?
    """, (f"%,{old_role},%",))]

    affected_privs = [dict(r) for r in _fa("""
        SELECT COUNT(*) c FROM tbl_role_module_privileges WHERE role_name=?
    """, (old_role,))]
    priv_count = dict(affected_privs[0])["c"] if affected_privs else 0

    st.markdown(f"**Impact of renaming '{old_role}' → '{new_role.strip()}':**")
    st.markdown(f"- {len(affected_users)} user access record(s)")
    st.markdown(f"- {len(affected_rules)} workflow rule(s)")
    st.markdown(f"- {priv_count} privilege record(s)")

    if affected_users:
        import pandas as pd
        df = pd.DataFrame([{
            "User": u["full_name"],
            "Username": u["username"],
            "Module": u["module_name"]
        } for u in affected_users])
        st.dataframe(df, use_container_width=True, hide_index=True)

    confirm = st.checkbox(
        f"I confirm renaming '{old_role}' to '{new_role.strip()}' system-wide",
        key="rr_confirm"
    )

    if st.button("Rename Role System-wide", type="primary",
                 key="rr_submit", disabled=not confirm):
        try:
            conn = get_conn()
            new = new_role.strip()

            # 1. Update tbl_user_module_access
            conn.execute(
                "UPDATE tbl_user_module_access SET role_name=? WHERE role_name=?",
                (new, old_role)
            )

            # 2. Update tbl_workflow_rules (allowed_roles is comma-separated)
            # Replace exact role name within comma-separated list
            rules = [dict(r) for r in _fa(
                "SELECT rule_id, allowed_roles FROM tbl_workflow_rules "
                "WHERE (',' || allowed_roles || ',') LIKE ?",
                (f"%,{old_role},%",)
            )]
            for rule in rules:
                roles_list = [r.strip() for r in rule["allowed_roles"].split(",")]
                updated = ",".join(new if r == old_role else r for r in roles_list)
                conn.execute(
                    "UPDATE tbl_workflow_rules SET allowed_roles=? WHERE rule_id=?",
                    (updated, rule["rule_id"])
                )

            # 3. Update tbl_role_module_privileges
            conn.execute(
                "UPDATE tbl_role_module_privileges SET role_name=? WHERE role_name=?",
                (new, old_role)
            )

            conn.commit(); conn.close()
            st.success(
                f"Role '{old_role}' successfully renamed to '{new}' "
                f"across {len(affected_users)} user(s), "
                f"{len(rules)} workflow rule(s), "
                f"and {priv_count} privilege record(s)."
            )
            st.rerun()
        except Exception as ex:
            st.error(f"Rename failed: {ex}")
