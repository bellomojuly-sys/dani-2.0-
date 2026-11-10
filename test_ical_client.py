"""Calendars are read offline from fixtures/calendar.ics (one weekly lesson,
one one-off call, one all-day event). Nothing here downloads anything."""

from datetime import date, datetime

import pytest

from ical_client import events_from_ics, read_calendars, split_urls
from models import AMSTERDAM

with open("fixtures/calendar.ics", "rb") as handle:
    ICS = handle.read()


def test_window_returns_the_three_occurrences_in_order():
    events = events_from_ics(ICS, date(2026, 11, 9), date(2026, 11, 16))
    assert [event.title for event in events] == ["Lezione MA-AAI", "Call con Ruud", "Demo Sprint 3"]


def test_weekly_event_appears_every_week_in_a_two_week_window():
    events = events_from_ics(ICS, date(2026, 11, 9), date(2026, 11, 23))
    lessons = [event for event in events if event.title == "Lezione MA-AAI"]
    assert [event.start.date() for event in lessons] == [date(2026, 11, 10), date(2026, 11, 17)]


def test_times_are_amsterdam_and_survive_the_winter_time_change():
    # 13 Oct is still summer time (+02:00); 10 Nov is winter time (+01:00).
    # The lesson stays at 09:00 local in both weeks.
    october = events_from_ics(ICS, date(2026, 10, 12), date(2026, 10, 19))[0]
    november = events_from_ics(ICS, date(2026, 11, 9), date(2026, 11, 16))[0]
    assert october.start == datetime(2026, 10, 13, 9, 0, tzinfo=AMSTERDAM)
    assert november.start == datetime(2026, 11, 10, 9, 0, tzinfo=AMSTERDAM)
    assert october.start.utcoffset().total_seconds() == 2 * 3600
    assert november.start.utcoffset().total_seconds() == 1 * 3600


def test_all_day_event_is_flagged_and_starts_at_midnight():
    events = events_from_ics(ICS, date(2026, 11, 13), date(2026, 11, 14))
    assert events[0].all_day is True
    assert events[0].start == datetime(2026, 11, 13, 0, 0, tzinfo=AMSTERDAM)


def test_calendar_name_comes_from_the_feed():
    assert events_from_ics(ICS, date(2026, 11, 9), date(2026, 11, 16))[0].calendar == "studio"


def test_an_empty_window_has_no_events():
    assert events_from_ics(ICS, date(2026, 11, 14), date(2026, 11, 16)) == []


def test_read_calendars_merges_feeds_and_sorts_by_start():
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        return ICS

    events = read_calendars(["u1", "u2"], date(2026, 11, 9), date(2026, 11, 16), fetch=fake_fetch)
    assert fetched == ["u1", "u2"]
    assert len(events) == 6
    assert [event.start for event in events] == sorted(event.start for event in events)


def test_split_urls_ignores_blanks():
    assert split_urls(" a , ,b,") == ["a", "b"]
    assert split_urls(None) == []


def test_malformed_ics_is_refused():
    with pytest.raises(ValueError):
        events_from_ics(b"not a calendar", date(2026, 11, 9), date(2026, 11, 16))
