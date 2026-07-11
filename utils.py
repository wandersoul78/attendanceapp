"""
utils.py
Small shared helpers so date/time formatting is consistent across the app.
"""

from datetime import datetime


def today_date_str() -> str:
    """e.g. '2026-07-11' — stored in its own Date column for easy date-range formulas."""
    return datetime.now().strftime("%Y-%m-%d")


def now_full_str() -> str:
    """e.g. '2026-07-11 02:30:23 PM' — stored in IN / OUT columns."""
    return datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")


def now_display_datetime() -> str:
    """e.g. '2026-07-11 · 09:22 AM' — shown at the top of the dashboard."""
    return datetime.now().strftime("%Y %m %d  ·  %I:%M %p")

def now_display_datetime() -> str:
    """e.g. '11 July 2026 · 09:22 AM' — shown at the top of the dashboard."""
    return datetime.now().strftime("%d %B %Y  ·  %I:%M %p")


def pretty_date(iso_date_str: str) -> str:
    """'2026-07-11' -> '11 July 2026', for friendlier on-screen display."""
    try:
        return datetime.strptime(iso_date_str, "%Y-%m-%d").strftime("%d %B %Y")
    except (ValueError, TypeError):
        return iso_date_str


def extract_time(full_str: str) -> str:
    """'2026-07-11 02:30:23 PM' -> '02:30:23 PM'. Handles blanks safely."""
    full_str = (full_str or "").strip()
    if not full_str:
        return ""
    parts = full_str.split(" ", 1)
    return parts[1] if len(parts) == 2 else ""