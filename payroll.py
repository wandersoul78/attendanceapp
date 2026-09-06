"""
payroll.py
Payroll calculation engine handling stepped overtime calculation,
weekly off (Tuesday) counting, manual overrides per employee, and monthly wage reports.
"""

import math
import calendar
from datetime import datetime, date, timezone, timedelta
import pandas as pd

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))


def format_iso_to_ist_display(iso_str: str) -> str:
    """Format ISO timestamp string to readable 12-hour time in IST (e.g. '09:30 AM')."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso_str))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(IST)
        else:
            dt = dt.astimezone(IST)
        return dt.strftime("%I:%M %p")
    except Exception:
        return str(iso_str)
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


def get_employee_monthly_breakdown(employee_id: str, year: int, month: int) -> dict:
    """
    Generate detailed day-by-day attendance breakdown and working days calculation
    for a specific employee in a given month.
    
    Identifies:
      - Full days attended (Check-IN + Check-OUT)
      - Missing or improper punches (e.g. checked in but forgot check-out)
      - Weekly offs (Tuesdays) and if worked on Tuesday
      - Extra paid holidays
      - Absent days
      - Full mathematical breakdown of how Total Paid Days and Salary are calculated.
    """
    year_month = f"{year:04d}-{month:02d}"
    today = datetime.now(IST).date()

    # 1. Employee Info & Salary
    employees = load_employees()
    emp = next((e for e in employees if str(e.get("id")) == str(employee_id)), None)
    emp_name = emp["name"] if emp else "Unknown Employee"

    total_days_in_month = calendar.monthrange(year, month)[1]
    target_date_str = f"{year_month}-{total_days_in_month:02d}"

    monthly_salary = get_employee_salary_for_month(employee_id, target_date_str)
    if monthly_salary <= 0 and emp:
        monthly_salary = float(emp.get("current_salary") or 0.0)

    daily_rate = monthly_salary / 30.0 if monthly_salary > 0 else 0.0
    hourly_ot_rate = daily_rate / 8.0 if daily_rate > 0 else 0.0

    # 2. Holidays and Weekly Offs
    auto_tuesdays_count = count_tuesdays_in_month(year, month)
    global_extra_holidays_count = get_monthly_extra_holidays(year_month)
    weekly_off_overrides = get_weekly_off_overrides(year_month)
    extra_holiday_overrides = get_extra_holiday_overrides(year_month)

    emp_weekly_offs = weekly_off_overrides.get(employee_id, auto_tuesdays_count)
    emp_extra_holidays = extra_holiday_overrides.get(employee_id, global_extra_holidays_count)

    # 3. Load attendance records for this month
    att_df = load_attendance_df(year_month)
    if not att_df.empty and "employee_id" in att_df.columns:
        emp_att = att_df[att_df["employee_id"].astype(str) == str(employee_id)]
    else:
        emp_att = pd.DataFrame()

    att_by_date = {}
    if not emp_att.empty:
        for _, row in emp_att.iterrows():
            d_str = str(row["date"])
            att_by_date[d_str] = row

    # 4. Iterate over every day of the month
    day_rows = []
    completed_punch_days = 0
    improper_punch_days = 0
    improper_dates = []
    worked_days_count = 0
    total_ot_hours = 0.0
    absent_days_count = 0
    tuesdays_observed = 0

    for day in range(1, total_days_in_month + 1):
        cur_date = date(year, month, day)
        date_str = cur_date.isoformat()
        day_name = cur_date.strftime("%A")
        day_short = cur_date.strftime("%a")
        is_tuesday = (cur_date.weekday() == 1)
        is_future = (cur_date > today)
        is_today = (cur_date == today)

        rec = att_by_date.get(date_str)
        has_in = bool(rec is not None and pd.notna(rec.get("check_in")) and str(rec.get("check_in")).strip())
        has_out = bool(rec is not None and pd.notna(rec.get("check_out")) and str(rec.get("check_out")).strip())
        ot_hours = float(rec.get("overtime_hours") or 0.0) if rec is not None else 0.0

        in_time_str = format_iso_to_ist_display(rec.get("check_in")) if has_in else "—"
        out_time_str = format_iso_to_ist_display(rec.get("check_out")) if has_out else "—"

        status_key = ""
        status_label = ""
        status_badge_color = ""
        remarks = ""
        is_paid = False
        can_fix = False

        if has_in or has_out:
            worked_days_count += 1
            total_ot_hours += ot_hours

            if has_in and has_out:
                completed_punch_days += 1
                if is_tuesday:
                    status_key = "WORKED_TUESDAY"
                    status_label = "🌴 Worked on Tuesday"
                    status_badge_color = "info"
                    remarks = "Attended on weekly off day (Counts towards Present Days)"
                else:
                    status_key = "PRESENT"
                    status_label = "✅ Present (Full Day)"
                    status_badge_color = "success"
                    remarks = "Regular working day complete"
                is_paid = True
            elif has_in and not has_out:
                if is_today:
                    status_key = "WORKING_TODAY"
                    status_label = "🟡 Working / In Progress"
                    status_badge_color = "warning"
                    remarks = "Checked in today; awaiting Check-OUT punch"
                    is_paid = True
                else:
                    improper_punch_days += 1
                    improper_dates.append(date_str)
                    status_key = "MISSING_OUT"
                    status_label = "⚠️ Missing Check-OUT"
                    status_badge_color = "danger"
                    remarks = "Checked IN but no Check-OUT punch recorded!"
                    is_paid = True
                    can_fix = True
            elif not has_in and has_out:
                improper_punch_days += 1
                improper_dates.append(date_str)
                status_key = "MISSING_IN"
                status_label = "⚠️ Missing Check-IN"
                status_badge_color = "danger"
                remarks = "Check-OUT recorded without Check-IN punch!"
                is_paid = True
                can_fix = True
        else:
            # No attendance record
            if is_future:
                status_key = "FUTURE"
                status_label = "⏳ Upcoming Date"
                status_badge_color = "secondary"
                remarks = "Upcoming date later in the month"
                is_paid = False
            elif is_tuesday:
                tuesdays_observed += 1
                status_key = "WEEKLY_OFF"
                status_label = "🌴 Weekly Off (Tuesday)"
                status_badge_color = "primary"
                remarks = "Company Weekly Holiday (Paid)"
                is_paid = True
            else:
                absent_days_count += 1
                status_key = "ABSENT"
                status_label = "❌ Absent / No Punch"
                status_badge_color = "danger"
                remarks = "No attendance recorded for this working day"
                is_paid = False
                can_fix = True

        day_rows.append({
            "date": date_str,
            "day_num": day,
            "day_name": day_name,
            "day_short": day_short,
            "display_date": f"{day:02d} {cur_date.strftime('%b')} ({day_short})",
            "is_tuesday": is_tuesday,
            "is_today": is_today,
            "is_future": is_future,
            "has_in": has_in,
            "has_out": has_out,
            "check_in": in_time_str,
            "check_out": out_time_str,
            "overtime_hours": ot_hours,
            "status_key": status_key,
            "status_label": status_label,
            "status_badge_color": status_badge_color,
            "is_paid": is_paid,
            "remarks": remarks,
            "can_fix": can_fix,
        })

    days_df = pd.DataFrame(day_rows)

    # 5. Summary calculations matching payroll.py
    present_days = worked_days_count
    total_paid_days = present_days + emp_weekly_offs + emp_extra_holidays

    base_pay = daily_rate * total_paid_days
    overtime_pay = hourly_ot_rate * total_ot_hours
    total_gross_salary = base_pay + overtime_pay

    return {
        "employee_id": employee_id,
        "employee_name": emp_name,
        "year": year,
        "month": month,
        "year_month": year_month,
        "month_name": datetime(year, month, 1).strftime("%B"),
        "monthly_salary": round(monthly_salary, 2),
        "daily_rate": round(daily_rate, 2),
        "hourly_ot_rate": round(hourly_ot_rate, 2),
        "total_days_in_month": total_days_in_month,
        "present_days": present_days,
        "completed_punch_days": completed_punch_days,
        "improper_punch_days": improper_punch_days,
        "improper_dates": improper_dates,
        "absent_days": absent_days_count,
        "weekly_offs": emp_weekly_offs,
        "extra_holidays": emp_extra_holidays,
        "total_paid_days": total_paid_days,
        "total_ot_hours": round(total_ot_hours, 1),
        "base_pay": round(base_pay, 2),
        "overtime_pay": round(overtime_pay, 2),
        "total_gross_salary": round(total_gross_salary, 2),
        "days_df": days_df,
    }

