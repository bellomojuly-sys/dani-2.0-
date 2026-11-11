"""The Calendar API client with a fake ``http``: no network, no Google key."""

import io
from datetime import date, datetime
from urllib import error

import pytest

from gcal_client import (
    GoogleError,
    calendar_id_from_ics_url,
    calendar_name,
    create_event,
    delete_event,
    event_from_item,
    move_event,
    read_events,
    send,
)
from models import AMSTERDAM

TIMED = {"id": "abc_20261112T140000Z", "iCalUID": "abc@google.com", "summary": "Call con Ruud",
         "start": {"dateTime": "2026-11-12T15:00:00+01:00"}, "end": {"dateTime": "2026-11-12T14:30:00Z"}}
ALL_DAY = {"id": "day1", "iCalUID": "day1@google.com", "start": {"date": "2026-11-13"}, "end": {"date": "2026-11-14"}}


class Fake:
    """Records every call and answers from a list (an Exception is raised)."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, token, body=None):
        self.calls.append((method, url, body))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=AMSTERDAM)


def test_calendar_id_comes_out_of_the_ical_address_without_the_secret():
    url = "https://calendar.google.com/calendar/ical/abc123%40group.calendar.google.com/private-SECRET/basic.ics"
    assert calendar_id_from_ics_url(url) == "abc123@group.calendar.google.com"
    for wrong in ("https://example.com/feed.ics", "https://calendar.google.com/calendar/ical", "fixture"):
        with pytest.raises(ValueError, match="not a Google Calendar iCal address"):
            calendar_id_from_ics_url(wrong)


def test_a_timed_item_becomes_an_event_in_amsterdam_time_with_its_ids():
    event = event_from_item(TIMED, "studio", "cal-1")
    assert (event.start, event.end) == (at(12, 15), at(12, 15, 30))
    assert (event.title, event.calendar, event.all_day) == ("Call con Ruud", "studio", False)
    assert (event.uid, event.api_id, event.calendar_id) == ("abc@google.com", "abc_20261112T140000Z", "cal-1")
    assert event.key == "abc@google.com|2026-11-12T15:00:00+01:00"  # same key as the iCal reader gives


def test_an_all_day_item_and_a_missing_title():
    event = event_from_item(ALL_DAY, "Università", "cal-2")
    assert event.all_day is True and event.start == at(13, 0) and event.title == "(no title)"


@pytest.mark.parametrize("item", [{"id": "x"}, {"id": "x", "start": {"dateTime": "soon"}, "end": {"dateTime": "later"}},
                                  {"id": "x", "start": {"date": "2026-11-13"}, "end": {"date": "2026-11-13"}}])
def test_a_broken_item_is_refused_with_its_id(item):
    with pytest.raises(ValueError, match="Google event 'x' is not a valid event"):
        event_from_item(item, "studio", "cal-1")


def test_read_events_follows_the_pages_and_skips_cancelled_items():
    http = Fake({"items": [TIMED, {"id": "gone", "status": "cancelled"}], "nextPageToken": "p2"}, {"items": [ALL_DAY]})
    events = read_events("tok", "me@gmail.com", "studio", date(2026, 11, 10), date(2026, 11, 17), http=http)
    assert [event.api_id for event in events] == ["abc_20261112T140000Z", "day1"]
    first, second = http.calls[0][1], http.calls[1][1]
    assert "/calendars/me%40gmail.com/events?" in first and "singleEvents=true" in first
    assert "timeMin=2026-11-10T00%3A00%3A00%2B01%3A00" in first and "pageToken" not in first
    assert "pageToken=p2" in second


def test_calendar_name_is_stripped():
    assert calendar_name("tok", "cal-1", http=Fake({"summary": "studio "})) == "studio"


def test_delete_is_silent_and_checked():
    http = Fake({}, {"status": "cancelled"})
    assert delete_event("tok", "cal-1", "abc_20261112T140000Z", http=http) is True
    assert http.calls[0][0] == "DELETE" and http.calls[0][1].endswith("/events/abc_20261112T140000Z?sendUpdates=none")
    assert http.calls[1][0] == "GET"


@pytest.mark.parametrize("code", [404, 410])
def test_delete_accepts_gone_as_confirmation(code):
    assert delete_event("tok", "cal-1", "e1", http=Fake({}, GoogleError(code, "gone"))) is True


def test_delete_refusals():
    with pytest.raises(GoogleError, match="HTTP 403"):  # shared read-only
        delete_event("tok", "cal-1", "e1", http=Fake(GoogleError(403, "forbidden")))
    with pytest.raises(RuntimeError, match="did not confirm the event was deleted"):
        delete_event("tok", "cal-1", "e1", http=Fake({}, {"status": "confirmed"}))
    with pytest.raises(GoogleError, match="HTTP 500"):  # the read-back itself failed
        delete_event("tok", "cal-1", "e1", http=Fake({}, GoogleError(500, "boom")))


def test_move_sends_only_the_times_silently_and_checks_the_answer():
    moved = {"start": {"dateTime": "2026-11-12T16:00:00+01:00"}, "end": {"dateTime": "2026-11-12T16:30:00+01:00"}}
    http = Fake(moved)
    assert move_event("tok", "cal-1", "e1", at(12, 16), at(12, 16, 30), http=http) is True
    method, url, body = http.calls[0]
    assert method == "PATCH" and url.endswith("/events/e1?sendUpdates=none")
    assert body == {"start": {"dateTime": "2026-11-12T16:00:00+01:00", "timeZone": "Europe/Amsterdam"},
                    "end": {"dateTime": "2026-11-12T16:30:00+01:00", "timeZone": "Europe/Amsterdam"}}


def test_move_refusals():
    with pytest.raises(ValueError, match="end must be after"):
        move_event("tok", "cal-1", "e1", at(12, 16), at(12, 16), http=Fake())
    unchanged = {"start": {"dateTime": "2026-11-12T15:00:00+01:00"}, "end": {"dateTime": "2026-11-12T15:30:00+01:00"}}
    with pytest.raises(RuntimeError, match="did not confirm the new time"):
        move_event("tok", "cal-1", "e1", at(12, 16), at(12, 16, 30), http=Fake(unchanged))
    with pytest.raises(RuntimeError, match="did not send the moved event back"):
        move_event("tok", "cal-1", "e1", at(12, 16), at(12, 16, 30), http=Fake({}))


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_send_puts_the_token_in_the_header_and_decodes_the_answer():
    seen = {}

    def opener(req, timeout):
        seen.update(method=req.get_method(), auth=req.get_header("Authorization"), data=req.data)
        return Answer(b'{"ok": true}')

    assert send("PATCH", "https://x", "tok", {"a": 1}, opener=opener) == {"ok": True}
    assert seen == {"method": "PATCH", "auth": "Bearer tok", "data": b'{"a": 1}'}
    assert send("DELETE", "https://x", "tok", opener=lambda req, timeout: Answer(b"")) == {}  # 204: empty body


def test_send_errors_carry_the_status_and_never_the_token():
    def forbidden(req, timeout):
        raise error.HTTPError("https://x", 403, "Forbidden", {}, io.BytesIO(b'{"error": {"message": "need writer access"}}'))

    with pytest.raises(GoogleError) as caught:
        send("GET", "https://x", "secret-token", opener=forbidden)
    assert caught.value.code == 403 and "need writer access" in str(caught.value) and "secret-token" not in str(caught.value)

    def not_json(req, timeout):
        raise error.HTTPError("https://x", 500, "Oops", {}, io.BytesIO(b"<html>"))

    with pytest.raises(GoogleError, match="HTTP 500: no details"):
        send("GET", "https://x", "tok", opener=not_json)

    def unreachable(req, timeout):
        raise error.URLError("no route")

    with pytest.raises(RuntimeError, match="could not be reached"):
        send("GET", "https://x", "tok", opener=unreachable)


def test_create_event_sends_only_title_and_times_and_reads_back():
    answer = {"id": "blk-1", "start": {"dateTime": "2026-11-12T10:00:00+01:00"},
              "end": {"dateTime": "2026-11-12T11:00:00+01:00"}}
    http = Fake(answer)
    assert create_event("tok", "cal-s", " Studio AI ", at(12, 10), at(12, 11), http=http) == "blk-1"
    method, url, body = http.calls[0]
    assert method == "POST" and url.endswith("/calendars/cal-s/events?sendUpdates=none")
    assert body == {"summary": "Studio AI",
                    "start": {"dateTime": "2026-11-12T10:00:00+01:00", "timeZone": "Europe/Amsterdam"},
                    "end": {"dateTime": "2026-11-12T11:00:00+01:00", "timeZone": "Europe/Amsterdam"}}


def test_create_event_refuses_bad_input_before_any_request():
    http = Fake()
    with pytest.raises(ValueError, match="end must be after the start"):
        create_event("tok", "cal-s", "Studio", at(12, 11), at(12, 10), http=http)
    with pytest.raises(ValueError, match="needs a title"):
        create_event("tok", "cal-s", "   ", at(12, 10), at(12, 11), http=http)
    assert http.calls == []


def test_create_event_raises_when_the_read_back_is_missing_or_wrong():
    with pytest.raises(RuntimeError, match="did not send the created event back"):
        create_event("tok", "cal-s", "Studio", at(12, 10), at(12, 11), http=Fake({"status": "confirmed"}))
    moved = {"id": "blk-1", "start": {"dateTime": "2026-11-12T10:15:00+01:00"},
             "end": {"dateTime": "2026-11-12T11:00:00+01:00"}}
    with pytest.raises(RuntimeError, match="did not confirm the event's time"):
        create_event("tok", "cal-s", "Studio", at(12, 10), at(12, 11), http=Fake(moved))
