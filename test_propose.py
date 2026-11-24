"""Move proposals: what is refused, what is only flagged. No model, no calendar."""

from datetime import datetime

import pytest

from models import AMSTERDAM, Event
from propose import build_proposal, describe, event_refs


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=AMSTERDAM)


CALL = Event(calendar="studio", title="Call con Ruud", uid="call", start=at(12, 15), end=at(12, 15, 30))
SHIFT = Event(calendar="lavoro", title="Turno ristorante", uid="shift", start=at(12, 17), end=at(12, 23))
DEMO = Event(calendar="studio", title="Demo Sprint 3", uid="demo", start=at(13, 0), end=at(14, 0), all_day=True)
GYM = Event(calendar="personale", title="Palestra", uid="gym", start=at(11, 7, 30), end=at(11, 9))
REFS = event_refs([GYM, CALL, SHIFT, DEMO])  # e1 gym, e2 call, e3 shift, e4 demo
MOVABLE = ["Studio", "personale"]


def propose(**arguments):
    return build_proposal(arguments, REFS, MOVABLE, "p1")


def test_a_free_time_gives_a_clean_proposal_that_keeps_the_duration():
    proposal = propose(event="e2", new_start="2026-11-12T10:00")
    assert (proposal.new_start, proposal.new_end) == (at(12, 10), at(12, 10, 30))
    assert (proposal.old_start, proposal.event_key, proposal.warnings) == (at(12, 15), CALL.key, [])
    assert describe(proposal) == ("Propongo di spostare «Call con Ruud» (studio) da 12/11 15:00–15:30 "
                                  "a 12/11 10:00–10:30. Confermi?")


def test_an_explicit_end_and_a_reference_in_capitals_are_accepted():
    proposal = propose(event=" E2 ", new_start="2026-11-12T10:00", new_end="2026-11-12T11:00")
    assert proposal.new_end == at(12, 11)


def test_moving_onto_a_shift_is_flagged_not_silently_accepted():
    proposal = propose(event="e2", new_start="2026-11-12T16:45")
    assert proposal.warnings == ["si sovrappone a «Turno ristorante» (17:00–23:00, lavoro)"]
    assert "Attenzione: si sovrappone a «Turno ristorante»" in describe(proposal)


def test_touching_edges_and_all_day_events_are_not_a_clash():
    assert propose(event="e2", new_start="2026-11-12T16:30").warnings == []  # ends exactly when the shift starts
    assert propose(event="e2", new_start="2026-11-13T10:00").warnings == []  # the all-day demo does not block


def test_sunday_is_flagged():
    assert propose(event="e2", new_start="2026-11-15T10:00").warnings == ["è di domenica"]


@pytest.mark.parametrize(
    "arguments, reason",
    [
        ({"event": "e9", "new_start": "2026-11-12T10:00"}, "non conosco l'evento"),
        ({"event": "e3", "new_start": "2026-11-12T10:00"}, "impegno fisso"),  # a restaurant shift
        ({"event": "e4", "new_start": "2026-11-12T10:00"}, "tutto il giorno"),
        ({"event": "e2", "new_start": "2026-11-12T10:00", "new_end": "2026-11-12T09:00"}, "fine deve essere dopo"),
        ({"event": "e2", "new_start": "2026-11-12T15:00"}, "già a quell'ora"),
        ({"event": "e2", "new_start": "giovedì alle 4"}, "richiesta non valida"),
        ({"new_start": "2026-11-12T10:00"}, "richiesta non valida"),
    ],
)
def test_refusals(arguments, reason):
    with pytest.raises(ValueError, match=reason):
        build_proposal(arguments, REFS, MOVABLE, "p1")


# --- study-block proposals (D2-052, D2-053) -----------------------------------

from models import Task  # noqa: E402
from propose import build_block_proposal, describe_block  # noqa: E402

BLOCK_TASKS = [Task(id="t1", title="Studio AI", status="In Progress", duration_minutes=90),
               Task(id="t2", title="Email Fontys", status="Not Started")]


def block(**arguments):
    return build_block_proposal(arguments, BLOCK_TASKS, [GYM, CALL, SHIFT, DEMO], "b1")


def test_accepting_a_block_keeps_the_task_duration_and_reads_like_a_preview():
    proposal = block(task_id="t1", start="2026-11-12T10:00")
    assert (proposal.start, proposal.end) == (at(12, 10), at(12, 11, 30))  # 90 minutes
    assert (proposal.kind, proposal.task_id, proposal.warnings) == ("block", "t1", [])
    assert describe_block(proposal) == ("Propongo di creare il blocco di studio «Studio AI» il 12/11 "
                                        "dalle 10:00 alle 11:30 nel calendario studio. Confermi?")


def test_a_task_without_an_estimate_gets_one_hour_and_an_explicit_end_wins():
    assert block(task_id="t2", start="2026-11-12T10:00").end == at(12, 11)
    assert block(task_id="t2", start="2026-11-12T10:00", end="2026-11-12T12:00").end == at(12, 12)


def test_a_block_moved_onto_a_shift_or_a_sunday_is_flagged_not_silently_accepted():
    moved = block(task_id="t1", start="2026-11-12T16:00")  # ends 17:30, the shift starts at 17:00
    assert moved.warnings == ["si sovrappone a «Turno ristorante» (17:00–23:00, lavoro)"]
    assert "Attenzione: si sovrappone a «Turno ristorante»" in describe_block(moved)
    assert block(task_id="t1", start="2026-11-15T10:00").warnings == ["è di domenica"]


@pytest.mark.parametrize(
    "arguments, reason",
    [
        ({"task_id": "t9", "start": "2026-11-12T10:00"}, "non conosco il task"),
        ({"task_id": "t1", "start": "2026-11-12T10:00", "end": "2026-11-12T09:00"}, "la fine deve essere dopo"),
        ({"task_id": "t1"}, "non valida"),  # no start at all
    ],
)
def test_block_requests_the_code_refuses(arguments, reason):
    with pytest.raises(ValueError, match=reason):
        build_block_proposal(arguments, BLOCK_TASKS, [SHIFT], "b1")


# --- a new Notion task from the chat (D2-055) -----------------------------------

from datetime import date  # noqa: E402

from propose import build_task_proposal, describe_task  # noqa: E402

AREAS = {"University", "Personal"}
TODAY = date(2026, 11, 11)


def task(**arguments):
    return build_task_proposal(arguments, AREAS, "t1", today=TODAY)


def test_a_full_task_proposal_is_built_and_described():
    proposal = task(title=" comprare le lenti ", area="personal", deadline="2026-11-20", duration_minutes=30)
    # The title is trimmed and the area takes her spelling, so Notion gets an existing option.
    assert (proposal.title, proposal.area) == ("comprare le lenti", "Personal")
    assert (proposal.deadline, proposal.duration_minutes, proposal.warnings) == (date(2026, 11, 20), 30, [])
    assert describe_task(proposal) == (
        "Propongo di creare il task «comprare le lenti» (area Personal, scadenza 20/11, 30 min) "
        "nella tua lista Notion. Confermi?"
    )


def test_a_title_alone_is_enough():
    proposal = task(title="chiamare il dentista")
    assert (proposal.area, proposal.deadline, proposal.duration_minutes) == (None, None, None)
    assert describe_task(proposal) == "Propongo di creare il task «chiamare il dentista» nella tua lista Notion. Confermi?"


def test_a_past_deadline_is_flagged_not_refused():
    proposal = task(title="pagare DUO", deadline="2026-11-01")
    assert proposal.warnings == ["la scadenza 01/11 è già passata"]
    assert "Attenzione: la scadenza 01/11 è già passata." in describe_task(proposal)


@pytest.mark.parametrize(
    "arguments, reason",
    [
        ({}, "non valida"),  # no title at all
        ({"title": "   "}, "bisogno di un titolo"),
        ({"title": "x", "deadline": "domani"}, "non valida"),
        ({"title": "x", "duration_minutes": 0}, "la durata deve essere positiva"),
        ({"title": "x", "area": "Zumba"}, "non conosco l'area"),
    ],
)
def test_task_requests_the_code_refuses(arguments, reason):
    with pytest.raises(ValueError, match=reason):
        build_task_proposal(arguments, AREAS, "t1", today=TODAY)
