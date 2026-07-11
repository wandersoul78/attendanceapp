"""
attendance.py
The check-in / check-out flow: figures out an employee's status for today
and renders a clean IN / OUT display plus the right button.
"""

import streamlit as st
import pandas as pd

from sheets import create_checkin_row, update_checkout_row
from utils import today_date_str, now_full_str, extract_time,pretty_date


def get_employee_status_today(df: pd.DataFrame, date_str: str, employee: str):
    """Return today's IN/OUT values for an employee, or None if not checked in."""
    if df.empty:
        return None
    match = df[(df["Employee"] == employee) & (df["Date"] == date_str)]
    if match.empty:
        return None
    row = match.iloc[0]
    return {
        "in": str(row.get("IN", "") or ""),
        "out": str(row.get("OUT", "") or ""),
    }


def render_punch_section(df: pd.DataFrame, employees: list[str]):
    st.subheader("Attendance")

    if not employees:
        st.warning("No employees found. Add names to the 'employees' tab in your Google Sheet.")
        return

    employee = st.selectbox("Employee", employees)
    date_str = today_date_str()
    record = get_employee_status_today(df, date_str, employee)

    in_time = extract_time(record["in"]) if record else ""
    out_time = extract_time(record["out"]) if record else ""

    col_in, col_out = st.columns(2)
    with col_in:
        st.markdown("**IN**")
        st.write(in_time if in_time else "—")
    with col_out:
        st.markdown("**OUT**")
        st.write(out_time if out_time else "—")

    st.write("")

    if record is None:
        if st.button("CHECK IN", use_container_width=True, type="primary"):
            with st.spinner("Saving..."):
                create_checkin_row(employee, date_str, now_full_str())
            st.rerun()

    elif record["in"] and not record["out"]:
        if st.button("CHECK OUT", use_container_width=True, type="primary"):
            with st.spinner("Saving..."):
                update_checkout_row(employee, date_str, now_full_str())
            st.rerun()

    else:
        st.success(f"Attendance complete for {employee}.")
