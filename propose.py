"""Turn a request to change the calendar or Notion into a proposal Giulia can read.

Nothing writes from here. Three kinds of proposal, all checked in code and all
applied only after she presses Confirm (preview -> yes -> write, roadmap M08):

  - ``build_proposal``: the model asked, in the chat, to move one event;
  - ``build_block_proposal``: she pressed Accept on a planner study block
    (D2-052), possibly at a different time than the planner proposed
    (D2-053) — the new time goes through the same checks;
  - ``build_task_proposal``: the model asked, in the chat, to create a new
    Notion task (D2-055). Only a title is required; area, deadline and
    duration are optional.

Refused (ValueError, nothing is proposed):
  - a reference that is not one of the events shown to the model, or a task
    that is not one of the open tasks;
  - an event of a fixed calendar (shifts, lessons): only the calendars she
    marked as tickable in Settings can be moved;
  - an all-day event, or an end that is not after the start;
  - a new task with an empty title, or with an area that is not one of hers
    (an unknown area would silently add an option to her Notion database).
Flagged (the proposal is made, with a warning she sees before confirming):
  - the new time is on a Sunday;
  - the new time overlaps another timed event (a shift included);
  - a new task whose deadline is already past.
"""

from datetime import date, datetime, timedelta
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


PROPOSE_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "propose_task",
        "description": (
            "Propose to create a new task in Giulia's Notion task list. This does NOT write "
            "anything: it creates a proposal that Giulia must confirm. Use an area only if it is "
            "one she already uses (as shown in her open tasks); leave it out when unsure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "What the task is, short, in her words"},
                "area": {"type": "string", "description": "One of her existing areas, exactly as shown"},
                "deadline": {"type": "string", "description": "Due date, YYYY-MM-DD. Leave out if none was given."},
                "duration_minutes": {"type": "integer", "description": "Estimated minutes. Leave out if none was given."},
            },
            "required": ["title"],
        },
    },
}


class TaskRequest(BaseModel):
    """The propose_task arguments the model sent, validated before anything else."""

    title: str
    area: Optional[str] = None
    deadline: Optional[date] = None
    duration_minutes: Optional[int] = None


class TaskProposal(BaseModel):
    """A new Notion task waiting for her Confirm. ``kind`` tells /api/confirm
    (and the page) to create a task instead of touching the calendar."""

    kind: str = "task"
    id: str
    title: str
    area: Optional[str] = None
    deadline: Optional[date] = None
    duration_minutes: Optional[int] = None
    warnings: list[str] = []


def build_task_proposal(arguments, known_areas, proposal_id, today=None):
    """Check the model's propose_task arguments and return a TaskProposal,
    or raise ValueError.

    ``known_areas`` are the areas of her open tasks: an area outside them is
    refused, because writing it would silently add an option to her database.
    A deadline already past is flagged, not refused: the task may be real.
    """
    try:
        wanted = TaskRequest.model_validate(arguments)
    except ValidationError as problem:
        raise ValueError(f"richiesta non valida: {problem.errors()[0]['msg']}") from None
    title = wanted.title.strip()
    if not title:
        raise ValueError("il task ha bisogno di un titolo")
    area = (wanted.area or "").strip() or None
    if area is not None:
        by_fold = {name.casefold(): name for name in known_areas}
        if area.casefold() not in by_fold:
            raise ValueError(f"non conosco l'area {area!r}: lasciala vuota o usa una delle sue")
        area = by_fold[area.casefold()]
    if wanted.duration_minutes is not None and wanted.duration_minutes <= 0:
        raise ValueError("la durata deve essere positiva")
    warnings = []
    if wanted.deadline is not None and today is not None and wanted.deadline < today:
        warnings.append(f"la scadenza {wanted.deadline:%d/%m} è già passata")
    return TaskProposal(
        id=proposal_id,
        title=title,
        area=area,
        deadline=wanted.deadline,
        duration_minutes=wanted.duration_minutes,
        warnings=warnings,
    )


def describe_task(proposal):
    """The preview sentence shown before she confirms a new task."""
    details = []
    if proposal.area:
        details.append(f"area {proposal.area}")
    if proposal.deadline:
        details.append(f"scadenza {proposal.deadline:%d/%m}")
    if proposal.duration_minutes:
        details.append(f"{proposal.duration_minutes} min")
    extra = f" ({', '.join(details)})" if details else ""
    text = f"Propongo di creare il task «{proposal.title}»{extra} nella tua lista Notion."
    if proposal.warnings:
        text += " Attenzione: " + "; ".join(proposal.warnings) + "."
    return text + " Confermi?"


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
