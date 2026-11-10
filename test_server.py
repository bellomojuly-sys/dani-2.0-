"""Every endpoint with fake sources, a fake Notion write and fake models."""

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from ical_client import read_calendars
from live import Live
from models import AMSTERDAM
from notion_client import task_from_page
from server import create_app
from store import read_settings
from test_chat import FakeChat, FakeWhisper

with open("fixtures/notion_query.json") as handle:
    TASKS = [task_from_page(page) for page in json.load(handle)["results"]]
with open("fixtures/calendar.ics", "rb") as handle:
    ICS = handle.read()

NOW = datetime(2026, 11, 10, 13, 21, 5, tzinfo=AMSTERDAM)


class Rig:
    """One app with its fakes, so a test can look at what was written."""

    def __init__(self, tmp_path, chat=None, voice=None, pin=None, mark_done=None):
        self.done = []
        self.path = str(tmp_path / "settings.json")
        self.live = Live(
            lambda: list(TASKS),
            lambda start, end: read_calendars(["fixture"], start, end, fetch=lambda url: ICS),
            lambda tasks, today, context: {"ok": False, "reason": "no model in tests", "priority": None},
            clock=lambda: NOW,
        )
        self.live.refresh("all")
        app = create_app(self.live, mark_done or self.done.append, chat, voice, pin, self.path, web_dir=None)
        self.http = TestClient(app)

    def event(self, title):
        return next(e for e in self.http.get("/api/state").json()["events"] if e["title"] == title)


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def test_state_has_tasks_events_sources_and_chat_flags(rig):
    state = rig.http.get("/api/state").json()
    assert len(state["tasks"]) == 3 and state["sources"]["notion"]["ok"] is True
    assert state["hidden_events"] == []
    assert state["chat"] == {"text": False, "whisper": False}


def test_ticking_a_task_marks_it_done_in_notion_and_removes_it(rig):
    answer = rig.http.post("/api/tick", json={"kind": "task", "id": TASKS[0].id})
    assert answer.status_code == 200 and answer.json()["notion"] == "done"
    assert rig.done == [TASKS[0].id]
    assert TASKS[0].id not in [task["id"] for task in rig.http.get("/api/state").json()["tasks"]]


def test_ticking_an_unknown_task_writes_nothing(rig):
    assert rig.http.post("/api/tick", json={"kind": "task", "id": "invented"}).status_code == 404
    assert rig.done == []


def test_a_failed_notion_write_is_reported_and_the_task_stays(tmp_path):
    def refuse(task_id):
        raise RuntimeError("Notion answered HTTP 403: no update capability")

    rig = Rig(tmp_path, mark_done=refuse)
    answer = rig.http.post("/api/tick", json={"kind": "task", "id": TASKS[0].id})
    assert answer.status_code == 502 and "403" in answer.json()["detail"]
    assert len(rig.http.get("/api/state").json()["tasks"]) == 3


def test_ticking_an_event_hides_it_and_remembers_it_on_disk(rig):
    rig.http.put("/api/settings", json={"tickable_calendars": ["studio"]})
    call = rig.event("Call con Ruud")
    answer = rig.http.post("/api/tick", json={"kind": "event", "id": call["key"]})
    assert answer.status_code == 200 and "pending" in answer.json()["calendar"]
    state = rig.http.get("/api/state").json()
    assert "Call con Ruud" not in [event["title"] for event in state["events"]]
    assert [entry["title"] for entry in state["hidden_events"]] == ["Call con Ruud"]
    assert read_settings(rig.path).hidden_events[0].key == call["key"]  # survives a restart
    assert rig.done == []  # an event never touches Notion


def test_an_event_of_a_fixed_calendar_cannot_be_ticked(rig):
    rig.http.put("/api/settings", json={"tickable_calendars": ["personale"]})
    call = rig.event("Call con Ruud")
    answer = rig.http.post("/api/tick", json={"kind": "event", "id": call["key"]})
    assert answer.status_code == 403
    assert read_settings(rig.path).hidden_events == []


def test_unknown_event_and_wrong_kind_are_refused(rig):
    assert rig.http.post("/api/tick", json={"kind": "event", "id": "nope"}).status_code == 404
    assert rig.http.post("/api/tick", json={"kind": "email", "id": "x"}).status_code == 422


def test_unhide_brings_the_event_back(rig):
    rig.http.put("/api/settings", json={"tickable_calendars": ["studio"]})
    key = rig.event("Call con Ruud")["key"]
    rig.http.post("/api/tick", json={"kind": "event", "id": key})
    assert rig.http.post("/api/unhide", json={"key": key}).status_code == 200
    assert rig.event("Call con Ruud")["key"] == key


def test_settings_are_saved_and_keep_the_hidden_events(rig):
    rig.http.put("/api/settings", json={"tickable_calendars": ["studio"]})
    rig.http.post("/api/tick", json={"kind": "event", "id": rig.event("Call con Ruud")["key"]})
    body = {"context": "Max 7 ore al giorno", "tickable_calendars": ["studio", " personale ", ""],
            "cycle": {"start": "2026-11-08", "cycle_length": 30, "period_length": 4}}
    saved = rig.http.put("/api/settings", json=body).json()
    assert saved["context"] == "Max 7 ore al giorno"
    assert saved["tickable_calendars"] == ["studio", "personale"]
    assert len(saved["hidden_events"]) == 1  # the page cannot erase them by saving
    assert rig.http.get("/api/settings").json() == saved
    assert rig.http.get("/api/state").json()["cycle"]["phase"] == "in arrivo"


def test_invalid_settings_are_refused_and_nothing_is_saved(rig):
    answer = rig.http.put("/api/settings", json={"cycle": {"start": "2026-11-08", "cycle_length": 3}})
    assert answer.status_code == 422
    assert rig.http.get("/api/settings").json()["cycle"] is None


def test_started_today_confirms_the_cycle_and_keeps_the_lengths(rig):
    rig.http.put("/api/settings", json={"cycle": {"start": "2026-11-08", "cycle_length": 30, "period_length": 4}})
    cycle = rig.http.post("/api/cycle/started").json()
    assert cycle == {"start": "2026-11-10", "cycle_length": 30, "period_length": 4, "confirmed": True}
    state = rig.http.get("/api/state").json()["cycle"]
    assert (state["phase"], state["day"], state["estimated"]) == ("mestruale", 1, False)


def test_started_today_works_without_previous_cycle_settings(rig):
    assert rig.http.post("/api/cycle/started").json()["cycle_length"] == 28


def test_refresh_rereads_a_source_and_gmail_is_not_connected(rig):
    assert rig.http.post("/api/refresh", json={"source": "notion"}).json()["sources"]["notion"]["ok"] is True
    assert rig.http.post("/api/refresh", json={"source": "gmail"}).status_code == 409
    assert rig.http.post("/api/refresh", json={"source": "bevel"}).status_code == 422


def test_chat_answers_with_context_and_data_in_the_prompt(tmp_path):
    chat = FakeChat("Oggi hai la lezione alle 9.")
    rig = Rig(tmp_path, chat=chat)
    rig.http.put("/api/settings", json={"context": "Niente studio la domenica"})
    answer = rig.http.post("/api/chat", json={"message": "Cosa ho oggi?", "history": []})
    assert answer.json() == {"reply": "Oggi hai la lezione alle 9."}
    system = chat.seen["messages"][0]["content"]
    assert "Niente studio la domenica" in system and "Lezione MA-AAI" in system
    assert rig.done == []  # the chat never writes


def test_chat_refusals(tmp_path, rig):
    assert rig.http.post("/api/chat", json={"message": "ciao"}).status_code == 503  # no key
    with_model = Rig(tmp_path, chat=FakeChat(""))
    assert with_model.http.post("/api/chat", json={"message": "ciao"}).status_code == 502  # empty answer
    assert with_model.http.post("/api/chat", json={"message": ""}).status_code == 422


def test_transcribe_returns_text_and_refuses_when_not_set_up(tmp_path, rig):
    assert rig.http.post("/api/transcribe", content=b"audio").status_code == 503
    voice = FakeWhisper("sposta la call")
    with_voice = Rig(tmp_path, voice=voice)
    answer = with_voice.http.post("/api/transcribe", content=b"audio", headers={"content-type": "audio/mp4"})
    assert answer.json() == {"text": "sposta la call"}
    assert voice.seen["file"] == ("voice.mp4", b"audio")
    assert with_voice.http.post("/api/transcribe", content=b"").status_code == 422


def test_with_a_pin_every_api_call_needs_it(tmp_path):
    rig = Rig(tmp_path, pin="4821")
    assert rig.http.get("/api/state").status_code == 401
    assert rig.http.get("/api/state", headers={"X-Dani-Pin": "0000"}).status_code == 401
    assert rig.http.post("/api/tick", json={"kind": "task", "id": TASKS[0].id}).status_code == 401
    assert rig.done == []
    assert rig.http.get("/api/state", headers={"X-Dani-Pin": "4821"}).status_code == 200
