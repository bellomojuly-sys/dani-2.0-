"""D2-073: Dani may propose to delete events — never delete them herself.

The model calls propose_delete with the references of the events she wants
gone ("cancella i blocchi di domani"). Code checks every reference and makes
one DeleteProposal; the events are deleted only after her yes, one occurrence
each, without notifications (server.py, /api/confirm).

Refused (ValueError, nothing is proposed):
  - no event, more than MAX_DELETE, or a reference the model was not shown;
  - an event of a fixed calendar (shifts, lessons): only the calendars she
    marked as tickable in Settings can be deleted;
  - an event read through iCal only (no API id): it cannot be written.
"""

from datetime import datetime

from pydantic import BaseModel

MAX_DELETE = 10

PROPOSE_DELETE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "propose_delete",
        "description": (
            "Propose to delete one or more calendar events. This does NOT change the calendar: it creates "
            "one proposal that Giulia confirms with a button. Use the event references shown in square "
            f"brackets (for example e3). At most {MAX_DELETE} events. Shifts and lessons cannot be deleted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {"type": "string", "description": "an event reference, e.g. e3"},
                    "minItems": 1,
                    "maxItems": MAX_DELETE,
                },
            },
            "required": ["events"],
            "additionalProperties": False,
        },
    },
}


class DeletedEvent(BaseModel):
    key: str
    title: str
    calendar: str
    start: datetime
    end: datetime
    all_day: bool = False


class DeleteProposal(BaseModel):
    """Events waiting for her yes to be deleted."""

    kind: str = "delete"
    id: str
    events: list[DeletedEvent]


def build_delete_proposal(arguments, refs, deletable_calendars, proposal_id):
    """Check a propose_delete call and return a DeleteProposal, or raise ValueError.

    ``refs`` is the same {"e1": Event, ...} the model was shown (event_refs).
    """
    raw = arguments.get("events") if isinstance(arguments, dict) else None
    if not isinstance(raw, list) or not raw or not all(isinstance(ref, str) for ref in raw):
        raise ValueError("nessun evento da cancellare")
    if len(raw) > MAX_DELETE:
        raise ValueError(f"al massimo {MAX_DELETE} eventi per volta")
    allowed = {name.casefold() for name in deletable_calendars}
    chosen = []
    for ref in dict.fromkeys(ref.strip().lower() for ref in raw):  # the same event once
        event = refs.get(ref)
        if event is None:
            raise ValueError(f"non conosco l'evento {ref!r}")
        if event.calendar.casefold() not in allowed:
            raise ValueError(f"«{event.title}» è nel calendario {event.calendar}, che è un impegno fisso")
        if not event.api_id:
            raise ValueError(f"«{event.title}» è letto via iCal: non si può cancellare")
        chosen.append(DeletedEvent(key=event.key, title=event.title, calendar=event.calendar,
                                   start=event.start, end=event.end, all_day=event.all_day))
    return DeleteProposal(id=proposal_id, events=chosen)


def describe_delete(proposal):
    """The preview: what goes, one line each."""
    lines = [f"Cancello {'questo evento' if len(proposal.events) == 1 else f'questi {len(proposal.events)} eventi'}:"]
    for event in proposal.events:
        when = f"{event.start:%d/%m}" + ("" if event.all_day else f" {event.start:%H:%M}–{event.end:%H:%M}")
        lines.append(f"• {when} {event.title} ({event.calendar})")
    lines.append("Solo questa volta se si ripete, nessuna notifica. Confermi?")
    return "\n".join(lines)
