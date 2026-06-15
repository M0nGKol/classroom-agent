"""Extract raw text from PDF, DOCX, or CSV files."""

from __future__ import annotations

import csv
from pathlib import Path

import pdfplumber
from docx import Document


def extract_text_from_pdf(path: str | Path) -> str:
    """Extract plain text from a PDF file."""
    path = Path(path)
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text.strip())
    return "\n\n".join(parts).strip()


def extract_text_from_docx(path: str | Path) -> str:
    """Extract plain text from a Word document."""
    path = Path(path)
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()


def extract_text_from_csv(path: str | Path) -> str:
    """Read a CSV and return a human-readable text representation."""
    path = Path(path)
    lines: list[str] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            lines.append(" | ".join(cell.strip() for cell in row))
    return "\n".join(lines).strip()


def extract_text_auto(path: str | Path) -> str:
    """
    Auto-detect file type by extension and return raw text.

    Supported: .pdf, .docx, .csv (case-insensitive).
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix == ".csv":
        return extract_text_from_csv(path)
    raise ValueError(f"Unsupported file type: {suffix!r} for {path}")
