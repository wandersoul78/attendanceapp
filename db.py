"""
db.py
Database interaction module supporting both Supabase (Cloud PostgreSQL)
and SQLite (Local fallback). Includes graceful exception handling for missing tables,
unclosed punch cleanup, and continuous/marathon shift splitting.
"""

import os
import sqlite3
import uuid
import pandas as pd
import streamlit as st
from datetime import datetime, date, time, timezone, timedelta

# SQLite fallback path
SQLITE_DB_PATH = "attendance.db"
IST = timezone(timedelta(hours=5, minutes=30))


def is_supabase_configured() -> bool:
    """Check if Supabase credentials are path-configured in st.secrets."""
    try:
        return "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets
    except Exception:
        return False


@st.cache_resource
def get_supabase_client():
    """Returns initialized Supabase client if configured."""
    if is_supabase_configured():
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    return None


def get_sqlite_conn():
    """Returns connection to local SQLite database."""
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables if using SQLite fallback."""
    if is_supabase_configured():
        return

    conn = get_sqlite_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employee_salary_history (
        id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        monthly_salary REAL NOT NULL,
        effective_from DATE NOT NULL,
        effective_to DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        date DATE NOT NULL,
        check_in TEXT,
        check_out TEXT,
        overtime_hours REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(employee_id, date),
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS monthly_holidays (
        id TEXT PRIMARY KEY,
        year_month TEXT UNIQUE NOT NULL,
        other_holidays_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employee_weekly_off_overrides (
        id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        year_month TEXT NOT NULL,
        weekly_offs INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(employee_id, year_month),
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employee_extra_holiday_overrides (
        id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        year_month TEXT NOT NULL,
        extra_holidays INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(employee_id, year_month),
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


def generate_id() -> str:
    return str(uuid.uuid4())


# ============================================================
# EMPLOYEE & SALARY MANAGEMENT
# ============================================================

def clear_employee_cache():
    """Clear cached employee directory data."""
    load_employees.clear()


@st.cache_data(ttl=60)
def load_employees() -> list[dict]:
    """Fetch all active employees with their currently effective salary."""
    init_db()
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            emp_res = supabase.table("employees").select("*").order("name").execute()
            employees = emp_res.data or []

            sal_res = supabase.table("employee_salary_history").select("*").is_("effective_to", "null").execute()
            sal_map = {r["employee_id"]: float(r["monthly_salary"]) for r in (sal_res.data or [])}

            for emp in employees:
                emp["current_salary"] = sal_map.get(emp["id"], 0.0)
            return employees
        except Exception:
            return []

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT e.id, e.name, s.monthly_salary as current_salary
            FROM employees e
            LEFT JOIN employee_salary_history s 
                ON e.id = s.employee_id AND (s.effective_to IS NULL OR s.effective_to = '')
            ORDER BY e.name
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def add_employee(name: str, monthly_salary: float, effective_from: str = None) -> bool:
    """Add a new employee and their starting salary."""
    if not name or not name.strip():
        return False
    
    name = name.strip()
    if effective_from is None:
        effective_from = date.today().isoformat()

    emp_id = generate_id()
    sal_id = generate_id()

    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("employees").insert({"id": emp_id, "name": name}).execute()
        supabase.table("employee_salary_history").insert({
            "id": sal_id,
            "employee_id": emp_id,
            "monthly_salary": monthly_salary,
            "effective_from": effective_from,
            "effective_to": None
        }).execute()
        clear_employee_cache()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO employees (id, name) VALUES (?, ?)", (emp_id, name))
        cursor.execute("""
            INSERT INTO employee_salary_history (id, employee_id, monthly_salary, effective_from, effective_to)
            VALUES (?, ?, ?, ?, NULL)
        """, (sal_id, emp_id, monthly_salary, effective_from))
        conn.commit()
        clear_employee_cache()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_employee_name(employee_id: str, new_name: str) -> bool:
    """Rename an employee."""
    if not new_name or not new_name.strip():
        return False
    
    new_name = new_name.strip()
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("employees").update({"name": new_name}).eq("id", employee_id).execute()
        clear_employee_cache()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE employees SET name = ? WHERE id = ?", (new_name, employee_id))
    conn.commit()
    conn.close()
    clear_employee_cache()
    return True


def delete_employee(employee_id: str) -> bool:
    """Delete an employee and all associated records."""
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("employees").delete().eq("id", employee_id).execute()
        clear_employee_cache()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    cursor.execute("DELETE FROM employee_salary_history WHERE employee_id = ?", (employee_id,))
    cursor.execute("DELETE FROM attendance WHERE employee_id = ?", (employee_id,))
    cursor.execute("DELETE FROM employee_weekly_off_overrides WHERE employee_id = ?", (employee_id,))
    cursor.execute("DELETE FROM employee_extra_holiday_overrides WHERE employee_id = ?", (employee_id,))
    conn.commit()
    conn.close()
    clear_employee_cache()
    return True


def update_employee_salary(employee_id: str, new_salary: float, effective_from: str) -> bool:
    """Update employee salary with historical rate tracking."""
    sal_id = generate_id()

    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("employee_salary_history").update({
            "effective_to": effective_from
        }).eq("employee_id", employee_id).is_("effective_to", "null").execute()

        supabase.table("employee_salary_history").insert({
            "id": sal_id,
            "employee_id": employee_id,
            "monthly_salary": new_salary,
            "effective_from": effective_from,
            "effective_to": None
        }).execute()
        clear_employee_cache()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE employee_salary_history 
        SET effective_to = ? 
        WHERE employee_id = ? AND (effective_to IS NULL OR effective_to = '')
    """, (effective_from, employee_id))
    
    cursor.execute("""
        INSERT INTO employee_salary_history (id, employee_id, monthly_salary, effective_from, effective_to)
        VALUES (?, ?, ?, ?, NULL)
    """, (sal_id, employee_id, new_salary, effective_from))
    conn.commit()
    conn.close()
    clear_employee_cache()
    return True


def get_employee_salary_for_month(employee_id: str, target_date_str: str) -> float:
    """Find effective salary for an employee on a given target date (preserves historical data)."""
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            res = supabase.table("employee_salary_history") \
                .select("monthly_salary") \
                .eq("employee_id", employee_id) \
                .lte("effective_from", target_date_str) \
                .order("effective_from", desc=True) \
                .limit(1) \
                .execute()
            if res.data:
                return float(res.data[0]["monthly_salary"])
            return 0.0
        except Exception:
            return 0.0

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT monthly_salary 
            FROM employee_salary_history
            WHERE employee_id = ? AND effective_from <= ?
            ORDER BY effective_from DESC
            LIMIT 1
        """, (employee_id, target_date_str))
        row = cursor.fetchone()
        return float(row["monthly_salary"]) if row else 0.0
    except Exception:
        return 0.0
    finally:
        conn.close()


# ============================================================
# ATTENDANCE PUNCHING & CONTINUOUS SHIFT CLEANUP
# ============================================================

def get_employee_status_today(employee_id: str, date_str: str) -> dict:
    """Return today's check_in and check_out record for employee, or None."""
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            res = supabase.table("attendance") \
                .select("*") \
                .eq("employee_id", employee_id) \
                .eq("date", date_str) \
                .execute()
            if res.data:
                return res.data[0]
            return None
        except Exception:
            return None

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM attendance WHERE employee_id = ? AND date = ?
        """, (employee_id, date_str))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def get_latest_unclosed_checkin(employee_id: str, today_str: str) -> dict:
    """Find any unclosed attendance record (check_in set, check_out empty) prior to today_str."""
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            res = supabase.table("attendance") \
                .select("*") \
                .eq("employee_id", employee_id) \
                .lt("date", today_str) \
                .is_("check_out", "null") \
                .order("date", desc=True) \
                .limit(1) \
                .execute()
            if res.data:
                return res.data[0]
            return None
        except Exception:
            return None

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM attendance 
            WHERE employee_id = ? AND date < ? AND (check_out IS NULL OR check_out = '')
            ORDER BY date DESC LIMIT 1
        """, (employee_id, today_str))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def process_continuous_overnight_punchout(employee_id: str, past_date_str: str, today_str: str, now_dt: datetime, ot_today: float) -> bool:
    """
    Handles continuous/marathon work from past_date_str (Day 1 09:00 AM) through today_str (Day 2):
    1. Closes Day 1 at Day 2 09:00 AM (adds 16.0 hours overtime for overnight work on Day 1).
    2. Creates Day 2 attendance record starting at Day 2 09:00 AM and ending at now_dt.
    """
    past_d_obj = date.fromisoformat(past_date_str)
    today_d_obj = date.fromisoformat(today_str)

    # 1. Close Day 1 at 09:00 AM on Day 2 -> 16 Hours Overtime (from 5 PM Day 1 to 9 AM Day 2)
    day2_9am = datetime.combine(today_d_obj, time(9, 0), tzinfo=IST)
    
    if is_supabase_configured():
        supabase = get_supabase_client()
        # Update Day 1
        supabase.table("attendance").update({
            "check_out": day2_9am.isoformat(),
            "overtime_hours": 16.0
        }).eq("employee_id", employee_id).eq("date", past_date_str).execute()

        # Upsert Day 2
        rec_id = generate_id()
        day2_9am_iso = day2_9am.isoformat()
        now_iso = now_dt.isoformat()
        supabase.table("attendance").upsert({
            "id": rec_id,
            "employee_id": employee_id,
            "date": today_str,
            "check_in": day2_9am_iso,
            "check_out": now_iso,
            "overtime_hours": ot_today
        }, on_conflict="employee_id,date").execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        # Update Day 1
        cursor.execute("""
            UPDATE attendance SET check_out = ?, overtime_hours = 16.0
            WHERE employee_id = ? AND date = ?
        """, (day2_9am.isoformat(), employee_id, past_date_str))

        # Upsert Day 2
        rec_id = generate_id()
        day2_9am_iso = day2_9am.isoformat()
        now_iso = now_dt.isoformat()
        cursor.execute("""
            INSERT INTO attendance (id, employee_id, date, check_in, check_out, overtime_hours)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_id, date) DO UPDATE SET
                check_in = excluded.check_in,
                check_out = excluded.check_out,
                overtime_hours = excluded.overtime_hours
        """, (rec_id, employee_id, today_str, day2_9am_iso, now_iso, ot_today))
        conn.commit()
        return True
    finally:
        conn.close()


def punch_in(employee_id: str, date_str: str, check_in_iso: str) -> bool:
    """Record Check-IN for an employee."""
    record_id = generate_id()
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("attendance").upsert({
            "id": record_id,
            "employee_id": employee_id,
            "date": date_str,
            "check_in": check_in_iso
        }, on_conflict="employee_id,date").execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attendance (id, employee_id, date, check_in)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(employee_id, date) DO UPDATE SET check_in = excluded.check_in
    """, (record_id, employee_id, date_str, check_in_iso))
    conn.commit()
    conn.close()
    return True


def punch_out(employee_id: str, date_str: str, check_out_iso: str, overtime_hours: float) -> bool:
    """Record Check-OUT and overtime hours for an employee."""
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("attendance").update({
            "check_out": check_out_iso,
            "overtime_hours": overtime_hours
        }).eq("employee_id", employee_id).eq("date", date_str).execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE attendance 
        SET check_out = ?, overtime_hours = ?
        WHERE employee_id = ? AND date = ?
    """, (check_out_iso, overtime_hours, employee_id, date_str))
    conn.commit()
    conn.close()
    return True


def update_attendance_record(employee_id: str, date_str: str, check_in_iso: str, check_out_iso: str, overtime_hours: float) -> bool:
    """Upsert full attendance record (Admin Edit)."""
    record_id = generate_id()
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("attendance").upsert({
            "id": record_id,
            "employee_id": employee_id,
            "date": date_str,
            "check_in": check_in_iso,
            "check_out": check_out_iso,
            "overtime_hours": overtime_hours
        }, on_conflict="employee_id,date").execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attendance (id, employee_id, date, check_in, check_out, overtime_hours)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(employee_id, date) DO UPDATE SET 
            check_in = excluded.check_in,
            check_out = excluded.check_out,
            overtime_hours = excluded.overtime_hours
    """, (record_id, employee_id, date_str, check_in_iso, check_out_iso, overtime_hours))
    conn.commit()
    conn.close()
    return True


def delete_attendance_record(employee_id: str, date_str: str) -> bool:
    """Delete an attendance record for an employee on a date (Admin Delete)."""
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("attendance").delete().eq("employee_id", employee_id).eq("date", date_str).execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE employee_id = ? AND date = ?", (employee_id, date_str))
    conn.commit()
    conn.close()
    return True


def load_attendance_df(year_month: str = None) -> pd.DataFrame:
    """Load attendance DataFrame with joined Employee names."""
    init_db()
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            query = supabase.table("attendance").select("*, employees(name)")
            if year_month:
                start_date = f"{year_month}-01"
                query = query.gte("date", start_date)
            res = query.execute()
            data = res.data or []
            if not data:
                return pd.DataFrame(columns=["id", "employee_id", "employee_name", "date", "check_in", "check_out", "overtime_hours"])
            
            flat_data = []
            for r in data:
                emp_name = r.get("employees", {}).get("name", "Unknown") if r.get("employees") else "Unknown"
                flat_data.append({
                    "id": r.get("id"),
                    "employee_id": r.get("employee_id"),
                    "employee_name": emp_name,
                    "date": r.get("date"),
                    "check_in": r.get("check_in"),
                    "check_out": r.get("check_out"),
                    "overtime_hours": float(r.get("overtime_hours") or 0.0)
                })
            return pd.DataFrame(flat_data)
        except Exception:
            return pd.DataFrame(columns=["id", "employee_id", "employee_name", "date", "check_in", "check_out", "overtime_hours"])

    conn = get_sqlite_conn()
    try:
        query = """
            SELECT a.id, a.employee_id, e.name as employee_name, a.date, a.check_in, a.check_out, a.overtime_hours
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
        """
        if year_month:
            query += f" WHERE a.date LIKE '{year_month}%'"
        query += " ORDER BY a.date DESC"
        
        df = pd.read_sql_query(query, conn)
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "employee_id", "employee_name", "date", "check_in", "check_out", "overtime_hours"])
    finally:
        conn.close()


# ============================================================
# HOLIDAYS & WEEKLY OFF OVERRIDES
# ============================================================

def get_monthly_extra_holidays(year_month: str) -> int:
    """Get global extra holiday count for a given month 'YYYY-MM'."""
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            res = supabase.table("monthly_holidays").select("other_holidays_count").eq("year_month", year_month).execute()
            if res.data:
                return int(res.data[0]["other_holidays_count"])
            return 0
        except Exception:
            return 0

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT other_holidays_count FROM monthly_holidays WHERE year_month = ?", (year_month,))
        row = cursor.fetchone()
        return int(row["other_holidays_count"]) if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def set_monthly_extra_holidays(year_month: str, count: int) -> bool:
    """Set global extra holiday count for a given month 'YYYY-MM'."""
    rec_id = generate_id()
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("monthly_holidays").upsert({
            "id": rec_id,
            "year_month": year_month,
            "other_holidays_count": count
        }, on_conflict="year_month").execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO monthly_holidays (id, year_month, other_holidays_count)
        VALUES (?, ?, ?)
        ON CONFLICT(year_month) DO UPDATE SET other_holidays_count = excluded.other_holidays_count
    """, (rec_id, year_month, count))
    conn.commit()
    conn.close()
    return True


def get_weekly_off_overrides(year_month: str) -> dict[str, int]:
    """Get employee_id -> weekly_offs override mapping for a given month."""
    init_db()
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            res = supabase.table("employee_weekly_off_overrides").select("employee_id, weekly_offs").eq("year_month", year_month).execute()
            if res.data:
                return {r["employee_id"]: int(r["weekly_offs"]) for r in res.data}
            return {}
        except Exception:
            return {}

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT employee_id, weekly_offs FROM employee_weekly_off_overrides WHERE year_month = ?", (year_month,))
        rows = cursor.fetchall()
        return {row["employee_id"]: int(row["weekly_offs"]) for row in rows}
    except Exception:
        return {}
    finally:
        conn.close()


def set_weekly_off_override(employee_id: str, year_month: str, weekly_offs: int) -> bool:
    """Set employee specific weekly off override for a month."""
    rec_id = generate_id()
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("employee_weekly_off_overrides").upsert({
            "id": rec_id,
            "employee_id": employee_id,
            "year_month": year_month,
            "weekly_offs": weekly_offs
        }, on_conflict="employee_id,year_month").execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO employee_weekly_off_overrides (id, employee_id, year_month, weekly_offs)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(employee_id, year_month) DO UPDATE SET weekly_offs = excluded.weekly_offs
    """, (rec_id, employee_id, year_month, weekly_offs))
    conn.commit()
    conn.close()
    return True


def get_extra_holiday_overrides(year_month: str) -> dict[str, int]:
    """Get employee_id -> extra_holidays override mapping for a given month."""
    init_db()
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            res = supabase.table("employee_extra_holiday_overrides").select("employee_id, extra_holidays").eq("year_month", year_month).execute()
            if res.data:
                return {r["employee_id"]: int(r["extra_holidays"]) for r in res.data}
            return {}
        except Exception:
            return {}

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT employee_id, extra_holidays FROM employee_extra_holiday_overrides WHERE year_month = ?", (year_month,))
        rows = cursor.fetchall()
        return {row["employee_id"]: int(row["extra_holidays"]) for row in rows}
    except Exception:
        return {}
    finally:
        conn.close()


def set_extra_holiday_override(employee_id: str, year_month: str, extra_holidays: int) -> bool:
    """Set employee specific extra holiday override for a month."""
    rec_id = generate_id()
    if is_supabase_configured():
        supabase = get_supabase_client()
        supabase.table("employee_extra_holiday_overrides").upsert({
            "id": rec_id,
            "employee_id": employee_id,
            "year_month": year_month,
            "extra_holidays": extra_holidays
        }, on_conflict="employee_id,year_month").execute()
        return True

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO employee_extra_holiday_overrides (id, employee_id, year_month, extra_holidays)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(employee_id, year_month) DO UPDATE SET extra_holidays = excluded.extra_holidays
    """, (rec_id, employee_id, year_month, extra_holidays))
    conn.commit()
    conn.close()
    return True
