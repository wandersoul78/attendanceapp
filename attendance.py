"""
attendance.py
Employee attendance check-in and check-out interface with Hindi (Devanagari) labels,
IST timezone support, and automatic unclosed punch cleanup.
"""

from datetime import datetime, timezone, timedelta
import streamlit as st
from db import (
    load_employees,
    get_employee_status_today,
    punch_in,
    punch_out,
    auto_close_pending_past_checkins,
)
from payroll import calculate_overtime_hours
from utils import now_display_datetime, get_ist_now, today_date_str

# Indian Standard Time offset (+05:30)
IST = timezone(timedelta(hours=5, minutes=30))


def format_iso_to_time(iso_str: str) -> str:
    """
    Format ISO timestamp string to readable 12-hour time in IST (e.g. 03:15 PM).
    Converts both legacy UTC timestamps and IST timestamps accurately.
    """
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(IST)
        else:
            dt = dt.astimezone(IST)
        return dt.strftime("%I:%M %p")
    except Exception:
        return iso_str


def render_punch_section():
    st.subheader("🕒 हाजिरी लगाएं (Attendance)")
    st.caption(now_display_datetime())

    employees = load_employees()

    if not employees:
        st.warning("कोई कर्मचारी नहीं मिला। (No employees registered.)")
        return

    emp_names = [e["name"] for e in employees]
    emp_map = {e["name"]: e["id"] for e in employees}

    selected_name = st.selectbox("कर्मचारी का नाम चुनें (Select Employee Name)", emp_names)
    selected_id = emp_map[selected_name]

    today_str = today_date_str()

    # Safeguard: Auto-close any unclosed punches from yesterday or earlier at 5:00 PM (0 OT)
    auto_closed_dates = auto_close_pending_past_checkins(selected_id, today_str)
    if auto_closed_dates:
        st.info(f"ℹ️ {selected_name} की पुरानी हाजिरी ({', '.join(auto_closed_dates)}) 05:00 PM पर समाप्त की गई है। (Admin can adjust if needed).")

    record = get_employee_status_today(selected_id, today_str)

    in_time_disp = format_iso_to_time(record.get("check_in")) if record else "—"
    out_time_disp = format_iso_to_time(record.get("check_out")) if record else "—"
    ot_hours = record.get("overtime_hours", 0.0) if record else 0.0

    col_in, col_out = st.columns(2)
    with col_in:
        st.markdown("**आने का समय (IN)**")
        st.subheader(in_time_disp)
    with col_out:
        st.markdown("**जाने का समय (OUT)**")
        st.subheader(out_time_disp)

    st.divider()

    now_dt = get_ist_now()
    now_iso = now_dt.isoformat()

    # Flow 1: Not checked in yet today
    if record is None or not record.get("check_in"):
        if st.button("📥 आने का समय दर्ज करें (CHECK IN)", use_container_width=True, type="primary"):
            punch_in(selected_id, today_str, now_iso)
            st.success(f"{selected_name} का आने का समय {now_dt.strftime('%I:%M %p')} बजे दर्ज हो गया है!")
            st.rerun()

    # Flow 2: Checked in, but not checked out yet
    elif record.get("check_in") and not record.get("check_out"):
        ot_projected = calculate_overtime_hours(now_dt)
        if ot_projected > 0:
            st.info(f"⏳ अभी जाने का समय दर्ज करने पर **{ot_projected:.1f} घंटे ओवरटाइम** दर्ज होगा।")

        if st.button("📤 जाने का समय दर्ज करें (CHECK OUT)", use_container_width=True, type="primary"):
            ot_hours_final = calculate_overtime_hours(now_dt)
            punch_out(selected_id, today_str, now_iso, ot_hours_final)
            st.success(f"{selected_name} का जाने का समय {now_dt.strftime('%I:%M %p')} बजे दर्ज हो गया है (ओवरटाइम: {ot_hours_final} घंटे)!")
            st.rerun()

    # Flow 3: Already checked out today
    else:
        st.success(f"✅ {selected_name} की आज की हाजिरी पूरी हो चुकी है।")
        if ot_hours > 0:
            st.info(f"ओवरटाइम (Overtime): **{ot_hours:.1f} घंटे**")
