"""The cache with fake sources and a fixed clock: no Notion, no download, no LLM."""

import json
from datetime import date, datetime

import pytest

from cycle import CycleSettings
from ical_client import read_calendars
from live import Live
from models import AMSTERDAM
from notion_client import task_from_page
from store import UserSettings, hide_event

with open("fixtures/notion_query.json") as handle:
    TASKS = [task_from_page(page) for page in json.load(handle)["results"]]
with open("fixtures/calendar.ics", "rb") as handle:
    ICS = handle.read()

NOW = datetime(2026, 11, 10, 13, 21, 5, tzinfo=AMSTERDAM)  # a Tuesday


def _events(start, end):
    return read_calendars(["fixture"], start, end, fetch=lambda url: ICS)


def _reverse_priority(tasks, today, context):
    rows = [{"rank": n, "id": t.id, "title": t.title, "reason": f"perché {n}"} for n, t in enumerate(reversed(tasks), 1)]
    return {"ok": True, "reason": "validated", "priority": rows}


def _live(fetch_tasks=lambda: list(TASKS), fetch_events=_events, prioritize=_reverse_priority, now=NOW):
    return Live(fetch_tasks, fetch_events, prioritize, clock=lambda: now)


def test_before_any_refresh_the_state_is_empty_and_says_never_updated():
    state = _live().state(UserSettings())
    assert state["tasks"] == [] and state["events"] == []
    assert state["sources"]["notion"] == {"ok": None, "at": None, "error": None}
    assert state["sources"]["gmail"]["error"] == "non collegato"


def test_refresh_records_time_and_ok_for_each_source():
    live = _live()
    live.refresh("all")
    state = live.state(UserSettings())
    assert state["sources"]["notion"] == {"ok": True, "at": "2026-11-10T13:21:05+01:00", "error": None}
    assert state["sources"]["calendar"]["ok"] is True
    assert len(state["tasks"]) == 3
    assert state["now"] == "2026-11-10T13:21:05+01:00" and state["days"][0] == "2026-11-10" and len(state["days"]) == 7
    assert state["calendars"] == ["studio"]


def test_a_failing_source_keeps_the_last_good_data_and_shows_the_error():
    answers = iter([list(TASKS), RuntimeError("Notion answered HTTP 502: bad gateway")])

    def fetch_tasks():
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    live = _live(fetch_tasks=fetch_tasks)
    live.refresh("notion")
    live.refresh("notion")
    state = live.state(UserSettings())
    assert len(state["tasks"]) == 3  # still the first answer
    assert state["sources"]["notion"]["ok"] is False
    assert state["sources"]["notion"]["error"] == "Notion answered HTTP 502: bad gateway"


def test_an_unexpected_error_shows_only_its_type():
    def broken(start, end):
        raise KeyError("https://secret-address")

    live = _live(fetch_events=broken)
    live.refresh("calendar")
    assert live.state(UserSettings())["sources"]["calendar"]["error"] == "KeyError"


def test_unknown_source_is_refused():
    with pytest.raises(ValueError, match="unknown source 'gmail'"):
        _live().refresh("gmail")


def test_priority_is_asked_once_until_tasks_or_context_change():
    calls = []

    def prioritize(tasks, today, context):
        calls.append(context)
        return _reverse_priority(tasks, today, context)

    live = _live(prioritize=prioritize)
    live.refresh("all")
    assert live.update_priority("rules A") is True
    assert live.update_priority("rules A") is False  # nothing changed: no LLM call
    assert live.update_priority("rules B") is True  # the context changed
    live.tasks = live.tasks[:2]
    assert live.update_priority("rules B") is True  # the tasks changed
    assert calls == ["rules A", "rules B", "rules B"]


def test_verified_priority_orders_the_tasks_and_carries_the_reasons():
    live = _live()
    live.refresh("all")
    live.update_priority("")
    state = live.state(UserSettings())
    assert [task["title"] for task in state["tasks"]] == [task.title for task in reversed(TASKS)]
    assert state["tasks"][0]["reason"] == "perché 1"
    assert state["priority"] == {"ok": True, "reason": "validated"}


def test_a_priority_made_for_another_context_is_not_shown_as_verified():
    live = _live()
    live.refresh("all")
    live.update_priority("old context")
    state = live.state(UserSettings(context="new context"))
    assert state["priority"]["ok"] is False
    assert state["tasks"][0]["reason"] is None


def test_dropping_a_ticked_task_keeps_the_verified_order_without_a_new_call():
    calls = []

    def prioritize(tasks, today, context):
        calls.append(1)
        return _reverse_priority(tasks, today, context)

    live = _live(prioritize=prioritize)
    live.refresh("all")
    live.update_priority("")
    live.drop_task(TASKS[2].id)
    state = live.state(UserSettings())
    assert [task["title"] for task in state["tasks"]] == [TASKS[1].title, TASKS[0].title]
    assert state["priority"]["ok"] is True
    assert live.update_priority("") is False and calls == [1]
    assert live.find_task(TASKS[2].id) is None and live.find_task(TASKS[0].id) is TASKS[0]


def test_events_are_tickable_only_in_the_chosen_calendars():
    live = _live()
    live.refresh("all")
    assert all(event["tickable"] for event in live.state(UserSettings(tickable_calendars=["Studio"]))["events"])
    assert not any(event["tickable"] for event in live.state(UserSettings(tickable_calendars=["personale"]))["events"])


def test_no_study_block_is_proposed_in_the_past():
    live = _live()  # it is 13:21
    live.refresh("all")
    first = live.state(UserSettings())["blocks"][0]
    assert first["start"] == "2026-11-10T13:30:00+01:00"  # the next quarter of an hour
    midnight = _live(now=datetime(2026, 11, 10, 0, 0, tzinfo=AMSTERDAM))
    midnight.refresh("all")
    assert midnight.state(UserSettings())["blocks"]  # 00:00 exactly: nothing is "past", no error


def test_a_hidden_event_disappears_and_frees_its_time_for_study():
    live = _live(now=datetime(2026, 11, 10, 8, 0, tzinfo=AMSTERDAM))
    live.refresh("all")
    before = live.state(UserSettings())
    lesson = next(event for event in before["events"] if event["title"] == "Lezione MA-AAI")
    hidden = hide_event(UserSettings(), live.find_event(lesson["key"]), NOW)
    after = live.state(hidden)
    assert lesson["key"] not in [event["key"] for event in after["events"]]
    assert len(after["events"]) == len(before["events"]) - 1
    assert after["blocks"][0]["start"] == "2026-11-10T09:00:00+01:00"  # the lesson's slot is free now
    assert before["blocks"][0]["start"] != "2026-11-10T09:00:00+01:00"


def test_cycle_is_in_the_state_only_when_set():
    live = _live()
    assert live.state(UserSettings())["cycle"] is None
    cycle = live.state(UserSettings(cycle=CycleSettings(start=date(2026, 11, 8))))["cycle"]
    assert cycle["phase"] == "in arrivo" and cycle["late_days"] == 2 and cycle["next_start"] == "2026-11-08"
