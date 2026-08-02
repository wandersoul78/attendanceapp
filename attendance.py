"""
attendance.py
Employee attendance check-in and check-out interface with Hindi (Devanagari) labels,
IST timezone support, 30-minute check-in rounding, unclosed punch cleanup,
continuous/marathon shift support, and mobile-first card widgets.
"""

from datetime import datetime, timezone, timedelta
import streamlit as st
from db import (
    load_employees,
    get_employee_status_today,
    punch_in,
    punch_out,
    get_latest_unclosed_checkin,
    process_continuous_overnight_punchout,
)
from payroll import calculate_overtime_hours
from utils import now_display_datetime, get_ist_now, today_date_str, round_check_in_time

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
    now_dt = get_ist_now()

    # Check for unclosed continuous shift from yesterday
    past_unclosed = get_latest_unclosed_checkin(selected_id, today_str)

    if past_unclosed:
        st.warning(
            f"⚠️ **लगातार ड्यूटी / Continuous Shift Alert**: "
            f"{selected_name} ने कल ({past_unclosed['date']}) **{format_iso_to_time(past_unclosed.get('check_in'))}** बजे Check IN किया था।"
        )
        
        ot_today = calculate_overtime_hours(now_dt)
        if st.button("📤 लगातार ड्यूटी का Check OUT दर्ज करें (Continuous Shift Punch Out)", use_container_width=True, type="primary"):
            process_continuous_overnight_punchout(selected_id, past_unclosed['date'], today_str, now_dt, ot_today)
            st.success(
                f"✅ {selected_name} की लगातार ड्यूटी की हाजिरी दर्ज हो गई है! "
                f"कल की ड्यूटी + 16 घंटे ओवर टाइम और आज ({today_str}) की पूरी हाजिरी अपने आप जुड़ गई है।"
            )
            st.rerun()
        st.divider()

    record = get_employee_status_today(selected_id, today_str)

    in_time_disp = format_iso_to_time(record.get("check_in")) if record else "—"
    out_time_disp = format_iso_to_time(record.get("check_out")) if record else "—"
    ot_hours = record.get("overtime_hours", 0.0) if record else 0.0

    # Mobile Card Widgets for IN and OUT status
    col_in, col_out = st.columns(2)
    with col_in:
        st.markdown(
            f"""
            <div style="background-color: #1e293b; padding: 16px; border-radius: 12px; text-align: center; border: 1px solid #334155; margin-bottom: 10px;">
                <div style="color: #94a3b8; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">आने का समय (IN)</div>
                <div style="color: #38bdf8; font-size: 26px; font-weight: 700; margin-top: 6px;">{in_time_disp}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_out:
        st.markdown(
            f"""
            <div style="background-color: #1e293b; padding: 16px; border-radius: 12px; text-align: center; border: 1px solid #334155; margin-bottom: 10px;">
                <div style="color: #94a3b8; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">जाने का समय (OUT)</div>
                <div style="color: #fb7185; font-size: 26px; font-weight: 700; margin-top: 6px;">{out_time_disp}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")

    # Flow 1: Not checked in yet today
    if record is None or not record.get("check_in"):
        if st.button("📥 आने का समय दर्ज करें (CHECK IN)", use_container_width=True, type="primary"):
            rounded_in_dt = round_check_in_time(now_dt)
            punch_in(selected_id, today_str, rounded_in_dt.isoformat())
            st.success(f"{selected_name} का आने का समय {rounded_in_dt.strftime('%I:%M %p')} बजे दर्ज हो गया है!")
            st.rerun()

    # Flow 2: Checked in, but not checked out yet
    elif record.get("check_in") and not record.get("check_out"):
        ot_projected = calculate_overtime_hours(now_dt)
        if ot_projected > 0:
            st.info(f"⏳ अभी जाने का समय दर्ज करने पर **{ot_projected:.1f} घंटे ओवरटाइम** दर्ज होगा।")

        if st.button("📤 जाने का समय दर्ज करें (CHECK OUT)", use_container_width=True, type="primary"):
            ot_hours_final = calculate_overtime_hours(now_dt)
            punch_out(selected_id, today_str, now_dt.isoformat(), ot_hours_final)
            st.success(f"{selected_name} का जाने का समय {now_dt.strftime('%I:%M %p')} बजे दर्ज हो गया है (ओवरटाइम: {ot_hours_final} घंटे)!")
            st.rerun()

    # Flow 3: Already checked out today
    else:
        st.success(f"✅ {selected_name} की आज की हाजिरी पूरी हो चुकी है।")
        if ot_hours > 0:
            st.info(f"ओवरटाइम (Overtime): **{ot_hours:.1f} घंटे**")
