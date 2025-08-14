# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

import db
from db import get_conn
import whatsapp

db.init()
st.set_page_config(page_title="WhatsApp CRM & Renewal Reminder", layout="wide")
st.title("WhatsApp CRM & Renewal Reminder")

# ---------- Helpers ----------
def list_clients():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM clients", conn)
    conn.close()
    return df

def list_policies():
    conn = get_conn()
    q = """SELECT p.*, c.name as client_name, c.phone as client_phone
           FROM policies p JOIN clients c ON c.id=p.client_id"""
    df = pd.read_sql_query(q, conn, parse_dates=["issued_date", "expiry_date"])
    conn.close()
    return df

def add_client(name, phone=None, email=None, notes=None):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("INSERT INTO clients (name,phone,email,notes) VALUES (?,?,?,?)",
                (name, phone, email, notes))
    conn.commit(); conn.close()

def add_policy(row_map):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""INSERT INTO policies
      (client_id, policy_no, insurer, policy_type, issued_date, expiry_date, premium, status, notes)
      VALUES (?,?,?,?,?,?,?,?,?)""", (
        row_map["client_id"], row_map.get("policy_no"), row_map.get("insurer"),
        row_map.get("policy_type"), row_map.get("issued_date"),
        row_map.get("expiry_date"), float(row_map.get("premium", 0) or 0),
        row_map.get("status", "Active"), row_map.get("notes")
    ))
    conn.commit(); conn.close()

def upsert_client(name, phone, email=""):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id FROM clients WHERE phone=?", (phone,))
    r = cur.fetchone()
    if r:
        cid = r["id"]
        cur.execute("UPDATE clients SET name=?, email=? WHERE id=?", (name, email, cid))
    else:
        cur.execute("INSERT INTO clients (name,phone,email) VALUES (?,?,?)", (name, phone, email))
        cid = cur.lastrowid
    conn.commit(); conn.close()
    return cid

# ---------- Sidebar ----------
tab = st.sidebar.radio("Menu", [
    "Dashboard", "Add Client & Policy", "Import from Excel", "Upcoming Renewals", "Bulk WhatsApp"
])

# ---------- Dashboard ----------
if tab == "Dashboard":
    pol = list_policies()
    st.metric("Total Clients", len(list_clients()))
    st.metric("Total Policies", len(pol))
    today = datetime.today().date()
    soon = pol[(pd.to_datetime(pol["expiry_date"]).dt.date >= today) &
               (pd.to_datetime(pol["expiry_date"]).dt.date <= today + timedelta(days=30))]
    st.metric("Renewals next 30d", len(soon))
    st.subheader("Recent Policies")
    st.dataframe(pol.sort_values("expiry_date").tail(50), use_container_width=True)

# ---------- Add Client & Policy ----------
elif tab == "Add Client & Policy":
    st.subheader("Add Client")
    with st.form("client_form", clear_on_submit=True):
        name = st.text_input("Client name*")
        phone = st.text_input("Phone (E.164, e.g. +91XXXXXXXXXX)")
        email = st.text_input("Email")
        notes = st.text_area("Notes")
        if st.form_submit_button("Save Client"):
            if not name or not phone:
                st.error("Name & phone are required.")
            else:
                add_client(name, phone, email, notes)
                st.success("Client saved")

    st.divider()
    st.subheader("Add Policy")
    clients_df = list_clients()
    if clients_df.empty:
        st.info("Add a client first.")
    else:
        with st.form("policy_form", clear_on_submit=True):
            cid = st.selectbox(
                "Client", clients_df["id"].tolist(),
                format_func=lambda i: f'{clients_df.loc[clients_df["id"]==i,"name"].values[0]}'
            )
            policy_no = st.text_input("Policy No")
            insurer = st.text_input("Insurer")
            policy_type = st.text_input("Policy Type")
            issued = st.date_input("Issued Date", value=datetime.today().date())
            expiry = st.date_input("Expiry Date", value=(datetime.today()+timedelta(days=365)).date())
            premium = st.number_input("Premium (₹)", min_value=0.0, value=10000.0)
            notes = st.text_area("Notes")
            if st.form_submit_button("Save Policy"):
                add_policy({
                    "client_id": cid, "policy_no": policy_no, "insurer": insurer,
                    "policy_type": policy_type, "issued_date": issued.isoformat(),
                    "expiry_date": expiry.isoformat(), "premium": premium, "notes": notes
                })
                st.success("Policy saved")

# ---------- Import from Excel ----------
elif tab == "Import from Excel":
    st.subheader("Upload Excel (clients & policies)")
    st.caption("Required columns: name, phone, policy_no, insurer, policy_type, issued_date (YYYY-MM-DD), expiry_date (YYYY-MM-DD), premium")
    file = st.file_uploader("Choose .xlsx", type=["xlsx"])
    if file:
        try:
            df = pd.read_excel(file)
            req = {"name","phone","policy_no","insurer","policy_type","issued_date","expiry_date"}
            if not req.issubset(set(df.columns.str.lower())):
                st.error(f"Missing columns. Found {list(df.columns)}")
            else:
                # normalize columns
                df.columns = [c.lower() for c in df.columns]
                # preview
                st.dataframe(df.head(20), use_container_width=True)
                if st.button("Import Now"):
                    imported = 0
                    for _, r in df.iterrows():
                        cid = upsert_client(str(r["name"]).strip(), str(r["phone"]).strip(), str(r.get("email","") or ""))
                        add_policy({
                            "client_id": cid,
                            "policy_no": str(r.get("policy_no","") or ""),
                            "insurer": str(r.get("insurer","") or ""),
                            "policy_type": str(r.get("policy_type","") or ""),
                            "issued_date": str(r.get("issued_date")),
                            "expiry_date": str(r.get("expiry_date")),
                            "premium": float(r.get("premium", 0) or 0),
                            "notes": str(r.get("notes","") or "")
                        })
                        imported += 1
                    st.success(f"Imported {imported} rows.")
        except Exception as e:
            st.error(f"Import failed: {e}")

# ---------- Upcoming Renewals ----------
elif tab == "Upcoming Renewals":
    pol = list_policies()
    if pol.empty:
        st.info("No policies yet.")
    else:
        window = st.selectbox("Show renewals due in", [7, 30, 60, 90], index=1)
        today = datetime.today().date()
        pol["expiry_date"] = pd.to_datetime(pol["expiry_date"]).dt.date
        soon = pol[(pol["expiry_date"] >= today) & (pol["expiry_date"] <= today + timedelta(days=int(window)))]
        st.write(f"Renewals due in next {window} days: {len(soon)}")
        st.dataframe(soon.sort_values("expiry_date"), use_container_width=True)
        # export
        if not soon.empty:
            buf = BytesIO()
            soon.to_excel(buf, index=False)
            st.download_button("Download Excel", buf.getvalue(), file_name=f"renewals_{window}d.xlsx")

# ---------- Bulk WhatsApp ----------
elif tab == "Bulk WhatsApp":
    st.subheader("Send WhatsApp Reminders (Bulk)")
    pol = list_policies()
    if pol.empty:
        st.info("No policies to send.")
    else:
        window = st.selectbox("Renewals due in (days)", [7, 14, 30, 60, 90], index=2)
        today = datetime.today().date()
        pol["expiry_date"] = pd.to_datetime(pol["expiry_date"]).dt.date
        due = pol[(pol["expiry_date"] >= today) & (pol["expiry_date"] <= today + timedelta(days=int(window)))]

        st.write(f"Eligible recipients: {len(due)}")
        st.dataframe(due[["client_name","client_phone","policy_no","insurer","expiry_date"]], use_container_width=True)

        template = st.text_area(
            "Message template",
            value=("Dear {name}, your policy {policy_no} with {insurer} is due on {expiry}. "
                   "Please contact your agent to renew. —Your Insurance Advisor"),
            height=120
        )

        if st.button("Send WhatsApp to all"):
            if due.empty:
                st.warning("Nothing to send.")
            else:
                sent, failed, simulated = 0, 0, 0
                for _, r in due.iterrows():
                    msg = template.format(
                        name=r["client_name"],
                        policy_no=r.get("policy_no",""),
                        insurer=r.get("insurer",""),
                        expiry=r["expiry_date"].strftime("%d-%m-%Y")
                    )
                    phone = str(r.get("client_phone","")).strip()
                    if not phone:
                        failed += 1; continue
                    sid = whatsapp.send_whatsapp(phone, msg)
                    if sid == "SIMULATED-SEND": simulated += 1
                    elif sid: sent += 1
                    else: failed += 1

                if simulated and not sent:
                    st.warning(f"[SIMULATION MODE] Prepared {simulated} messages (no Twilio keys set).")
                if sent:
                    st.success(f"✅ Sent {sent} messages.")
                if failed:
                    st.error(f"❌ Failed {failed} messages. Check numbers / Twilio logs.")

st.caption("Tip: Trial Twilio can only send to verified numbers. For production, use a WhatsApp Business number and approved templates.")

