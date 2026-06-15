# CLAUDE. md - AI Classroom Setup Agent

## Project Purpose

Automate classroom setup: parse schedule/course/student documents,
create Zoom meetings, Google Calendar events, and send Gmail invitations.

## Tech Stack

- Python 3.12+
- Gemini API (google-generativeai)
- Zoom API (Server-to-Server Auth, requests library)
- Google APIS (google-auth, google-api-python-client)
- PDF parsing: pdfplumber
- DOCX parsing: python-docx
- CSV: built-in csv module
- Environment: python-dotenv

## File Structure

main. py - entry point, orchestrates all steps
extractor.py - document parsing (PDF/DOCX/CSV)
ai processor. py - Gemini API calls, returns structured JSON
zoom_client. py - Zoom meeting creation
calendar_client.py - Google Calendar event creation
gmail_client.py - Gmail email sending
conflict_checker.py - schedule overlap detection
reporter. py - summary report generation

## Input Files (place in /uploads)

schedule.pdf or schedule.docx
courses.pdf or courses. docx
students.csv or students. docx

## Key Rules

- All secrets in .env, never hardcoded
- Each module is independent and testable
- Use type hints and docstrings
- Handle API errors gracefully with retries
