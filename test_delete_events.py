"""D2-073: Dani proposes to delete events; only her yes deletes them."""

import json

import pytest
from fastapi.testclient import TestClient

from delete_events import MAX_DELETE, build_delete_proposal, describe_delete
from models import Event
from server import create_app
from test_chat import ScriptedChat
from test_server import CalendarRig, FakeTelegram, _post, at

GYM = Event(calendar="personale", title="Palestra", uid="gym", api_id="gym-1", calendar_id="c", start=at(11, 7, 30), end=at(11, 9))
SHIFT = Event(calendar="lavoro", title="Turno", uid="s", api_id="s-1", calendar_id="c", start=at(12, 17), end=at(12, 23))
ICAL = Event(calendar="personale", title="Feed", uid="f", start=at(13, 10), end=at(13, 11))
REFS = {"e1": GYM, "e2": SHIFT, "e3": ICAL}


def test_a_delete_proposal_lists_the_events_once():
    proposal = build_delete_proposal({"events": ["e1", " E1 "]}, REFS, ["personale"], "p1")
    assert [e.title for e in proposal.events] == ["Palestra"] and proposal.kind == "delete"
    assert describe_delete(proposal) == ("Cancello questo evento:\n• 11/11 07:30–09:00 Palestra (personale)\n"
                                         "Solo questa volta se si ripete, nessuna notifica. Confermi?")


def test_several_events_and_an_all_day_one_are_described():
    holiday = GYM.model_copy(update={"title": "Ferie", "all_day": True, "start": at(14, 0), "end": at(15, 0)})
    proposal = build_delete_proposal({"events": ["e1", "e4"]}, {**REFS, "e4": holiday}, ["personale"], "p")
    assert describe_delete(proposal).splitlines()[:3] == [
        "Cancello questi 2 eventi:", "• 11/11 07:30–09:00 Palestra (personale)", "• 14/11 Ferie (personale)"]


@pytest.mark.parametrize("arguments, problem", [
    ({"events": []}, "nessun evento"),
    ({}, "nessun evento"),
    ({"events": "e1"}, "nessun evento"),
    ({"events": [1]}, "nessun evento"),
    ("e1", "nessun evento"),
    ({"events": ["e9"]}, "non conosco l'evento 'e9'"),
    ({"events": ["e2"]}, "impegno fisso"),
    ({"events": ["e3"]}, "letto via iCal"),
    ({"events": ["e1"] * (MAX_DELETE + 1)}, f"al massimo {MAX_DELETE}"),
])
def test_refusals(arguments, problem):
    with pytest.raises(ValueError, match=problem):
        build_delete_proposal(arguments, REFS, ["personale"], "p")


# --- through the chat and /api/confirm ---------------------------------------------


def rig_asked_to_delete(tmp_path, *titles, telegram=None):
    rig = CalendarRig(tmp_path)
    rig.http.put("/api/settings", json={"tickable_calendars": ["personale", "studio"]})
    keys = [e["key"] for e in rig.http.get("/api/state").json()["events"]]
    refs = [f"e{keys.index(rig.key(title)) + 1}" for title in titles]
    chat = ScriptedChat([("Ok.", [("propose_delete", json.dumps({"events": refs}))])])
    app = create_app(rig.live, lambda task_id: None, chat, None, None, rig.path, web_dir=None,
                     delete_event=rig._delete, telegram=telegram)
    return rig, chat, TestClient(app)


def test_the_chat_proposes_and_only_her_yes_deletes(tmp_path):
    rig, chat, http = rig_asked_to_delete(tmp_path, "Palestra", "Call con Ruud")
    body = http.post("/api/chat", json={"message": "cancella palestra e call", "history": []}).json()
    assert "propose_delete" in [t["function"]["name"] for t in chat.requests[0]["tools"]]
    assert "call the propose_delete tool" in chat.requests[0]["messages"][0]["content"]
    assert body["proposal"]["kind"] == "delete" and body["reply"].startswith("Ok.\n\nCancello questi 2 eventi:")
    assert rig.deleted == []  # a proposal deletes nothing
    done = http.post("/api/confirm", json={"id": body["proposal"]["id"]}).json()
    assert done == {"ok": True, "title": "2 eventi", "read_back": True, "message": "Fatto: cancellati 2 eventi."}
    assert rig.deleted == ["gym-1", "call-1"]
    assert http.post("/api/confirm", json={"id": body["proposal"]["id"]}).status_code == 404  # twice: nothing more


def test_a_shift_is_never_proposed_for_deletion(tmp_path):
    rig, _, http = rig_asked_to_delete(tmp_path, "Turno ristorante")
    body = http.post("/api/chat", json={"message": "cancella il turno", "history": []}).json()
    assert body["reply"].startswith("Non posso proporre di cancellarlo") and "impegno fisso" in body["reply"]
    assert "proposal" not in body and rig.deleted == []


def test_an_event_already_gone_counts_as_deleted_and_a_failure_keeps_the_rest(tmp_path):
    rig, _, http = rig_asked_to_delete(tmp_path, "Palestra", "Call con Ruud")
    proposal_id = http.post("/api/chat", json={"message": "x", "history": []}).json()["proposal"]["id"]
    rig.calendar = [e for e in rig.calendar if e.api_id != "gym-1"]  # she deleted it herself meanwhile
    rig.live.refresh("calendar")
    rig.fail = RuntimeError("Google down")
    failed = http.post("/api/confirm", json={"id": proposal_id})
    assert failed.status_code == 502 and "cancellati 1 eventi su 2" in failed.json()["detail"]
    rig.fail = None
    assert http.post("/api/confirm", json={"id": proposal_id}).json()["ok"] is True
    assert rig.deleted == ["call-1"]


def test_without_calendar_writes_the_model_is_not_offered_the_tool(tmp_path):
    rig = CalendarRig(tmp_path)
    chat = ScriptedChat([("Non posso.", [])])
    app = create_app(rig.live, lambda task_id: None, chat, None, None, rig.path, web_dir=None,
                     move_event=rig._move)
    TestClient(app).post("/api/chat", json={"message": "cancella", "history": []})
    assert "propose_delete" not in [t["function"]["name"] for t in chat.requests[0]["tools"]]
    assert "You cannot delete calendar events." in chat.requests[0]["messages"][0]["content"]


def test_on_telegram_the_proposal_has_cancella_and_annulla(tmp_path):
    tg = FakeTelegram()
    rig, _, http = rig_asked_to_delete(tmp_path, "Palestra", telegram=tg)
    _post(http, {"message": {"chat": {"id": 42}, "text": "cancella la palestra"}})
    text, buttons = tg.sent[-1]
    assert text.startswith("Ok.\n\nCancello questo evento") and [b[0] for b in buttons] == ["Cancella", "Annulla"]
    _post(http, {"callback_query": {"id": "cb", "data": buttons[0][1], "message": {"chat": {"id": 42}}}})
    assert rig.deleted == ["gym-1"] and tg.sent[-1][0] == "Fatto: cancellato 1 evento."
