"""Zoom Server-to-Server OAuth: create meetings and return join URLs."""

from __future__ import annotations

import base64
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

_TOKEN_CACHE: dict[str, Any] = {"access_token": None, "expires_at": 0.0}
ZOOM_API_BASE = "https://api.zoom.us/v2"


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _fetch_access_token() -> str:
    account_id = os.environ.get("ZOOM_ACCOUNT_ID")
    client_id = os.environ.get("ZOOM_CLIENT_ID")
    client_secret = os.environ.get("ZOOM_CLIENT_SECRET")
    if not all([account_id, client_id, client_secret]):
        raise ValueError(
            "ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, and ZOOM_CLIENT_SECRET must be set in .env"
        )

    url = "https://zoom.us/oauth/token"
    params = {"grant_type": "account_credentials", "account_id": account_id}
    headers = {"Authorization": _basic_auth_header(client_id, client_secret)}
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.post(url, params=params, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            token = data.get("access_token")
            if not token:
                raise ValueError("Zoom token response missing access_token")
            expires_in = float(data.get("expires_in", 3600))
            _TOKEN_CACHE["access_token"] = token
            _TOKEN_CACHE["expires_at"] = time.time() + expires_in - 60
            return token
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to obtain Zoom access token after retries: {last_err}") from last_err


def _get_access_token() -> str:
    if _TOKEN_CACHE["access_token"] and time.time() < _TOKEN_CACHE["expires_at"]:
        return _TOKEN_CACHE["access_token"]
    return _fetch_access_token()


def create_meeting(topic: str, start_time: str, duration_minutes: int) -> str:
    """
    Create a Zoom meeting scheduled at ``start_time`` (ISO 8601).

    Returns the ``join_url`` for participants.

    Uses ``ZOOM_HOST_EMAIL`` (Zoom user login email) as the meeting host user.
    """
    host = os.environ.get("ZOOM_HOST_EMAIL", "").strip()
    if not host:
        raise ValueError(
            "ZOOM_HOST_EMAIL must be set in .env (Zoom user email to host meetings)"
        )

    user_id = requests.utils.quote(host, safe="")
    url = f"{ZOOM_API_BASE}/users/{user_id}/meetings"

    body: dict[str, Any] = {
        "topic": topic,
        "type": 2,
        "start_time": start_time,
        "duration": int(duration_minutes),
        "timezone": "Asia/Phnom_Penh",
        "settings": {
            "join_before_host": False,
            "waiting_room": True,
        },
    }

    last_err: Exception | None = None
    for attempt in range(3):
        token = _get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(url, json=body, headers=headers, timeout=30)
            if r.status_code == 401:
                _TOKEN_CACHE["access_token"] = None
                _TOKEN_CACHE["expires_at"] = 0.0
                token = _get_access_token()
                headers["Authorization"] = f"Bearer {token}"
                r = requests.post(url, json=body, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            join_url = data.get("join_url")
            if not join_url:
                raise ValueError("Zoom API response missing join_url")
            return join_url
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to create Zoom meeting after retries: {last_err}") from last_err
