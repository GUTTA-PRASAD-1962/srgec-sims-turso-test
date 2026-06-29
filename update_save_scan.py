"""Update save_scan and show_scan in utils/helpers.py to use Azure Blob Storage"""

with open('utils/helpers.py', encoding='utf-8') as f:
    content = f.read()

old_save = '''def save_scan(file, prefix=""):
    if not file: return None
    try:
        scan_dir = Path("uploads/invoices")
        scan_dir.mkdir(parents=True, exist_ok=True)
        safe = prefix.replace("/","_").replace(" ","_")
        ext  = file.name.split(".")[-1].lower()
        path = scan_dir / f"{safe}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        path.write_bytes(file.read())
        return str(path)
    except: return None'''

new_save = '''def save_scan(file, prefix=""):
    if not file: return None
    try:
        safe = prefix.replace("/","_").replace(" ","_").replace("-","_")
        ext  = file.name.split(".")[-1].lower()
        blob_name = f"uploads/{safe}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
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
    except: return None'''

old_show = '''def show_scan(scan_path):
    if not scan_path: return
    p = Path(scan_path)
    if not p.exists():
        st.caption(f"Scan not found: {scan_path}"); return
    data = p.read_bytes()
    b64  = base64.b64encode(data).decode()
    ext  = p.suffix.lower()
    if ext in (".jpg",".jpeg",".png"):
        mime = "image/png" if ext==".png" else "image/jpeg"
        st.markdown(f\'<img src="data:{mime};base64,{b64}" style="max-width:100%;border-radius:4px;border:1px solid #ddd"/>\',
                    unsafe_allow_html=True)
    elif ext == ".pdf":
        st.markdown(f\'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="520px" style="border:1px solid #ddd;border-radius:4px"></iframe>\',
                    unsafe_allow_html=True)
    st.download_button(f"Download {p.name}", data, file_name=p.name, key=f"dl_{p.name}_{id(scan_path)}")'''

new_show = '''def show_scan(scan_path):
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
                    f\'<iframe src="{sas_url}" width="100%" height="520px" \' +
                    \'style="border:1px solid #ddd;border-radius:4px"></iframe>\',
                    unsafe_allow_html=True)
            st.markdown(f\'[Download File]({sas_url})\')
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
        st.markdown(f\'<img src="data:{mime};base64,{b64}" style="max-width:100%;border-radius:4px;border:1px solid #ddd"/>\',
                    unsafe_allow_html=True)
    elif ext == ".pdf":
        st.markdown(f\'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="520px" style="border:1px solid #ddd;border-radius:4px"></iframe>\',
                    unsafe_allow_html=True)
    st.download_button(f"Download {p.name}", data, file_name=p.name, key=f"dl_{p.name}_{id(scan_path)}")'''

if old_save in content:
    content = content.replace(old_save, new_save, 1)
    print("save_scan updated")
else:
    print("save_scan pattern not found")

if old_show in content:
    content = content.replace(old_show, new_show, 1)
    print("show_scan updated")
else:
    print("show_scan pattern not found")

with open('utils/helpers.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
