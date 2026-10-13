import json


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
