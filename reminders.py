"""The day's scheduled messages (D2-063): appointment reminders and the evening check-in.

Render free sleeps, so Dani cannot wake up at 14:45 to remind Giulia of a
15:00 call. Instead, when the morning briefing is sent, Dani plans every
message of the day and hands them to ntfy with a delivery time; ntfy
delivers them while Render sleeps.

Her rules (page "Dani — chi è Dani"):
  - a reminder REMINDER_MINUTES before each timed event that has not started;
  - silence during shifts, lessons and meetings: a message whose delivery
    time falls inside one of those events is not sent;
  - at most MAX_PER_HOUR messages in any hour (the earliest ones win);
  - the evening check-in "com'è andata oggi?" at EVENING, or after the last
    shift of the day when she works late; none after LAST_MESSAGE.

A pure function: the same day and events always give the same messages.
"""

from datetime import datetime, time, timedelta

REMINDER_MINUTES = 15
MAX_PER_HOUR = 4
EVENING = time(21, 0)
LAST_MESSAGE = time(23, 30)
# Events she must not be interrupted in: shifts, lessons, meetings.
SILENT_WORDS = ("lavoro", "eitje", "turno", "lezione", "lesson", "università", "universita", "meeting", "riunione", "call")


def is_silent(event):
    """True when a message must not arrive during this event."""
    text = f"{event.calendar} {event.title}".casefold()
    return any(word in text for word in SILENT_WORDS)


def plan_day_messages(now, events):
    """Return [{"at": datetime, "title", "text", "kind"}] for the rest of ``now``'s day.

    ``events`` are the day's events (Event objects, Amsterdam time); all-day
    events get no reminder. Messages in the past are never planned.
    """
    today = now.date()
    timed = sorted((e for e in events if not e.all_day and e.start.date() == today), key=lambda e: e.start)
    quiet = [e for e in timed if is_silent(e)]

    def inside_quiet(moment):
        return any(e.start <= moment < e.end for e in quiet)

    messages = []
    for event in timed:
        at = event.start - timedelta(minutes=REMINDER_MINUTES)
        if at <= now or inside_quiet(at):
            continue
        messages.append({
            "at": at,
            "title": f"Tra {REMINDER_MINUTES} minuti: {event.title}",
            "text": f"Chief, alle {event.start:%H:%M} hai «{event.title}». Preparati adesso, non tra dieci minuti.",
            "kind": "reminder",
        })

    evening = datetime.combine(today, EVENING, tzinfo=now.tzinfo)
    late_shift_end = max((e.end for e in quiet if e.end.date() == today and e.end > evening), default=None)
    if late_shift_end is not None:
        evening = late_shift_end + timedelta(minutes=30)
    if evening > now and evening.time() <= LAST_MESSAGE and evening.date() == today and not inside_quiet(evening):
        messages.append({
            "at": evening,
            "title": "Com'è andata oggi?",
            "text": "July, com'è andata oggi? Dimmi in due parole come stai e cosa hai chiuso: domani lo pianifico meglio.",
            "kind": "evening",
        })

    messages.sort(key=lambda m: m["at"])
    kept = []
    for message in messages:
        window = [m for m in kept if message["at"] - m["at"] < timedelta(hours=1)]
        if len(window) < MAX_PER_HOUR:
            kept.append(message)
    return kept
