"""utils/helpers.py"""
import streamlit as st
import pandas as pd
import io, base64, json
from pathlib import Path
from datetime import datetime


def format_date(d):
    if not d: return "—"
    try: return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
    except: return str(d)[:10]


def format_currency(amount):
    if amount is None: return "—"
    return f"Rs.{float(amount):,.2f}"


def generate_item_id(module_code, dept_code, type_prefix, purchase_date):
    """
    Generate the next sequential Unique Item ID using the
    SuperAdmin-configurable format (tbl_uid_format_config).
    Falls back to default format: MOD_DEPT_MM_YYYY_TYPE_NNNNN if no config exists.
    """
    from db.connection import fetchone
    try:
        dt = datetime.strptime(str(purchase_date)[:10], "%Y-%m-%d")
        mm = dt.strftime("%m"); yyyy = dt.strftime("%Y")
    except:
        mm = datetime.now().strftime("%m"); yyyy = datetime.now().strftime("%Y")

    safe_mod  = str(module_code).upper().replace(" ", "")
    safe_dept = str(dept_code).upper().replace(" ", "")
    safe_type = str(type_prefix).upper().replace(" ", "")

    try:
        cfg = fetchone(
            "SELECT * FROM tbl_uid_format_config WHERE is_active=1 "
            "ORDER BY config_id DESC LIMIT 1"
        )
    except Exception:
        cfg = None

    if cfg:
        cfg = dict(cfg)
        components = cfg["components"].split(",")
        separator  = cfg["separator"] or ""
        seq_digits = cfg["seq_digits"]
    else:
        components = ["MOD","DEPT","MM","YYYY","TYPE","SEQ"]
        separator  = "_"
        seq_digits = 5

    value_map = {
        "MOD":  safe_mod,
        "DEPT": safe_dept,
        "MM":   mm,
        "YYYY": yyyy,
        "TYPE": safe_type,
    }

    prefix_parts = [value_map.get(c, c) for c in components if c != "SEQ"]
    prefix = separator.join(prefix_parts)
    if "SEQ" in components and prefix:
        prefix = prefix + separator

    row = fetchone(
        "SELECT unique_item_id FROM tbl_items WHERE unique_item_id LIKE ? "
        "ORDER BY item_id DESC LIMIT 1",
        (f"{prefix}%",)
    )
    if row:
        try:
            tail = str(dict(row)["unique_item_id"])[len(prefix):]
            seq = int(tail) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    seq_str = str(seq).zfill(seq_digits)

    final_parts = []
    for c in components:
        if c == "SEQ":
            final_parts.append(seq_str)
        else:
            final_parts.append(value_map.get(c, c))
    return separator.join(final_parts)


def save_scan(file, prefix=""):
    if not file: return None
    try:
        import time
        safe = prefix.replace("/","_").replace(" ","_").replace("-","_")
        ext  = file.name.split(".")[-1].lower()
        # Use timestamp + microseconds to ensure uniqueness
        blob_name = f"uploads/{safe}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{int(time.time()*1000)%10000}.{ext}"
        file_bytes = file.read()
        # Try Azure first
        try:
            from utils.azure_storage import upload_file, is_azure_configured
            if is_azure_configured():
                content_type = "application/pdf" if ext=="pdf" else f"image/{ext}"
                return upload_file(file_bytes, blob_name, content_type)
        except Exception:
            pass
        # Fallback to local storage
        local_path = Path(blob_name)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(file_bytes)
        return str(local_path)
    except: return None


def show_scan(scan_path):
    if not scan_path: return
    # Try Azure first
    try:
        from utils.azure_storage import get_sas_url, is_azure_configured
        if is_azure_configured() and not Path(scan_path).exists():
            sas_url = get_sas_url(scan_path)
            ext = scan_path.split(".")[-1].lower()
            if ext in ("jpg","jpeg","png"):
                st.image(sas_url)
            elif ext == "pdf":
                st.markdown(
                    f'<iframe src="{sas_url}" width="100%" height="520px" ' +
                    'style="border:1px solid #ddd;border-radius:4px"></iframe>',
                    unsafe_allow_html=True)
            st.markdown(f'[Download File]({sas_url})')
            return
    except Exception:
        pass
    # Fallback to local
    p = Path(scan_path)
    if not p.exists():
        st.caption(f"Scan not found: {scan_path}"); return
    data = p.read_bytes()
    b64  = base64.b64encode(data).decode()
    ext  = p.suffix.lower()
    if ext in (".jpg",".jpeg",".png"):
        mime = "image/png" if ext==".png" else "image/jpeg"
        st.markdown(f'<img src="data:{mime};base64,{b64}" style="max-width:100%;border-radius:4px;border:1px solid #ddd"/>',
                    unsafe_allow_html=True)
    elif ext == ".pdf":
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="520px" style="border:1px solid #ddd;border-radius:4px"></iframe>',
                    unsafe_allow_html=True)
    st.download_button(f"Download {p.name}", data, file_name=p.name, key=f"dl_{p.name}_{id(scan_path)}")


def export_df(df, filename="export.xlsx"):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    st.download_button("Export to Excel", buf.getvalue(), filename,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def get_dynamic_fields(type_id):
    from db.connection import fetchall
    return [dict(f) for f in fetchall(
        "SELECT * FROM tbl_field_defs WHERE type_id=? ORDER BY sort_order", (type_id,))]


def render_dynamic_fields(fields, key_prefix=""):
    """Render dynamic fields and return {field_name: value} dict."""
    values = {}
    cfg_fields   = [f for f in fields if f["is_config_field"]]
    basic_fields = [f for f in fields if not f["is_config_field"]]

    def render_field(fld, kp):
        fkey = f"{kp}_{fld['field_name']}"
        ft   = fld["field_type"]
        lbl  = fld["field_label"] + (" *" if fld["is_required"] else "")
        ph   = fld.get("placeholder") or ""
        if ft == "text":
            return st.text_input(lbl, placeholder=ph, key=fkey)
        elif ft == "number":
            return st.number_input(lbl, min_value=0.0, step=1.0, key=fkey)
        elif ft == "date":
            return st.text_input(lbl, placeholder="YYYY-MM-DD", key=fkey)
        elif ft == "textarea":
            return st.text_area(lbl, placeholder=ph, key=fkey, height=80)
        elif ft == "boolean":
            return "Yes" if st.checkbox(lbl, key=fkey) else "No"
        elif ft == "dropdown":
            try: opts = json.loads(fld.get("field_options") or "[]")
            except: opts = []
            return st.selectbox(lbl, opts, key=fkey) if opts else st.text_input(lbl, key=fkey)
        return ""

    if basic_fields:
        for i in range(0, len(basic_fields), 3):
            row = basic_fields[i:i+3]
            cols = st.columns(len(row))
            for j, fld in enumerate(row):
                values[fld["field_name"]] = cols[j].text_input(
                    fld["field_label"]+(" *" if fld["is_required"] else ""),
                    placeholder=fld.get("placeholder",""),
                    key=f"{key_prefix}_{fld['field_name']}")

    if cfg_fields:
        with st.expander("Technical Configuration", expanded=True):
            for i in range(0, len(cfg_fields), 3):
                row = cfg_fields[i:i+3]
                cols = st.columns(len(row))
                for j, fld in enumerate(row):
                    with cols[j]:
                        values[fld["field_name"]] = render_field(fld, key_prefix)

    return values


def save_field_values(conn, item_id, type_id, values):
    from db.connection import fetchall
    fmap = {f["field_name"]: f["field_id"] for f in fetchall(
        "SELECT field_id, field_name FROM tbl_field_defs WHERE type_id=?", (type_id,))}
    for fname, fval in values.items():
        if fname in fmap and fval is not None and str(fval).strip():
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO tbl_item_field_values (item_id,field_id,field_value) VALUES (?,?,?)",
                    (item_id, fmap[fname], str(fval)))
            except Exception:
                pass
