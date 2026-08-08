"""
app.py
Entry point for the Company Attendance & Payroll Streamlit Application.
Optimized with mobile-first CSS styling and PIN protection.
"""

import streamlit as st
from db import is_supabase_configured
from attendance import render_punch_section
from admin import render_admin_dashboard

st.set_page_config(
    page_title="Attendance Portal",
    page_icon="🕒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom Mobile-First CSS Styling
st.markdown("""
<style>
/* Hide Streamlit Header, Footer, and Main Menu */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Remove top padding for cleaner mobile display */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 600px !important;
}

/* Touch-Friendly Large Mobile Buttons */
div.stButton > button:first-child {
    font-size: 20px !important;
    font-weight: 700 !important;
    padding: 16px 20px !important;
    border-radius: 12px !important;
    box-shadow: 0px 4px 10px rgba(0,0,0,0.12) !important;
}

/* Dropdown Select Box styling for mobile */
div[data-baseweb="select"] {
    font-size: 18px !important;
    border-radius: 10px !important;
}

/* Subheaders & Metric text */
h3 {
    font-size: 24px !important;
}
</style>
""", unsafe_allow_html=True)

# Fetch admin PIN from secrets or use default '1234'
ADMIN_PIN = st.secrets.get("ADMIN_PIN", "1234")

# Session state for Admin Auth
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# Sidebar Navigation / Logout
with st.sidebar:
    st.title("🔒 Settings")
    if st.session_state.admin_authenticated:
        st.success("🔑 Admin Mode Active")
        if st.button("Lock / Logout Admin", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()

# ----------------------------------------------------
# MAIN PORTAL DISPLAY
# ----------------------------------------------------

# IF Admin is Authenticated -> Show Tabs (Employee Punch & Admin Dashboard)
if st.session_state.admin_authenticated:
    col_hdr_left, col_hdr_right = st.columns([2, 1])
    with col_hdr_left:
        st.caption("🔑 **Admin Mode Active**")
    with col_hdr_right:
        if st.button("🚪 Exit Admin", key="top_exit_admin_btn", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()

    nav_tab1, nav_tab2 = st.tabs(["🕒 Employee Punch", "📊 Admin & Payroll Dashboard"])
    with nav_tab1:
        render_punch_section()
    with nav_tab2:
        render_admin_dashboard()

# IF Employee View (Default) -> Show ONLY Employee Punch Screen
else:
    render_punch_section()

    st.divider()
    with st.expander("🔑 Admin Login"):
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
