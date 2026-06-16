"""pages/superadmin.py — SuperAdmin configuration panel"""
import streamlit as st
import pandas as pd
import hashlib, json
from datetime import datetime
from db.connection import fetchall as _fa, fetchone as _fo, get_conn
from utils.auth import current_user

def show():
    user = current_user()
    if not user.get("is_super_admin"):
        st.error("SuperAdmin access only."); return

    st.title("Super Admin Configuration Panel")
    st.info("Configure all 8 modules — item types, fields, workflow rules, users, and departments.")

    tab1,tab2,tab3,tab4,tab5 = st.tabs([
        "Modules","Users & Access","Item Types & Fields","Workflow Rules","Departments"
    ])
    with tab1: _modules()
    with tab2: _users()
    with tab3: _fields()
    with tab4: _workflow()
    with tab5: _depts()

def _modules():
    mods = [dict(r) for r in _fa("SELECT * FROM tbl_modules ORDER BY sort_order")]
    if mods:
        st.dataframe(pd.DataFrame([{
            "Code":m["module_code"],"Name":m["module_name"],
            "Icon":m["module_icon"],"Active":"Yes" if m["is_active"] else "No"
        } for m in mods]),use_container_width=True,hide_index=True)
    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    mc=c1.text_input("Code *",key="sa_mc"); mn=c2.text_input("Name *",key="sa_mn")
    mi=c3.text_input("Icon",value="📦",key="sa_mi"); mo=c4.number_input("Order",value=9,key="sa_mo")
    if st.button("Save Module",key="sa_msave"):
        if mc and mn:
            conn=get_conn()
            try:
                conn.execute("INSERT OR REPLACE INTO tbl_modules (module_code,module_name,module_icon,is_active,sort_order) VALUES (?,?,?,1,?)",
                             (mc.upper(),mn,mi,mo))
                conn.commit(); st.success("Saved."); st.rerun()
            except Exception as e: st.error(str(e))
            finally: conn.close()

def _users():
    st.subheader("Users & Module Access")
    users = [dict(r) for r in _fa("""
        SELECT u.user_id, u.full_name, u.username, u.employee_id,
               u.is_super_admin, u.is_active, d.dept_name
        FROM tbl_users u LEFT JOIN tbl_departments d ON d.dept_id=u.dept_id
        ORDER BY u.full_name
    """)]
    if users:
        st.dataframe(pd.DataFrame([{
            "ID":u["user_id"],"Name":u["full_name"],"Username":u["username"],
            "Emp ID":u["employee_id"],"Dept":u.get("dept_name","—"),
            "SA":"Yes" if u["is_super_admin"] else "","Active":"Yes" if u["is_active"] else "No"
        } for u in users]),use_container_width=True,hide_index=True)
    st.divider()
    st.markdown("**Create User**")
    u1,u2,u3 = st.columns(3)
    uname=u1.text_input("Username *",key="sa_uname"); ufull=u2.text_input("Full Name *",key="sa_ufull"); uemp=u3.text_input("Emp ID *",key="sa_uemp")
    u4,u5,u6 = st.columns(3)
    upwd=u4.text_input("Password *",type="password",key="sa_upwd")
    depts=[dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    dm={"— No Dept —":None}; dm.update({d["dept_name"]:d["dept_id"] for d in depts})
    udept=u5.selectbox("Dept",list(dm.keys()),key="sa_udept"); usa=u6.checkbox("SuperAdmin",key="sa_usa")
    if st.button("Create User",type="primary",key="sa_ucreate"):
        if uname and ufull and uemp and upwd:
            conn=get_conn()
            try:
                conn.execute("INSERT INTO tbl_users (username,password_hash,full_name,employee_id,dept_id,is_super_admin,is_active,created_at) VALUES (?,?,?,?,?,?,1,?)",
                             (uname,hashlib.sha256(upwd.encode()).hexdigest(),ufull,uemp,dm[udept],1 if usa else 0,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit(); st.success(f"User '{ufull}' created."); st.rerun()
            except Exception as e: st.error(str(e))
            finally: conn.close()
    st.divider()
    st.markdown("**Grant Module Access**")
    mods=[dict(r) for r in _fa("SELECT * FROM tbl_modules WHERE is_active=1 ORDER BY sort_order")]
    g1,g2,g3 = st.columns(3)
    sel_u=g1.selectbox("User",[f"{u['full_name']} (#{u['user_id']})" for u in users],key="sa_guser")
    sel_m=g2.selectbox("Module",[m["module_name"] for m in mods],key="sa_gmod")
    sel_r=g3.selectbox("Role",["SuperAdmin","SysAdmin","HoD","Coordinator","Technician","Lab-IC","User"],key="sa_grole")
    if st.button("Grant Access",key="sa_ggrant"):
        uid=int(sel_u.split("#")[1].rstrip(")"))
        mid=[m["module_id"] for m in mods if m["module_name"]==sel_m][0]
        conn=get_conn()
        try:
            conn.execute("INSERT OR REPLACE INTO tbl_user_module_access (user_id,module_id,role_name,is_active,granted_at) VALUES (?,?,?,1,?)",
                         (uid,mid,sel_r,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); st.success("Access granted."); st.rerun()
        except Exception as e: st.error(str(e))
        finally: conn.close()
    # Access list
    access=[dict(r) for r in _fa("""
        SELECT u.full_name, m.module_name, a.role_name
        FROM tbl_user_module_access a
        JOIN tbl_users u ON u.user_id=a.user_id
        JOIN tbl_modules m ON m.module_id=a.module_id
        WHERE a.is_active=1 ORDER BY m.sort_order, u.full_name
    """)]
    if access:
        st.divider()
        st.markdown("**Current Access:**")
        st.dataframe(pd.DataFrame([{"User":a["full_name"],"Module":a["module_name"],"Role":a["role_name"]} for a in access]),
                     use_container_width=True,hide_index=True)

def _fields():
    st.subheader("Item Types & Field Definitions")
    mods=[dict(r) for r in _fa("SELECT * FROM tbl_modules WHERE is_active=1 ORDER BY sort_order")]
    sel_m=st.selectbox("Module",[m["module_name"] for m in mods],key="sa_fm")
    mid=[m["module_id"] for m in mods if m["module_name"]==sel_m][0]
    types=[dict(r) for r in _fa("SELECT * FROM tbl_item_types WHERE module_id=? ORDER BY type_name",(mid,))]
    if types:
        st.dataframe(pd.DataFrame([{"Type":t["type_name"],"Code":t["type_code"],"Prefix":t["id_prefix"],"Config":"Yes" if t["has_config"] else ""} for t in types]),
                     use_container_width=True,hide_index=True)
    st.divider()
    st.markdown("**Add Item Type**")
    t1,t2,t3,t4=st.columns(4)
    tn=t1.text_input("Name *",key="sa_itn"); tc=t2.text_input("Code *",key="sa_itc"); tp=t3.text_input("Prefix *",key="sa_itp"); th=t4.checkbox("Has Config",key="sa_ith")
    if st.button("Add Type",key="sa_itadd"):
        if tn and tc and tp:
            conn=get_conn()
            try:
                conn.execute("INSERT INTO tbl_item_types (module_id,type_name,type_code,id_prefix,has_config) VALUES (?,?,?,?,?)",(mid,tn,tc.upper(),tp.upper(),1 if th else 0))
                conn.commit(); st.success("Added."); st.rerun()
            except Exception as e: st.error(str(e))
            finally: conn.close()
    st.divider()
    if types:
        st.markdown("**Add Field to Item Type**")
        sel_t=st.selectbox("Item Type",[t["type_name"] for t in types],key="sa_ftype")
        tid=[t["type_id"] for t in types if t["type_name"]==sel_t][0]
        fields=[dict(r) for r in _fa("SELECT * FROM tbl_field_defs WHERE type_id=? ORDER BY sort_order",(tid,))]
        if fields:
            st.dataframe(pd.DataFrame([{"Label":f["field_label"],"Name":f["field_name"],"Type":f["field_type"],"Req":"Yes" if f["is_required"] else "","Cfg":"Yes" if f["is_config_field"] else ""} for f in fields]),
                         use_container_width=True,hide_index=True)
        f1,f2,f3=st.columns(3)
        fn=f1.text_input("Field Name (key) *",key="sa_fn"); fl=f2.text_input("Label *",key="sa_fl"); ft=f3.selectbox("Type",["text","number","date","dropdown","boolean","textarea"],key="sa_ft")
        f4,f5=st.columns(2)
        fr=f4.checkbox("Required",key="sa_fr"); fc=f5.checkbox("Config Field",key="sa_fc")
        fo="" if ft!="dropdown" else st.text_input("Options (comma separated)",key="sa_fo")
        if st.button("Add Field",key="sa_fadd"):
            if fn and fl:
                opts=json.dumps([o.strip() for o in fo.split(",") if o.strip()]) if fo else None
                conn=get_conn()
                try:
                    conn.execute("INSERT INTO tbl_field_defs (type_id,field_name,field_label,field_type,is_required,is_config_field,field_options,sort_order) VALUES (?,?,?,?,?,?,?,?)",
                                 (tid,fn,fl,ft,1 if fr else 0,1 if fc else 0,opts,len(fields)))
                    conn.commit(); st.success("Field added."); st.rerun()
                except Exception as e: st.error(str(e))
                finally: conn.close()

def _workflow():
    st.subheader("Workflow Rule Configuration")
    mods=[dict(r) for r in _fa("SELECT * FROM tbl_modules WHERE is_active=1 ORDER BY sort_order")]
    sel_m=st.selectbox("Module",[m["module_name"] for m in mods],key="sa_wm")
    mid=[m["module_id"] for m in mods if m["module_name"]==sel_m][0]
    rules=[dict(r) for r in _fa("SELECT * FROM tbl_workflow_rules WHERE module_id=? ORDER BY sort_order",(mid,))]

    if rules:
        st.dataframe(pd.DataFrame([{"From":r["from_status"],"Action":r["action_label"],"To":r["to_status"],"Roles":r["allowed_roles"],"Active":"Yes" if r["is_active"] else "No"} for r in rules]),
                     use_container_width=True,hide_index=True)

    st.divider()

    # ── Rule selector: choose existing rule to edit, or "Add New Rule" ──
    rule_opts = {"➕ Add New Rule": None}
    rule_opts.update({
        f"{r['from_status']} → {r['action_label']} → {r['to_status']}": r["rule_id"]
        for r in rules
    })
    sel_label = st.selectbox(
        "Select a rule to edit, or choose 'Add New Rule'",
        list(rule_opts.keys()), key="sa_w_select"
    )
    sel_rule_id = rule_opts[sel_label]
    editing = sel_rule_id is not None
    cur = next((r for r in rules if r["rule_id"] == sel_rule_id), None) if editing else None

    if editing:
        st.info(f"Editing rule: **{sel_label}**")
    else:
        st.caption("Fill in the fields below to create a new rule.")

    # ── Form fields, pre-filled if editing ──────────────────────────────
    w1,w2=st.columns(2)
    wf=w1.text_input("From Status *", value=cur["from_status"] if editing else "", key=f"sa_wf_{sel_rule_id}")
    wt=w2.text_input("To Status *",   value=cur["to_status"]   if editing else "", key=f"sa_wt_{sel_rule_id}")
    w3,w4=st.columns(2)
    wl=w3.text_input("Action Label *", value=cur["action_label"]  if editing else "", key=f"sa_wl_{sel_rule_id}")
    wr=w4.text_input("Allowed Roles (comma separated) *", value=cur["allowed_roles"] if editing else "", key=f"sa_wr_{sel_rule_id}")
    w5,w6=st.columns(2)
    wrc=w5.checkbox("Requires Comment", value=bool(cur["requires_comment"]) if editing else True, key=f"sa_wrc_{sel_rule_id}")
    wra=w6.checkbox("Requires Assignee", value=bool(cur["requires_assignee"]) if editing else False, key=f"sa_wra_{sel_rule_id}")
    wact = st.checkbox("Active", value=bool(cur["is_active"]) if editing else True, key=f"sa_wact_{sel_rule_id}")

    btn_label = "💾 Save Changes" if editing else "➕ Add Rule"
    if st.button(btn_label, key=f"sa_wsubmit_{sel_rule_id}", type="primary"):
        if wf and wt and wl and wr:
            conn=get_conn()
            try:
                if editing:
                    conn.execute(
                        "UPDATE tbl_workflow_rules SET from_status=?, to_status=?, "
                        "action_label=?, allowed_roles=?, requires_comment=?, "
                        "requires_assignee=?, is_active=? WHERE rule_id=?",
                        (wf.upper(), wt.upper(), wl, wr,
                         1 if wrc else 0, 1 if wra else 0, 1 if wact else 0,
                         sel_rule_id)
                    )
                    conn.commit()
                    st.success("Rule updated.")
                else:
                    conn.execute(
                        "INSERT INTO tbl_workflow_rules (module_id,from_status,to_status,"
                        "action_label,allowed_roles,requires_comment,requires_assignee,sort_order) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (mid, wf.upper(), wt.upper(), wl, wr,
                         1 if wrc else 0, 1 if wra else 0, len(rules))
                    )
                    conn.commit()
                    st.success("Rule added.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
            finally:
                conn.close()
        else:
            st.warning("Please fill in all required fields (marked *).")

    if editing:
        st.divider()
        if st.button("🗑️ Delete This Rule Permanently", key=f"sa_wdelete_{sel_rule_id}"):
            conn=get_conn()
            try:
                conn.execute("DELETE FROM tbl_workflow_rules WHERE rule_id=?", (sel_rule_id,))
                conn.commit()
                st.success("Rule deleted.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
            finally:
                conn.close()
def _depts():
    st.subheader("Departments & Locations")
    depts=[dict(r) for r in _fa("SELECT * FROM tbl_departments WHERE is_active=1 ORDER BY dept_name")]
    if depts:
        st.dataframe(pd.DataFrame([{"ID":d["dept_id"],"Name":d["dept_name"],"Code":d["dept_code"]} for d in depts]),use_container_width=True,hide_index=True)
    st.divider()
    d1,d2=st.columns(2)
    dn=d1.text_input("Dept Name *",key="sa_dn"); dc=d2.text_input("Dept Code *",key="sa_dc")
    if st.button("Add Dept",key="sa_dadd"):
        if dn and dc:
            conn=get_conn()
            try:
                conn.execute("INSERT INTO tbl_departments (dept_name,dept_code) VALUES (?,?)",(dn,dc.upper()))
                conn.commit(); st.success("Added."); st.rerun()
            except Exception as e: st.error(str(e))
            finally: conn.close()
    st.divider()
    dm={d["dept_name"]:d["dept_id"] for d in depts}
    l1,l2,l3,l4=st.columns(4)
    ld=l1.selectbox("Dept *",list(dm.keys()),key="sa_ld"); ln=l2.text_input("Location Name *",key="sa_ln"); lc=l3.text_input("Code *",key="sa_lc"); lt=l4.selectbox("Type",["LAB","ROOM","FLOOR","BLOCK"],key="sa_lt")
    if st.button("Add Location",key="sa_ladd"):
        if ln and lc:
            conn=get_conn()
            try:
                conn.execute("INSERT INTO tbl_locations (dept_id,location_name,location_code,location_type) VALUES (?,?,?,?)",(dm[ld],ln,lc.upper(),lt))
                conn.commit(); st.success("Added."); st.rerun()
            except Exception as e: st.error(str(e))
            finally: conn.close()
