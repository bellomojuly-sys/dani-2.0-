import json
from types import SimpleNamespace

from agent import (
    read_tool_calls,
    run_tool_call,
    build_tool_result_message,
    run_tool_loop,
)
from tools import read_tasks, prioritize_tasks, validate_priority_result, TOOL_SCHEMAS


def _fake_tool_call(call_id, name, arguments):
    """Build a fake tool call shaped like the OpenAI/DeepSeek SDK object."""
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _fake_message(tool_calls):
    return SimpleNamespace(tool_calls=tool_calls)


def test_read_tool_calls_names_the_requested_tool():
    message = _fake_message([_fake_tool_call("call_1", "read_tasks", "{}")])
    calls = read_tool_calls(message)
    assert len(calls) == 1
    assert calls[0]["name"] == "read_tasks"
    assert calls[0]["arguments"] == {}


def test_read_tool_calls_is_empty_when_no_tool_requested():
    message = _fake_message(None)
    assert read_tool_calls(message) == []


def test_run_tool_call_executes_the_tool_exactly_once():
    runs = []

    def spy_tool(arguments):
        runs.append(arguments)
        return ["done"]

    call = {"id": "call_1", "name": "spy", "arguments": {}}
    result = run_tool_call(call, tools={"spy": spy_tool})

    assert len(runs) == 1
    assert result == ["done"]


def test_run_tool_call_runs_the_real_read_tasks_tool():
    call = {"id": "call_1", "name": "read_tasks", "arguments": {}}
    result = run_tool_call(call)
    assert len(result) == 3


def test_run_tool_call_rejects_unknown_tool_with_structured_error():
    call = {"id": "call_1", "name": "delete_everything", "arguments": {}}
    result = run_tool_call(call)
    assert isinstance(result, dict)
    assert "error" in result


def test_tool_result_message_carries_the_three_real_titles():
    call = {"id": "call_1", "name": "read_tasks", "arguments": {}}
    message = build_tool_result_message(call)

    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call_1"

    returned_titles = [task["title"] for task in json.loads(message["content"])]
    assert returned_titles == [task["title"] for task in read_tasks()]


def test_tool_result_message_does_not_contain_an_invented_title():
    call = {"id": "call_1", "name": "read_tasks", "arguments": {}}
    message = build_tool_result_message(call)
    assert "Buy a yacht" not in message["content"]


class _FakeClient:
    """A scripted stand-in for the OpenAI/DeepSeek client (no network).

    It returns the scripted messages in order, one per create() call. With
    repeat_last=True it keeps returning the last one, to simulate a model that
    never stops requesting tools (used to test the iteration cap).
    """

    def __init__(self, scripted_messages, repeat_last=False):
        self._messages = scripted_messages
        self._repeat_last = repeat_last
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model=None, messages=None, tools=None):
        if self.calls < len(self._messages):
            message = self._messages[self.calls]
        elif self._repeat_last:
            message = self._messages[-1]
        else:
            raise AssertionError("fake client ran out of scripted messages")
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_run_tool_loop_records_the_call_trace_in_order():
    spy_tools = {
        "read_tasks": lambda arguments: [{"id": "t1"}],
        "prioritize_tasks": lambda arguments: {"priority": [{"id": "t1"}]},
        "validate_priority_result": lambda arguments: {"valid": True},
    }
    scripted = [
        _fake_message([_fake_tool_call("c1", "read_tasks", "{}")]),
        _fake_message([_fake_tool_call("c2", "prioritize_tasks", "{}")]),
        _fake_message([_fake_tool_call("c3", "validate_priority_result", "{}")]),
        _fake_message(None),  # final answer: no more tool calls
    ]
    client = _FakeClient(scripted)

    result = run_tool_loop(client, [], TOOL_SCHEMAS, tools=spy_tools)

    names = [entry["name"] for entry in result["trace"]]
    assert names == ["read_tasks", "prioritize_tasks", "validate_priority_result"]
    assert result["status"] == "answered"


def test_run_tool_loop_stops_at_the_iteration_limit():
    spy_tools = {"read_tasks": lambda arguments: [{"id": "t1"}]}
    scripted = [_fake_message([_fake_tool_call("c", "read_tasks", "{}")])]
    # The model always asks for a tool and never answers.
    client = _FakeClient(scripted, repeat_last=True)

    result = run_tool_loop(client, [], TOOL_SCHEMAS, max_iterations=3, tools=spy_tools)

    assert result["status"] == "stopped"
    assert len(result["trace"]) == 3
