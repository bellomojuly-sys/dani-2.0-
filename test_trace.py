from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from tracing import (
    TraceEnvelope,
    TraceEvent,
    new_run_id,
    now_iso,
    start_run,
    record_event,
    end_run,
)
from agent import run_tool_loop
from tools import TOOL_SCHEMAS
from test_agent import _FakeClient, _fake_message, _fake_tool_call


class _Clock:
    """A fake clock: returns the given stamps in order, repeats the last one.

    Lets a test pin timestamps exactly, so "started before event before ended"
    is checked deterministically, never against the real wall clock (F1).
    """

    def __init__(self, stamps):
        self._stamps = list(stamps)
        self.calls = 0

    def __call__(self):
        stamp = self._stamps[min(self.calls, len(self._stamps) - 1)]
        self.calls += 1
        return stamp


# --- The envelope on its own --------------------------------------------------


def test_start_run_opens_an_envelope_with_a_run_id_and_a_start_timestamp():
    run = start_run(run_id="R1", clock=lambda: "T0")
    assert run.run_id == "R1"
    assert run.started_at == "T0"
    assert run.ended_at is None
    assert run.events == []


def test_two_runs_get_different_run_ids():
    # With nothing injected, each run must get its own unique id.
    assert start_run().run_id != start_run().run_id


def test_new_run_id_is_unique_each_time():
    assert new_run_id() != new_run_id()


def test_every_event_shares_the_run_id_of_the_envelope():
    # This is the D2-021 Verify: events share the run id.
    run = start_run(run_id="R1", clock=lambda: "T0")
    e1 = record_event(run, "read_tasks", arguments={}, status="ok", duration_ms=1.0, clock=lambda: "T1")
    e2 = record_event(run, "prioritize_tasks", arguments={}, status="ok", duration_ms=1.0, clock=lambda: "T2")

    assert e1.run_id == "R1"
    assert e2.run_id == "R1"
    # All events of one run share one id, and that id is the envelope's.
    assert {event.run_id for event in run.events} == {"R1"}


def test_an_event_is_stored_with_a_timestamp_and_order():
    run = start_run(run_id="R1", clock=lambda: "T0")
    e1 = record_event(run, "read_tasks", arguments={}, status="ok", duration_ms=1.0, clock=lambda: "T1")
    e2 = record_event(run, "prioritize_tasks", arguments={}, status="ok", duration_ms=1.0, clock=lambda: "T2")

    assert e1.timestamp == "T1"
    assert e2.timestamp == "T2"
    # seq numbers the events in the order they happened.
    assert [event.seq for event in run.events] == [1, 2]
    assert [event.name for event in run.events] == ["read_tasks", "prioritize_tasks"]


def test_timestamps_are_ordered_start_then_event_then_end():
    clock = _Clock(["2026-11-02T10:00:00+00:00",
                    "2026-11-02T10:00:01+00:00",
                    "2026-11-02T10:00:02+00:00"])
    run = start_run(run_id="R1", clock=clock)
    event = record_event(run, "read_tasks", arguments={}, status="ok", duration_ms=1.0, clock=clock)
    end_run(run, clock=clock)

    assert run.started_at <= event.timestamp <= run.ended_at


def test_end_run_sets_the_end_timestamp():
    run = start_run(run_id="R1", clock=lambda: "T0")
    assert run.ended_at is None
    end_run(run, clock=lambda: "T9")
    assert run.ended_at == "T9"


def test_envelope_requires_a_run_id_and_a_start():
    # The envelope is a validated model: it cannot exist without its identity.
    with pytest.raises(ValidationError):
        TraceEnvelope(started_at="T0")  # no run_id
    with pytest.raises(ValidationError):
        TraceEnvelope(run_id="R1")  # no started_at


# --- The envelope produced by a real loop run ---------------------------------


def test_the_loop_returns_an_envelope_whose_events_share_the_run_id():
    spy_tools = {
        "read_tasks": lambda arguments: [{"id": "t1"}],
        "prioritize_tasks": lambda arguments: {"priority": [{"id": "t1"}]},
        "validate_priority_result": lambda arguments: {"valid": True},
    }
    scripted = [
        _fake_message([_fake_tool_call("c1", "read_tasks", "{}")]),
        _fake_message([_fake_tool_call("c2", "prioritize_tasks", "{}")]),
        _fake_message([_fake_tool_call("c3", "validate_priority_result", "{}")]),
        _fake_message(None),
    ]
    client = _FakeClient(scripted)

    result = run_tool_loop(client, [], TOOL_SCHEMAS, tools=spy_tools, run_id="RUN-A")
    run = result["run"]

    assert run.run_id == "RUN-A"
    assert run.ended_at is not None
    # One event per tool call, in order, all sharing the one run id.
    assert [event.name for event in run.events] == [
        "read_tasks",
        "prioritize_tasks",
        "validate_priority_result",
    ]
    assert {event.run_id for event in run.events} == {"RUN-A"}


def test_two_loop_runs_get_different_run_ids():
    spy_tools = {"read_tasks": lambda arguments: [{"id": "t1"}]}
    scripted = [_fake_message(None)]  # answers at once, no tool call

    run_a = run_tool_loop(_FakeClient(scripted), [], TOOL_SCHEMAS, tools=spy_tools)["run"]
    run_b = run_tool_loop(_FakeClient(scripted), [], TOOL_SCHEMAS, tools=spy_tools)["run"]

    assert run_a.run_id != run_b.run_id


# --- D2-022: a full, typed event (tool, arguments, status, duration) ----------


def test_record_event_stores_the_tool_call_arguments_status_and_duration():
    # The accepted case: a well-formed event keeps every field it was given.
    run = start_run(run_id="R1", clock=lambda: "T0")
    event = record_event(
        run,
        "read_tasks",
        arguments={"limit": 3},
        status="ok",
        duration_ms=12.5,
        clock=lambda: "T1",
    )
    assert event.name == "read_tasks"
    assert event.arguments == {"limit": 3}
    assert event.status == "ok"
    assert event.duration_ms == 12.5
    # It is stored as the same typed event, not a loose dict.
    assert run.events == [event]
    assert isinstance(run.events[0], TraceEvent)


def test_an_event_with_an_unknown_status_is_refused():
    # status is a closed set: anything but "ok"/"error" cannot be recorded.
    with pytest.raises(ValidationError):
        TraceEvent(
            run_id="R1",
            seq=1,
            timestamp="T1",
            name="read_tasks",
            arguments={},
            status="maybe",
            duration_ms=1.0,
        )


def test_an_event_without_a_duration_is_refused():
    # Every field is required: an event that does not say how long it took
    # cannot be built, so it is never recorded with a silent default.
    with pytest.raises(ValidationError):
        TraceEvent(
            run_id="R1",
            seq=1,
            timestamp="T1",
            name="read_tasks",
            arguments={},
            status="ok",
        )


def test_the_loop_records_arguments_status_and_duration_per_event():
    # A broken tool returns an {"error": ...} result; a good one does not.
    spy_tools = {
        "read_tasks": lambda arguments: [{"id": "t1"}],
        "broken_tool": lambda arguments: {"error": "boom"},
    }
    scripted = [
        _fake_message([_fake_tool_call("c1", "read_tasks", '{"limit": 3}')]),
        _fake_message([_fake_tool_call("c2", "broken_tool", "{}")]),
        _fake_message(None),
    ]
    # A fake span timer: timer() is read just before and just after each call,
    # so each tool's duration is a known, exact number of milliseconds.
    #   read_tasks:  10.5 - 10.0  = 0.5 s  -> 500 ms
    #   broken_tool: 20.25 - 20.0 = 0.25 s -> 250 ms
    timer = _Clock([10.0, 10.5, 20.0, 20.25])

    run = run_tool_loop(
        _FakeClient(scripted), [], TOOL_SCHEMAS, tools=spy_tools, run_id="RUN-D", timer=timer
    )["run"]

    first, second = run.events
    assert first.name == "read_tasks"
    assert first.arguments == {"limit": 3}  # the real arguments the model sent
    assert first.status == "ok"  # a non-error result
    assert first.duration_ms == 500.0

    assert second.name == "broken_tool"
    assert second.status == "error"  # the {"error": ...} result is seen as a failure
    assert second.duration_ms == 250.0
