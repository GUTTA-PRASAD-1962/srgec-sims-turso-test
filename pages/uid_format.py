"""
pages/uid_format.py — Customize Asset Unique ID Format (SuperAdmin only)
==========================================================================
Configures how Unique Item IDs are generated across ALL SIMS modules
(UPS, Electrical, CCTV, Furniture, LCD/Projector, Civil, Stationery, IT).

Default format: MODCODE_DEPTCODE_MM_YYYY_TYPEPREFIX_NNNNN
Configurable components: MOD, DEPT, MM, YYYY, TYPE, SEQ
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
def _ist(): return (datetime.utcnow() + timedelta(hours=5, minutes=30))
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user, require_module_access


ALL_COMPONENTS = {
    "MOD":  "Module Code     (e.g. UPS)",
    "DEPT": "Department Code (e.g. CSE)",
    "MM":   "Purchase Month  (e.g. 06)",
    "YYYY": "Purchase Year   (e.g. 2026)",
    "TYPE": "Item Type Prefix(e.g. UPS)",
    "SEQ":  "Sequence Number (e.g. 00001)",
}

DEFAULT_FORMAT = {
    "components": ["MOD", "DEPT", "MM", "YYYY", "TYPE", "SEQ"],
    "separator":  "_",
    "seq_digits": 5,
}


def _ensure_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tbl_uid_format_config (
            config_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            components  TEXT NOT NULL,
            separator   TEXT NOT NULL DEFAULT '_',
            seq_digits  INTEGER NOT NULL DEFAULT 5,
            is_active   INTEGER DEFAULT 1,
            updated_by  INTEGER,
            updated_at  TEXT DEFAULT (datetime('now','+5 hours','+30 minutes'))
        )
    """)
    conn.commit()
    conn.close()


def get_active_format():
    _ensure_table()
    row = _fo("SELECT * FROM tbl_uid_format_config WHERE is_active=1 ORDER BY config_id DESC LIMIT 1")
    if not row:
        return dict(DEFAULT_FORMAT)
    row = dict(row)
    return {
        "components": row["components"].split(","),
        "separator":  row["separator"],
        "seq_digits": row["seq_digits"],
    }


def build_sample_uid(fmt, sample_vals=None):
    sample_vals = sample_vals or {
        "MOD": "UPS", "DEPT": "CSE", "MM": "06", "YYYY": "2026",
        "TYPE": "UPS", "SEQ": str(1).zfill(fmt["seq_digits"]),
    }
    parts = [sample_vals.get(c, c) for c in fmt["components"]]
    return fmt["separator"].join(parts)


def show(module_code=None):
    """SuperAdmin-only page. module_code unused but accepted for routing compatibility."""
    user = current_user()
    if not user.get("is_super_admin"):
        st.error("⛔ Only SuperAdmin can access this page.")
        return

    _ensure_table()
    st.title("🆔 Customize Asset Unique ID Format")
    st.caption(
        "Configure how Unique Item IDs are generated for ALL modules "
        "(UPS, Electrical, CCTV, Furniture, LCD/Projector, Civil, Stationery, IT). "
        "Existing item IDs are NOT changed — only new entries use the updated format."
    )

    cur_fmt = get_active_format()

    if st.session_state.get("_uidfmt_msg"):
        t, m = st.session_state.pop("_uidfmt_msg")
        (st.success if t == "s" else st.error)(m)

    tab1, tab2, tab3 = st.tabs([
        "⚙️ Configure Format",
        "👁 Current Format Preview",
        "📜 Format History",
    ])

    # ══ TAB 1 — CONFIGURE ════════════════════════════════════════════
    with tab1:
        st.markdown("### Step 1 — Select & Order Components")
        st.caption(
            "Check the components to include, then arrange their order below. "
            "Components are joined using the separator you choose."
        )

        selected = []
        cols = st.columns(3)
        for i, (key, label) in enumerate(ALL_COMPONENTS.items()):
            col = cols[i % 3]
            checked = col.checkbox(
                label, value=(key in cur_fmt["components"]),
                key=f"uidfmt_chk_{key}"
            )
            if checked:
                selected.append(key)

        if not selected:
            st.error("Select at least one component.")
            return

        st.markdown("---")
        st.markdown("### Step 2 — Order the Selected Components")
        st.caption("Type the order number (1, 2, 3...) for each selected component.")

        order_map = {}
        ocols = st.columns(min(len(selected), 6))
        for i, key in enumerate(selected):
            default_order = (cur_fmt["components"].index(key) + 1
                            if key in cur_fmt["components"] else i + 1)
            order_map[key] = ocols[i % len(ocols)].number_input(
                ALL_COMPONENTS[key].split("(")[0].strip(),
                min_value=1, max_value=len(selected),
                value=min(default_order, len(selected)),
                step=1, key=f"uidfmt_ord_{key}"
            )

        ordered_components = sorted(selected, key=lambda k: order_map[k])

        st.markdown("---")
        st.markdown("### Step 3 — Separator & Sequence Settings")
        c1, c2 = st.columns(2)
        separator = c1.selectbox(
            "Separator Character",
            ["_", "-", ".", "/", "(none)"],
            index=["_", "-", ".", "/", "(none)"].index(cur_fmt["separator"])
                  if cur_fmt["separator"] in ["_", "-", ".", "/"] else 4,
            key="uidfmt_sep"
        )
        sep_actual = "" if separator == "(none)" else separator

        seq_digits = c2.number_input(
            "Sequence Number Digits (zero-padding)",
            min_value=3, max_value=10, value=cur_fmt["seq_digits"], step=1,
            key="uidfmt_seqdigits"
        )

        new_fmt = {
            "components": ordered_components,
            "separator":  sep_actual,
            "seq_digits": int(seq_digits),
        }

        st.markdown("---")
        st.markdown("### Step 4 — Preview")
        sample = build_sample_uid(new_fmt)
        st.markdown(
            f"<div style='background:#E8F4FD;padding:16px;border-radius:8px;"
            f"border-left:5px solid #2E75B6;font-size:1.3rem;font-family:monospace;"
            f"text-align:center'><b>{sample}</b></div>",
            unsafe_allow_html=True
        )
        st.caption(
            "Example: Item purchased in **June 2026** for module **UPS**, "
            "Department **CSE**, Type **UPS**, Sequence **1** → shown above."
        )

        with st.expander("📋 More examples with different sequence numbers"):
            for seq_n in [1, 2, 10, 999]:
                ex_vals = {
                    "MOD": "UPS", "DEPT": "CSE", "MM": "06", "YYYY": "2026",
                    "TYPE": "UPS", "SEQ": str(seq_n).zfill(new_fmt["seq_digits"]),
                }
                st.code(build_sample_uid(new_fmt, ex_vals))

        st.markdown("---")
        col1, col2 = st.columns(2)
        if col1.button("💾 Save Format Configuration", type="primary",
                       use_container_width=True, key="uidfmt_save"):
            conn = get_conn()
            conn.execute("UPDATE tbl_uid_format_config SET is_active=0")
            conn.execute("""
                INSERT INTO tbl_uid_format_config
                    (components, separator, seq_digits, is_active, updated_by, updated_at)
                VALUES (?,?,?,1,?,?)
            """,(",".join(new_fmt["components"]), new_fmt["separator"],
                 new_fmt["seq_digits"], user.get("user_id"),
                 _ist().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
            st.session_state["_uidfmt_msg"] = (
                "s", f"✅ UID format updated! New format: `{sample}`. "
                     f"All new items registered from now on (in any module) will use this format."
            )
            st.rerun()

        if col2.button("🔄 Reset to Default Format", use_container_width=True,
                       key="uidfmt_reset"):
            conn = get_conn()
            conn.execute("UPDATE tbl_uid_format_config SET is_active=0")
            conn.execute("""
                INSERT INTO tbl_uid_format_config
                    (components, separator, seq_digits, is_active, updated_by, updated_at)
                VALUES (?,?,?,1,?,?)
            """,(",".join(DEFAULT_FORMAT["components"]), DEFAULT_FORMAT["separator"],
                 DEFAULT_FORMAT["seq_digits"], user.get("user_id"),
                 _ist().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
            st.session_state["_uidfmt_msg"] = (
                "s", f"Reset to default format: `{build_sample_uid(DEFAULT_FORMAT)}`"
            )
            st.rerun()

    # ══ TAB 2 — CURRENT FORMAT PREVIEW ═══════════════════════════════
    with tab2:
        st.markdown("### Currently Active Format")
        active = get_active_format()
        st.markdown(f"**Components (in order):** {' → '.join(active['components'])}")
        st.markdown(f"**Separator:** `{active['separator'] or '(none)'}`")
        st.markdown(f"**Sequence Digits:** {active['seq_digits']}")
        st.markdown("---")
        sample = build_sample_uid(active)
        st.markdown(
            f"<div style='background:#f0fff4;padding:16px;border-radius:8px;"
            f"border-left:5px solid #28a745;font-size:1.3rem;font-family:monospace;"
            f"text-align:center'><b>{sample}</b></div>",
            unsafe_allow_html=True
        )

        st.markdown("---")
        st.markdown("### Recently Generated Item IDs (last 10, all modules)")
        recent = _fa("""
            SELECT i.unique_item_id, i.description, m.module_code, i.created_at
            FROM tbl_items i
            LEFT JOIN tbl_modules m ON m.module_id = i.module_id
            ORDER BY i.item_id DESC LIMIT 10
        """)
        if recent:
            st.dataframe(pd.DataFrame([dict(r) for r in recent]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("No items registered yet.")

    # ══ TAB 3 — FORMAT HISTORY ════════════════════════════════════════
    with tab3:
        st.markdown("### Format Change History")
        history = _fa("""
            SELECT c.*, u.full_name AS changed_by_name
            FROM tbl_uid_format_config c
            LEFT JOIN tbl_users u ON u.user_id = c.updated_by
            ORDER BY c.config_id DESC
        """)
        if not history:
            st.info("No format changes recorded yet.")
            return

        rows = []
        for h in history:
            h = dict(h)
            fmt = {"components": h["components"].split(","),
                   "separator": h["separator"], "seq_digits": h["seq_digits"]}
            rows.append({
                "Config ID": h["config_id"],
                "Format": build_sample_uid(fmt),
                "Components": " → ".join(fmt["components"]),
                "Active": "✅" if h["is_active"] else "—",
                "Changed By": h.get("changed_by_name", "—"),
                "Changed At": h["updated_at"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
