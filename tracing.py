"""Trace envelope for one agent run (D2-021).

A run gets one envelope with a unique ``run_id`` and timestamps. Every event
recorded during the run carries that SAME ``run_id``, so all the evidence of a
single run can be found and reconstructed together (this is the start of M04).

The run_id factory and the clock are injectable, so tests are deterministic and
never depend on the real uuid or the real wall clock (F1).

The file is called ``tracing`` and not ``trace`` on purpose: ``trace`` is a
module in the Python standard library, and a local file with that name would
shadow it.
"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def new_run_id():
    """Return a fresh, unique run id (the hex form of a uuid4)."""
    return uuid4().hex


def now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class TraceEnvelope(BaseModel):
    """One run's trace: a shared run_id, start/end timestamps and its events.

    ``events`` is a list of dicts; each event carries the envelope's ``run_id``
    and its own ``timestamp``. Later microphases add more fields to an event
    (D2-022: tool name, arguments, status, duration; D2-023: redaction).
    """

    run_id: str
    started_at: str
    ended_at: str | None = None
    events: list[dict] = Field(default_factory=list)


def start_run(run_id=None, clock=now_iso):
    """Open a trace envelope: a unique run_id and the start timestamp.

    ``run_id`` and ``clock`` are injectable so a test can pin them and assert
    exact values without depending on uuid or the real time. With nothing
    injected, a fresh unique id and the real UTC clock are used.
    """
    return TraceEnvelope(run_id=run_id or new_run_id(), started_at=clock())


def record_event(envelope, name, clock=now_iso):
    """Append one event to the run, stamped with the run's OWN run_id.

    The event's ``run_id`` is read from the envelope, never generated here, so
    every event of a run shares the same ``run_id``. If this took a new id
    instead, the "events share the run id" test would fail on purpose. Returns
    the event that was appended.
    """
    event = {
        "run_id": envelope.run_id,
        "seq": len(envelope.events) + 1,
        "timestamp": clock(),
        "name": name,
    }
    envelope.events.append(event)
    return event


def end_run(envelope, clock=now_iso):
    """Close the run by recording the end timestamp. Returns the envelope."""
    envelope.ended_at = clock()
    return envelope
