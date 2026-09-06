"""
monthly_view.py
Interactive Monthly Attendance and Working Days calculation breakdown view
for individual employees. Highlights missing punches, weekly offs, paid holidays,
and transparent step-by-step wage calculations.
"""

import importlib
from datetime import date, datetime
import streamlit as st
import pandas as pd
from db import load_employees
import payroll
try:
    from payroll import get_employee_monthly_breakdown
except ImportError:
    payroll = importlib.reload(payroll)
    from payroll import get_employee_monthly_breakdown
from utils import get_ist_now


def render_employee_monthly_view(default_emp_id: str = None, is_admin: bool = False):
    """
    Render individual employee monthly attendance breakdown.
    Can be used within both Admin Dashboard and Employee Portal.
    """
    employees = load_employees()
    if not employees:
        st.warning("कोई कर्मचारी नहीं मिला। (No employees registered.)")
        return

    emp_names = [e["name"] for e in employees]
    emp_map_name_to_id = {e["name"]: e["id"] for e in employees}
    emp_map_id_to_name = {e["id"]: e["name"] for e in employees}

    # Determine default selection
    default_name_index = 0
    if default_emp_id and default_emp_id in emp_map_id_to_name:
        default_name = emp_map_id_to_name[default_emp_id]
        if default_name in emp_names:
            default_name_index = emp_names.index(default_name)

    # ----------------------------------------------------
    # CONTROLS ROW
    # ----------------------------------------------------
    today = get_ist_now().date()
    col_emp, col_y, col_m = st.columns([2, 1, 1.2])

    with col_emp:
        selected_emp_name = st.selectbox(
            "Select Employee / कर्मचारी चुनें",
            emp_names,
            index=default_name_index,
            key=f"monthly_view_emp_select_{'admin' if is_admin else 'emp'}"
        )
        selected_emp_id = emp_map_name_to_id[selected_emp_name]

    with col_y:
        selected_year = st.number_input(
            "Year / वर्ष",
            min_value=2020,
            max_value=2035,
            value=today.year,
            key=f"monthly_view_year_{'admin' if is_admin else 'emp'}"
        )

    with col_m:
        selected_month = st.selectbox(
            "Month / महीना",
            options=list(range(1, 13)),
            format_func=lambda m: datetime(2000, m, 1).strftime("%B"),
            index=today.month - 1,
            key=f"monthly_view_month_{'admin' if is_admin else 'emp'}"
        )

    # Generate breakdown
    breakdown = get_employee_monthly_breakdown(selected_emp_id, selected_year, selected_month)

    st.write("")

    # ----------------------------------------------------
    # MISSED PUNCH ALERT BANNER
    # ----------------------------------------------------
    improper_count = breakdown["improper_punch_days"]
    if improper_count > 0:
        st.error(
            f"⚠️ **अधूरी हाजिरी चेतावनी / Incomplete Punch Alert**: "
            f"**{selected_emp_name}** के इस महीने में **{improper_count} तारीख(एं)** पर पंच अधूरा है (Check-IN हुआ पर Check-OUT नहीं)! "
            f"कृपया इसे सही करें ताकि सही कार्य दिवस (Working Days) गिने जा सकें।"
        )
        
        # Display the specific dates that need attention
        with st.expander("🔍 अधूरी तारीखों की सूची देखें (View Incomplete Punch Dates)", expanded=True):
            imp_df = breakdown["days_df"][breakdown["days_df"]["date"].isin(breakdown["improper_dates"])]
            for _, imp_row in imp_df.iterrows():
                c_alert_txt, c_alert_btn = st.columns([3, 1])
                with c_alert_txt:
                    st.markdown(
                        f"• **{imp_row['display_date']}**: Check-IN: `{imp_row['check_in']}` | "
                        f"Check-OUT: <span style='color: #ef4444; font-weight: bold;'>{imp_row['check_out']} (छूटा हुआ / MISSED)</span> — {imp_row['remarks']}",
                        unsafe_allow_html=True
                    )
                if is_admin:
                    with c_alert_btn:
                        # Direct button to jump to edit attendance log
                        if st.button(f"✏️ Fix {imp_row['day_num']:02d} {breakdown['month_name'][:3]}", key=f"fix_punch_btn_{imp_row['date']}"):
                            st.session_state.edit_target_emp = selected_emp_name
                            st.session_state.edit_target_date = date.fromisoformat(imp_row["date"])
                            st.session_state.admin_nav_tab = "✏️ Edit Attendance Logs"
                            st.rerun()

    # ----------------------------------------------------
    # HIGH-LEVEL SUMMARY METRIC CARDS
    # ----------------------------------------------------
    m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)

    with m_col1:
        st.metric(
            "Present Days",
            f"{breakdown['present_days']} days",
            help="कुल दिन जब कर्मचारी उपस्थित रहा (Days with attendance punch)"
        )
    with m_col2:
        st.metric(
            "Missed Punches",
            f"{breakdown['improper_punch_days']}",
            delta="- Needs Review" if breakdown['improper_punch_days'] > 0 else "All Good",
            delta_color="inverse" if breakdown['improper_punch_days'] > 0 else "normal",
            help="दिन जब Check-IN हुआ लेकिन Check-OUT दर्ज नहीं हुआ"
        )
    with m_col3:
        st.metric(
            "Weekly Offs",
            f"{breakdown['weekly_offs']} days",
            help="सप्ताहिक अवकाश (Tuesdays count / override)"
        )
    with m_col4:
        st.metric(
            "Extra Holidays",
            f"{breakdown['extra_holidays']} days",
            help="अतिरिक्त सवेतन छुट्टियां (Company Extra Paid Holidays)"
        )
    with m_col5:
        st.metric(
            "Total Paid Days",
            f"{breakdown['total_paid_days']} / {breakdown['total_days_in_month']}",
            help="कुल वेतन दिवस = उपस्थित दिन + मंगलवार + छुट्टियां"
        )
    with m_col6:
        st.metric(
            "Gross Salary",
            f"₹{breakdown['total_gross_salary']:,.2f}",
            help=f"मूल वेतन: ₹{breakdown['base_pay']:,.2f} + ओवरटाइम: ₹{breakdown['overtime_pay']:,.2f}"
        )

    # ----------------------------------------------------
    # TRANSPARENT WORKING DAYS & SALARY CALCULATION BOX
    # ----------------------------------------------------
    with st.expander("🧮 कार्य दिवस व वेतन गणना का विवरण (How Working Days & Salary are Calculated)", expanded=False):
        st.markdown(f"""
        ### 📌 **कार्य दिवस व वेतन गणना फॉर्मूला (Calculation Breakdown)**
        कर्मचारी: **{selected_emp_name}** | महीना: **{breakdown['month_name']} {selected_year}** (कुल दिन: **{breakdown['total_days_in_month']}**)
        
        ---
        #### 1️⃣ **सवेतन दिवस गणना (Total Paid Days)**:
        $$\\text{{Total Paid Days}} = \\text{{Present Days}} + \\text{{Weekly Offs (Tuesdays)}} + \\text{{Extra Holidays}}$$
        $$\\mathbf{{{breakdown['total_paid_days']} \\text{{ Paid Days}}}} = {breakdown['present_days']} \\text{{ (Present)}} + {breakdown['weekly_offs']} \\text{{ (Weekly Offs)}} + {breakdown['extra_holidays']} \\text{{ (Extra Holidays)}}$$

        - **उपस्थित दिन (Present Days)**: **{breakdown['present_days']}** दिन *(पूर्ण पंच: {breakdown['completed_punch_days']}, छूटे पंच: {breakdown['improper_punch_days']})*
        - **सप्ताहिक अवकाश (Weekly Offs)**: **{breakdown['weekly_offs']}** दिन *(मंगलवार की छुट्टियां)*
        - **कंपनी छुट्टियां (Extra Holidays)**: **{breakdown['extra_holidays']}** दिन
        - **अनुपस्थित दिन (Absent Days)**: **{breakdown['absent_days']}** दिन *(बिना हाजिरी के कार्य दिवस)*

        ---
        #### 2️⃣ **वेतन दर व भुगतान गणना (Salary Calculation)**:
        - **मासिक तय वेतन (Monthly Base Salary)**: **₹{breakdown['monthly_salary']:,.2f}**
        - **प्रतिदिन दर (Daily Rate)**: $\\text{{₹{breakdown['monthly_salary']:,.2f}}} \\div 30 = \\mathbf{{\\text{{₹{breakdown['daily_rate']:,.2f} / day}}}}$
        - **मूल भुगतान (Base Pay)**: $\\text{{₹{breakdown['daily_rate']:,.2f}}} \\times {breakdown['total_paid_days']} \\text{{ days}} = \\mathbf{{\\text{{₹{breakdown['base_pay']:,.2f}}}}}$
        - **प्रति घंटा ओवरटाइम दर (Hourly OT Rate)**: $\\text{{₹{breakdown['daily_rate']:,.2f}}} \\div 8 = \\mathbf{{\\text{{₹{breakdown['hourly_ot_rate']:,.2f} / hr}}}}$
        - **ओवरटाइम भुगतान (Overtime Pay)**: $\\text{{₹{breakdown['hourly_ot_rate']:,.2f}}} \\times {breakdown['total_ot_hours']} \\text{{ hrs}} = \\mathbf{{\\text{{₹{breakdown['overtime_pay']:,.2f}}}}}$
        
        $$\\mathbf{{\\text{{कुल वेतन (Net Gross Salary) = ₹{breakdown['base_pay']:,.2f} + ₹{breakdown['overtime_pay']:,.2f} = ₹{breakdown['total_gross_salary']:,.2f}}}}}$$
        """)

    st.divider()

    # ----------------------------------------------------
    # DAY-BY-DAY ATTENDANCE SHEET & FILTERS
    # ----------------------------------------------------
    st.markdown("### 📅 दैनिक हाजिरी विवरण (Day-by-Day Attendance Record)")

    days_df = breakdown["days_df"].copy()

    # Filter Options
    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        filter_option = st.radio(
            "Filter by Status / स्थिति के अनुसार देखें",
            options=[
                f"All Days ({len(days_df)})",
                f"⚠️ Missed Punches ({breakdown['improper_punch_days']})",
                f"✅ Present Days ({breakdown['present_days']})",
                f"❌ Absent Days ({breakdown['absent_days']})",
                f"🌴 Weekly Offs ({breakdown['weekly_offs']})"
            ],
            horizontal=True,
            key=f"filter_rad_{'admin' if is_admin else 'emp'}"
        )

    # Apply Filter
    if "Missed Punches" in filter_option:
        filtered_df = days_df[days_df["status_key"].isin(["MISSING_OUT", "MISSING_IN"])]
    elif "Present Days" in filter_option:
        filtered_df = days_df[days_df["status_key"].isin(["PRESENT", "WORKED_TUESDAY", "WORKING_TODAY", "MISSING_OUT", "MISSING_IN"])]
    elif "Absent Days" in filter_option:
        filtered_df = days_df[days_df["status_key"] == "ABSENT"]
    elif "Weekly Offs" in filter_option:
        filtered_df = days_df[days_df["is_tuesday"] == True]
    else:
        filtered_df = days_df

    if filtered_df.empty:
        st.info("इस फ़िल्टर में कोई रिकॉर्ड नहीं मिला। (No records found for this filter.)")
    else:
        # Prepare display table
        display_table = pd.DataFrame({
            "Date": filtered_df["display_date"],
            "Status": filtered_df["status_label"],
            "Check IN": filtered_df["check_in"],
            "Check OUT": filtered_df["check_out"],
            "Overtime": filtered_df["overtime_hours"].apply(lambda h: f"{h:.1f} hrs" if h > 0 else "—"),
            "Paid Status": filtered_df["is_paid"].apply(lambda p: "✅ Paid" if p else "— Unpaid"),
            "Remarks / Notes": filtered_df["remarks"]
        })

        # Render styled dataframe
        st.dataframe(
            display_table,
            use_container_width=True,
            hide_index=True
        )

    # ----------------------------------------------------
    # EXPORT INDIVIDUAL MONTHLY CSV
    # ----------------------------------------------------
    export_df = pd.DataFrame({
        "Date": days_df["date"],
        "Day": days_df["day_name"],
        "Status": days_df["status_label"],
        "Check IN": days_df["check_in"],
        "Check OUT": days_df["check_out"],
        "Overtime (Hours)": days_df["overtime_hours"],
        "Paid Day": days_df["is_paid"].apply(lambda p: "Yes" if p else "No"),
        "Remarks": days_df["remarks"]
    })

    csv_data = export_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label=f"📥 Download {selected_emp_name}'s {breakdown['month_name']} Sheet (CSV)",
        data=csv_data,
        file_name=f"Attendance_{selected_emp_name}_{selected_year}_{selected_month:02d}.csv",
        mime="text/csv",
        type="secondary",
        key=f"export_csv_btn_{'admin' if is_admin else 'emp'}"
    )
