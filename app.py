"""
app.py
Entry point for the Company Attendance & Payroll Streamlit Application.
Run locally with: streamlit run app.py
"""

import streamlit as st
from db import is_supabase_configured
from attendance import render_punch_section
from admin import render_admin_dashboard

st.set_page_config(
    page_title="Company Attendance Portal",
    page_icon="🕒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Fetch admin PIN from secrets or use default '1234'
ADMIN_PIN = st.secrets.get("ADMIN_PIN", "1234")

# Check URL Query Parameters (e.g. ?mode=admin)
query_params = st.query_params
initial_mode = query_params.get("mode", "employee")

# Session state for Admin Auth
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# Sidebar / Top Control for Mode Switching
with st.sidebar:
    st.title("🔒 Navigation")
    if not st.session_state.admin_authenticated:
        st.markdown("### Admin Authentication")
        entered_pin = st.text_input("Enter Admin PIN", type="password", key="sidebar_pin_input")
        if st.button("Unlock Admin Panel", use_container_width=True, type="primary"):
            if str(entered_pin).strip() == str(ADMIN_PIN).strip():
                st.session_state.admin_authenticated = True
                st.success("Admin Access Granted!")
                st.rerun()
            else:
                st.error("Invalid Admin PIN.")
    else:
        st.success("🔑 Admin Mode Unlocked")
        if st.button("Lock / Logout Admin", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.query_params.clear()
            st.rerun()

# ----------------------------------------------------
# MAIN PORTAL DISPLAY
# ----------------------------------------------------
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🕒 Company Attendance Portal")
with col_status:
    if is_supabase_configured():
        st.success("⚡ Database: Supabase Cloud")
    else:
        st.info("💾 Database: Local SQLite")

st.divider()

# IF Admin is Authenticated -> Show Tabs (Employee Punch & Admin Dashboard)
if st.session_state.admin_authenticated:
    nav_tab1, nav_tab2 = st.tabs(["🕒 Employee Punch", "📊 Admin & Payroll Dashboard"])
    with nav_tab1:
        render_punch_section()
    with nav_tab2:
        render_admin_dashboard()

# IF Employee View (Default) -> Show ONLY Employee Punch Screen
else:
    render_punch_section()

    st.divider()
    with st.expander("🔑 Admin Login (For Managers Only)"):
        with st.form("admin_login_form"):
            pin_input = st.text_input("Enter Admin PIN", type="password")
            submit_login = st.form_submit_button("Access Admin Dashboard", type="primary")
            if submit_login:
                if str(pin_input).strip() == str(ADMIN_PIN).strip():
                    st.session_state.admin_authenticated = True
                    st.success("Admin Access Granted!")
                    st.rerun()
                else:
                    st.error("Incorrect Admin PIN. Access Denied.")
