"""Print and save a run summary to outputs/report.txt."""

from __future__ import annotations

from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
REPORT_PATH = OUTPUT_DIR / "report.txt"


def generate_report(
    events_created: list[dict[str, Any]],
    emails_sent: int,
    conflicts: list[str],
    errors: list[str],
) -> None:
    """Print a summary and write it to ``outputs/report.txt``."""
    lines: list[str] = []
    lines.append("=== AI Classroom Setup Agent — Run Report ===\n")

    lines.append(f"Calendar events created: {len(events_created)}")
    for ev in events_created:
        course = ev.get("course_name", "?")
        lines.append(f"  - {course}")
        if ev.get("calendar_link"):
            lines.append(f"    Calendar: {ev['calendar_link']}")
        if ev.get("zoom_url"):
            lines.append(f"    Zoom: {ev['zoom_url']}")
    lines.append("")

    lines.append(f"Invitation emails sent: {emails_sent}\n")

    lines.append("Schedule conflicts:")
    if conflicts:
        for c in conflicts:
            lines.append(f"  ! {c}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("Errors:")
    if errors:
        for e in errors:
            lines.append(f"  ! {e}")
    else:
        lines.append("  (none)")

    text = "\n".join(lines) + "\n"
    print(text)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Report saved to {REPORT_PATH}")
