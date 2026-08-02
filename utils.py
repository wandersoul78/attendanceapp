"""
utils.py
Small shared helpers so date/time formatting is consistent across the app
using Indian Standard Time (IST / UTC+5:30).
"""

from datetime import datetime, timezone, timedelta

# Indian Standard Time timezone offset (+05:30)
IST = timezone(timedelta(hours=5, minutes=30))


def get_ist_now() -> datetime:
    """Return current datetime in Indian Standard Time (IST)."""
    return datetime.now(IST)


def today_date_str() -> str:
    """Return today's date string 'YYYY-MM-DD' in IST."""
    return get_ist_now().strftime("%Y-%m-%d")


def now_full_str() -> str:
    """Return full datetime string 'YYYY-MM-DD HH:MM:SS AM/PM' in IST."""
    return get_ist_now().strftime("%Y-%m-%d %I:%M:%S %p")


def now_display_datetime() -> str:
    """Return formatted display datetime in IST e.g. '02 August 2026 · 03:15 PM'."""
    return get_ist_now().strftime("%d %B %Y  ·  %I:%M %p IST")


def pretty_date(iso_date_str: str) -> str:
    """'2026-07-11' -> '11 July 2026', for friendlier on-screen display."""
    try:
        return datetime.strptime(iso_date_str, "%Y-%m-%d").strftime("%d %B %Y")
    except (ValueError, TypeError):
        return iso_date_str