"""
Server-Authoritative Time Gate
===============================
All cutoff logic evaluated server-side in Central Standard Time (America/Chicago).
Never relies on client-side timestamps.

Cutoff Rules (from framework):
  - Standard days: 11:00 AM CST — new entries locked
  - Fridays: 10:30 AM CST — new entries locked
  - FOMC days: 12:45 PM CST — hard lock + review prompt for open positions
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional

import pytz

from app.core.config import get_settings
from app.db.schemas import CutoffStatusSchema


def get_cst_now() -> datetime:
    """Get current server time in CST (America/Chicago). Never client-side."""
    tz = pytz.timezone(get_settings().app.app_timezone)
    return datetime.now(tz)


def parse_cutoff_time(cutoff_str: str) -> time:
    """Parse a cutoff time string (HH:MM) into a time object."""
    parts = cutoff_str.split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def is_friday(dt: Optional[datetime] = None) -> bool:
    """Check if the given datetime (or now) is a Friday."""
    dt = dt or get_cst_now()
    return dt.weekday() == 4  # Monday=0, Friday=4


def is_fomc_day(dt: Optional[datetime] = None) -> bool:
    """
    Check if today is an FOMC meeting day.

    v1 implementation: checks against a hardcoded list of known FOMC dates.
    Future: integrate with economic calendar API.
    """
    dt = dt or get_cst_now()

    # 2026 FOMC meeting dates (2-day meetings, we gate on both days)
    # Source: Federal Reserve schedule — update annually
    fomc_dates_2026 = {
        # January 27-28
        (1, 27), (1, 28),
        # March 17-18
        (3, 17), (3, 18),
        # May 5-6
        (5, 5), (5, 6),
        # June 16-17
        (6, 16), (6, 17),
        # July 28-29
        (7, 28), (7, 29),
        # September 15-16
        (9, 15), (9, 16),
        # October 27-28
        (10, 27), (10, 28),
        # December 15-16
        (12, 15), (12, 16),
    }

    return (dt.month, dt.day) in fomc_dates_2026


def get_applicable_cutoff(dt: Optional[datetime] = None) -> tuple[str, time]:
    """
    Determine which cutoff rule applies right now.
    Returns (rule_name, cutoff_time).
    Priority: FOMC > Friday > Standard
    """
    settings = get_settings()
    dt = dt or get_cst_now()

    if is_fomc_day(dt):
        return "FOMC", parse_cutoff_time(settings.app.cutoff_fomc)
    elif is_friday(dt):
        return "FRIDAY", parse_cutoff_time(settings.app.cutoff_friday)
    else:
        return "STANDARD", parse_cutoff_time(settings.app.cutoff_standard)


def is_past_cutoff(dt: Optional[datetime] = None) -> bool:
    """Check if current time is past the applicable cutoff."""
    dt = dt or get_cst_now()
    _, cutoff_time = get_applicable_cutoff(dt)
    return dt.time() >= cutoff_time


def get_cutoff_status(dt: Optional[datetime] = None) -> CutoffStatusSchema:
    """
    Get the full cutoff status for API responses and UI display.
    All times are server-authoritative CST.
    """
    dt = dt or get_cst_now()
    rule_name, cutoff_time = get_applicable_cutoff(dt)
    is_locked = dt.time() >= cutoff_time

    # Calculate remaining seconds until cutoff
    time_remaining: Optional[int] = None
    if not is_locked:
        cutoff_dt = dt.replace(
            hour=cutoff_time.hour,
            minute=cutoff_time.minute,
            second=0,
            microsecond=0,
        )
        delta = cutoff_dt - dt
        time_remaining = max(0, int(delta.total_seconds()))

    return CutoffStatusSchema(
        is_locked=is_locked,
        cutoff_time=f"{cutoff_time.strftime('%I:%M %p')} CST ({rule_name})",
        current_time=dt.strftime("%I:%M %p CST"),
        is_fomc_day=is_fomc_day(dt),
        is_friday=is_friday(dt),
        time_remaining_seconds=time_remaining,
    )


def enforce_entry_cutoff(dt: Optional[datetime] = None) -> None:
    """
    Enforce the entry cutoff. Raises CutoffExceededError if past cutoff.
    Called by API endpoints that transition status to CONFIRMED.
    """
    from app.core.exceptions import CutoffExceededError

    dt = dt or get_cst_now()
    if is_past_cutoff(dt):
        _, cutoff_time = get_applicable_cutoff(dt)
        raise CutoffExceededError(
            cutoff_time=cutoff_time.strftime("%I:%M %p"),
            current_time=dt.strftime("%I:%M %p"),
        )
