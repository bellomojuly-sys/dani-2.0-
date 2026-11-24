"""The day's scheduled messages (D2-063): reminders, silence, the 4-per-hour cap."""

from datetime import datetime

from models import AMSTERDAM, Event
from reminders import MAX_PER_HOUR, plan_day_messages


def at(hour, minute=0, day=24):
    return datetime(2026, 11, day, hour, minute, tzinfo=AMSTERDAM)


def event(title, start, end, calendar="personale", all_day=False):
    return Event(calendar=calendar, title=title, start=start, end=end, all_day=all_day)


def test_one_reminder_15_minutes_before_each_future_timed_event_and_the_evening_check_in():
    events = [event("Dentista", at(10), at(11)), event("Palestra", at(18), at(19)),
              event("Già passato", at(7), at(8)), event("Deadline", at(0), at(23, 59), all_day=True)]
    messages = plan_day_messages(at(8, 30), events)
    assert [(m["at"], m["kind"]) for m in messages] == [
        (at(9, 45), "reminder"), (at(17, 45), "reminder"), (at(21), "evening")]
    assert "Dentista" in messages[0]["title"] and "alle 10:00" in messages[0]["text"]


def test_nothing_arrives_during_a_shift_a_lesson_or_a_meeting():
    events = [event("Lezione MA-AAI", at(9), at(12, 45), calendar="Università"),
              event("Call con Ruud", at(12, 50), at(13, 30))]  # its reminder would fall in the lesson
    assert plan_day_messages(at(8), events)[0]["kind"] == "reminder"
    assert [m["at"] for m in plan_day_messages(at(8), events)] == [at(8, 45), at(21)]


def test_on_a_late_shift_the_evening_check_in_waits_until_after_it():
    shift = event("Turno", at(17), at(23), calendar="lavoro")
    evening = [m for m in plan_day_messages(at(8), [shift]) if m["kind"] == "evening"]
    assert evening[0]["at"] == at(23, 30)
    very_late = event("Turno", at(17), at(23, 30), calendar="lavoro")
    assert [m for m in plan_day_messages(at(8), [very_late]) if m["kind"] == "evening"] == []  # after 23:30: none


def test_never_more_than_four_messages_in_an_hour():
    events = [event(f"E{n}", at(10, n * 10), at(10, n * 10 + 5)) for n in range(6)]
    messages = plan_day_messages(at(8), events)
    reminders = [m for m in messages if m["kind"] == "reminder"]
    assert len(reminders) == MAX_PER_HOUR and reminders[0]["title"].endswith("E0")


def test_after_the_evening_nothing_is_planned():
    assert plan_day_messages(at(21, 30), [event("Tardi", at(22), at(23))]) == [
        {"at": at(21, 45), "title": "Tra 15 minuti: Tardi",
         "text": "Chief, alle 22:00 hai «Tardi». Preparati adesso, non tra dieci minuti.", "kind": "reminder"}]
