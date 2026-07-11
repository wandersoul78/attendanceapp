"""
dashboard.py
Renders the "today's attendance" summary: counts + a per-employee status list.
Status is derived purely from whether IN / OUT are filled — no Status column
needed in the sheet.
"""

import streamlit as st
import pandas as pd

from utils import extract_time, pretty_date

def render_dashboard(df: pd.DataFrame, employees: list[str], date_str: str):
    st.subheader(f"Today's Attendance — {pretty_date(date_str)}")

    if df.empty:
        today_df = pd.DataFrame(columns=["Employee", "Date", "IN", "OUT"])
    else:
        today_df = df[df["Date"] == date_str]

    present = working = checked_out = 0
    rows = []

    for emp in employees:
        match = today_df[today_df["Employee"] == emp]
        if match.empty:
            rows.append({"Employee": emp, "Status": "Absent", "Detail": ""})
            continue

        record = match.iloc[0]
        in_val = str(record.get("IN", "") or "")
        out_val = str(record.get("OUT", "") or "")

        if out_val:
            checked_out += 1
            present += 1
            rows.append({"Employee": emp, "Status": "Checked Out", "Detail": f"Out {extract_time(out_val)}"})
        else:
            working += 1
            present += 1
            rows.append({"Employee": emp, "Status": "Working", "Detail": f"In {extract_time(in_val)}"})

    absent = len(employees) - present

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Present", present)
    col2.metric("Working", working)
    col3.metric("Checked Out", checked_out)
    col4.metric("Absent", absent)

    st.divider()

    icon_map = {"Working": "🟢", "Checked Out": "🔴", "Absent": "⚪"}
    for r in rows:
        icon = icon_map.get(r["Status"], "⚪")
        st.write(f"{icon} **{r['Employee']}** — {r['Status']}  {r['Detail']}")
