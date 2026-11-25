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
    assert voice.seen["file"] == ("voice.m4a", b"audio")
    with_voice.http.post("/api/transcribe", content=b"audio", headers={"content-type": "audio/webm"})
    assert voice.seen["file"] == ("voice.webm", b"audio")
    assert with_voice.http.post("/api/transcribe", content=b"").status_code == 422


def test_with_a_pin_every_api_call_needs_it(tmp_path):
    rig = Rig(tmp_path, pin="4821")
    assert rig.http.get("/api/state").status_code == 401
    assert rig.http.get("/api/state", headers={"X-Dani-Pin": "0000"}).status_code == 401
    assert rig.http.post("/api/tick", json={"kind": "task", "id": TASKS[0].id}).status_code == 401
    assert rig.done == []
    assert rig.http.get("/api/state", headers={"X-Dani-Pin": "4821"}).status_code == 200


# --- Google Calendar connected in writing ------------------------------------------

from models import Event, Task  # noqa: E402
from test_chat import FakeToolChat  # noqa: E402


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=AMSTERDAM)


class CalendarRig:
    """An app whose events come "from the API" (they have ids) and whose
    calendar writes are recorded and applied to an in-memory calendar."""

    def __init__(self, tmp_path, chat=None, fail=None, tasks=None):
        self.calendar = [
            Event(calendar="personale", title="Palestra", uid="gym", api_id="gym-1", calendar_id="c-p", start=at(11, 7, 30), end=at(11, 9)),
            Event(calendar="studio", title="Call con Ruud", uid="call", api_id="call-1", calendar_id="c-s", start=at(12, 15), end=at(12, 15, 30)),
            Event(calendar="lavoro", title="Turno ristorante", uid="shift", api_id="shift-1", calendar_id="c-l", start=at(12, 17), end=at(12, 23)),
            Event(calendar="studio", title="Blocco iCal", uid="ical", start=at(13, 10), end=at(13, 11)),  # no api_id
        ]
        self.tasks = list(tasks or [])
        self.deleted, self.moved, self.created, self.created_tasks, self.fail = [], [], [], [], fail
        self.path = str(tmp_path / "settings.json")
        self.live = Live(lambda: list(self.tasks), lambda start, end: list(self.calendar),
                         lambda tasks, today, context: {"ok": False, "reason": "none", "priority": None}, clock=lambda: NOW)
        self.live.refresh("all")
        app = create_app(self.live, lambda task_id: None, chat, None, None, self.path, web_dir=None,
                         delete_event=self._delete, move_event=self._move, create_block=self._create,
                         create_task=self._create_task)
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

    def _create(self, title, start, end):
        if self.fail:
            raise self.fail
        api_id = f"blk-{len(self.created) + 1}"
        self.created.append((title, start, end))
        self.calendar.append(Event(calendar="studio", title=title, uid=api_id, api_id=api_id, calendar_id="c-s", start=start, end=end))
        return api_id

    def _create_task(self, title, area, deadline, duration_minutes):
        if self.fail:
            raise self.fail
        made = Task(id=f"nt-{len(self.created_tasks) + 1}", title=title, area=area,
                    status="Not Started", deadline=deadline, duration_minutes=duration_minutes)
        self.created_tasks.append(made)
        self.tasks.append(made)
        return made

    def key(self, title):
        return next(e.key for e in self.calendar if e.title == title)


def test_ticking_an_api_event_deletes_it_from_the_calendar(tmp_path):
    rig = CalendarRig(tmp_path)
    answer = rig.http.post("/api/tick", json={"kind": "event", "id": rig.key("Palestra")})
    assert answer.json()["calendar"] == "deleted" and rig.deleted == ["gym-1"]
    state = rig.http.get("/api/state").json()
    assert "Palestra" not in [e["title"] for e in state["events"]] and state["hidden_events"] == []
    assert state["calendar_write"] == {"delete": True, "move": True, "create_block": True}


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
    assert rig.http.get("/api/state").json()["calendar_write"] == {"delete": False, "move": False, "create_block": False}


# --- study blocks: accept, move, reject (D2-052, D2-053) ----------------------

from models import Task  # noqa: E402

STUDY_TASK = Task(id="t-study", title="Studio AI", status="In Progress", duration_minutes=60)


def test_accepting_a_block_changes_nothing_until_confirmed_and_confirming_twice_adds_nothing(tmp_path):
    rig = CalendarRig(tmp_path, tasks=[STUDY_TASK])
    answer = rig.http.post("/api/block", json={"task_id": "t-study", "start": "2026-11-12T10:00"}).json()
    assert "Propongo di creare il blocco di studio «Studio AI»" in answer["reply"]
    assert answer["proposal"]["warnings"] == []
    assert rig.created == []  # the calendar is unchanged after a proposal

    done = rig.http.post("/api/confirm", json={"id": answer["proposal"]["id"]})
    assert done.json() == {"ok": True, "title": "Studio AI", "read_back": True}
    assert rig.created == [("Studio AI", at(12, 10), at(12, 11))]
    assert rig.http.post("/api/confirm", json={"id": answer["proposal"]["id"]}).status_code == 404
    assert len(rig.created) == 1


def test_a_block_moved_onto_a_shift_is_flagged_before_her_yes(tmp_path):
    rig = CalendarRig(tmp_path, tasks=[STUDY_TASK])
    answer = rig.http.post("/api/block", json={"task_id": "t-study", "start": "2026-11-12T16:30"}).json()
    assert answer["proposal"]["warnings"] == ["si sovrappone a «Turno ristorante» (17:00–23:00, lavoro)"]
    assert rig.created == []


def test_block_requests_the_code_refuses_and_without_calendar_write(tmp_path):
    rig = CalendarRig(tmp_path, tasks=[STUDY_TASK])
    assert rig.http.post("/api/block", json={"task_id": "ghost", "start": "2026-11-12T10:00"}).status_code == 422
    read_only = Rig(tmp_path)  # no create_block wired
    answer = read_only.http.post("/api/block", json={"task_id": TASKS[0].id, "start": "2026-11-12T10:00"})
    assert answer.status_code == 503
    assert rig.created == [] and read_only.done == []


def test_confirm_refuses_a_block_whose_task_was_closed_in_the_meantime(tmp_path):
    rig = CalendarRig(tmp_path, tasks=[STUDY_TASK])
    proposal = rig.http.post("/api/block", json={"task_id": "t-study", "start": "2026-11-12T10:00"}).json()["proposal"]
    rig.tasks = []
    rig.live.refresh("notion")  # the task was done (or removed) after the proposal
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 409
    assert rig.created == []


def test_a_failed_calendar_write_keeps_the_block_proposal(tmp_path):
    rig = CalendarRig(tmp_path, tasks=[STUDY_TASK])
    proposal = rig.http.post("/api/block", json={"task_id": "t-study", "start": "2026-11-12T10:00"}).json()["proposal"]
    rig.fail = RuntimeError("Google Calendar answered HTTP 403: need writer access")
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 502
    rig.fail = None  # she can confirm again once it is fixed
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 200


def test_a_rejected_block_is_not_proposed_again_and_restore_undoes_it(rig):
    blocks = rig.http.get("/api/state").json()["blocks"]
    rejected_id = blocks[0]["task_id"]
    assert rig.http.post("/api/block/reject", json={"task_id": rejected_id}).json() == {"ok": True}
    state = rig.http.get("/api/state").json()
    assert rejected_id not in {block["task_id"] for block in state["blocks"]}
    assert read_settings(rig.path).rejected_blocks == [rejected_id]  # survives a restart
    rig.http.post("/api/block/restore", json={"task_id": rejected_id})
    assert rejected_id in {block["task_id"] for block in rig.http.get("/api/state").json()["blocks"]}


# --- a new Notion task from the chat (D2-055) ------------------------------------


def _task_call(arguments):
    return FakeToolChat("", [("propose_task", json.dumps(arguments))])


def test_a_task_proposal_writes_nothing_until_confirmed_then_creates_and_reads_back(tmp_path):
    existing = Task(id="t-1", title="Studiare F6", area="University", status="Not Started")
    rig = CalendarRig(tmp_path, tasks=[existing],
                      chat=_task_call({"title": "comprare le lenti", "area": "university", "deadline": "2026-11-20"}))
    answer = rig.http.post("/api/chat", json={"message": "nuovo task: comprare le lenti"}).json()
    proposal = answer["proposal"]
    assert answer["reply"].startswith("Propongo di creare il task «comprare le lenti»")
    assert answer["reply"].endswith("Confermi?")
    assert proposal["kind"] == "task" and proposal["area"] == "University"
    assert rig.created_tasks == []  # Notion is unchanged after a proposal

    done = rig.http.post("/api/confirm", json={"id": proposal["id"]})
    assert done.json() == {"ok": True, "title": "comprare le lenti", "read_back": True}
    assert [made.title for made in rig.created_tasks] == ["comprare le lenti"]
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 404
    assert len(rig.created_tasks) == 1  # confirming twice changes nothing more


def test_an_unknown_area_is_refused_in_the_chat_and_nothing_is_proposed(tmp_path):
    rig = CalendarRig(tmp_path, chat=_task_call({"title": "x", "area": "Zumba"}))
    answer = rig.http.post("/api/chat", json={"message": "nuovo task: x"}).json()
    assert "Non posso proporre questo task" in answer["reply"] and "proposal" not in answer
    assert rig.created_tasks == []


def test_a_failed_notion_create_is_reported_and_the_proposal_survives(tmp_path):
    rig = CalendarRig(tmp_path, chat=_task_call({"title": "pagare DUO"}))
    proposal = rig.http.post("/api/chat", json={"message": "nuovo task: pagare DUO"}).json()["proposal"]
    rig.fail = RuntimeError("Notion answered HTTP 502: boom")
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 502
    assert rig.created_tasks == []
    rig.fail = None  # she can confirm again once it is fixed
    assert rig.http.post("/api/confirm", json={"id": proposal["id"]}).status_code == 200


# --- D2-056: the chat reads by itself and says what it read ----------------------


def test_chat_with_read_tools_returns_the_answer_and_what_was_read(tmp_path):
    from reader import build_read_tools
    from test_chat import ScriptedChat

    rig = Rig(tmp_path)
    chat = ScriptedChat([("", [("read_tasks", '{"area": "University"}')]), ("Hai tre task.", [])])
    tools = build_read_tools(lambda start, end: [], lambda: list(rig.live.tasks))
    app = create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None, read_tools=tools)
    answer = TestClient(app).post("/api/chat", json={"message": "cosa devo fare per l'università?", "history": []})
    assert answer.status_code == 200
    assert answer.json() == {"reply": "Hai tre task.", "reads": [{"tool": "read_tasks", "arguments": {"area": "University"}}]}
    assert rig.done == []  # reading never writes


# --- D2-057: token monitoring ----------------------------------------------------


def test_usage_endpoint_reports_totals_or_says_it_is_off(tmp_path):
    from types import SimpleNamespace

    from usage import UsageLog

    rig = Rig(tmp_path)
    assert rig.http.get("/api/usage").json() == {"enabled": False}
    log = UsageLog(lambda: NOW.date())
    log.record("deepseek-flash", "chat", SimpleNamespace(prompt_tokens=900, completion_tokens=80))
    app = create_app(rig.live, rig.done.append, None, None, "1234", rig.path, web_dir=None, usage_log=log)
    http = TestClient(app)
    assert http.get("/api/usage").status_code == 401  # behind the PIN like every /api route
    body = http.get("/api/usage", headers={"X-Dani-Pin": "1234"}).json()
    assert body["enabled"] is True and body["today"] == {"input": 900, "output": 80, "calls": 1}


def test_state_says_which_commit_is_live(rig, monkeypatch):
    assert rig.http.get("/api/state").json()["version"] == "locale"
    monkeypatch.setenv("RENDER_GIT_COMMIT", "0fba9fa1234567")
    assert rig.http.get("/api/state").json()["version"] == "0fba9fa"


def test_the_page_and_its_code_are_never_served_from_an_old_cache(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html></html>")
    (web / "app.js").write_text("// code")
    rig = Rig(tmp_path)
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=str(web))
    http = TestClient(app)
    assert http.get("/").headers["cache-control"] == "no-cache"
    assert http.get("/app.js").headers["cache-control"] == "no-cache"
    assert "cache-control" not in http.get("/api/state").headers


def test_the_life_page_goes_into_the_chat_prompt_and_its_status_into_the_state(tmp_path):
    from context import LifeContext

    rig = Rig(tmp_path)
    life = LifeContext(lambda: "Domenica niente studio. Obiettivo: lavoro entro dicembre.")
    life.refresh()
    chat = FakeChat("Va bene.")
    app = create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None, life=life)
    http = TestClient(app)
    assert http.post("/api/chat", json={"message": "pianifica", "history": []}).status_code == 200
    assert "lavoro entro dicembre" in chat.seen["messages"][0]["content"]
    assert http.get("/api/state").json()["life_context"] == {"on": True, "chars": 57, "error": None}


# --- D2-059: a plan from the chat, confirmed block by block ----------------------


def test_a_plan_from_the_chat_is_checked_on_the_whole_period_and_written_only_after_yes(tmp_path):
    from models import Event
    from test_chat import ScriptedChat

    rig = Rig(tmp_path)
    asked, created = [], []
    december_shift = Event(calendar="lavoro", title="Turno", start=datetime(2026, 12, 2, 17, 0, tzinfo=AMSTERDAM),
                           end=datetime(2026, 12, 2, 23, 0, tzinfo=AMSTERDAM))

    def fetch(start, end):
        asked.append((start, end))
        return [december_shift] if start.month == 12 else []

    rig.live.fetch_events = fetch
    plan = json.dumps({"blocks": [
        {"title": "Betsy · BT-003", "start": "2026-12-01T10:00", "end": "2026-12-01T12:00", "why": "consegna 1 feb"},
        {"title": "Lettura", "start": "2026-12-02T15:30", "end": "2026-12-02T16:30"}]})
    chat = ScriptedChat([("Ecco dicembre.", [("propose_plan", plan)])])
    app = create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None,
                     create_block=lambda title, start, end: created.append(title) or "new-id")
    http = TestClient(app)
    body = http.post("/api/chat", json={"message": "pianifica i primi di dicembre", "history": []}).json()
    assert (datetime(2026, 12, 1).date(), datetime(2026, 12, 3).date()) in asked  # the whole period, end included
    assert [p["title"] for p in body["proposals"]] == ["Betsy · BT-003", "Lettura"]
    assert body["proposals"][1]["warnings"] == ["finisce dopo le 16:00 (giorno di turno)"]
    assert "2 blocchi" in body["reply"] and "1 ha un avviso" in body["reply"]
    assert created == []  # a proposal writes nothing
    first = body["proposals"][0]["id"]
    assert http.post("/api/confirm", json={"id": first}).json()["ok"] is True
    assert created == ["Betsy · BT-003"]
    assert http.post("/api/confirm", json={"id": first}).status_code == 404  # twice changes nothing more
    assert created == ["Betsy · BT-003"]


def test_a_broken_plan_from_the_model_writes_nothing(tmp_path):
    from test_chat import ScriptedChat

    rig = Rig(tmp_path)
    created = []
    chat = ScriptedChat([("", [("propose_plan", '{"blocks": []}')])])
    app = create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None,
                     create_block=lambda title, start, end: created.append(title) or "x")
    body = TestClient(app).post("/api/chat", json={"message": "pianifica", "history": []}).json()
    assert body["reply"].startswith("Non posso proporre questo piano") and "proposals" not in body
    assert created == []


# --- D2-060: the week's focus -----------------------------------------------------


def test_focus_endpoints_save_the_answer_and_put_it_in_the_chat_prompt(tmp_path):
    from focus import WeekFocus

    rig = Rig(tmp_path)  # NOW is Tuesday 10 November: the question is about this week
    chat = FakeChat("Va bene.")
    focus = WeekFocus()
    http = TestClient(create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None, week_focus=focus))
    first = http.get("/api/focus").json()
    assert first["ask"] is True and first["ask_week"] == "2026-11-09" and "questa settimana" in first["question"]
    saved = http.put("/api/focus", json={"week": "2026-11-09", "text": "demo dello Sprint 3"}).json()
    assert saved["ask"] is False and saved["this_focus"] == "demo dello Sprint 3"
    http.post("/api/chat", json={"message": "cosa faccio oggi?", "history": []})
    assert "demo dello Sprint 3" in chat.seen["messages"][0]["content"]
    assert http.put("/api/focus", json={"week": "2026-11-10", "text": "x"}).status_code == 422  # not a Monday
    assert TestClient(create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None)).get(
        "/api/focus").json() == {"enabled": False}


# --- D2-061: the morning briefing -------------------------------------------------


def test_briefing_is_shown_and_sent_once_per_day_behind_the_pin(tmp_path):
    rig = Rig(tmp_path)
    sent = []
    app = create_app(rig.live, rig.done.append, None, None, "1234", rig.path, web_dir=None,
                     send_note=lambda title, text, at=None, priority=None, link=None: sent.append((title, text, at)))
    http = TestClient(app)
    pin = {"X-Dani-Pin": "1234"}
    assert http.post("/api/briefing/send").status_code == 401  # the schedule needs the PIN too
    shown = http.get("/api/briefing", headers=pin).json()
    assert shown["title"] == "Buongiorno July · martedì 10 novembre" and shown["channel"] is True
    assert "Lezione MA-AAI" in shown["text"] and shown["text"].endswith("July, oggi come stai?")
    assert http.post("/api/briefing/send", headers=pin).json()["sent"] is True
    assert http.post("/api/briefing/send", headers=pin).json() == {"sent": False, "reason": "già inviato oggi"}
    assert http.post("/api/briefing/send?force=true", headers=pin).json()["sent"] is True
    briefings = [entry for entry in sent if entry[2] is None]
    assert len(briefings) == 2  # the briefing itself, twice (once forced)


def test_without_a_channel_the_briefing_is_shown_but_not_sent(rig):
    assert rig.http.get("/api/briefing").json()["channel"] is False
    assert rig.http.post("/api/briefing/send").status_code == 503


def test_a_failed_send_is_reported_and_can_be_retried(tmp_path):
    rig = Rig(tmp_path)
    calls = []

    def flaky(title, text, at=None, priority=None, link=None):
        calls.append(title)
        if len(calls) == 1:
            raise RuntimeError("ntfy answered HTTP 502")

    http = TestClient(create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, send_note=flaky))
    assert http.post("/api/briefing/send").status_code == 502
    assert http.post("/api/briefing/send").json()["sent"] is True  # not marked as sent after a failure


def test_the_character_page_goes_into_every_chat_prompt(tmp_path):
    from context import LifeContext

    rig = Rig(tmp_path)
    character = LifeContext(lambda: "Dani chiama Giulia Chief per il lavoro.")
    character.refresh()
    chat = FakeChat("Ok, Chief.")
    http = TestClient(create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None, character=character))
    http.post("/api/chat", json={"message": "ciao", "history": []})
    assert "Dani chiama Giulia Chief" in chat.seen["messages"][0]["content"]


# --- D2-063: the day's messages are scheduled with the briefing -------------------


def test_the_morning_send_schedules_the_days_reminders_with_a_delivery_time(tmp_path):
    rig = Rig(tmp_path)  # NOW is 13:21 on Tuesday 10 November
    sent = []
    http = TestClient(create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None,
                                 send_note=lambda title, text, at=None, priority=None, link=None: sent.append((title, at))))
    body = http.post("/api/briefing/send").json()
    later = [(title, at) for title, at in sent if at is not None]
    assert body["scheduled"] == len(later) and body["not_scheduled"] == 0
    assert all(at > NOW for _, at in later)  # nothing in the past
    assert later[-1][0] == "Com'è andata oggi?"


# --- D2-064: the mood diary --------------------------------------------------------


def test_how_she_feels_is_saved_from_the_chat_and_from_the_home(tmp_path):
    from mood import MoodLog
    from test_chat import ScriptedChat

    rig = Rig(tmp_path)
    log = MoodLog()
    chat = ScriptedChat([("Allora oggi andiamo piano, July.", [("record_mood", '{"energy": 2, "sleep": 5, "note": "stanca"}')]),
                         ("Va bene.", [])])
    http = TestClient(create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None, mood_log=log))
    body = http.post("/api/chat", json={"message": "sono stanca, ho dormito 5 ore", "history": []}).json()
    assert body["mood"] == {"energy": 2, "sleep": 5.0, "note": "stanca"} and body["reply"].startswith("Allora")
    http.post("/api/chat", json={"message": "cosa faccio?", "history": []})
    assert "bare minimum" in chat.requests[1]["messages"][0]["content"]  # the low day reaches the next answer
    assert http.put("/api/mood", json={"energy": 9}).status_code == 422
    assert http.put("/api/mood", json={"energy": 4}).json()["mood"]["energy"] == 4
    assert rig.done == []  # the diary never touches her Tasks


# --- D2-065: forecasts ---------------------------------------------------------------


def test_forecast_is_served_put_in_the_chat_prompt_and_at_risk_lines_reach_the_briefing(tmp_path):
    from models import Task

    rig = Rig(tmp_path)  # NOW: Tuesday 10 November 13:21
    rig.live.tasks = [Task(id="big", title="Consegna enorme", status="Not Started",
                           deadline=datetime(2026, 11, 10).date(), duration_minutes=900)]
    chat = FakeChat("Ok.")
    http = TestClient(create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None))
    body = http.get("/api/forecast").json()
    assert body["rows"][0]["status"] == "a rischio" and body["error"] is None
    http.post("/api/chat", json={"message": "come sono messa?", "history": []})
    assert "Forecast of her deadlines" in chat.seen["messages"][0]["content"]
    assert "Attenzione: Entro il 2026-11-10" in http.get("/api/briefing").json()["text"]


def test_a_tap_on_the_briefing_opens_the_morning_call(tmp_path):
    rig = Rig(tmp_path)
    links = []
    http = TestClient(create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None,
                                 send_note=lambda title, text, at=None, priority=None, link=None: links.append((at, link))))
    http.post("/api/briefing/send")
    assert links[0] == (None, "buongiorno")  # the briefing itself opens #buongiorno
    assert all(link is None for at, link in links[1:])  # reminders open the app normally


# --- D2-067: the wake-up guard ---------------------------------------------------------


def test_wake_counts_snoozes_escalates_and_needs_the_pin(tmp_path):
    rig = Rig(tmp_path)
    sent = []
    http = TestClient(create_app(rig.live, rig.done.append, None, None, "1234", rig.path, web_dir=None,
                                 send_note=lambda title, text, at=None, priority=None, link=None: sent.append((title, priority))))
    pin = {"X-Dani-Pin": "1234"}
    assert http.post("/api/wake", json={"event": "snoozed"}).status_code == 401
    for _ in range(3):
        body = http.post("/api/wake", json={"event": "snoozed"}, headers=pin).json()
    assert body == {"event": "snoozed", "snoozes": 3, "sent": 3}
    assert sent[-3][0] == "Chief. Alzati." and sent[-3][1] == 5
    assert http.post("/api/wake", json={"event": "stopped"}, headers=pin).json()["sent"] == 1
    assert sent[-1][0] == "Brava, July"
    assert http.post("/api/wake", json={"event": "dormo"}, headers=pin).status_code == 422


# --- D2-068: the model priority only on her action ------------------------------------


def test_priority_is_asked_only_when_she_presses_reorder(tmp_path):
    asked = []

    def prioritize(tasks, today, context):
        asked.append(today)
        return {"ok": False, "reason": "test", "priority": None}

    rig = Rig(tmp_path, chat=FakeChat("x"), prioritize=prioritize)
    assert asked == []  # a start (or a wake-up of Render) asks nothing
    assert rig.http.get("/api/state").json()["priority"]["reason"].startswith("regola")
    assert rig.http.post("/api/priority").json() == {"ok": False, "reason": "test"}
    rig.http.post("/api/priority")
    assert len(asked) == 2  # forced every time she presses it


def test_reorder_needs_the_model(rig):
    assert rig.http.post("/api/priority").status_code == 503


# --- D2-069: Telegram -------------------------------------------------------------------


class FakeTelegram(dict):
    def __init__(self, chat_id="42"):
        self.sent, self.to_others, self.answers = [], [], []
        super().__init__(send=lambda text, buttons=None: self.sent.append((text, buttons)),
                         send_to=lambda chat_id, text: self.to_others.append((chat_id, text)),
                         answer=lambda callback_id, text: self.answers.append(text),
                         voice=lambda file_id: b"ogg-bytes", chat_id=chat_id, secret="s3cret")


def _post(http, update, secret="s3cret", header="s3cret"):
    return http.post(f"/telegram/{secret}", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": header})


def test_telegram_needs_the_secret_and_talks_only_to_giulia(tmp_path):
    rig, tg = Rig(tmp_path), FakeTelegram()
    http = TestClient(create_app(rig.live, rig.done.append, FakeChat("Ciao July."), None, None, rig.path, web_dir=None, telegram=tg))
    assert _post(http, {}, secret="wrong").status_code == 404
    assert _post(http, {}, header="wrong").status_code == 404
    _post(http, {"message": {"chat": {"id": 7}, "text": "chi sei?"}})
    assert tg.sent == [] and tg.to_others == []  # a stranger gets nothing
    _post(http, {"message": {"chat": {"id": 42}, "text": "come sto messa oggi?"}})
    assert tg.sent == [("Ciao July.", None)]


def test_before_the_chat_id_is_set_dani_only_says_it(tmp_path):
    rig, tg = Rig(tmp_path), FakeTelegram(chat_id=None)
    http = TestClient(create_app(rig.live, rig.done.append, FakeChat("x"), None, None, rig.path, web_dir=None, telegram=tg))
    _post(http, {"message": {"chat": {"id": 42}, "text": "ciao"}})
    assert tg.to_others == [("42", "Ciao! Il tuo chat id è 42: mettilo su Render come TELEGRAM_CHAT_ID.")]
    assert tg.sent == []


def test_a_voice_message_goes_through_whisper_and_a_proposal_comes_with_buttons(tmp_path):
    from test_chat import FakeWhisper, ScriptedChat

    rig, tg = Rig(tmp_path), FakeTelegram()
    task = '{"title": "Comprare le lenti", "area": "Personal"}'
    rig.live.tasks[0] = rig.live.tasks[0].model_copy(update={"area": "Personal"})
    chat = ScriptedChat([("", [("propose_task", task)])])
    created = []
    app = create_app(rig.live, rig.done.append, chat, FakeWhisper("nuovo task comprare le lenti"), None, rig.path,
                     web_dir=None, telegram=tg, create_task=lambda *a: created.append(a) or rig.live.tasks[0])
    http = TestClient(app)
    _post(http, {"message": {"chat": {"id": 42}, "voice": {"file_id": "v1"}}})
    assert chat.requests[0]["messages"][-1]["content"] == "nuovo task comprare le lenti"
    card_text, buttons = tg.sent[-1]
    assert "Comprare le lenti" in card_text and buttons[0][0] == "Conferma" and buttons[1][0] == "Rifiuta"
    proposal_id = buttons[0][1][2:]
    assert created == []  # nothing written before the button
    _post(http, {"callback_query": {"id": "q1", "data": f"c:{proposal_id}", "message": {"chat": {"id": 42}}}})
    assert len(created) == 1 and tg.answers[-1].startswith(("Fatto", "Scritto"))


def test_the_minute_clock_sends_due_reminders_once_even_after_a_restart(tmp_path):
    from datetime import timedelta

    rig, tg = Rig(tmp_path), FakeTelegram()  # NOW is 13:21; the fixture week has timed events
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, telegram=tg)
    day_end = NOW.replace(hour=23, minute=59)
    sent = 0
    moment = NOW
    while moment < day_end:
        moment += timedelta(minutes=1)
        sent += app.state.tick(moment)
    assert sent == len(tg.sent) and sent >= 1
    assert any("com'è andata" in text for text, _ in tg.sent)
    rig.live.clock = lambda: day_end  # Render restarts at 23:59
    again = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, telegram=FakeTelegram())
    assert again.state.tick(day_end + timedelta(seconds=30)) == 0  # nothing earlier is sent twice


def test_with_telegram_the_briefing_and_the_wake_up_go_there(tmp_path):
    rig, tg = Rig(tmp_path), FakeTelegram()
    http = TestClient(create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, telegram=tg))
    body = http.post("/api/briefing/send").json()
    assert body["sent"] is True and body["scheduled"] == 0  # the clock sends the reminders, not ntfy
    assert tg.sent[0][0].startswith("Buongiorno July")
    http.post("/api/wake", json={"event": "snoozed"})
    assert "sveglia" in tg.sent[-1][0]
    assert http.get("/healthz").json() == {"ok": True}


# --- D2-070: the wake-up call ------------------------------------------------------------


def _caller(calls, wake_time="06:45"):
    from twilio_client import is_from_twilio

    return {"call": lambda url: calls.append(url) or "CA1", "base_url": "https://dani", "secret": "tw1",
            "verify": lambda url, params, given: is_from_twilio("auth", url, params, given), "wake_time": wake_time}


def _signed(http, path, params):
    from urllib.parse import urlencode

    from twilio_client import signature

    return http.post(path, content=urlencode(params), headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Twilio-Signature": signature("auth", f"https://dani{path}", params)})


def test_the_wake_call_starts_at_wake_time_and_stops_when_she_solves_it(tmp_path):
    from datetime import timedelta

    rig, calls = Rig(tmp_path), []
    morning_time = NOW.replace(hour=6, minute=45)
    rig.live.clock = lambda: morning_time
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, caller=_caller(calls))
    http = TestClient(app)
    app.state.tick(morning_time - timedelta(minutes=1))
    assert calls == []
    app.state.tick(morning_time)
    assert calls == ["https://dani/twilio/tw1/voice"]
    assert http.post("/twilio/tw1/voice").status_code == 403  # not signed by Twilio
    question = _signed(http, "/twilio/tw1/voice", {"CallSid": "CA1"}).text
    assert "Quanto fa" in question and "Buongiorno July" in question
    a, b = question.split("Quanto fa ")[1].split("?")[0].split(" per ")
    done = _signed(http, "/twilio/tw1/answer", {"CallSid": "CA1", "Digits": str(int(a) * int(b))}).text
    assert "Brava July" in done
    app.state.tick(morning_time + timedelta(minutes=5))
    assert len(calls) == 1  # awake: no more calls


def test_a_snooze_rings_her_at_once(tmp_path):
    rig, calls = Rig(tmp_path), []
    http = TestClient(create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None,
                                 caller=_caller(calls, wake_time=None)))
    assert http.post("/api/wake", json={"event": "snoozed"}).status_code == 200
    assert len(calls) == 1
    assert http.post("/twilio/wrong/voice").status_code == 404


# --- V1: memory, mail, Fitbit ------------------------------------------------------------


class FakeMemory:
    def __init__(self):
        self.messages, self.events, self.reacted, self.measures, self.kv = [], [], [], [], {}

    def log_message(self, channel, role, content):
        self.messages.append((channel, role, content))

    def recent_messages(self, channel, limit=24):
        return [{"role": r, "content": c} for ch, r, c in self.messages if ch == channel][-limit:]

    def log_event(self, kind, ref="", detail=None):
        self.events.append((kind, ref))
        return len(self.events)

    def react(self, event_id, reaction, at):
        self.reacted.append((event_id, reaction))

    def put_measure(self, day, name, value, source):
        self.measures.append((name, value, source))

    def reactions(self, since):
        return [{"kind": k, "reaction": None} for k, _ in self.events]


def test_conversations_are_remembered_and_telegram_history_survives_a_restart(tmp_path):
    from test_chat import ScriptedChat

    rig, memory = Rig(tmp_path), FakeMemory()
    http = TestClient(create_app(rig.live, rig.done.append, FakeChat("Ciao July."), None, None, rig.path,
                                 web_dir=None, memory=memory))
    http.post("/api/chat", json={"message": "ciao", "history": []})
    assert memory.messages == [("app", "user", "ciao"), ("app", "assistant", "Ciao July.")]
    memory.messages.append(("telegram", "user", "ho dormito male"))
    memory.messages.append(("telegram", "assistant", "Oggi piano, allora."))
    chat = FakeChat("Me lo ricordo.")
    restarted = TestClient(create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None,
                                      memory=memory, telegram=FakeTelegram()))
    _post(restarted, {"message": {"chat": {"id": 42}, "text": "come mi sentivo stamattina?"}})
    sent = chat.seen["messages"]
    assert {"role": "user", "content": "ho dormito male"} in sent  # read back from the memory, not lost


def test_reminders_have_done_and_snooze_buttons_and_her_reaction_is_recorded(tmp_path):
    from datetime import timedelta

    from models import Event

    rig, memory, tg = Rig(tmp_path), FakeMemory(), FakeTelegram()
    rig.live.events = [Event(calendar="personale", title="Dentista", start=NOW.replace(hour=15, minute=0, second=0),
                             end=NOW.replace(hour=16, minute=0, second=0))]
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, telegram=tg, memory=memory)
    moment = NOW
    while not any(buttons for _, buttons in tg.sent) and moment < NOW.replace(hour=23):
        moment += timedelta(minutes=1)
        app.state.tick(moment)
    text, buttons = next((t, b) for t, b in tg.sent if b)
    assert [label for label, _ in buttons] == ["Fatto", "Posticipa 15'"]
    http = TestClient(app)
    _post(http, {"callback_query": {"id": "q", "data": buttons[1][1], "message": {"chat": {"id": 42}}}})
    assert memory.reacted[-1][1] == "snoozed" and tg.answers[-1].startswith("Ok, te lo ricordo")
    assert http.get("/api/memory/summary").json()["enabled"] is True


def test_the_briefing_has_the_mail_and_last_nights_sleep_and_a_short_night_reaches_the_chat(tmp_path):
    from mail_client import parse_message
    from test_mail_client import raw

    rig, memory = Rig(tmp_path), FakeMemory()

    class FakeFitbit:
        def read_day(self, day):
            return {"sleep_hours": 5.2, "sleep_efficiency": 80, "steps": 4000, "resting_hr": 60}

    mail = lambda since: [parse_message(raw("Gianluca <g@bar.it>", "Sito"))]
    chat = FakeChat("Piano leggero.")
    http = TestClient(create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None,
                                 memory=memory, mail=mail, fitbit=FakeFitbit()))
    text = http.get("/api/briefing").json()["text"]
    assert "Stanotte hai dormito 5.2 ore (Fitbit)." in text and "• Gianluca: Sito" in text
    assert text.splitlines()[-1] == "E tu, July, oggi come stai?"  # the extra lines come before the closing
    assert ("sleep_hours", 5.2, "fitbit") in memory.measures
    http.post("/api/chat", json={"message": "cosa faccio oggi?", "history": []})
    assert "A short night" in chat.seen["messages"][0]["content"]


def test_fitbit_connect_needs_the_pin_and_a_valid_state(tmp_path):
    rig = Rig(tmp_path)

    class FakeFitbit:
        client_id, redirect_uri, codes = "CID", "https://dani/fitbit/callback", []

        def connect(self, code, redirect_uri):
            self.codes.append(code)

    fitbit = FakeFitbit()
    http = TestClient(create_app(rig.live, rig.done.append, None, None, "1234", rig.path, web_dir=None, fitbit=fitbit),
                      follow_redirects=False)
    assert http.get("/fitbit/connect").status_code == 401
    jump = http.get("/fitbit/connect?key=1234")
    assert jump.status_code == 307 and jump.headers["location"].startswith("https://www.fitbit.com/oauth2/authorize")
    state = jump.headers["location"].split("state=")[1].split("&")[0]
    assert http.get("/fitbit/callback?code=C1&state=wrong").status_code == 400
    assert http.get(f"/fitbit/callback?code=C1&state={state}").json()["ok"] is True and fitbit.codes == ["C1"]


def test_a_broken_memory_never_stops_dani(tmp_path):
    class Broken(FakeMemory):
        def log_message(self, *args):
            raise RuntimeError("memory could not be reached")

    rig = Rig(tmp_path)
    http = TestClient(create_app(rig.live, rig.done.append, FakeChat("Eccomi."), None, None, rig.path,
                                 web_dir=None, memory=Broken()))
    assert http.post("/api/chat", json={"message": "ciao", "history": []}).json()["reply"] == "Eccomi."
