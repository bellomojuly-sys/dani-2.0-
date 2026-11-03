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
    be in it. ``safe_trace`` redacts sensitive fields from a dump of it (D2-023).
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


# --- D2-023: redaction of sensitive fields ------------------------------------
# The trace stores the arguments the model passed to each tool. If a secret (an
# API key, a token) ever lands in one of those fields, it must not be persisted
# in the trace. Redaction is a SAFETY NET, not the main defence: secrets should
# not reach the trace at all, but if one does, this hides it.
#
# Decision Log D2-023 (docs/DECISION-LOG-D2-023-redaction.md), option A: a value
# is hidden when its field NAME is one we treat as sensitive. We never inspect
# the value itself, so a secret stored under an innocent field name is NOT
# caught — a known, accepted limit. The field is kept and its value becomes the
# marker [REDACTED], so the run stays reconstructable (Gate M04).

REDACTED = "[REDACTED]"

# The sensitive field names, lowercased. A new sensitive field is one more
# entry here plus its test. Matching is by name only, case-insensitive.
SENSITIVE_FIELD_NAMES = frozenset(
    {"api_key", "token", "secret", "password", "authorization"}
)


def _is_sensitive(key):
    """True if a field name is one we redact (by name only, case-insensitive)."""
    return isinstance(key, str) and key.lower() in SENSITIVE_FIELD_NAMES


def redact(value):
    """Return a copy of ``value`` with every sensitive-named field hidden.

    A dict is rebuilt key by key: a key whose NAME is sensitive gets the marker
    [REDACTED] (we do not look at the value at all — that is option A, by field
    name); any other value is redacted recursively, so a secret nested deeper
    inside the arguments is still caught. A list is redacted item by item.
    Anything else (a string, a number, None) is returned unchanged. The input is
    never mutated: a new structure is built and returned.
    """
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive(key) else redact(inner)
            for key, inner in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def safe_trace(envelope):
    """Return the run's trace as a JSON-ready dict with sensitive fields hidden.

    The envelope is dumped to plain data and then redacted as a whole, so no
    sensitive-named field — in the envelope or in any event's arguments —
    survives in the safe trace. The original envelope is left untouched, so the
    live run keeps its real values; only the persisted/returned copy is safe.
    """
    return redact(envelope.model_dump())
