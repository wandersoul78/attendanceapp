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
    page_title="Company Attendance & Payroll",
    page_icon="🕒",
    layout="wide"
)

# Header & Connection Info
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🕒 Attendance & Payroll Portal")
with col_status:
    if is_supabase_configured():
        st.success("⚡ Database: Supabase Cloud")
    else:
        st.info("💾 Database: Local SQLite")

st.divider()

# Navigation Tabs
nav_tab1, nav_tab2 = st.tabs(["🕒 Employee Punch", "📊 Admin & Payroll Dashboard"])

with nav_tab1:
    render_punch_section()

with nav_tab2:
    render_admin_dashboard()
