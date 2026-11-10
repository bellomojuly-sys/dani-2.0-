"""The dashboard run with every outside piece faked: no Notion, no download,
no DeepSeek. The fixtures stand in for the real answers."""

import json
from datetime import date, datetime
from types import SimpleNamespace

from dashboard import (
    build_messages,
    load_settings,
    make_read_tasks,
    order_tasks,
    run_dashboard,
    week_from,
)
from ical_client import read_calendars
from models import AMSTERDAM, Task
from notion_client import task_from_page

with open("fixtures/notion_query.json") as handle:
    TASKS = [task_from_page(page) for page in json.load(handle)["results"]]
with open("fixtures/calendar.ics", "rb") as handle:
    ICS = handle.read()

TODAY = date(2026, 11, 10)  # a Tuesday: the fixture lesson is that morning


def _events(start, end):
    return read_calendars(["fixture"], start, end, fetch=lambda url: ICS)


# --- settings -----------------------------------------------------------------

def test_load_settings_names_every_missing_variable():
    result = load_settings({"NOTION_TOKEN": "t"})
    assert result == {"error": "Missing in .env: NOTION_TASKS_DB_ID, GCAL_ICS_URL"}


def test_load_settings_splits_the_calendar_addresses_and_allows_no_llm_key():
    env = {"NOTION_TOKEN": "t", "NOTION_TASKS_DB_ID": "db", "GCAL_ICS_URL": "a, b"}
    settings = load_settings(env)
    assert settings["ics_urls"] == ["a", "b"]
    assert settings["deepseek_api_key"] is None


# --- the real read_tasks tool ---------------------------------------------------

def test_read_tasks_tool_hands_the_real_tasks_to_the_model():
    read_tasks = make_read_tasks(TASKS)
    rows = read_tasks({})
    assert [row["title"] for row in rows] == [task.title for task in TASKS]
    assert rows[0]["id"] == TASKS[0].id and rows[0]["deadline"] == "2026-11-12"


def test_read_tasks_tool_keeps_the_no_arguments_contract():
    assert make_read_tasks(TASKS)({"x": 1})["error"].startswith("read_tasks takes no arguments")


def test_messages_carry_today_and_the_skill():
    system = build_messages(TODAY)[0]["content"]
    assert "2026-11-10" in system and "read_tasks" in system


# --- ordering -------------------------------------------------------------------

def test_verified_priority_decides_the_order():
    outcome = {"ok": True, "reason": "validated", "priority": [{"id": TASKS[2].id}, {"id": TASKS[0].id}, {"id": TASKS[1].id}]}
    assert [task.id for task in order_tasks(TASKS, outcome)] == [TASKS[2].id, TASKS[0].id, TASKS[1].id]


def test_without_verified_priority_deadline_then_label_decides():
    outcome = {"ok": False, "reason": "no key", "priority": None}
    # 12 Nov first, 20 Nov second, no deadline last.
    assert [task.title for task in order_tasks(TASKS, outcome)] == [
        "Finish the Notion client",
        "Book the dentist",
        "Write the feedback brief",
    ]


def test_week_is_seven_days_from_today():
    assert week_from(TODAY)[0] == TODAY and len(week_from(TODAY)) == 7


# --- the whole run, with fakes -------------------------------------------------

def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _message(tool_calls=None, content=None):
    return SimpleNamespace(tool_calls=tool_calls, content=content)


class _Client:
    """Replays a scripted DeepSeek conversation: read, prioritize, validate, answer."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=self._messages.pop(0))])


def _scripted_client():
    ids = [task.id for task in TASKS]
    order = [{"id": task.id, "title": task.title, "reason": "fixture"} for task in reversed(TASKS)]
    return _Client(
        [
            _message([_tool_call("c1", "read_tasks", {})]),
            _message([_tool_call("c2", "prioritize_tasks", {"order": order})]),
            _message([_tool_call("c3", "validate_priority_result", {"priority": order, "known_ids": ids})]),
            _message(content="Done."),
        ]
    )


def test_full_run_writes_a_page_with_real_tasks_events_and_blocks():
    pages = []
    summary = run_dashboard(TODAY, lambda: TASKS, _events, _scripted_client(), pages.append)
    html = pages[0]
    assert summary["tasks"] == 3 and summary["events"] == 3 and summary["priority"] is True
    assert "Finish the Notion client" in html and "Lezione MA-AAI" in html
    assert "verificata" in html
    # The lesson on Tuesday 09:00-12:45 blocks the morning: the first study block
    # of the day starts after it.
    assert "12:45 – " in html


def test_full_run_without_llm_is_honest_about_the_priority():
    pages = []
    summary = run_dashboard(TODAY, lambda: TASKS, _events, None, pages.append)
    assert summary["priority"] is False and summary["reason"] == "no DEEPSEEK_API_KEY"
    assert "Nessuna priorità verificata" in pages[0]


def test_full_run_survives_a_failing_model():
    class Broken:
        chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: 1 / 0))

    pages = []
    summary = run_dashboard(TODAY, lambda: TASKS, _events, Broken(), pages.append)
    assert summary["priority"] is False and "model unavailable" in summary["reason"]
    assert len(pages) == 1


def test_titles_are_escaped_not_rendered():
    evil = [Task(id="x", title="<script>alert(1)</script>", status="Not Started")]
    pages = []
    run_dashboard(TODAY, lambda: evil, lambda s, e: [], None, pages.append)
    assert "<script>alert(1)</script>" not in pages[0]
    assert "&lt;script&gt;" in pages[0]


def test_sunday_card_has_no_blocks_and_oversized_task_is_reported():
    big = [Task(id="b", title="Thesis", status="Not Started", duration_minutes=12 * 60)]
    pages = []
    summary = run_dashboard(TODAY, lambda: big, lambda s, e: [], None, pages.append)
    assert summary["blocks"] == 0 and summary["unplaced"] == ["Thesis"]
    assert "non piazzato" in pages[0]
