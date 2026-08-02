"""
payroll.py
Payroll calculation engine handling stepped overtime calculation,
weekly off (Tuesday) counting, manual overrides per employee, and monthly wage reports.
"""

import math
import calendar
from datetime import datetime, date
import pandas as pd
from db import (
    load_employees,
    load_attendance_df,
    get_monthly_extra_holidays,
    get_employee_salary_for_month,
    get_weekly_off_overrides,
    get_extra_holiday_overrides,
)


def calculate_overtime_hours(check_out_dt: datetime) -> float:
    """
    Calculates overtime hours based on standard 5:00 PM (17:00) shift end:
    - 5:00 PM to 5:30 PM (0-30 mins past 5 PM) -> 0 Hours Overtime
    - 5:31 PM to 6:30 PM -> 1 Hour Overtime
    - 6:31 PM to 7:30 PM -> 2 Hours Overtime
    - 7:31 PM to 8:30 PM -> 3 Hours Overtime
    Formula: If M > 30, OT = ceil((M - 30) / 60)
    """
    if check_out_dt is None:
        return 0.0

    shift_end_mins = 17 * 60  # 5:00 PM in minutes from midnight (1020 mins)
    checkout_mins = check_out_dt.hour * 60 + check_out_dt.minute

    mins_past_5pm = checkout_mins - shift_end_mins
    if mins_past_5pm <= 30:
        return 0.0

    ot_hours = math.ceil((mins_past_5pm - 30) / 60.0)
    return float(ot_hours)


def count_tuesdays_in_month(year: int, month: int) -> int:
    """
    Count number of Tuesdays (weekly holiday) in a given month and year.
    Tuesday is weekday index 1 (Monday=0, Tuesday=1).
    """
    num_days = calendar.monthrange(year, month)[1]
    tuesdays = 0
    for day in range(1, num_days + 1):
        if date(year, month, day).weekday() == 1:
            tuesdays += 1
    return tuesdays


def generate_monthly_payroll(year: int, month: int) -> pd.DataFrame:
    """
    Generate comprehensive payroll summary for all employees for a given month.
    
    Formula:
      - Daily Rate = Monthly Salary / 30
      - Weekly Offs = Overridden Count if specified for employee, else Auto Tuesdays Count
      - Extra Holidays = Overridden Count if specified for employee, else Global Extra Holidays
      - Total Paid Days = Present Days + Weekly Offs + Extra Holidays
      - Base Pay = Daily Rate * Total Paid Days
      - Overtime Pay = (Daily Rate / 8) * Overtime Hours
      - Net Gross Salary = Base Pay + Overtime Pay
    """
    year_month = f"{year:04d}-{month:02d}"
    employees = load_employees()
    att_df = load_attendance_df(year_month)

    auto_tuesdays_count = count_tuesdays_in_month(year, month)
    global_extra_holidays_count = get_monthly_extra_holidays(year_month)
    weekly_off_overrides = get_weekly_off_overrides(year_month)
    extra_holiday_overrides = get_extra_holiday_overrides(year_month)

    total_days_in_month = calendar.monthrange(year, month)[1]
    target_date_str = f"{year_month}-{total_days_in_month:02d}"

    records = []

    for emp in employees:
        emp_id = emp["id"]
        emp_name = emp["name"]

        # Salary for this employee in this specific month
        monthly_salary = get_employee_salary_for_month(emp_id, target_date_str)
        if monthly_salary <= 0:
            monthly_salary = float(emp.get("current_salary") or 0.0)

        # Weekly Offs & Extra Holidays: check if custom override set for employee this month
        emp_weekly_offs = weekly_off_overrides.get(emp_id, auto_tuesdays_count)
        emp_extra_holidays = extra_holiday_overrides.get(emp_id, global_extra_holidays_count)

        # Filter attendance logs for this employee
        if not att_df.empty and "employee_id" in att_df.columns:
            emp_att = att_df[att_df["employee_id"] == emp_id]
        else:
            emp_att = pd.DataFrame()

        # Present days = count of unique dates marked
        present_days = len(emp_att["date"].unique()) if not emp_att.empty else 0

        # Sum of overtime hours
        total_ot_hours = float(emp_att["overtime_hours"].sum()) if not emp_att.empty else 0.0

        # Calculation basis
        total_paid_days = present_days + emp_weekly_offs + emp_extra_holidays

        daily_rate = monthly_salary / 30.0 if monthly_salary > 0 else 0.0
        hourly_ot_rate = daily_rate / 8.0 if daily_rate > 0 else 0.0

        base_pay = daily_rate * total_paid_days
        overtime_pay = hourly_ot_rate * total_ot_hours
        net_gross_salary = base_pay + overtime_pay

        records.append({
            "employee_id": emp_id,
            "Employee": emp_name,
            "Base Salary": round(monthly_salary, 2),
            "Present Days": present_days,
            "Weekly Offs": emp_weekly_offs,
            "Extra Holidays": emp_extra_holidays,
            "Total Paid Days": total_paid_days,
            "Overtime (Hours)": round(total_ot_hours, 1),
            "Daily Rate": round(daily_rate, 2),
            "Base Pay": round(base_pay, 2),
            "Overtime Pay": round(overtime_pay, 2),
            "Total Gross Salary": round(net_gross_salary, 2)
        })

    return pd.DataFrame(records)
