# Setting up the SE-B12 class in Google Calendar

These files turn your academic schedule + student list into a Google Calendar that students join automatically.

## What you got

- **SE-B12_Semester6_Schedule.ics** — all class sessions as recurring weekly events (Mon/Tue/Wed), from 15-Jun-2026 to 07-Nov-2026, in Cambodia time (ICT). Every session already lists all 37 students as guests, plus course, instructor, and phone number.
- **student_emails_paste.txt** — all 37 emails on one line, ready to copy-paste into a guest field.
- **student_roster.csv** — the same emails with No. and Section (A/B), for reference.

## The schedule built into the .ics

| Day | 08:00–09:30 | 09:45–11:15 | 13:00–14:30 | 14:45–16:15 |
|-----|-------------|-------------|-------------|-------------|
| Mon | Operation Research | Product Development | Research Methodology | Professional Development VI |
| Tue | Professional Development VI | Professional Development VI | Operation Research | Professional Development VI |
| Wed | Professional Development VI | Product Development | Research Methodology | Professional Development VI |

Each event repeats every week until 07-Nov-2026.

## Recommended way to set it up

The cleanest approach for a class everyone shares is **one calendar for the whole batch**:

1. Go to Google Calendar (web) → left sidebar → **Other calendars → + → Create new calendar**. Name it "SE-B12 Semester 6". Create.
2. **Import the schedule:** Settings (gear) → **Import & export → Import**. Choose `SE-B12_Semester6_Schedule.ics`, pick the new "SE-B12 Semester 6" calendar as the destination, and Import. All 12 recurring events appear.
3. **Share it with students so they can join:** Open the calendar's Settings → **Share with specific people** → add students (paste from `student_emails_paste.txt`) with "See all event details". They'll get an invite to add the calendar to their own Google Calendar.

This keeps every student on the same calendar; when you change a class, everyone sees it.

## Alternative: invite students to each event directly

If you'd rather have students RSVP to individual events instead of subscribing to a calendar:

1. Import the `.ics` into your main calendar (same Import step as above).
2. Open each event → **Add guests** → paste the list from `student_emails_paste.txt` → **Save → Send invitations**.

Note: when you import an `.ics`, Google does **not** automatically email guests. You must open the event and hit Save so it offers to send invitations. The guest list is already embedded, so you only need to confirm sending.

## Notes & things to check

- **Timezone** is set to Asia/Phnom_Penh (ICT, UTC+7). Confirm your Google Calendar timezone matches.
- The schedule shows only Mon/Tue/Wed have classes; Thu–Sun are left empty, so no events were created for them.
- "Professional Development VI" runs in several slots (it's a 135-hour course) — each slot is its own repeating event.
- The student emails are read from your roster image. Double-check a couple before mass-sending, especially long ones like `noeun.soksokunmengfong24@kit.edu.kh`.
- Want a separate calendar per course (so students can toggle each on/off), or two calendars split by Section A / B? I can regenerate the files that way.
