"""
attendance.py
Employee attendance check-in and check-out interface with IST timezone support.
"""

from datetime import datetime
import streamlit as st
from db import load_employees, get_employee_status_today, punch_in, punch_out
from payroll import calculate_overtime_hours
from utils import now_display_datetime, get_ist_now, today_date_str


def format_iso_to_time(iso_str: str) -> str:
    """Format ISO timestamp string to readable 12-hour time (e.g. 03:15 PM IST)."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p")
    except Exception:
        return iso_str


def render_punch_section():
    st.subheader("🕒 Mark Attendance")
    st.caption(now_display_datetime())

    employees = load_employees()

    if not employees:
        st.warning("No employees found. Please register employees in the Admin Dashboard.")
        return

    emp_names = [e["name"] for e in employees]
    emp_map = {e["name"]: e["id"] for e in employees}

    selected_name = st.selectbox("Select Employee Name", emp_names)
    selected_id = emp_map[selected_name]

    today_str = today_date_str()
    record = get_employee_status_today(selected_id, today_str)

    in_time_disp = format_iso_to_time(record.get("check_in")) if record else "—"
    out_time_disp = format_iso_to_time(record.get("check_out")) if record else "—"
    ot_hours = record.get("overtime_hours", 0.0) if record else 0.0

    col_in, col_out = st.columns(2)
    with col_in:
        st.markdown("**IN TIME**")
        st.subheader(in_time_disp)
    with col_out:
        st.markdown("**OUT TIME**")
        st.subheader(out_time_disp)

    st.divider()

    now_dt = get_ist_now()
    now_iso = now_dt.isoformat()

    # Flow 1: Not checked in yet today
    if record is None or not record.get("check_in"):
        if st.button("📥 CHECK IN NOW", use_container_width=True, type="primary"):
            punch_in(selected_id, today_str, now_iso)
            st.success(f"Checked IN successfully at {now_dt.strftime('%I:%M %p')} IST!")
            st.rerun()

    # Flow 2: Checked in, but not checked out yet
    elif record.get("check_in") and not record.get("check_out"):
        ot_projected = calculate_overtime_hours(now_dt)
        if ot_projected > 0:
            st.info(f"⏳ Current Punch Out will log **{ot_projected:.1f} Hours Overtime**.")

        if st.button("📤 CHECK OUT NOW", use_container_width=True, type="primary"):
            ot_hours_final = calculate_overtime_hours(now_dt)
            punch_out(selected_id, today_str, now_iso, ot_hours_final)
            st.success(f"Checked OUT successfully at {now_dt.strftime('%I:%M %p')} IST (Overtime: {ot_hours_final} hrs)!")
            st.rerun()

    # Flow 3: Already checked out today
    else:
        st.success(f"✅ Attendance complete for {selected_name} today.")
        if ot_hours > 0:
            st.info(f"Overtime Recorded: **{ot_hours:.1f} Hours**")
