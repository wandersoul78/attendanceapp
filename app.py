"""
app.py
Entry point. Run locally with:  streamlit run app.py
"""

import streamlit as st

from sheets import load_employees, load_attendance_df
from attendance import render_punch_section
from dashboard import render_dashboard
from utils import today_date_str, now_display_datetime

st.set_page_config(page_title="Company Attendance", page_icon="🕒", layout="centered")

st.title("🕒 Company Attendance")
st.caption(now_display_datetime())

try:
    employees = load_employees()
    df = load_attendance_df()
except Exception as e:
    st.error(
        "Could not connect to Google Sheets. Check that your `.streamlit/secrets.toml` "
        "is filled in correctly and that the sheet is shared with your service account "
        "email. Details below."
    )
    st.exception(e)
    st.stop()

render_punch_section(df, employees)

st.divider()

render_dashboard(df, employees, today_date_str())

if st.button("🔄 Refresh"):
    st.rerun()
