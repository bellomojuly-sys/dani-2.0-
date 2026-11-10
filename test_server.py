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

    def __init__(self, tmp_path, chat=None, voice=None, pin=None, mark_done=None, prioritize=None):
        self.done = []
        self.path = str(tmp_path / "settings.json")
        self.live = Live(
            lambda: list(TASKS),
            lambda start, end: read_calendars(["fixture"], start, end, fetch=lambda url: ICS),
            prioritize or (lambda tasks, today, context: {"ok": False, "reason": "no model in tests", "priority": None}),
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
    assert saved.pop("priority_recalculated") is True
    assert rig.http.get("/api/settings").json() == saved
    assert rig.http.get("/api/state").json()["cycle"]["phase"] == "in arrivo"


def test_saving_a_new_context_reasks_the_priority_at_once(tmp_path):
    asked = []

    def prioritize(tasks, today, context):
        asked.append(context)
        rows = [{"id": task.id, "reason": "test"} for task in tasks]
        return {"ok": True, "reason": "verified", "priority": rows}

    rig = Rig(tmp_path, prioritize=prioritize)
    answer = rig.http.put("/api/settings", json={"context": "Prima gli esami"}).json()
    assert answer["priority_recalculated"] is True
    assert asked == ["Prima gli esami"]  # the model saw the new context, now
    assert rig.http.get("/api/state").json()["priority"]["ok"] is True


def test_saving_the_same_context_twice_asks_the_model_once(tmp_path):
    asked = []

    def prioritize(tasks, today, context):
        asked.append(context)
        return {"ok": True, "reason": "verified",
                "priority": [{"id": task.id, "reason": "test"} for task in tasks]}

    rig = Rig(tmp_path, prioritize=prioritize)
    rig.http.put("/api/settings", json={"context": "Prima gli esami"})
    rig.http.put("/api/settings", json={"context": "Prima gli esami"})
    assert asked == ["Prima gli esami"]  # update_priority skipped the second call


def test_a_priority_failure_does_not_lose_the_save(tmp_path):
    def refuse(tasks, today, context):
        raise RuntimeError("model down")

    rig = Rig(tmp_path, prioritize=refuse)
    answer = rig.http.put("/api/settings", json={"context": "Prima gli esami"})
    assert answer.status_code == 200
    assert answer.json()["priority_recalculated"] is False
    assert read_settings(rig.path).context == "Prima gli esami"  # saved on disk anyway


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


# --- Google Calendar connected in writing ------------------------------------------

from models import Event  # noqa: E402
from test_chat import FakeToolChat  # noqa: E402


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=AMSTERDAM)


class CalendarRig:
    """An app whose events come "from the API" (they have ids) and whose
    calendar writes are recorded and applied to an in-memory calendar."""

    def __init__(self, tmp_path, chat=None, fail=None):
        self.calendar = [
            Event(calendar="personale", title="Palestra", uid="gym", api_id="gym-1", calendar_id="c-p", start=at(11, 7, 30), end=at(11, 9)),
            Event(calendar="studio", title="Call con Ruud", uid="call", api_id="call-1", calendar_id="c-s", start=at(12, 15), end=at(12, 15, 30)),
            Event(calendar="lavoro", title="Turno ristorante", uid="shift", api_id="shift-1", calendar_id="c-l", start=at(12, 17), end=at(12, 23)),
            Event(calendar="studio", title="Blocco iCal", uid="ical", start=at(13, 10), end=at(13, 11)),  # no api_id
        ]
        self.deleted, self.moved, self.fail = [], [], fail
        self.path = str(tmp_path / "settings.json")
        self.live = Live(lambda: [], lambda start, end: list(self.calendar),
                         lambda tasks, today, context: {"ok": False, "reason": "none", "priority": None}, clock=lambda: NOW)
        self.live.refresh("all")
        app = create_app(self.live, lambda task_id: None, chat, None, None, self.path, web_dir=None,
                         delete_event=self._delete, move_event=self._move)
        self.http = TestClient(app)

    def _delete(self, event):
        if self.fail:
            raise self.fail
        self.deleted.append(event.api_id)
        self.calendar = [e for e in self.calendar if e.api_id != event.api_id]

    def _move(self, event, start, end):
        if self.fail:
            raise self.fail
        self.moved.append((event.api_id, start, end))
        self.calendar = [e.model_copy(update={"start": start, "end": end}) if e.api_id == event.api_id else e for e in self.calendar]

    def key(self, title):
        return next(e.key for e in self.calendar if e.title == title)


def test_ticking_an_api_event_deletes_it_from_the_calendar(tmp_path):
    rig = CalendarRig(tmp_path)
    answer = rig.http.post("/api/tick", json={"kind": "event", "id": rig.key("Palestra")})
    assert answer.json()["calendar"] == "deleted" and rig.deleted == ["gym-1"]
    state = rig.http.get("/api/state").json()
    assert "Palestra" not in [e["title"] for e in state["events"]] and state["hidden_events"] == []
    assert state["calendar_write"] == {"delete": True, "move": True}


def test_a_fixed_calendar_is_never_deleted_and_an_ical_event_is_only_hidden(tmp_path):
    rig = CalendarRig(tmp_path)
    assert rig.http.post("/api/tick", json={"kind": "event", "id": rig.key("Turno ristorante")}).status_code == 403
    answer = rig.http.post("/api/tick", json={"kind": "event", "id": rig.key("Blocco iCal")})
    assert "pending" in answer.json()["calendar"]
    assert rig.deleted == []


def test_a_refused_delete_is_reported_and_the_event_stays(tmp_path):
    rig = CalendarRig(tmp_path, fail=RuntimeError("Google Calendar answered HTTP 403: need writer access"))
    answer = rig.http.post("/api/tick", json={"kind": "event", "id": rig.key("Palestra")})
    assert answer.status_code == 502 and "403" in answer.json()["detail"]
    assert "Palestra" in [e["title"] for e in rig.http.get("/api/state").json()["events"]]


def _move_call(event, new_start):
    return FakeToolChat("", [("propose_move", json.dumps({"event": event, "new_start": new_start}))])


def test_a_proposal_changes_nothing_until_confirmed_and_confirming_twice_changes_nothing_more(tmp_path):
    rig = CalendarRig(tmp_path, chat=_move_call("e2", "2026-11-12T10:00"))  # e2 = Call con Ruud
    answer = rig.http.post("/api/chat", json={"message": "sposta la call alle 10"}).json()
    proposal = answer["proposal"]
    assert "Propongo di spostare «Call con Ruud»" in answer["reply"] and answer["reply"].endswith("Confermi?")
    assert proposal["new_start"] == "2026-11-12T10:00:00+01:00" and proposal["warnings"] == []
    assert rig.moved == []  # the calendar is unchanged after a proposal

    done = rig.http.post("/api/confirm", json={"id": proposal["id"]})
    assert done.json() == {"ok": True, "title": "Call con Ruud", "read_back": True}
    assert rig.moved == [("call-1", at(12, 10), at(12, 10, 30))]
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 404
    assert len(rig.moved) == 1


def test_a_proposal_onto_a_shift_carries_the_warning(tmp_path):
    rig = CalendarRig(tmp_path, chat=_move_call("e2", "2026-11-12T17:00"))
    answer = rig.http.post("/api/chat", json={"message": "sposta la call alle 17"}).json()
    assert answer["proposal"]["warnings"] == ["si sovrappone a «Turno ristorante» (17:00–23:00, lavoro)"]


def test_a_move_the_code_refuses_gives_a_reply_and_no_proposal(tmp_path):
    rig = CalendarRig(tmp_path, chat=_move_call("e3", "2026-11-13T17:00"))  # e3 = the shift
    answer = rig.http.post("/api/chat", json={"message": "sposta il turno"}).json()
    assert "proposal" not in answer and "impegno fisso" in answer["reply"]


def test_rejecting_removes_the_proposal(tmp_path):
    rig = CalendarRig(tmp_path, chat=_move_call("e2", "2026-11-12T10:00"))
    proposal = rig.http.post("/api/chat", json={"message": "sposta"}).json()["proposal"]
    assert rig.http.post("/api/reject", json={"id": proposal["id"]}).json() == {"ok": True}
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 404
    assert rig.moved == []


def test_confirm_refuses_when_the_event_changed_or_the_write_fails(tmp_path):
    rig = CalendarRig(tmp_path, chat=_move_call("e2", "2026-11-12T10:00"))
    proposal = rig.http.post("/api/chat", json={"message": "sposta"}).json()["proposal"]
    rig.calendar = [e.model_copy(update={"start": at(12, 14), "end": at(12, 14, 30)}) if e.uid == "call" else e for e in rig.calendar]
    rig.live.refresh("calendar")  # she moved it by hand in the meantime
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 409
    assert rig.moved == []

    failing = CalendarRig(tmp_path, chat=_move_call("e2", "2026-11-12T10:00"))
    proposal = failing.http.post("/api/chat", json={"message": "sposta"}).json()["proposal"]
    failing.fail = RuntimeError("Google Calendar answered HTTP 403: need writer access")
    assert failing.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 502
    failing.fail = None  # the proposal is still there: she can confirm again once it is fixed
    assert failing.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 200


def test_an_ical_event_cannot_be_moved(tmp_path):
    rig = CalendarRig(tmp_path, chat=_move_call("e4", "2026-11-13T12:00"))  # e4 = Blocco iCal
    proposal = rig.http.post("/api/chat", json={"message": "sposta"}).json()["proposal"]
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 409
    assert rig.moved == []


def test_without_calendar_write_the_chat_only_talks_and_confirm_is_refused(tmp_path):
    chat = FakeChat("Non posso ancora spostarlo.")
    rig = Rig(tmp_path, chat=chat)
    assert rig.http.post("/api/chat", json={"message": "sposta la call"}).json() == {"reply": "Non posso ancora spostarlo."}
    assert "not connected yet" in chat.seen["messages"][0]["content"]
    assert rig.http.post("/api/confirm", json={"id": "x"}).status_code == 404
    assert rig.http.get("/api/state").json()["calendar_write"] == {"delete": False, "move": False}
