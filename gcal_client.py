"""Read and change Giulia's Google Calendars through the Calendar API.

The iCal addresses (ical_client.py) can only read, and Google refreshes them
with a delay. This module uses the Calendar API with a *service account*: a
robot account with its own e-mail, to which Giulia shared her calendars. Its
key is a JSON file outside the repository; ``.env`` holds only the path.

Same style as notion_client.py: plain HTTPS + JSON with urllib, one visible
request per function, and an injectable ``http`` so tests never touch the
network. ``google-auth`` is used for one thing only: turning the key file into
a short-lived access token (``token_source``).

The two writes, ``delete_event`` and ``move_event``:
  - act on one event id. For a repeating event the id is the id of the single
    occurrence, so the rest of the series is never touched;
  - send ``sendUpdates=none``: nobody gets an e-mail;
  - read the result back and raise if it is not what was asked.
They are called only after Giulia's yes (a tick, or Confirm on a proposal).
"""

import json
from datetime import date, datetime, time, timedelta
from urllib import error, parse, request

from models import AMSTERDAM, Event

API = "https://www.googleapis.com/calendar/v3"
# calendar.events: read and write events. calendar.readonly: read a calendar's name.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


class GoogleError(RuntimeError):
    """A refused Calendar API request. ``code`` is the HTTP status."""

    def __init__(self, code, detail):
        super().__init__(f"Google Calendar answered HTTP {code}: {detail}")
        self.code = code


def send(method, url, token, body=None, opener=request.urlopen, timeout=20):
    """One request to the Calendar API; returns the decoded JSON ({} if empty).

    The token travels only in the Authorization header and is never part of an
    error message. ``opener`` is injectable for the tests.
    """
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except error.HTTPError as failure:
        try:
            detail = json.loads(failure.read())["error"]["message"]
        except (ValueError, KeyError, TypeError):
            detail = "no details"
        raise GoogleError(failure.code, str(detail)[:200]) from None
    except error.URLError as failure:
        raise RuntimeError(f"Google Calendar could not be reached: {failure.reason}") from None


def calendar_id_from_ics_url(url):
    """The calendar id is inside its secret iCal address:
    .../calendar/ical/<id>/private-<secret>/basic.ics. The secret part is
    dropped here and never returned."""
    parts = parse.urlsplit(url).path.split("/")
    if "ical" not in parts or len(parts) <= parts.index("ical") + 1 or not parts[parts.index("ical") + 1]:
        raise ValueError("not a Google Calendar iCal address")
    return parse.unquote(parts[parts.index("ical") + 1])


def _events_url(calendar_id, event_id=None):
    url = f"{API}/calendars/{parse.quote(calendar_id, safe='')}/events"
    return url if event_id is None else f"{url}/{parse.quote(event_id, safe='')}"


def _moment(value):
    """Google gives {"dateTime": ...} for a timed event and {"date": ...} for
    an all-day one. Both become an Amsterdam datetime; the bool says all-day."""
    if "dateTime" in value:
        return datetime.fromisoformat(value["dateTime"]).astimezone(AMSTERDAM), False
    return datetime.combine(date.fromisoformat(value["date"]), time.min, tzinfo=AMSTERDAM), True


def event_from_item(item, calendar_name, calendar_id):
    """Map one item of an events list to a typed Event (ValueError if broken)."""
    try:
        start, all_day = _moment(item["start"])
        end, _ = _moment(item["end"])
        return Event(
            calendar=calendar_name,
            title=item.get("summary") or "(no title)",
            start=start,
            end=end,
            all_day=all_day,
            uid=item.get("iCalUID", ""),
            api_id=item["id"],
            calendar_id=calendar_id,
        )
    except (KeyError, ValueError) as problem:
        raise ValueError(f"Google event {item.get('id')!r} is not a valid event: {problem}") from None


def calendar_name(token, calendar_id, http=send):
    """The calendar's own name. Also the cheapest check that it is shared with us."""
    return str(http("GET", f"{API}/calendars/{parse.quote(calendar_id, safe='')}", token).get("summary", "")).strip()


def read_events(token, calendar_id, name, start, end, http=send):
    """Every occurrence of one calendar in [start 00:00, end 00:00) Amsterdam.

    ``singleEvents=true`` makes Google expand repeating events, so each item
    is one occurrence with its own id. Google answers a page at a time; we
    follow ``nextPageToken`` until there is none.
    """
    query = {
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "250",
        "timeMin": datetime.combine(start, time.min, tzinfo=AMSTERDAM).isoformat(),
        "timeMax": datetime.combine(end, time.min, tzinfo=AMSTERDAM).isoformat(),
    }
    events = []
    while True:
        answer = http("GET", _events_url(calendar_id) + "?" + parse.urlencode(query), token)
        for item in answer.get("items", []):
            if item.get("status") != "cancelled":
                events.append(event_from_item(item, name, calendar_id))
        if not answer.get("nextPageToken"):
            return events
        query["pageToken"] = answer["nextPageToken"]


def delete_event(token, calendar_id, event_id, http=send):
    """Delete one event (one occurrence), silently, and check it is gone.

    Read-back: asking for the event again must answer "cancelled" (or 404/410,
    which also mean gone). Anything else raises.
    """
    http("DELETE", _events_url(calendar_id, event_id) + "?sendUpdates=none", token)
    try:
        after = http("GET", _events_url(calendar_id, event_id), token)
    except GoogleError as failure:
        if failure.code in (404, 410):
            return True
        raise
    if after.get("status") != "cancelled":
        raise RuntimeError("Google Calendar did not confirm the event was deleted")
    return True


def create_event(token, calendar_id, title, start, end, http=send):
    """Create one timed event (a study block Giulia accepted), silently.

    Only title, start and end are sent. ``sendUpdates=none``: nobody gets an
    e-mail. Read-back: the answer must carry an id and exactly the times we
    asked for; anything else raises. Returns the new event's id.
    """
    if end <= start:
        raise ValueError("the end must be after the start")
    if not title.strip():
        raise ValueError("the event needs a title")
    body = {
        "summary": title.strip(),
        "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Amsterdam"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Amsterdam"},
    }
    answer = http("POST", _events_url(calendar_id) + "?sendUpdates=none", token, body)
    try:
        created_id = answer["id"]
        got_start, _ = _moment(answer["start"])
        got_end, _ = _moment(answer["end"])
    except (KeyError, ValueError):
        raise RuntimeError("Google Calendar did not send the created event back") from None
    if (got_start, got_end) != (start, end):
        raise RuntimeError("Google Calendar did not confirm the event's time")
    return created_id


def move_event(token, calendar_id, event_id, new_start, new_end, http=send):
    """Move one event (one occurrence) to new_start–new_end, silently.

    Only start and end are sent, so title, description and guests cannot
    change. Read-back: the answer must carry exactly the times we asked for.
    """
    if new_end <= new_start:
        raise ValueError("the new end must be after the new start")
    body = {
        "start": {"dateTime": new_start.isoformat(), "timeZone": "Europe/Amsterdam"},
        "end": {"dateTime": new_end.isoformat(), "timeZone": "Europe/Amsterdam"},
    }
    answer = http("PATCH", _events_url(calendar_id, event_id) + "?sendUpdates=none", token, body)
    try:
        start, _ = _moment(answer["start"])
        end, _ = _moment(answer["end"])
    except (KeyError, ValueError):
        raise RuntimeError("Google Calendar did not send the moved event back") from None
    if (start, end) != (new_start, new_end):
        raise RuntimeError("Google Calendar did not confirm the new time")
    return True


def token_source(key_file):  # pragma: no cover - real Google sign-in
    """Return token() -> a valid access token made from the service-account key.

    A token lasts about an hour; ``token()`` asks for a new one only when the
    current one has expired.
    """
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    transport = Request()

    def token():
        if not credentials.valid:
            credentials.refresh(transport)
        return credentials.token

    return token
