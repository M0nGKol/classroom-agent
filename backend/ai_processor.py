"""Use Gemini to turn extracted document text into structured JSON."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _model_name() -> str:
    """Return the configured model name, defaulting to gemini-2.5-flash."""
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()


def _fallback_from_csv_extracted_text(text: str) -> dict[str, Any]:
    """
    When ``SKIP_GEMINI`` is set, parse pipe-separated tables produced by
    :func:`extractor.extract_text_from_csv` inside ``=== File: … ===`` blocks.
    """
    out: dict[str, Any] = {"courses": [], "schedule": [], "students": []}
    pattern = re.compile(
        r"=== File:\s*([^\n]+?)\s*===\s*\n(.*?)(?=\n=== File:|\Z)",
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        fname = m.group(1).strip()
        body = m.group(2).strip()
        if not fname.lower().endswith(".csv"):
            continue
        base = Path(fname).name.lower()
        lines = [ln for ln in body.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        header = [c.strip() for c in lines[0].split("|")]
        for line in lines[1:]:
            vals = [c.strip() for c in line.split("|")]
            if len(vals) < len(header):
                vals.extend([""] * (len(header) - len(vals)))
            row = {header[i]: vals[i] for i in range(len(header))}

            if base == "courses.csv":
                out["courses"].append(
                    {"name": row.get("name", ""), "description": row.get("description", "")}
                )
            elif base == "schedule.csv":
                dm_raw = row.get("duration_minutes", "60")
                try:
                    duration_minutes = int(dm_raw)
                except (TypeError, ValueError):
                    duration_minutes = 60
                out["schedule"].append(
                    {
                        "course_name": row.get("course_name", ""),
                        "start_time": row.get("start_time", ""),
                        "duration_minutes": duration_minutes,
                    }
                )
            elif base == "students.csv":
                out["students"].append(
                    {"name": row.get("name", ""), "email": row.get("email", "")}
                )

    return out


EXTRACTION_PROMPT = """You are extracting structured data from classroom documents (schedule, courses, student lists).

From the text below, extract:
1. courses — each item: name (string), description (string, may be empty)
2. schedule — each item: course_name (string), start_time (ISO 8601 string with timezone offset or Z), duration_minutes (integer)
3. students — each item: name (string), email (string)

Rules:
- If a field is missing, use reasonable defaults: empty string for text, 60 for duration if unknown, infer emails only when clearly present.
- start_time must be parseable ISO 8601 (e.g. 2026-04-20T14:00:00+07:00 or 2026-04-20T07:00:00Z).
- Respond with ONLY valid JSON, no markdown fences, no commentary.

Required JSON shape exactly:
{"courses":[{"name":"","description":""}],"schedule":[{"course_name":"","start_time":"","duration_minutes":0}],"students":[{"name":"","email":""}]}

Documents text:
---
"""


def _strip_json_fences(raw: str) -> str:
    """Remove optional ```json ... ``` wrappers if the model adds them."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def process_documents_text(extracted_text: str) -> dict[str, Any]:
    """
    Call Gemini with the full extracted text and return a structured dict:

    {"courses": [...], "schedule": [...], "students": [...]}

    Set ``SKIP_GEMINI=1`` to skip the API and parse CSV-style blocks from
    :mod:`extractor` output (for offline tests when quota is exhausted).
    """
    if os.getenv("SKIP_GEMINI", "").lower() in ("1", "true", "yes"):
        return _fallback_from_csv_extracted_text(extracted_text)

    from google import genai
    from google.genai import errors as genai_errors

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment or .env")

    client = genai.Client(api_key=api_key)
    model = _model_name()
    full_prompt = EXTRACTION_PROMPT + extracted_text

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config={"response_mime_type": "application/json"},
            )
            raw = response.text or ""
            break
        except Exception as e:
            last_err = e
            err_s = str(e).lower()
            # Don't retry on quota exhausted or definitive not-found
            if "quota" in err_s or "resource_exhausted" in err_s:
                raise RuntimeError(f"Gemini quota exhausted for model '{model}': {e}") from e
            if "not found" in err_s and "models/" in err_s:
                raise RuntimeError(
                    f"Model '{model}' not found. Check GEMINI_MODEL in your .env."
                ) from e
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"Gemini request failed for model '{model}': {last_err}") from last_err

    cleaned = _strip_json_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini did not return valid JSON: {e}\nRaw:\n{raw[:2000]}") from e

    for key in ("courses", "schedule", "students"):
        if key not in data:
            data[key] = []
    return data
