import json
from types import SimpleNamespace

from main import build_messages, require_api_key, format_report, run
from tools import read_tasks, TOOL_SCHEMAS
from skill import TOOLBOX_SKILL


# --- Fakes: same shape as the OpenAI/DeepSeek SDK, but no network -------------
def _fake_tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id, type="function", function=SimpleNamespace(name=name, arguments=arguments)
    )


def _fake_message(tool_calls, content=None):
    return SimpleNamespace(tool_calls=tool_calls, content=content)


class _FakeClient:
    """Scripted stand-in for the client: returns messages in order, no API."""

    def __init__(self, scripted_messages):
        self._messages = scripted_messages
        self.calls = 0
        self.last_model = "unset"
        self.last_tools = "unset"
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model=None, messages=None, tools=None):
        self.last_model = model
        self.last_tools = tools
        message = self._messages[self.calls]
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# --- require_api_key: fail loud when the key is missing (D2-007) --------------
def test_require_api_key_returns_the_key_when_present():
    assert require_api_key({"DEEPSEEK_API_KEY": "abc"}) == {"api_key": "abc"}


def test_require_api_key_reports_a_missing_key():
    result = require_api_key({})
    assert result == {"error": "Missing DEEPSEEK_API_KEY"}


def test_require_api_key_treats_an_empty_key_as_missing():
    # An empty string is not a usable key: it must fail loud, not slip through.
    assert require_api_key({"DEEPSEEK_API_KEY": ""}) == {"error": "Missing DEEPSEEK_API_KEY"}


# --- build_messages: only the intended messages are sent (D2-009) -------------
def test_build_messages_is_system_then_user_with_the_skill():
    messages = build_messages()
    assert [m["role"] for m in messages] == ["system", "user"]
    assert TOOLBOX_SKILL in messages[0]["content"]
    assert messages[1]["content"] == "What should I do first today?"


def test_build_messages_system_content_is_exactly_the_composed_prompt():
    # Pin the exact system prompt (framing + skill + closing instruction), so
    # any change to that wording is caught, not only the skill's presence.
    expected = (
        "You are Dani, a personal planning assistant.\n"
        + TOOLBOX_SKILL
        + "\nAfter the result is validated, tell the user in plain text what to do first and why."
    )
    assert build_messages()[0]["content"] == expected


# --- format_report: shows a priority only when it was verified ----------------
def test_format_report_shows_the_validated_priority():
    result = {
        "trace": [
            {"name": "read_tasks", "result": [{"id": "t1"}]},
            {"name": "prioritize_tasks", "result": {"priority": [
                {"rank": 1, "id": "t1", "title": "Finish the AMEXIO case model", "reason": "deadline"}
            ]}},
            {"name": "validate_priority_result", "result": {"valid": True}},
        ],
        "final": _fake_message(None, content="Do the case model first."),
    }
    lines = format_report(result)
    # The first line names the tools in call order, from the real trace.
    assert any(
        line.startswith("Tool call order:")
        and "read_tasks" in line
        and "validate_priority_result" in line
        for line in lines
    )
    assert "Validated priority — what to do first:" in lines
    assert any("t1 — Finish the AMEXIO case model (deadline)" in line for line in lines)
    assert "Dani says: Do the case model first." in lines


def test_format_report_shows_honest_failure_and_no_priority():
    # Source failed: the report must state the reason and show no priority.
    result = {
        "trace": [{"name": "read_tasks", "result": {"error": "task source unavailable"}}],
        "final": None,
    }
    lines = format_report(result)
    assert "No verified answer: task source unavailable" in lines
    assert not any("Validated priority" in line for line in lines)
    assert not any(line.startswith("Dani says:") for line in lines)


# --- run: a full run through a FAKE client, never the real API ----------------
def test_run_uses_the_injected_client_and_prints_the_validated_report():
    real_ids = [task["id"] for task in read_tasks()]
    order = {"order": [
        {"id": "t1", "title": "Finish the AMEXIO case model", "reason": "deadline"},
        {"id": "t2", "title": "Study MCP", "reason": "needed next"},
        {"id": "t3", "title": "Answer the email from my teacher", "reason": "quick"},
    ]}
    validate_args = {"priority": [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}], "known_ids": real_ids}
    scripted = [
        _fake_message([_fake_tool_call("c1", "read_tasks", "{}")]),
        _fake_message([_fake_tool_call("c2", "prioritize_tasks", json.dumps(order))]),
        _fake_message([_fake_tool_call("c3", "validate_priority_result", json.dumps(validate_args))]),
        _fake_message(None, content="Start with the case model."),
    ]
    client = _FakeClient(scripted)

    printed = []
    result = run(client, out=printed.append)

    assert client.calls == 4  # the fake client was used, not the real API
    # run() must send the right model and the tool schemas to the client.
    assert client.last_model == "deepseek-flash"
    assert client.last_tools is TOOL_SCHEMAS
    assert result["status"] == "answered"
    assert any("Validated priority" in line for line in printed)
    assert "Dani says: Start with the case model." in printed
