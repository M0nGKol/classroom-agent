"""Gmail API: send HTML invitation emails."""

from __future__ import annotations

import base64
import html
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# Same scopes as calendar_client so `credentials.json` + `token.json` work for both.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]
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


def send_invitation(
    student_name: str,
    student_email: str,
    course_name: str,
    schedule: str,
    zoom_url: str,
) -> None:
    """
    Send a friendly HTML email with class details.

    ``schedule`` may be a single session description or a full multi-line schedule.
    """
    creds = _get_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    safe_name = html.escape(student_name)
    safe_course = html.escape(course_name)
    safe_schedule = html.escape(schedule).replace("\n", "<br/>")
    safe_url = html.escape(zoom_url, quote=True)
    body_html = f"""\
<html>
<body style="font-family: system-ui, sans-serif; line-height: 1.5;">
  <p>Hi {safe_name},</p>
  <p>You are invited to the following class:</p>
  <p><strong>{safe_course}</strong></p>
  <p><strong>When / details</strong><br/>{safe_schedule}</p>
  <p><strong>Zoom</strong><br/>
     <a href="{safe_url}">{html.escape(zoom_url)}</a></p>
  <p>See you there!</p>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["to"] = student_email
    user_email = _get_sender_profile_email(service)
    msg["from"] = user_email
    msg["subject"] = f"Invitation: {course_name}"
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except HttpError as e:
        raise RuntimeError(f"Gmail API error: {e}") from e


def _get_sender_profile_email(service) -> str:
    """Resolve authenticated Gmail address for the From header."""
    try:
        prof = service.users().getProfile(userId="me").execute()
        return prof.get("emailAddress") or os.environ.get("GMAIL_SENDER_EMAIL", "me")
    except Exception:
        return os.environ.get("GMAIL_SENDER_EMAIL", "me")
