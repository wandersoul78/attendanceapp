"""
test_payroll.py
Unit tests to verify overtime calculation, Tuesday counting, and check-in time rounding.
"""

from datetime import datetime, timezone, timedelta
from payroll import calculate_overtime_hours, count_tuesdays_in_month
from utils import round_check_in_time, IST


def test_check_in_rounding():
    # 8:59 AM -> 9:00 AM
    dt1 = datetime(2026, 8, 2, 8, 59, tzinfo=IST)
    res1 = round_check_in_time(dt1)
    assert res1.hour == 9 and res1.minute == 0, f"Failed at 8:59 AM: {res1}"

    # 8:50 AM -> 9:00 AM
    dt2 = datetime(2026, 8, 2, 8, 50, tzinfo=IST)
    res2 = round_check_in_time(dt2)
    assert res2.hour == 9 and res2.minute == 0, f"Failed at 8:50 AM: {res2}"

    # 8:45 AM -> 9:00 AM
    dt3 = datetime(2026, 8, 2, 8, 45, tzinfo=IST)
    res3 = round_check_in_time(dt3)
    assert res3.hour == 9 and res3.minute == 0, f"Failed at 8:45 AM: {res3}"

    # 8:31 AM -> 9:00 AM
    dt4 = datetime(2026, 8, 2, 8, 31, tzinfo=IST)
    res4 = round_check_in_time(dt4)
    assert res4.hour == 9 and res4.minute == 0, f"Failed at 8:31 AM: {res4}"

    # 8:30 AM -> 8:00 AM
    dt5 = datetime(2026, 8, 2, 8, 30, tzinfo=IST)
    res5 = round_check_in_time(dt5)
    assert res5.hour == 8 and res5.minute == 0, f"Failed at 8:30 AM: {res5}"

    # 8:29 AM -> 8:00 AM
    dt6 = datetime(2026, 8, 2, 8, 29, tzinfo=IST)
    res6 = round_check_in_time(dt6)
    assert res6.hour == 8 and res6.minute == 0, f"Failed at 8:29 AM: {res6}"

    # 8:15 AM -> 8:00 AM
    dt7 = datetime(2026, 8, 2, 8, 15, tzinfo=IST)
    res7 = round_check_in_time(dt7)
    assert res7.hour == 8 and res7.minute == 0, f"Failed at 8:15 AM: {res7}"

    print("[OK] All Check-IN Rounding Unit Tests Passed!")


def test_overtime_calculation():
    # 5:00 PM (17:00) -> 0 OT
    dt1 = datetime(2026, 8, 2, 17, 0)
    assert calculate_overtime_hours(dt1) == 0.0, f"Failed at 5:00 PM: {calculate_overtime_hours(dt1)}"

    # 5:15 PM (17:15) -> 0 OT
    dt2 = datetime(2026, 8, 2, 17, 15)
    assert calculate_overtime_hours(dt2) == 0.0, f"Failed at 5:15 PM: {calculate_overtime_hours(dt2)}"

    # 5:30 PM (17:30) -> 0 OT (30 min buffer)
    dt3 = datetime(2026, 8, 2, 17, 30)
    assert calculate_overtime_hours(dt3) == 0.0, f"Failed at 5:30 PM: {calculate_overtime_hours(dt3)}"

    # 5:31 PM (17:31) -> 1.0 hr OT
    dt4 = datetime(2026, 8, 2, 17, 31)
    assert calculate_overtime_hours(dt4) == 1.0, f"Failed at 5:31 PM: {calculate_overtime_hours(dt4)}"

    # 6:00 PM (18:00) -> 1.0 hr OT
    dt5 = datetime(2026, 8, 2, 18, 0)
    assert calculate_overtime_hours(dt5) == 1.0, f"Failed at 6:00 PM: {calculate_overtime_hours(dt5)}"

    # 6:30 PM (18:30) -> 1.0 hr OT
    dt6 = datetime(2026, 8, 2, 18, 30)
    assert calculate_overtime_hours(dt6) == 1.0, f"Failed at 6:30 PM: {calculate_overtime_hours(dt6)}"

    # 6:31 PM (18:31) -> 2.0 hrs OT
    dt7 = datetime(2026, 8, 2, 18, 31)
    assert calculate_overtime_hours(dt7) == 2.0, f"Failed at 6:31 PM: {calculate_overtime_hours(dt7)}"

    # 7:00 PM (19:00) -> 2.0 hrs OT
    dt8 = datetime(2026, 8, 2, 19, 0)
    assert calculate_overtime_hours(dt8) == 2.0, f"Failed at 7:00 PM: {calculate_overtime_hours(dt8)}"

    # 7:30 PM (19:30) -> 2.0 hrs OT
    dt9 = datetime(2026, 8, 2, 19, 30)
    assert calculate_overtime_hours(dt9) == 2.0, f"Failed at 7:30 PM: {calculate_overtime_hours(dt9)}"

    # 8:00 PM (20:00) -> 3.0 hrs OT
    dt10 = datetime(2026, 8, 2, 20, 0)
    assert calculate_overtime_hours(dt10) == 3.0, f"Failed at 8:00 PM: {calculate_overtime_hours(dt10)}"

    print("[OK] All Overtime Unit Tests Passed!")


def test_tuesdays_count():
    # August 2026: Aug 4, Aug 11, Aug 18, Aug 25 -> 4 Tuesdays
    tues_aug_2026 = count_tuesdays_in_month(2026, 8)
    assert tues_aug_2026 == 4, f"Failed August 2026 Tuesdays count: {tues_aug_2026}"

    print("[OK] All Tuesdays Count Tests Passed!")


def test_employee_monthly_breakdown():
    from payroll import get_employee_monthly_breakdown
    from db import add_employee, load_employees, update_attendance_record, delete_employee

    # Ensure at least one test employee exists
    emps = load_employees()
    if not emps:
        add_employee("Test Worker", 30000.0, "2026-01-01")
        emps = load_employees()

    test_emp = emps[0]
    test_emp_id = test_emp["id"]

    # Test breakdown for August 2026 (31 days, 4 Tuesdays)
    res = get_employee_monthly_breakdown(test_emp_id, 2026, 8)

    assert res["total_days_in_month"] == 31, f"Expected 31 days in Aug, got {res['total_days_in_month']}"
    assert res["year"] == 2026
    assert res["month"] == 8
    assert res["month_name"] == "August"
    assert len(res["days_df"]) == 31, f"Expected 31 rows in days_df, got {len(res['days_df'])}"

    # Check mathematical formula consistency
    expected_paid_days = res["present_days"] + res["weekly_offs"] + res["extra_holidays"]
    assert res["total_paid_days"] == expected_paid_days, (
        f"Paid days formula mismatch: {res['total_paid_days']} != {expected_paid_days}"
    )

    expected_base_pay = round(res["daily_rate"] * res["total_paid_days"], 2)
    assert round(res["base_pay"], 2) == expected_base_pay, (
        f"Base pay formula mismatch: {res['base_pay']} != {expected_base_pay}"
    )

    expected_gross = round(res["base_pay"] + res["overtime_pay"], 2)
    assert round(res["total_gross_salary"], 2) == expected_gross, (
        f"Total gross salary mismatch: {res['total_gross_salary']} != {expected_gross}"
    )

    # Test improper punch detection:
    # Insert a record with check_in but NO check_out on 2026-08-05 (past date)
    update_attendance_record(test_emp_id, "2026-08-05", "2026-08-05T09:00:00+05:30", None, 0.0)
    res_after = get_employee_monthly_breakdown(test_emp_id, 2026, 8)
    assert res_after["improper_punch_days"] >= 1, "Failed to detect incomplete/missed check-out punch"
    assert "2026-08-05" in res_after["improper_dates"], "Failed to flag 2026-08-05 in improper_dates"

    day_5 = res_after["days_df"][res_after["days_df"]["date"] == "2026-08-05"].iloc[0]
    assert day_5["status_key"] == "MISSING_OUT", f"Expected MISSING_OUT, got {day_5['status_key']}"
    # Clean up test record so database remains clean
    delete_employee(test_emp_id)

    print("[OK] All Employee Monthly Breakdown Unit Tests Passed!")


if __name__ == "__main__":
    test_check_in_rounding()
    test_overtime_calculation()
    test_tuesdays_count()
    test_employee_monthly_breakdown()
