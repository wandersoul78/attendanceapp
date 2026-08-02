"""
admin.py
Admin and Payroll Management Interface for Streamlit.
Includes Attendance Log Editor, Employee directory, salary history updates, name edits,
employee deletion, holiday & weekly off overrides, and comprehensive monthly wage export.
"""

from datetime import date, datetime, time, timezone, timedelta
import streamlit as st
import pandas as pd
from db import (
    load_employees,
    add_employee,
    update_employee_salary,
    update_employee_name,
    delete_employee,
    get_monthly_extra_holidays,
    set_monthly_extra_holidays,
    set_weekly_off_override,
    get_employee_status_today,
    update_attendance_record,
    delete_attendance_record,
    load_attendance_df,
)
from payroll import generate_monthly_payroll, count_tuesdays_in_month, calculate_overtime_hours

IST = timezone(timedelta(hours=5, minutes=30))


def format_iso_to_time_display(iso_str: str) -> str:
    """Format ISO string to readable IST time or dash."""
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


def parse_iso_to_time_obj(iso_str: str) -> time:
    """Parse ISO string to Python time object in IST."""
    if not iso_str:
        return time(9, 0)
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(IST)
        else:
            dt = dt.astimezone(IST)
        return dt.time()
    except Exception:
        return time(9, 0)


def render_admin_dashboard():
    st.title("📊 Admin Dashboard")

    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 Payroll Report",
        "✏️ Edit Attendance Logs",
        "👥 Employee Management",
        "🌴 Holidays & Weekly Offs"
    ])

    # ----------------------------------------------------
    # TAB 1: PAYROLL REPORT
    # ----------------------------------------------------
    with tab1:
        st.subheader("Monthly Payroll Summary")

        col_y, col_m = st.columns(2)
        today = date.today()
        
        with col_y:
            selected_year = st.number_input("Year", min_value=2020, max_value=2035, value=today.year)
        with col_m:
            selected_month = st.selectbox(
                "Month",
                options=list(range(1, 13)),
                format_func=lambda m: datetime(2000, m, 1).strftime("%B"),
                index=today.month - 1
            )

        tuesdays = count_tuesdays_in_month(selected_year, selected_month)
        extra_holidays = get_monthly_extra_holidays(f"{selected_year:04d}-{selected_month:02d}")

        st.info(
            f"📅 **Calendar Default for {datetime(2000, selected_month, 1).strftime('%B')} {selected_year}**: "
            f"Auto Tuesdays: **{tuesdays}** | Extra Holidays: **{extra_holidays}** "
            f"*(You can edit weekly off count per employee under 'Holidays & Weekly Offs')*"
        )

        payroll_df = generate_monthly_payroll(selected_year, selected_month)

        if payroll_df.empty:
            st.warning("No employee records found. Add employees in the 'Employee Management' tab.")
        else:
            display_cols = [c for c in payroll_df.columns if c != "employee_id"]

            total_payout = payroll_df["Total Gross Salary"].sum()
            total_ot_hours = payroll_df["Overtime (Hours)"].sum()

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Payout", f"₹{total_payout:,.2f}")
            m2.metric("Total Overtime Hours", f"{total_ot_hours:.1f} hrs")
            m3.metric("Employees Count", len(payroll_df))

            st.dataframe(
                payroll_df[display_cols].style.format({
                    "Base Salary": "₹{:,.2f}",
                    "Daily Rate": "₹{:,.2f}",
                    "Base Pay": "₹{:,.2f}",
                    "Overtime Pay": "₹{:,.2f}",
                    "Total Gross Salary": "₹{:,.2f}",
                }),
                use_container_width=True
            )

            # Export to CSV
            csv_data = payroll_df[display_cols].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Payroll CSV",
                data=csv_data,
                file_name=f"Payroll_Report_{selected_year}_{selected_month:02d}.csv",
                mime="text/csv",
                type="primary"
            )

    # ----------------------------------------------------
    # TAB 2: EDIT ATTENDANCE LOGS
    # ----------------------------------------------------
    with tab2:
        st.subheader("✏️ Add or Edit Attendance Records")
        st.caption("Manually adjust check-in/check-out times, add missing punches, or delete mistaken records for any employee.")

        employees = load_employees()
        if not employees:
            st.warning("No employees registered.")
        else:
            emp_names = [e["name"] for e in employees]
            emp_map = {e["name"]: e["id"] for e in employees}

            col_ed_emp, col_ed_date = st.columns(2)
            with col_ed_emp:
                edit_emp_name = st.selectbox("Select Employee", emp_names, key="edit_att_emp_select")
                edit_emp_id = emp_map[edit_emp_name]
            with col_ed_date:
                edit_date = st.date_input("Select Date", value=today, key="edit_att_date_select")
                edit_date_str = edit_date.isoformat()

            record = get_employee_status_today(edit_emp_id, edit_date_str)

            if record:
                st.info(
                    f"📌 Existing Record for **{edit_emp_name}** on **{edit_date_str}**: "
                    f"IN: **{format_iso_to_time_display(record.get('check_in'))}** | "
                    f"OUT: **{format_iso_to_time_display(record.get('check_out'))}** | "
                    f"Overtime: **{record.get('overtime_hours', 0.0)} hrs**"
                )
            else:
                st.warning(f"No attendance record found for **{edit_emp_name}** on **{edit_date_str}**.")

            st.divider()

            with st.form("edit_attendance_form"):
                st.markdown("#### 🕒 Set Check-IN and Check-OUT Times")
                
                initial_in_time = parse_iso_to_time_obj(record.get("check_in")) if record else time(9, 0)
                initial_out_time = parse_iso_to_time_obj(record.get("check_out")) if record and record.get("check_out") else time(17, 0)
                has_checkout_initial = bool(record and record.get("check_out"))

                col_in_t, col_out_t = st.columns(2)
                with col_in_t:
                    new_in_time = st.time_input("Check-IN Time", value=initial_in_time)
                with col_out_t:
                    include_checkout = st.checkbox("Include Check-OUT", value=has_checkout_initial)
                    new_out_time = st.time_input("Check-OUT Time", value=initial_out_time)

                submit_att_edit = st.form_submit_button("Save Attendance Log", type="primary", use_container_width=True)

                if submit_att_edit:
                    in_dt = datetime.combine(edit_date, new_in_time, tzinfo=IST)
                    in_iso = in_dt.isoformat()

                    out_iso = None
                    ot_final = 0.0

                    if include_checkout:
                        out_dt = datetime.combine(edit_date, new_out_time, tzinfo=IST)
                        out_iso = out_dt.isoformat()
                        ot_final = calculate_overtime_hours(out_dt)

                    update_attendance_record(edit_emp_id, edit_date_str, in_iso, out_iso, ot_final)
                    st.success(f"Successfully saved attendance for {edit_emp_name} on {edit_date_str}!")
                    st.rerun()

            if record:
                st.divider()
                with st.expander("🗑️ Delete Attendance Record for this Date"):
                    if st.button(f"Delete Attendance on {edit_date_str}", type="primary"):
                        delete_attendance_record(edit_emp_id, edit_date_str)
                        st.success(f"Deleted attendance record for {edit_emp_name} on {edit_date_str}.")
                        st.rerun()

    # ----------------------------------------------------
    # TAB 3: EMPLOYEE MANAGEMENT
    # ----------------------------------------------------
    with tab3:
        st.subheader("Manage Employees & Salaries")

        employees = load_employees()

        col_add, col_list = st.columns([1, 1.2])

        with col_add:
            st.markdown("### ➕ Add New Employee")
            with st.form("add_employee_form", clear_on_submit=True):
                new_name = st.text_input("Employee Name")
                new_salary = st.number_input("Monthly Salary (₹)", min_value=0.0, step=1000.0, value=25000.0)
                eff_date = st.date_input("Effective From Date", value=today)
                
                submit_add = st.form_submit_button("Add Employee", use_container_width=True, type="primary")

                if submit_add:
                    if not new_name.strip():
                        st.error("Please enter a valid employee name.")
                    else:
                        success = add_employee(new_name, new_salary, eff_date.isoformat())
                        if success:
                            st.success(f"Employee '{new_name}' added successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to add employee (name might already exist).")

        with col_list:
            st.markdown("### 📋 Active Directory")
            if not employees:
                st.info("No employees registered yet.")
            else:
                for emp in employees:
                    with st.expander(f"👤 {emp['name']} — Current: ₹{emp.get('current_salary', 0):,.2f}"):
                        st.caption(f"Employee ID: `{emp['id']}`")
                        
                        # 1. Edit Name Section
                        st.markdown("#### ✏️ Edit Name")
                        with st.form(f"rename_form_{emp['id']}"):
                            edited_name = st.text_input("Full Name", value=emp['name'], key=f"name_input_{emp['id']}")
                            submit_rename = st.form_submit_button("Save Name Change")
                            if submit_rename:
                                if edited_name and edited_name.strip() != emp['name']:
                                    update_employee_name(emp['id'], edited_name.strip())
                                    st.success("Employee name updated!")
                                    st.rerun()

                        st.divider()

                        # 2. Update Salary Section
                        st.markdown("#### 💰 Update Salary Rate")
                        with st.form(f"update_salary_{emp['id']}"):
                            updated_sal = st.number_input(
                                "New Monthly Salary (₹)",
                                min_value=0.0,
                                value=float(emp.get('current_salary', 0)),
                                step=1000.0,
                                key=f"sal_input_{emp['id']}"
                            )
                            update_eff_date = st.date_input(
                                "Effective Date of Change",
                                value=today,
                                key=f"date_input_{emp['id']}"
                            )
                            submit_sal = st.form_submit_button("Update Salary Rate")

                            if submit_sal:
                                update_employee_salary(emp['id'], updated_sal, update_eff_date.isoformat())
                                st.success("Salary rate updated! Historical reports remain preserved.")
                                st.rerun()

                        st.divider()

                        # 3. Delete Employee Section
                        st.markdown("#### 🗑️ Delete Employee")
                        confirm_delete = st.checkbox(f"I understand this will permanently delete {emp['name']}", key=f"del_chk_{emp['id']}")
                        if st.button(f"Permanently Delete {emp['name']}", key=f"del_btn_{emp['id']}", type="primary"):
                            if confirm_delete:
                                delete_employee(emp['id'])
                                st.success(f"Deleted {emp['name']} permanently.")
                                st.rerun()
                            else:
                                st.warning("Please check the confirmation box first.")

    # ----------------------------------------------------
    # TAB 4: HOLIDAYS & WEEKLY OFF ADJUSTMENTS
    # ----------------------------------------------------
    with tab4:
        st.subheader("Configure Extra Holidays & Employee Weekly Offs")

        col_adj_y, col_adj_m = st.columns(2)
        with col_adj_y:
            adj_year = st.number_input("Target Year", min_value=2020, max_value=2035, value=today.year)
        with col_adj_m:
            adj_month = st.selectbox(
                "Target Month",
                options=list(range(1, 13)),
                format_func=lambda m: datetime(2000, m, 1).strftime("%B"),
                index=today.month - 1
            )

        ym_key = f"{adj_year:04d}-{adj_month:02d}"
        auto_tues = count_tuesdays_in_month(adj_year, adj_month)
        current_extra = get_monthly_extra_holidays(ym_key)

        st.divider()
        st.markdown("### 🌴 1. Company Extra Holidays")
        with st.form("set_holidays_form"):
            extra_count = st.number_input(
                f"Extra Holidays in {datetime(2000, adj_month, 1).strftime('%B')} {adj_year}",
                min_value=0,
                max_value=15,
                value=current_extra
            )
            submit_h = st.form_submit_button("Save Holiday Setting", type="primary")

            if submit_h:
                set_monthly_extra_holidays(ym_key, extra_count)
                st.success(f"Updated extra holidays for {ym_key} to {extra_count} day(s).")
                st.rerun()

        st.divider()
        st.markdown("### ✏️ 2. Edit Weekly Offs per Employee")
        st.caption(
            f"Default Tuesdays count for {datetime(2000, adj_month, 1).strftime('%B')} {adj_year} is **{auto_tues}**. "
            f"If an employee was absent for an entire week (e.g. 1 week away), you can lower their Weekly Offs here."
        )

        payroll_df_adj = generate_monthly_payroll(adj_year, adj_month)

        if payroll_df_adj.empty:
            st.info("No employees found.")
        else:
            for idx, row in payroll_df_adj.iterrows():
                emp_id = row["employee_id"]
                emp_name = row["Employee"]
                curr_weekly_offs = int(row["Weekly Offs"])

                with st.expander(f"👤 {emp_name} — Current Weekly Offs: {curr_weekly_offs} days"):
                    with st.form(f"off_override_form_{emp_id}_{ym_key}"):
                        new_offs = st.number_input(
                            f"Weekly Off Days allowed for {emp_name}",
                            min_value=0,
                            max_value=10,
                            value=curr_weekly_offs,
                            key=f"off_val_{emp_id}_{ym_key}"
                        )
                        submit_off = st.form_submit_button("Update Weekly Off Days")
                        if submit_off:
                            set_weekly_off_override(emp_id, ym_key, new_offs)
                            st.success(f"Updated Weekly Offs for {emp_name} in {ym_key} to {new_offs} day(s).")
                            st.rerun()
