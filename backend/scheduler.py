"""
Scheduler — runs the classroom setup pipeline automatically.

Two triggers:
  1. Daily at a configured time (env: SCHEDULE_TIME, default "07:00", Asia/Phnom_Penh).
     Can be restricted to specific days of the week (SCHEDULE_DAYS, default all 7).
  2. File-watcher: polls uploads/ every POLL_INTERVAL_SECONDS (default 60 s);
     if new or modified files arrive, the pipeline is triggered immediately.

Runtime config can be updated live via update_config() — no restart needed.

Usage (standalone):
    python -m backend.scheduler
    SCHEDULE_TIME=08:30 python -m backend.scheduler

Usage (embedded in FastAPI via app.py lifespan):
    The app.py lifespan already imports and starts the scheduler automatically.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Configuration (mutable at runtime via update_config)
# ---------------------------------------------------------------------------

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
LOGS_DIR    = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Protected by _config_lock so updates are thread-safe
_config_lock = threading.Lock()

_config: dict = {
    "enabled":          True,
    "schedule_time":    os.environ.get("SCHEDULE_TIME", "07:00").strip(),
    # Specific calendar dates to run on, e.g. ["2026-06-15", "2026-09-01"]
    # Empty list = no scheduled dates (use Trigger Now or file-watcher only)
    "schedule_dates":   [],
    "poll_interval":    int(os.environ.get("POLL_INTERVAL_SECONDS", "60")),
    "timezone":         os.environ.get("SCHEDULE_TIMEZONE", "Asia/Phnom_Penh"),
}


def get_config() -> dict:
    with _config_lock:
        return dict(_config)


def update_config(
    *,
    enabled: bool | None = None,
    schedule_time: str | None = None,
    schedule_dates: list[str] | None = None,
    poll_interval: int | None = None,
) -> dict:
    """
    Update scheduler config at runtime. Only provided keys are changed.
    Returns the new config dict.
    """
    with _config_lock:
        if enabled is not None:
            _config["enabled"] = bool(enabled)
        if schedule_time is not None:
            _parse_hhmm(schedule_time)           # raises ValueError on bad format
            _config["schedule_time"] = schedule_time.strip()
        if schedule_dates is not None:
            # Validate each date is YYYY-MM-DD and is not in the past
            today = datetime.now().date()
            validated: list[str] = []
            for d in schedule_dates:
                try:
                    parsed = datetime.strptime(str(d).strip(), "%Y-%m-%d").date()
                    validated.append(str(parsed))  # normalise format
                except ValueError:
                    raise ValueError(f"Invalid date format '{d}', expected YYYY-MM-DD")
            _config["schedule_dates"] = sorted(set(validated))
        if poll_interval is not None:
            _config["poll_interval"] = max(10, int(poll_interval))
        logger.info("Scheduler config updated: %s", dict(_config))
        return dict(_config)


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

_pipeline_lock = threading.Lock()
_is_running    = False


def _run_pipeline_once(trigger: str = "manual") -> None:
    """Execute the pipeline exactly once. Skips if already running."""
    global _is_running
    with _pipeline_lock:
        if _is_running:
            logger.info("Scheduler: pipeline already running — skipping '%s'.", trigger)
            return
        _is_running = True

    try:
        logger.info("Scheduler: starting pipeline (trigger='%s') ...", trigger)
        _log_event(f"RUN STARTED  trigger={trigger}")

        try:
            from main import run as pipeline_run          # running inside backend/
        except ModuleNotFoundError:
            from backend.main import run as pipeline_run  # running from project root

        pipeline_run()
        logger.info("Scheduler: pipeline done (trigger='%s').", trigger)
        _log_event(f"RUN FINISHED trigger={trigger} status=SUCCESS")
    except Exception as exc:
        logger.exception("Scheduler: pipeline failed (trigger='%s'): %s", trigger, exc)
        _log_event(f"RUN FINISHED trigger={trigger} status=FAILED: {exc}")
    finally:
        with _pipeline_lock:
            _is_running = False


def _log_event(msg: str) -> None:
    entry = f"[{datetime.now().isoformat()}] {msg}\n"
    with open(LOGS_DIR / "scheduler.log", "a", encoding="utf-8") as f:
        f.write(entry)


def tail_log(n: int = 20) -> list[str]:
    """Return the last n lines of scheduler.log (newest last)."""
    log_path = LOGS_DIR / "scheduler.log"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return lines[-n:]


# ---------------------------------------------------------------------------
# Trigger 1 — Daily time-based trigger
# ---------------------------------------------------------------------------

def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' → (hour, minute). Raises ValueError on bad input."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format '{time_str}', expected HH:MM")
    return int(parts[0]), int(parts[1])


def _seconds_until(hour: int, minute: int) -> float:
    """Seconds from now until next HH:MM (today or tomorrow)."""
    now    = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _daily_trigger_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        cfg = get_config()
        if not cfg["enabled"] or not cfg["schedule_dates"]:
            # Nothing scheduled — sleep and re-check every 30 s
            _interruptible_sleep(30, stop_event)
            continue

        hour, minute = _parse_hhmm(cfg["schedule_time"])
        wait_secs = _seconds_until(hour, minute)
        logger.info(
            "Scheduler: next check at %02d:%02d %s (in %.0f s). Dates: %s",
            hour, minute, cfg["timezone"], wait_secs, cfg["schedule_dates"],
        )

        # Sleep until trigger time, waking every second to check stop/config changes
        _interruptible_sleep(wait_secs, stop_event)
        if stop_event.is_set():
            break

        # Re-read config — may have changed while we slept
        cfg = get_config()
        if not cfg["enabled"]:
            _interruptible_sleep(61, stop_event)
            continue

        # Check if today's date is in the scheduled dates
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str not in cfg["schedule_dates"]:
            logger.info(
                "Scheduler: today (%s) not in scheduled dates %s — skipping.",
                today_str, cfg["schedule_dates"],
            )
            _interruptible_sleep(61, stop_event)
            continue

        logger.info("Scheduler: today %s is a scheduled date — firing pipeline.", today_str)
        threading.Thread(
            target=_run_pipeline_once, args=("daily-schedule",), daemon=True
        ).start()

        # Remove the date that just fired so it doesn't re-trigger
        with _config_lock:
            remaining = [d for d in _config["schedule_dates"] if d != today_str]
            _config["schedule_dates"] = remaining
            logger.info("Scheduler: removed fired date %s. Remaining: %s", today_str, remaining)

        _interruptible_sleep(61, stop_event)


# ---------------------------------------------------------------------------
# Trigger 2 — File-watcher
# ---------------------------------------------------------------------------

def _snapshot_uploads() -> dict[str, float]:
    if not UPLOADS_DIR.is_dir():
        return {}
    return {
        p.name: p.stat().st_mtime
        for p in UPLOADS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in (".pdf", ".docx", ".csv")
    }


def _file_watcher_loop(stop_event: threading.Event) -> None:
    logger.info("Scheduler: file-watcher started.")
    previous = _snapshot_uploads()

    while not stop_event.is_set():
        interval = get_config()["poll_interval"]
        _interruptible_sleep(interval, stop_event)
        if stop_event.is_set():
            break

        current   = _snapshot_uploads()
        new_files = set(current) - set(previous)
        changed   = {n for n in current if n in previous and current[n] != previous[n]}

        if new_files or changed:
            detected = sorted(new_files | changed)
            logger.info("Scheduler: file-watcher detected %s — triggering.", detected)
            previous = current
            threading.Thread(
                target=_run_pipeline_once, args=("file-watcher",), daemon=True
            ).start()
        else:
            previous = current


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _interruptible_sleep(seconds: float, stop_event: threading.Event) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if stop_event.is_set():
            return
        time.sleep(min(1.0, deadline - time.monotonic()))


# ---------------------------------------------------------------------------
# Public API — start / stop / trigger
# ---------------------------------------------------------------------------

_stop_event: threading.Event   = threading.Event()
_threads:    list[threading.Thread] = []


def start() -> None:
    global _stop_event, _threads
    if _threads and any(t.is_alive() for t in _threads):
        logger.info("Scheduler: already running.")
        return

    _stop_event = threading.Event()
    daily   = threading.Thread(target=_daily_trigger_loop,   args=(_stop_event,), daemon=True, name="scheduler-daily")
    watcher = threading.Thread(target=_file_watcher_loop,    args=(_stop_event,), daemon=True, name="scheduler-watcher")
    _threads = [daily, watcher]
    for t in _threads:
        t.start()
    logger.info("Scheduler: started (daily + file-watcher).")


def stop() -> None:
    _stop_event.set()
    logger.info("Scheduler: stop signal sent.")


def trigger_now(reason: str = "manual-api") -> dict[str, str]:
    threading.Thread(target=_run_pipeline_once, args=(reason,), daemon=True).start()
    return {"message": f"Pipeline triggered (reason='{reason}')"}


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = get_config()
    logger.info("=" * 60)
    logger.info("AI Classroom Agent — Scheduler")
    logger.info("  Daily : %s  days=%s  tz=%s", cfg["schedule_time"], cfg["schedule_days"], cfg["timezone"])
    logger.info("  Watch : every %d s → uploads/", cfg["poll_interval"])
    logger.info("  Press Ctrl+C to stop.")
    logger.info("=" * 60)
    start()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        stop()
