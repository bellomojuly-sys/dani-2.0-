import json
from types import SimpleNamespace

from agent import (
    read_tool_calls,
    run_tool_call,
    build_tool_result_message,
    run_tool_loop,
    final_outcome,
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


def test_read_tool_calls_treats_missing_arguments_as_empty_dict():
    # The SDK may send None or an empty/whitespace string for a no-arg call;
    # all of these must parse to an empty dict, never crash.
    for raw in (None, "", "   "):
        message = _fake_message([_fake_tool_call("c", "read_tasks", raw)])
        calls = read_tool_calls(message)
        assert calls[0]["arguments"] == {}


def test_read_tool_calls_parses_json_arguments():
    # A real JSON argument string must be parsed into the matching dict.
    message = _fake_message([_fake_tool_call("c", "prioritize_tasks", '{"order": []}')])
    calls = read_tool_calls(message)
    assert calls[0]["arguments"] == {"order": []}


def test_read_tool_calls_handles_a_message_without_the_attribute():
    # A message object that has no tool_calls attribute at all must be treated
    # as "no tool requested", not crash.
    message = SimpleNamespace()
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
        # Record what the loop passed on the LAST create() call, so a test can
        # check the request was built correctly (model, messages, tools).
        self.last_model = "unset"
        self.last_messages = "unset"
        self.last_tools = "unset"
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model=None, messages=None, tools=None):
        self.last_model = model
        self.last_messages = messages
        self.last_tools = tools
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
    # The answered result carries the model's final message.
    assert result["final"] is scripted[-1]


def test_run_tool_loop_stops_at_the_iteration_limit():
    spy_tools = {"read_tasks": lambda arguments: [{"id": "t1"}]}
    scripted = [_fake_message([_fake_tool_call("c", "read_tasks", "{}")])]
    # The model always asks for a tool and never answers.
    client = _FakeClient(scripted, repeat_last=True)

    result = run_tool_loop(client, [], TOOL_SCHEMAS, max_iterations=3, tools=spy_tools)

    assert result["status"] == "stopped"
    assert len(result["trace"]) == 3
    # A stopped run has no final message.
    assert result["final"] is None


def test_run_tool_loop_default_iteration_cap_is_five():
    # With no max_iterations given, the default cap must apply (not more).
    spy_tools = {"read_tasks": lambda arguments: [{"id": "t1"}]}
    scripted = [_fake_message([_fake_tool_call("c", "read_tasks", "{}")])]
    client = _FakeClient(scripted, repeat_last=True)

    result = run_tool_loop(client, [], TOOL_SCHEMAS, tools=spy_tools)

    assert result["status"] == "stopped"
    assert len(result["trace"]) == 5


def test_run_tool_loop_sends_the_model_messages_and_tools():
    # The request to the model must carry the right model, the running
    # messages list, and the tool schemas.
    scripted = [_fake_message(None)]  # answers at once, no tool calls
    client = _FakeClient(scripted)
    messages = [{"role": "user", "content": "hi"}]

    run_tool_loop(client, messages, TOOL_SCHEMAS)

    assert client.last_model == "deepseek-flash"
    assert client.last_messages is messages
    assert client.last_tools is TOOL_SCHEMAS


def test_run_tool_loop_feeds_each_tool_result_back_into_the_messages():
    # The loop must append a 'tool' message carrying the real result, tied to
    # the call id, so the model answers from the result and not from memory.
    spy_tools = {"read_tasks": lambda arguments: [{"id": "t1", "title": "real"}]}
    assistant_turn = _fake_message([_fake_tool_call("c1", "read_tasks", "{}")])
    scripted = [assistant_turn, _fake_message(None)]
    client = _FakeClient(scripted)
    messages = []

    run_tool_loop(client, messages, TOOL_SCHEMAS, tools=spy_tools)

    # The assistant turn object itself was appended to the transcript.
    assert messages[0] is assistant_turn
    # Exactly one tool message, with the right role, id and serialized result.
    tool_messages = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "c1"
    assert tool_messages[0]["content"] == json.dumps([{"id": "t1", "title": "real"}])


def test_full_run_covers_every_source_id_exactly_once():
    real_ids = [task["id"] for task in read_tasks()]
    order = {"order": [
        {"id": "t2", "title": "Study MCP", "reason": "needed next"},
        {"id": "t1", "title": "Finish the AMEXIO case model", "reason": "deadline"},
        {"id": "t3", "title": "Answer the email from my teacher", "reason": "quick"},
    ]}
    validate_args = {
        "priority": [{"id": "t2"}, {"id": "t1"}, {"id": "t3"}],
        "known_ids": real_ids,
    }
    scripted = [
        _fake_message([_fake_tool_call("c1", "read_tasks", "{}")]),
        _fake_message([_fake_tool_call("c2", "prioritize_tasks", json.dumps(order))]),
        _fake_message([_fake_tool_call("c3", "validate_priority_result", json.dumps(validate_args))]),
        _fake_message(None),
    ]
    client = _FakeClient(scripted)

    result = run_tool_loop(client, [], TOOL_SCHEMAS)  # real tools
    outcome = final_outcome(result)

    assert outcome["ok"] is True
    assert outcome["reason"] == "validated"
    seen = [row["id"] for row in outcome["priority"]]
    assert sorted(seen) == sorted(real_ids)
    for task_id in real_ids:
        assert seen.count(task_id) == 1


def test_honest_failure_when_the_task_source_fails():
    failing_tools = {
        "read_tasks": lambda arguments: {"error": "task source unavailable"},
        "prioritize_tasks": prioritize_tasks,
        "validate_priority_result": validate_priority_result,
    }
    scripted = [
        _fake_message([_fake_tool_call("c1", "read_tasks", "{}")]),
        _fake_message(None),  # the model stops and answers honestly
    ]
    client = _FakeClient(scripted)

    result = run_tool_loop(client, [], TOOL_SCHEMAS, tools=failing_tools)
    outcome = final_outcome(result)

    assert outcome["ok"] is False
    assert outcome["reason"] == "task source unavailable"
    assert outcome["priority"] is None


def test_no_fabricated_priority_after_a_source_failure():
    # Even if the model invents a task after the source failed, and even if a
    # (bogus) validation passes, the outcome must refuse to present a priority.
    failing_tools = {
        "read_tasks": lambda arguments: {"error": "task source unavailable"},
        "prioritize_tasks": prioritize_tasks,
        "validate_priority_result": lambda arguments: {"valid": True},
    }
    invented = {"order": [{"id": "x", "title": "made up", "reason": "invented"}]}
    scripted = [
        _fake_message([_fake_tool_call("c1", "read_tasks", "{}")]),
        _fake_message([_fake_tool_call("c2", "prioritize_tasks", json.dumps(invented))]),
        _fake_message([_fake_tool_call("c3", "validate_priority_result", json.dumps({"priority": [{"id": "x"}], "known_ids": ["x"]}))]),
        _fake_message(None),
    ]
    client = _FakeClient(scripted)

    result = run_tool_loop(client, [], TOOL_SCHEMAS, tools=failing_tools)
    outcome = final_outcome(result)

    assert outcome["ok"] is False
    assert outcome["priority"] is None


def test_final_outcome_refuses_a_result_that_was_never_validated():
    # Source read fine and a priority was produced, but validate_priority_result
    # never ran: the outcome must refuse it with the right reason, not present it.
    loop_result = {
        "trace": [
            {"name": "read_tasks", "result": [{"id": "t1"}]},
            {"name": "prioritize_tasks", "result": {"priority": [{"id": "t1"}]}},
        ]
    }
    outcome = final_outcome(loop_result)
    assert outcome["ok"] is False
    assert outcome["reason"] == "result not validated"
    assert outcome["priority"] is None


def test_final_outcome_does_not_treat_a_non_error_read_as_a_failure():
    # A read result that is a dict WITHOUT an 'error' key is not a source
    # failure, so the outcome must not be "task source unavailable".
    loop_result = {
        "trace": [
            {"name": "read_tasks", "result": {"status": "ok"}},
            {"name": "validate_priority_result", "result": {"valid": True}},
        ]
    }
    outcome = final_outcome(loop_result)
    assert outcome["reason"] != "task source unavailable"


def test_final_outcome_validated_without_a_prioritize_entry_has_no_priority():
    # Defensive: validation passed but no prioritize_tasks ran. The outcome is
    # ok with priority None, and must not crash reaching for a missing entry.
    loop_result = {
        "trace": [
            {"name": "read_tasks", "result": [{"id": "t1"}]},
            {"name": "validate_priority_result", "result": {"valid": True}},
        ]
    }
    outcome = final_outcome(loop_result)
    assert outcome["ok"] is True
    assert outcome["reason"] == "validated"
    assert outcome["priority"] is None


def test_final_outcome_refuses_when_validation_returned_false():
    # Source read fine, but validate_priority_result returned valid: False.
    loop_result = {
        "trace": [
            {"name": "read_tasks", "result": [{"id": "t1"}]},
            {"name": "prioritize_tasks", "result": {"priority": [{"id": "t1"}]}},
            {"name": "validate_priority_result", "result": {"valid": False, "error": "missing ids"}},
        ]
    }
    outcome = final_outcome(loop_result)
    assert outcome["ok"] is False
    assert outcome["reason"] == "result not validated"
    assert outcome["priority"] is None
