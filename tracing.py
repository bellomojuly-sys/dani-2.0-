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
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_run_id():
    """Return a fresh, unique run id (the hex form of a uuid4)."""
    return uuid4().hex


def now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class TraceEvent(BaseModel):
    """One recorded step of a run: which tool, with what, how it went, how long.

    Every event carries the run's shared ``run_id`` and its own ``seq`` and
    ``timestamp`` (D2-021). D2-022 adds the full picture of the tool call: the
    ``arguments`` it was given, the ``status`` it ended in, and the
    ``duration_ms`` it took. ``status`` is a closed set ("ok" or "error"), so a
    value outside it is refused, and ``duration_ms`` is the span of the call
    (end minus start) in milliseconds. Because every field is typed, a
    malformed event cannot be recorded: the JSON trace validates (D2-022).
    """

    run_id: str
    seq: int
    timestamp: str
    name: str
    arguments: dict
    status: Literal["ok", "error"]
    duration_ms: float


class TraceEnvelope(BaseModel):
    """One run's trace: a shared run_id, start/end timestamps and its events.

    ``events`` is a list of typed ``TraceEvent`` objects; each one carries the
    envelope's ``run_id`` and its own ``timestamp``. Typing the list means the
    whole envelope is a validated schema: nothing but a well-formed event can
    be in it. D2-023 will add redaction of sensitive fields.
    """

    run_id: str
    started_at: str
    ended_at: str | None = None
    events: list[TraceEvent] = Field(default_factory=list)


def start_run(run_id=None, clock=now_iso):
    """Open a trace envelope: a unique run_id and the start timestamp.

    ``run_id`` and ``clock`` are injectable so a test can pin them and assert
    exact values without depending on uuid or the real time. With nothing
    injected, a fresh unique id and the real UTC clock are used.
    """
    return TraceEnvelope(run_id=run_id or new_run_id(), started_at=clock())


def record_event(envelope, name, arguments, status, duration_ms, clock=now_iso):
    """Append one validated TraceEvent to the run, sharing the run's run_id.

    The event's ``run_id`` is read from the envelope, never generated here, so
    every event of a run shares the same ``run_id``. If this took a new id
    instead, the "events share the run id" test would fail on purpose.

    ``arguments``, ``status`` and ``duration_ms`` describe the tool call that
    just finished (D2-022). Building a ``TraceEvent`` validates the event before
    it is stored, so an impossible ``status`` or a wrong type raises here and is
    never recorded quietly. Returns the event that was appended.
    """
    event = TraceEvent(
        run_id=envelope.run_id,
        seq=len(envelope.events) + 1,
        timestamp=clock(),
        name=name,
        arguments=arguments,
        status=status,
        duration_ms=duration_ms,
    )
    envelope.events.append(event)
    return event


def end_run(envelope, clock=now_iso):
    """Close the run by recording the end timestamp. Returns the envelope."""
    envelope.ended_at = clock()
    return envelope
