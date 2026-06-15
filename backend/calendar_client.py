"""Google Calendar: create events with Asia/Phnom_Penh timezone."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# Combined with Gmail so one `token.json` authorizes both APIs.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]
TIMEZONE = "Asia/Phnom_Penh"
PROJECT_ROOT = Path(__file__).resolve().parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"


def _get_credentials() -> Credentials:
    creds: Credentials | None = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE.name}; add OAuth client JSON from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def create_event(
    course_name: str,
    start_time: str,
    duration_minutes: int,
    zoom_url: str,
) -> str:
    """
    Create a calendar event and return an HTML link to the event.

    ``start_time`` is an RFC3339 / ISO 8601 datetime string.
    ``zoom_url`` is embedded in the event description.
    """
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    description = (
        f"Course: {course_name}\n\n"
        f"Join Zoom: {zoom_url}\n"
    )

    body = {
        "summary": course_name,
        "description": description,
        "start": {"dateTime": start_time, "timeZone": TIMEZONE},
        "end": {
            "dateTime": _end_datetime_iso(start_time, int(duration_minutes)),
            "timeZone": TIMEZONE,
        },
    }

    try:
        created = (
            service.events()
            .insert(calendarId="primary", body=body)
            .execute()
        )
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}") from e

    link = created.get("htmlLink") or created.get("hangoutLink") or ""
    return link


def _end_datetime_iso(start_iso: str, duration_minutes: int) -> str:
    """Compute end time ISO string in the same offset style as start (best-effort)."""
    from datetime import datetime, timedelta, timezone

    s = start_iso.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        start = datetime.fromisoformat(s)
    except ValueError:
        return start_iso
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=duration_minutes)
    return end.isoformat()
