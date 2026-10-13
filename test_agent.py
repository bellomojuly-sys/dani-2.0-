from types import SimpleNamespace

from agent import read_tool_calls, run_tool_call


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
