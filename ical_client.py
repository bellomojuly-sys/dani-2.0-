"""Read Giulia's Google Calendars through their secret iCal addresses.

Read-only and without OAuth (Decision Log 2026-11-05): Google gives every
calendar a private ``.ics`` address; we download it and parse it. Repeating
events are expanded one occurrence at a time by ``recurring-ical-events``,
the one new dependency, so a weekly lesson appears every week in the window.

Two layers, so each can be tested offline:
  - ``events_from_ics``  parses iCal bytes and returns typed Events in a window;
  - ``read_calendars``   downloads each address (through an injectable
                         ``fetch`` function) and merges the results.
The secret addresses come from the environment and never appear in an error.
"""

from datetime import date, datetime, time, timedelta
from urllib import error, request

import icalendar
import recurring_ical_events

from models import AMSTERDAM, Event


def to_https(url):
    """Apps like Eitje give a ``webcal://`` subscription link. It is the same
    address served over HTTPS, but urllib does not know the webcal scheme, so
    we swap it. Any other address is returned unchanged."""
    if url.lower().startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    return url


def fetch_bytes(url, opener=request.urlopen, timeout=20):
    """Download one iCal address. The URL is secret, so it is not in errors."""
    try:
        with opener(to_https(url), timeout=timeout) as response:
            return response.read()
    except error.HTTPError as failure:
        raise RuntimeError(f"a calendar address answered HTTP {failure.code}") from None
    except error.URLError as failure:
        raise RuntimeError(f"a calendar address could not be reached: {failure.reason}") from None


def _unescape(text):
    """iCal escapes commas, semicolons and newlines in text with a backslash
    (RFC 5545): a feed named ``Bellomo\\, Giulia`` means ``Bellomo, Giulia``.
    ``icalendar`` keeps the backslashes, so we remove them here. A literal
    backslash arrives as ``\\\\`` and is restored last."""
    marker = "\0"
    return (
        text.replace("\\\\", marker)
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace(marker, "\\")
    )


def _to_amsterdam(value):
    """iCal gives a date for all-day events and a datetime for timed ones.

    A date becomes midnight Amsterdam; an aware datetime is converted to
    Amsterdam; a naive datetime (rare, "floating" time) is read as Amsterdam.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=AMSTERDAM)
        return value.astimezone(AMSTERDAM)
    return datetime.combine(value, time.min, tzinfo=AMSTERDAM)


def events_from_ics(ics_bytes, start, end, calendar_name=None):
    """Return the occurrences between ``start`` and ``end`` (dates) as Events.

    The window is [start 00:00, end 00:00) Amsterdam. The calendar name comes
    from the feed's X-WR-CALNAME unless one is given. Occurrences are sorted by
    start time.
    """
    calendar = icalendar.Calendar.from_ical(ics_bytes)
    name = _unescape(calendar_name or str(calendar.get("X-WR-CALNAME", "calendar")).strip())
    window_start = datetime.combine(start, time.min, tzinfo=AMSTERDAM)
    window_end = datetime.combine(end, time.min, tzinfo=AMSTERDAM)
    events = []
    for occurrence in recurring_ical_events.of(calendar).between(window_start, window_end):
        begins = occurrence["DTSTART"].dt
        events.append(
            Event(
                calendar=name,
                title=_unescape(str(occurrence.get("SUMMARY", "(no title)"))),
                start=_to_amsterdam(begins),
                end=_to_amsterdam(occurrence["DTEND"].dt),
                all_day=not isinstance(begins, datetime),
                uid=str(occurrence.get("UID", "")),
            )
        )
    return sorted(events, key=lambda event: event.start)


def read_calendars(urls, start, end, fetch=fetch_bytes):
    """Download every address and return all their events in one sorted list."""
    events = []
    for url in urls:
        events.extend(events_from_ics(fetch(url), start, end))
    return sorted(events, key=lambda event: event.start)


def split_urls(value):
    """Turn the GCAL_ICS_URL variable (one or more addresses, comma-separated)
    into a clean list; blanks are ignored."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]
