"""Orchestrate extraction, AI parsing, conflicts, Zoom, Calendar, Gmail, and reporting."""

from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from backend.ai_processor import process_documents_text
from backend.calendar_client import create_event
from backend.conflict_checker import find_schedule_conflicts
from backend.extractor import extract_text_auto
from backend.gmail_client import send_invitation
from backend.reporter import generate_report
from backend.zoom_client import create_meeting

load_dotenv()

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"


def _skip_external() -> bool:
    return os.getenv("SKIP_EXTERNAL_APIS", "").lower() in ("1", "true", "yes")


def _collect_upload_text() -> str:
    if not UPLOADS_DIR.is_dir():
        raise FileNotFoundError(f"Missing uploads directory: {UPLOADS_DIR}")

    chunks: list[str] = []
    paths = sorted(p for p in UPLOADS_DIR.iterdir() if p.is_file() and not p.name.startswith("."))
    if not paths:
        raise ValueError(f"No input files in {UPLOADS_DIR}")

    for path in paths:
        suffix = path.suffix.lower()
        if suffix not in (".pdf", ".docx", ".csv"):
            print(f"  Skipping unsupported file: {path.name}")
            continue
        print(f"  Reading {path.name} ...")
        text = extract_text_auto(path)
        chunks.append(f"=== File: {path.name} ===\n{text}")

    combined = "\n\n".join(chunks).strip()
    if not combined:
        raise ValueError("No text extracted from supported files in uploads/")
    return combined


def _format_invitation_schedule(events: list[dict[str, Any]]) -> tuple[str, str]:
    """Build schedule text and a primary Zoom URL for the email template."""
    lines: list[str] = []
    primary_zoom = ""
    for ev in events:
        course = ev.get("course_name", "Class")
        start = ev.get("start_time", "")
        dur = ev.get("duration_minutes", 60)
        zu = ev.get("zoom_url", "")
        if not primary_zoom and zu:
            primary_zoom = zu
        lines.append(f"{course} — starts {start} — duration {dur} min — Zoom: {zu}")
    return "\n".join(lines), primary_zoom


def run() -> None:
    errors: list[str] = []
    events_created: list[dict[str, Any]] = []
    emails_sent = 0
    conflicts: list[str] = []

    try:
        print("Step 1/7: Extracting text from uploads/ ...")
        combined_text = _collect_upload_text()
        print(f"  Extracted {len(combined_text)} characters.\n")

        if os.getenv("SKIP_GEMINI", "").lower() in ("1", "true", "yes"):
            print("Step 2/7: Structuring data (SKIP_GEMINI — CSV parse) ...")
        else:
            print("Step 2/7: Processing with Gemini ...")
        data = process_documents_text(combined_text)
        print(
            f"  Courses: {len(data.get('courses', []))}, "
            f"schedule slots: {len(data.get('schedule', []))}, "
            f"students: {len(data.get('students', []))}.\n"
        )

        print("Step 3/7: Checking for schedule conflicts ...")
        conflicts = find_schedule_conflicts(data.get("schedule", []))
        if conflicts:
            print(f"  Found {len(conflicts)} potential overlap(s).")
        else:
            print("  No overlapping slots detected.")
        print()

        skip = _skip_external()
        if skip:
            print("  SKIP_EXTERNAL_APIS is set — skipping Zoom, Calendar, Gmail API calls.\n")

        schedule_items: list[dict[str, Any]] = list(data.get("schedule", []))

        print("Step 4/7: Creating Zoom meetings ...")
        print("Step 5/7: Creating Google Calendar events ...")
        for item in schedule_items:
            course_name = str(item.get("course_name", "Class"))
            start_time = str(item.get("start_time", "")).strip()
            try:
                duration_minutes = int(item.get("duration_minutes", 60))
            except (TypeError, ValueError):
                duration_minutes = 60

            if not start_time:
                errors.append(f"Skipping schedule row (missing start_time): {item!r}")
                continue

            try:
                if skip:
                    zoom_url = "https://example.com/zoom-skipped"
                    cal_link = "https://example.com/calendar-skipped"
                else:
                    zoom_url = create_meeting(course_name, start_time, duration_minutes)
                    cal_link = create_event(course_name, start_time, duration_minutes, zoom_url)
                events_created.append(
                    {
                        "course_name": course_name,
                        "start_time": start_time,
                        "duration_minutes": duration_minutes,
                        "zoom_url": zoom_url,
                        "calendar_link": cal_link,
                    }
                )
                print(f"  OK: {course_name}")
            except Exception as e:
                msg = f"Zoom/Calendar for {course_name!r}: {e}"
                errors.append(msg)
                print(f"  ERROR: {msg}")

        print()

        print("Step 6/7: Sending Gmail invitations ...")
        students = data.get("students", [])
        sched_text, primary_zoom = _format_invitation_schedule(events_created)

        for student in students:
            name = str(student.get("name", "Student")).strip()
            email_addr = str(student.get("email", "")).strip()
            if not email_addr:
                errors.append(f"Student missing email, skipped: {student!r}")
                continue
            course_label = "Your upcoming classes"
            if len(schedule_items) == 1:
                course_label = str(schedule_items[0].get("course_name", course_label))

            try:
                if skip:
                    emails_sent += 1
                    print(f"  (skip) Would email {email_addr}")
                else:
                    send_invitation(
                        name,
                        email_addr,
                        course_label,
                        sched_text or "Schedule details to be announced.",
                        primary_zoom or "https://zoom.us",
                    )
                    emails_sent += 1
                    print(f"  Sent to {email_addr}")
            except Exception as e:
                msg = f"Gmail to {email_addr}: {e}"
                errors.append(msg)
                print(f"  ERROR: {msg}")

        print()

        print("Step 7/7: Generating report ...")
        generate_report(events_created, emails_sent, conflicts, errors)

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        errors.append(err_msg)
        print(f"\nFatal error: {err_msg}\n")
        traceback.print_exc()
        generate_report(events_created, emails_sent, conflicts, errors)


if __name__ == "__main__":
    run()
