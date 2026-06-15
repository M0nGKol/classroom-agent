"""
Per-user Google OAuth (web flow) for Calendar + Gmail.

Unlike calendar_client.py / gmail_client.py's file-based `token.json` (which
authorizes a single Google account for the scheduled/CLI pipeline), this
module lets each visitor of the deployed app sign in with *their own* Google
account so that "Run Now" creates events / sends mail as them.

Required environment variables (set these in Render):
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REDIRECT_URI   e.g. https://your-backend.onrender.com/api/auth/google/callback
    SESSION_SECRET        any long random string (signs the session cookie)

These come from a *Web application* OAuth client in Google Cloud Console
(separate from the "Desktop app" client used for credentials.json). See
GOOGLE_OAUTH_SETUP.md for step-by-step setup.
"""

from __future__ import annotations

import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

# Same scopes as calendar_client / gmail_client so one sign-in covers both APIs.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def is_configured() -> bool:
    """True if the web OAuth client env vars are present."""
    return bool(
        os.environ.get("GOOGLE_CLIENT_ID")
        and os.environ.get("GOOGLE_CLIENT_SECRET")
        and os.environ.get("GOOGLE_REDIRECT_URI")
    )


def _client_config() -> dict[str, Any]:
    return {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _redirect_uri() -> str:
    return os.environ["GOOGLE_REDIRECT_URI"]


def build_flow(state: str | None = None) -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        state=state,
        redirect_uri=_redirect_uri(),
    )


def get_authorization_url() -> tuple[str, str]:
    """Return (authorization_url, state) to redirect the user to Google."""
    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


def exchange_code(code: str, state: str | None = None) -> Credentials:
    """Exchange an authorization code (from the OAuth callback) for credentials."""
    flow = build_flow(state=state)
    flow.fetch_token(code=code)
    return flow.credentials


def credentials_to_dict(creds: Credentials) -> dict[str, Any]:
    """Serialize credentials for storage in the session cookie."""
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }


def credentials_from_dict(data: dict[str, Any]) -> Credentials:
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )


def get_valid_credentials(data: dict[str, Any]) -> tuple[Credentials, dict[str, Any]]:
    """
    Build credentials from a stored dict, refreshing the access token if
    expired. Returns (credentials, possibly-updated dict to re-save in the
    session).
    """
    creds = credentials_from_dict(data)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            data = credentials_to_dict(creds)
        else:
            raise RuntimeError("Google session expired — please sign in again.")
    return creds, data


def fetch_user_email(creds: Credentials) -> str | None:
    """Best-effort fetch of the signed-in user's email for display."""
    try:
        from googleapiclient.discovery import build  # noqa: PLC0415

        service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        return service.userinfo().get().execute().get("email")
    except Exception:
        return None
