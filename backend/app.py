"""FastAPI server for AI Classroom Setup Agent."""

from __future__ import annotations

import copy
import os
import shutil
import threading
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

import google_auth

load_dotenv()


# ---------------------------------------------------------------------------
# Lifespan: start / stop the scheduler alongside the FastAPI server
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    """Start the background scheduler when the server boots; stop it on shutdown."""
    import scheduler as sched  # noqa: PLC0415
    sched.start()
    yield
    sched.stop()


app = FastAPI(title="AI Classroom Setup Agent API", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Session cookie (used to remember each visitor's signed-in Google account)
# ---------------------------------------------------------------------------
# Render sets RENDER=true on its services; locally this is unset so cookies
# work over plain http://localhost. In production the cookie must be
# SameSite=None + Secure for the cross-site Vercel <-> Render setup.
_in_production = os.getenv("RENDER", "").lower() == "true" or os.getenv("COOKIE_SECURE", "").lower() in ("1", "true", "yes")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-only-insecure-secret-change-me"),
    same_site="none" if _in_production else "lax",
    https_only=_in_production,
)

# Allow the local dev frontend plus any deployed Vercel frontend(s).
# Set FRONTEND_URL (and optionally FRONTEND_URLS, comma-separated, for previews)
# in the Render environment to your Vercel domain(s), e.g.
#   FRONTEND_URL=https://your-app.vercel.app
_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra_origins = [
    o.strip()
    for o in (os.getenv("FRONTEND_URL", "") + "," + os.getenv("FRONTEND_URLS", "")).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Global run state (single-user assumption, sufficient for a class project)
# ---------------------------------------------------------------------------

STEP_IDS = [
    "extract",
    "ai_process",
    "conflicts",
    "zoom",
    "calendar",
    "email",
    "report",
]

STEP_LABELS = {
    "extract": "Extracting documents",
    "ai_process": "AI Processing with Gemini",
    "conflicts": "Checking schedule conflicts",
    "zoom": "Creating Zoom meetings",
    "calendar": "Creating Google Calendar events",
    "email": "Sending invitation emails",
    "report": "Generating report",
}

_lock = threading.Lock()
_run_state: dict[str, Any] = {
    "status": "idle",   # idle | running | done | error
    "steps": [],
    "report": None,
}


def _fresh_steps() -> list[dict[str, Any]]:
    return [
        {"id": sid, "label": STEP_LABELS[sid], "status": "pending", "message": ""}
        for sid in STEP_IDS
    ]


def _step_index(step_id: str) -> int:
    return STEP_IDS.index(step_id)


def _set_step(step_id: str, status: str, message: str = "") -> None:
    with _lock:
        for step in _run_state["steps"]:
            if step["id"] == step_id:
                step["status"] = status
                step["message"] = message
                break


def _set_status(status: str) -> None:
    with _lock:
        _run_state["status"] = status


def _set_report(report: dict[str, Any]) -> None:
    with _lock:
        _run_state["report"] = report


# ---------------------------------------------------------------------------
# Background pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(google_creds_dict: dict[str, Any] | None = None) -> None:
    """Run the pipeline.

    ``google_creds_dict`` is the signed-in user's Google OAuth credentials
    (as stored in their session), if any. When present, Calendar events and
    Gmail invitations are created/sent as that user instead of the deployer's
    local token.json account.
    """
    from ai_processor import process_documents_text
    from calendar_client import create_event
    from conflict_checker import find_schedule_conflicts
    from extractor import extract_text_auto
    from gmail_client import send_invitation
    from reporter import generate_report
    from zoom_client import create_meeting

    errors: list[str] = []
    events_created: list[dict[str, Any]] = []
    emails_sent = 0
    conflicts: list[str] = []

    skip = os.getenv("SKIP_EXTERNAL_APIS", "").lower() in ("1", "true", "yes")

    google_creds = None
    if google_creds_dict:
        try:
            google_creds, _ = google_auth.get_valid_credentials(google_creds_dict)
        except Exception as e:
            errors.append(f"Google sign-in: {e}")

    try:
        # Step 1 — Extract
        _set_step("extract", "running")
        paths = sorted(
            p for p in UPLOADS_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in (".pdf", ".docx", ".csv")
        )
        if not paths:
            raise FileNotFoundError("No supported files found in uploads/")
        chunks: list[str] = []
        for p in paths:
            text = extract_text_auto(p)
            chunks.append(f"=== File: {p.name} ===\n{text}")
        combined_text = "\n\n".join(chunks).strip()
        _set_step("extract", "done", f"Read {len(paths)} file(s), {len(combined_text)} chars")

        # Step 2 — AI
        _set_step("ai_process", "running")
        data = process_documents_text(combined_text)
        n_courses = len(data.get("courses", []))
        n_schedule = len(data.get("schedule", []))
        n_students = len(data.get("students", []))
        _set_step(
            "ai_process", "done",
            f"Found {n_courses} course(s), {n_schedule} session(s), {n_students} student(s)",
        )

        # Step 3 — Conflicts
        _set_step("conflicts", "running")
        conflicts = find_schedule_conflicts(data.get("schedule", []))
        if conflicts:
            _set_step("conflicts", "done", f"{len(conflicts)} overlap(s) detected")
        else:
            _set_step("conflicts", "done", "No overlapping sessions")

        schedule_items: list[dict[str, Any]] = list(data.get("schedule", []))

        # Step 4 — Zoom
        _set_step("zoom", "running")
        zoom_urls: dict[str, str] = {}
        for item in schedule_items:
            course_name = str(item.get("course_name", "Class"))
            start_time = str(item.get("start_time", "")).strip()
            try:
                duration_minutes = int(item.get("duration_minutes", 60))
            except (TypeError, ValueError):
                duration_minutes = 60
            if not start_time:
                errors.append(f"Missing start_time for {course_name!r}")
                continue
            try:
                if skip:
                    zoom_url = "https://example.com/zoom-skipped"
                else:
                    zoom_url = create_meeting(course_name, start_time, duration_minutes)
                zoom_urls[course_name] = zoom_url
            except Exception as e:
                msg = f"Zoom for {course_name!r}: {e}"
                errors.append(msg)
        _set_step("zoom", "done", f"Created {len(zoom_urls)} meeting(s)")

        # Step 5 — Calendar
        _set_step("calendar", "running")
        for item in schedule_items:
            course_name = str(item.get("course_name", "Class"))
            start_time = str(item.get("start_time", "")).strip()
            try:
                duration_minutes = int(item.get("duration_minutes", 60))
            except (TypeError, ValueError):
                duration_minutes = 60
            zoom_url = zoom_urls.get(course_name, "")
            if not start_time:
                continue
            try:
                if skip:
                    cal_link = "https://example.com/calendar-skipped"
                else:
                    cal_link = create_event(
                        course_name, start_time, duration_minutes, zoom_url,
                        credentials=google_creds,
                    )
                events_created.append({
                    "course_name": course_name,
                    "start_time": start_time,
                    "duration_minutes": duration_minutes,
                    "zoom_url": zoom_url,
                    "calendar_link": cal_link,
                })
            except Exception as e:
                errors.append(f"Calendar for {course_name!r}: {e}")
        _set_step("calendar", "done", f"Created {len(events_created)} event(s)")

        # Step 6 — Email
        _set_step("email", "running")
        students = data.get("students", [])
        sched_lines = [
            f"{ev['course_name']} — {ev['start_time']} ({ev['duration_minutes']} min)"
            for ev in events_created
        ]
        sched_text = "\n".join(sched_lines) or "Schedule details TBD"
        primary_zoom = next((ev["zoom_url"] for ev in events_created if ev.get("zoom_url")), "")
        course_label = (
            schedule_items[0].get("course_name", "Your upcoming classes")
            if len(schedule_items) == 1
            else "Your upcoming classes"
        )
        for student in students:
            name = str(student.get("name", "Student")).strip()
            email_addr = str(student.get("email", "")).strip()
            if not email_addr:
                errors.append(f"Student missing email: {student!r}")
                continue
            try:
                if skip:
                    emails_sent += 1
                else:
                    send_invitation(
                        name, email_addr, course_label, sched_text, primary_zoom,
                        credentials=google_creds,
                    )
                    emails_sent += 1
            except Exception as e:
                errors.append(f"Email to {email_addr}: {e}")
        _set_step("email", "done", f"Sent {emails_sent} invitation(s)")

        # Step 7 — Report
        _set_step("report", "running")
        generate_report(events_created, emails_sent, conflicts, errors)
        _set_step("report", "done", "Report saved to outputs/report.txt")

        _set_report({
            "events_created": events_created,
            "emails_sent": emails_sent,
            "conflicts": conflicts,
            "errors": errors,
        })
        _set_status("done")

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        errors.append(err_msg)
        traceback.print_exc()
        # Mark the currently-running step as error
        with _lock:
            for step in _run_state["steps"]:
                if step["status"] == "running":
                    step["status"] = "error"
                    step["message"] = err_msg
        _set_report({
            "events_created": events_created,
            "emails_sent": emails_sent,
            "conflicts": conflicts,
            "errors": errors,
        })
        _set_status("error")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_files(
    schedule: UploadFile = File(None),
    courses: UploadFile = File(None),
    students: UploadFile = File(None),
) -> dict[str, Any]:
    """Save uploaded files to uploads/. Existing files with the same name are replaced."""
    saved: list[str] = []
    for upload in (schedule, courses, students):
        if upload is None or not upload.filename:
            continue
        dest = UPLOADS_DIR / upload.filename
        with dest.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        saved.append(upload.filename)

    return {"saved": saved, "total": len(saved)}


@app.post("/api/run")
def start_run(request: Request) -> dict[str, str]:
    """Start the automation pipeline in a background thread.

    If the caller is signed in with Google (see /api/auth/*), Calendar
    events and Gmail invitations are created/sent as that user.
    """
    with _lock:
        if _run_state["status"] == "running":
            return {"message": "Already running"}
        _run_state["status"] = "running"
        _run_state["steps"] = _fresh_steps()
        _run_state["report"] = None

    google_creds_dict = request.session.get("google_credentials")
    t = threading.Thread(target=_run_pipeline, args=(google_creds_dict,), daemon=True)
    t.start()
    return {"message": "Pipeline started"}


# ---------------------------------------------------------------------------
# Google sign-in (per-user OAuth for Calendar + Gmail)
# ---------------------------------------------------------------------------

@app.get("/api/auth/google/login")
def google_login(request: Request):
    """Redirect the browser to Google's OAuth consent screen."""
    if not google_auth.is_configured():
        return {"error": "Google OAuth is not configured on this server."}
    auth_url, state, code_verifier = google_auth.get_authorization_url()
    request.session["oauth_state"] = state
    request.session["oauth_code_verifier"] = code_verifier
    return RedirectResponse(auth_url)


@app.get("/api/auth/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    """Handle the redirect back from Google, then send the user back to the frontend."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

    if error:
        return RedirectResponse(f"{frontend_url}/?google_error={error}")
    if not code:
        return RedirectResponse(f"{frontend_url}/?google_error=missing_code")

    expected_state = request.session.pop("oauth_state", None)
    code_verifier = request.session.pop("oauth_code_verifier", None)
    if expected_state and state != expected_state:
        return RedirectResponse(f"{frontend_url}/?google_error=state_mismatch")

    try:
        creds = google_auth.exchange_code(code, state=state, code_verifier=code_verifier)
        request.session["google_credentials"] = google_auth.credentials_to_dict(creds)
        request.session["google_email"] = google_auth.fetch_user_email(creds)
    except Exception as e:
        # Log the full detail server-side (visible in Render logs) — the
        # exception class name alone (e.g. "InvalidGrantError") isn't enough
        # to diagnose the real cause.
        traceback.print_exc()
        if "google_credentials" in request.session:
            # A previous request on this same session already completed the
            # exchange successfully (e.g. a duplicate/retried callback after
            # a slow cold-start) — treat this as already signed in.
            return RedirectResponse(f"{frontend_url}/?google=connected")
        from urllib.parse import quote  # noqa: PLC0415
        detail = quote(f"{type(e).__name__}: {e}"[:200])
        return RedirectResponse(f"{frontend_url}/?google_error={detail}")

    return RedirectResponse(f"{frontend_url}/?google=connected")


@app.get("/api/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    """Tell the frontend whether the current visitor is signed in with Google."""
    connected = "google_credentials" in request.session
    return {
        "configured": google_auth.is_configured(),
        "connected": connected,
        "email": request.session.get("google_email") if connected else None,
    }


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> dict[str, str]:
    """Forget the current visitor's Google sign-in."""
    request.session.pop("google_credentials", None)
    request.session.pop("google_email", None)
    return {"message": "Signed out"}


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    """Return current pipeline status and step list."""
    with _lock:
        return copy.deepcopy(_run_state)


@app.get("/api/report")
def get_report() -> dict[str, Any]:
    """Return the final report once the pipeline has completed."""
    with _lock:
        if _run_state["report"] is None:
            return {"error": "No report available yet"}
        return copy.deepcopy(_run_state["report"])


@app.post("/api/reset")
def reset() -> dict[str, str]:
    """Reset state so a new run can be started."""
    with _lock:
        _run_state["status"] = "idle"
        _run_state["steps"] = []
        _run_state["report"] = None
    return {"message": "Reset OK"}


# ---------------------------------------------------------------------------
# Scheduler endpoints
# ---------------------------------------------------------------------------

@app.post("/api/trigger-now")
def trigger_now() -> dict[str, str]:
    """
    Immediately fire the automation pipeline via the scheduler.
    The pipeline runs in a background thread; this endpoint returns at once.
    """
    import scheduler as sched  # noqa: PLC0415
    return sched.trigger_now(reason="manual-api")


@app.get("/api/scheduler-status")
def scheduler_status() -> dict[str, Any]:
    """Return current scheduler configuration and whether threads are alive."""
    import scheduler as sched  # noqa: PLC0415
    cfg = sched.get_config()
    threads_alive = [t.name for t in sched._threads if t.is_alive()]
    return {
        **cfg,
        "active_threads": threads_alive,
        "pipeline_running": sched._is_running,
        "recent_log": sched.tail_log(10),
    }


@app.post("/api/scheduler-config")
def update_scheduler_config(body: dict[str, Any]) -> dict[str, Any]:
    """
    Update scheduler configuration at runtime. Accepted fields:
      enabled (bool), schedule_time (HH:MM str), schedule_days (list[int] 0-6), poll_interval (int seconds)
    """
    import scheduler as sched  # noqa: PLC0415
    try:
        new_cfg = sched.update_config(
            enabled=body.get("enabled"),
            schedule_time=body.get("schedule_time"),
            schedule_dates=body.get("schedule_dates"),
            poll_interval=body.get("poll_interval"),
        )
        return {"ok": True, "config": new_cfg}
    except (ValueError, TypeError) as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(e))
