"""
sheets.py
Handles all communication with Google Sheets via a service account.

Expected Google Sheet layout (two tabs, in ONE spreadsheet):

Tab "employees"
    Employee
    Rahul
    Amit
    Deepak
    Vijay
    Rakesh

Tab "attendance"
    Employee | Date | IN | OUT

Each row is one employee's record for one day. Date holds just the date
(e.g. "2026-07-11") so it's easy to use in date-range formulas elsewhere.
IN and OUT each hold a full date+time value (e.g. "2026-07-11 02:30:23 PM").
OUT stays blank until the employee checks out — status is derived from
whether IN / OUT are filled, no separate Status column needed.
"""

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

ATTENDANCE_HEADERS = ["Employee", "Date", "IN", "OUT"]


@st.cache_resource(show_spinner=False)
def get_client():
    """Authenticate once per app session using the service account in secrets.toml."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet():
    client = get_client()
    sheet_id = st.secrets["sheet"]["spreadsheet_id"]
    return client.open_by_key(sheet_id)


def get_employees_sheet():
    return get_spreadsheet().worksheet("employees")


def get_attendance_sheet():
    return get_spreadsheet().worksheet("attendance")


def load_employees() -> list[str]:
    """Read the employees tab, skipping the header row."""
    ws = get_employees_sheet()
    values = ws.col_values(1)[1:]
    return [name.strip() for name in values if name.strip()]


def load_attendance_df() -> pd.DataFrame:
    """
    Read the whole attendance tab into a DataFrame, always fetched fresh
    (no caching) so the dashboard reflects the latest punches.
    Column names are matched case/whitespace-insensitively so a header typed
    slightly differently in the sheet doesn't silently break lookups.
    """
    ws = get_attendance_sheet()
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    if df.empty:
        return pd.DataFrame(columns=ATTENDANCE_HEADERS)

    rename_map = {}
    for col in df.columns:
        key = col.strip().lower()
        for canonical in ATTENDANCE_HEADERS:
            if key == canonical.lower():
                rename_map[col] = canonical
    df = df.rename(columns=rename_map)

    for col in ATTENDANCE_HEADERS:
        if col not in df.columns:
            df[col] = ""

    df["Employee"] = df["Employee"].astype(str).str.strip()
    df["Date"] = df["Date"].astype(str).str.strip()
    return df


def _next_empty_row(ws) -> int:
    """Row number right after the last row that has any data, header included."""
    values = ws.get_all_values()
    return len(values) + 1


def find_today_row(ws, employee: str, date_str: str):
    """Return the 1-indexed sheet row number for employee's record on date_str, or None."""
    all_values = ws.get_all_values()
    for idx, row in enumerate(all_values[1:], start=2):  # skip header, sheet rows are 1-indexed
        if len(row) >= 2 and row[0].strip() == employee and row[1].strip() == date_str:
            return idx
    return None


def create_checkin_row(employee: str, date_str: str, in_time: str):
    """
    Write a new row when an employee checks in for the first time today.
    Uses an explicit A:D range (not append_row) so the row always lands in
    columns A-D, regardless of any stray data elsewhere in the sheet.
    """
    ws = get_attendance_sheet()
    row_num = _next_empty_row(ws)
    ws.update(range_name=f"A{row_num}:D{row_num}", values=[[employee, date_str, in_time, ""]])


def update_checkout_row(employee: str, date_str: str, out_time: str):
    """Update today's existing row for this employee with a check-out time."""
    ws = get_attendance_sheet()
    row_idx = find_today_row(ws, employee, date_str)
    if row_idx is None:
        # Safety net: if no matching row was found, create one rather than fail silently.
        row_num = _next_empty_row(ws)
        ws.update(range_name=f"A{row_num}:D{row_num}", values=[[employee, date_str, "", out_time]])
        return
    ws.update_cell(row_idx, 4, out_time)  # OUT column (D)
