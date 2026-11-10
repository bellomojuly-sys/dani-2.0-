"""Turn a request to change the calendar into a proposal Giulia can read.

Nothing writes from here. Two kinds of proposal, both checked in code and both
applied only after she presses Confirm (preview -> yes -> write, roadmap M08):

  - ``build_proposal``: the model asked, in the chat, to move one event;
  - ``build_block_proposal``: she pressed Accept on a planner study block
    (D2-052), possibly at a different time than the planner proposed
    (D2-053) — the new time goes through the same checks.

Refused (ValueError, nothing is proposed):
  - a reference that is not one of the events shown to the model, or a task
    that is not one of the open tasks;
  - an event of a fixed calendar (shifts, lessons): only the calendars she
    marked as tickable in Settings can be moved;
  - an all-day event, or an end that is not after the start.
Flagged (the proposal is made, with a warning she sees before confirming):
  - the new time is on a Sunday;
  - the new time overlaps another timed event (a shift included).
"""

from datetime import datetime, timedelta
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


def _clashes(new_start, new_end, events, skip_key=None):
    """The warnings any new time gets: Sunday, and every timed event it
    overlaps (all-day events do not count; ``skip_key`` is the event being
    moved, which cannot clash with itself)."""
    warnings = []
    if new_start.weekday() == SUNDAY:
        warnings.append("è di domenica")
    for other in events:
        if other.key == skip_key or other.all_day:
            continue
        if other.start < new_end and other.end > new_start:
            warnings.append(f"si sovrappone a «{other.title}» ({other.start:%H:%M}–{other.end:%H:%M}, {other.calendar})")
    return warnings


def find_warnings(event, new_start, new_end, events):
    """What the new time of a moved event clashes with."""
    return _clashes(new_start, new_end, events, skip_key=event.key)


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


class BlockRequest(BaseModel):
    """What the page sends when Giulia accepts a planner block: which task,
    and (when she moved it first, D2-053) the time she wants."""

    task_id: str
    start: datetime
    end: Optional[datetime] = None


class BlockProposal(BaseModel):
    """A study block waiting for her Confirm. ``kind`` tells /api/confirm to
    create an event instead of moving one."""

    kind: str = "block"
    id: str
    task_id: str
    title: str
    start: datetime
    end: datetime
    warnings: list[str] = []


def build_block_proposal(arguments, tasks, events, proposal_id, default_minutes=60):
    """Check an Accept (or Accept-at-another-time) of a planner block and
    return a BlockProposal, or raise ValueError.

    ``tasks`` are the open tasks; ``events`` the week's timed events. The time
    she chose goes through the same checks as a move: Sunday and overlaps
    (a shift included) are flagged, an end before the start is refused.
    """
    try:
        wanted = BlockRequest.model_validate(arguments)
    except ValidationError as problem:
        raise ValueError(f"richiesta non valida: {problem.errors()[0]['msg']}") from None
    task = next((task for task in tasks if task.id == wanted.task_id), None)
    if task is None:
        raise ValueError(f"non conosco il task {wanted.task_id!r} fra quelli aperti")
    start = _amsterdam(wanted.start)
    minutes = task.duration_minutes or default_minutes
    end = _amsterdam(wanted.end) if wanted.end else start + timedelta(minutes=minutes)
    if end <= start:
        raise ValueError("la fine deve essere dopo l'inizio")
    return BlockProposal(
        id=proposal_id,
        task_id=task.id,
        title=task.title,
        start=start,
        end=end,
        warnings=_clashes(start, end, events),
    )


def describe_block(proposal):
    """The preview sentence shown before she confirms a study block."""
    text = (
        f"Propongo di creare il blocco di studio «{proposal.title}» "
        f"il {proposal.start:%d/%m} dalle {proposal.start:%H:%M} alle {proposal.end:%H:%M} "
        f"nel calendario studio."
    )
    if proposal.warnings:
        text += " Attenzione: " + "; ".join(proposal.warnings) + "."
    return text + " Confermi?"


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
