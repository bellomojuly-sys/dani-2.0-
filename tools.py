def _check_no_arguments(tool_name, arguments):
    """Return a structured error dict if arguments were given, else None.

    "No arguments" is accepted as either None or an empty dict {}.
    Anything else (a non-empty dict, or a value that is not a dict) is a
    validation error. We RETURN the error instead of raising it, so the
    tool loop can hand it back to the LLM to correct itself, and so a wrong
    call never crashes and never produces an invented result.
    """
    if arguments is None or arguments == {}:
        return None
    return {"error": f"{tool_name} takes no arguments, got: {arguments!r}"}


def read_tasks(arguments=None):
    """Return the three hardcoded tasks for the first MVP.

    This is an ordinary Python function: no LLM, no API call.
    Each task is a dict with a stable short "id" and a readable "title".
    The "id" is what later validation will check (each id appears once,
    no id is invented).

    The tool validates the arguments it receives BEFORE doing any work.
    read_tasks takes no arguments, so anything other than an empty set of
    arguments is rejected with a structured error (a dict with an "error"
    key), never a crash and never an invented result.
    """
    error = _check_no_arguments("read_tasks", arguments)
    if error is not None:
        return error
    return [
        {"id": "t1", "title": "Finish the AMEXIO case model"},
        {"id": "t2", "title": "Study MCP"},
        {"id": "t3", "title": "Answer the email from my teacher"},
    ]


# --- Tool schema: the "business card" the LLM reads ---------------------------
# The LLM never sees the Python code above. It only sees this description and
# decides whether to ask for the tool. read_tasks takes no arguments, so the
# parameters object has no properties.
READ_TASKS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_tasks",
        "description": "Return the user's current tasks, each with an id and a title.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


# --- Toolbox: what we hand to the LLM, and how we run a tool by name ----------
# TOOL_SCHEMAS is the list of descriptions we send to the LLM.
# TOOLS maps each tool name to the real Python function, so we can execute the
# tool the LLM asks for by looking it up here.
TOOL_SCHEMAS = [READ_TASKS_SCHEMA]
TOOLS = {"read_tasks": read_tasks}
