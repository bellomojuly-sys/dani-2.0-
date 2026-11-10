"""Turn the model's request "move this event" into a proposal Giulia can read.

The model never writes. In the chat it can only call ``propose_move`` with an
event reference and a new time; this module checks that request in code and
builds a ``Proposal``: what moves, from when to when, and what it would clash
with. Nothing changes in the calendar until she presses Confirm
(preview -> yes -> write, roadmap M08).

Refused (ValueError, nothing is proposed):
  - a reference that is not one of the events shown to the model;
  - an event of a fixed calendar (shifts, lessons): only the calendars she
    marked as tickable in Settings can be moved;
  - an all-day event, or an end that is not after the start.
Flagged (the proposal is made, with a warning she sees before confirming):
  - the new time is on a Sunday;
  - the new time overlaps another timed event.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ValidationError

from models import AMSTERDAM

SUNDAY = 6

PROPOSE_MOVE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "propose_move",
        "description": (
            "Propose to move one calendar event to a new time. This does NOT change the calendar: "
            "it creates a proposal that Giulia must confirm. Use the event reference shown in "
            "square brackets (for example e3)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "event": {"type": "string", "description": "The event reference, e.g. e3"},
                "new_start": {"type": "string", "description": "New start, Amsterdam time, YYYY-MM-DDTHH:MM"},
                "new_end": {"type": "string", "description": "New end, same format. Leave out to keep the duration."},
            },
            "required": ["event", "new_start"],
        },
    },
}


class MoveRequest(BaseModel):
    """The arguments the model sent, validated before anything else."""

    event: str
    new_start: datetime
    new_end: Optional[datetime] = None


class Proposal(BaseModel):
    id: str
    event_key: str
    title: str
    calendar: str
    old_start: datetime
    old_end: datetime
    new_start: datetime
    new_end: datetime
    warnings: list[str] = []


def event_refs(events):
    """Short names for the model: {"e1": first event, "e2": second, ...}."""
    return {f"e{number}": event for number, event in enumerate(events, 1)}


def _amsterdam(moment):
    """A time without a zone is read as Amsterdam time."""
    return moment.replace(tzinfo=AMSTERDAM) if moment.tzinfo is None else moment.astimezone(AMSTERDAM)


def find_warnings(event, new_start, new_end, events):
    """What the new time clashes with. Other all-day events do not count."""
    warnings = []
    if new_start.weekday() == SUNDAY:
        warnings.append("è di domenica")
    for other in events:
        if other.key == event.key or other.all_day:
            continue
        if other.start < new_end and other.end > new_start:
            warnings.append(f"si sovrappone a «{other.title}» ({other.start:%H:%M}–{other.end:%H:%M}, {other.calendar})")
    return warnings


def build_proposal(arguments, refs, movable_calendars, proposal_id):
    """Check the model's arguments and return a Proposal, or raise ValueError.

    ``refs`` is the same {"e1": Event, ...} the model was shown (event_refs).
    """
    try:
        wanted = MoveRequest.model_validate(arguments)
    except ValidationError as problem:
        raise ValueError(f"richiesta non valida: {problem.errors()[0]['msg']}") from None
    event = refs.get(wanted.event.strip().lower())
    if event is None:
        raise ValueError(f"non conosco l'evento {wanted.event!r}")
    if event.calendar.casefold() not in {name.casefold() for name in movable_calendars}:
        raise ValueError(f"«{event.title}» è nel calendario {event.calendar}, che è un impegno fisso")
    if event.all_day:
        raise ValueError("gli eventi di tutto il giorno non si spostano da qui")
    new_start = _amsterdam(wanted.new_start)
    new_end = _amsterdam(wanted.new_end) if wanted.new_end else new_start + (event.end - event.start)
    if new_end <= new_start:
        raise ValueError("la fine deve essere dopo l'inizio")
    if (new_start, new_end) == (event.start, event.end):
        raise ValueError("è già a quell'ora")
    return Proposal(
        id=proposal_id,
        event_key=event.key,
        title=event.title,
        calendar=event.calendar,
        old_start=event.start,
        old_end=event.end,
        new_start=new_start,
        new_end=new_end,
        warnings=find_warnings(event, new_start, new_end, list(refs.values())),
    )


def describe(proposal):
    """The preview sentence shown in the chat."""
    text = (
        f"Propongo di spostare «{proposal.title}» ({proposal.calendar}) "
        f"da {proposal.old_start:%d/%m %H:%M}–{proposal.old_end:%H:%M} "
        f"a {proposal.new_start:%d/%m %H:%M}–{proposal.new_end:%H:%M}."
    )
    if proposal.warnings:
        text += " Attenzione: " + "; ".join(proposal.warnings) + "."
    return text + " Confermi?"
