"""Detect overlapping time slots in an AI-extracted schedule."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _parse_start(dt_str: str) -> datetime | None:
    """Parse ISO 8601 start_time; return timezone-aware UTC or None."""
    if not dt_str or not str(dt_str).strip():
        return None
    s = str(dt_str).strip()
    # Handle 'Z' suffix
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def find_schedule_conflicts(schedule: list[dict[str, Any]]) -> list[str]:
    """
    Detect overlapping intervals (same instant counts as overlap).

    Each schedule item should have: course_name, start_time, duration_minutes.

    Returns a list of human-readable conflict warnings (empty if none).
    """
    if not schedule:
        return []

    intervals: list[tuple[datetime, datetime, str]] = []
    for item in schedule:
        name = str(item.get("course_name", "Unknown"))
        start = _parse_start(item.get("start_time", ""))
        if start is None:
            continue
        try:
            duration = int(item.get("duration_minutes", 60))
        except (TypeError, ValueError):
            duration = 60
        if duration < 0:
            duration = 0
        end = start + timedelta(minutes=duration)
        intervals.append((start, end, name))

    warnings: list[str] = []
    for i, (s1, e1, n1) in enumerate(intervals):
        for j, (s2, e2, n2) in enumerate(intervals):
            if j <= i:
                continue
            # Overlap if ranges intersect (closed-open convention: [s1,e1) vs [s2,e2) — use strict overlap for touching endpoints)
            if s1 < e2 and s2 < e1:
                warnings.append(
                    f"Overlap: {n1!r} ({s1.isoformat()}–{e1.isoformat()}) vs "
                    f"{n2!r} ({s2.isoformat()}–{e2.isoformat()})"
                )
    return warnings
