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
