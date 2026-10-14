import json

from tools import TOOLS


def read_tool_calls(message):
    """Return the tool calls the LLM requested from a response message.

    The OpenAI/DeepSeek SDK puts tool requests on `message.tool_calls`; each
    one carries a function name and its arguments as a JSON string. We turn
    them into a simple, testable list of dicts:
        {"id": str, "name": str, "arguments": dict}
    If the model requested no tool, we return an empty list.
    """
    tool_calls = getattr(message, "tool_calls", None) or []
    calls = []
    for tool_call in tool_calls:
        raw_arguments = tool_call.function.arguments or "{}"
        arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
        calls.append(
            {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": arguments,
            }
        )
    return calls


def run_tool_call(call, tools=TOOLS):
    """Execute one requested tool call exactly once and return its result.

    We look the tool up by name in the toolbox and call it with the
    arguments the LLM provided. Calling this function once runs the tool
    once: there is no loop and no retry here. An unknown tool name is a
    structured error, never a crash and never an invented result.
    """
    name = call["name"]
    if name not in tools:
        return {"error": f"unknown tool: {name!r}"}
    function = tools[name]
    return function(call["arguments"])


def build_tool_result_message(call):
    """Run the requested tool and wrap its result as a 'tool' role message.

    This is the last leg of the round: the content is the JSON-serialized
    tool result, tied back to the request through `tool_call_id`. The LLM
    receives the REAL data (the three real task titles) and answers from it,
    so it cannot invent tasks.
    """
    result = run_tool_call(call)
    return {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": json.dumps(result),
    }


def run_tool_loop(client, messages, tool_schemas, model="deepseek-flash", max_iterations=5, tools=TOOLS):
    """Let the LLM call tools in sequence until it answers, with a hard limit.

    One iteration = one model turn. Each turn we hand the model the toolbox,
    read the tools it requested, run each one, and feed the results back. When
    the model stops requesting tools and answers in plain text, the loop ends
    with status "answered". If it keeps requesting tools past max_iterations,
    the loop ends with status "stopped": this is the safety cap, so the agent
    can never run forever.

    We return an ordered call trace (each entry {"name", "result"}), so the
    whole run can be reconstructed and checked afterwards.
    """
    trace = []
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=model, messages=messages, tools=tool_schemas
        )
        message = response.choices[0].message
        messages.append(message)

        calls = read_tool_calls(message)
        if not calls:
            return {"status": "answered", "final": message, "trace": trace}

        for call in calls:
            result = run_tool_call(call, tools=tools)
            trace.append({"name": call["name"], "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result),
                }
            )

    return {"status": "stopped", "final": None, "trace": trace}


def final_outcome(loop_result):
    """Turn a loop result into a verified outcome, never a bare guess.

    The outcome is ok only if validate_priority_result passed in the run. Then
    we return the validated priority report. Otherwise ok is False with the
    reason and no priority, so an unverified result is never presented as an
    answer.
    """
    trace = loop_result["trace"]

    # Honest failure first: if the task source itself failed, there is no
    # trustworthy task list, so we refuse to present any priority, even if the
    # model went on to fabricate one and a later check passed (D2-020).
    read = [entry for entry in trace if entry["name"] == "read_tasks"]
    source_failed = any(
        isinstance(entry["result"], dict) and "error" in entry["result"] for entry in read
    )
    if source_failed:
        return {"ok": False, "reason": "task source unavailable", "priority": None}

    validate = [entry for entry in trace if entry["name"] == "validate_priority_result"]
    valid = (
        bool(validate)
        and isinstance(validate[-1]["result"], dict)
        and validate[-1]["result"].get("valid") is True
    )
    if not valid:
        return {"ok": False, "reason": "result not validated", "priority": None}

    prioritize = [entry for entry in trace if entry["name"] == "prioritize_tasks"]
    priority = prioritize[-1]["result"].get("priority") if prioritize else None
    return {"ok": True, "reason": "validated", "priority": priority}
