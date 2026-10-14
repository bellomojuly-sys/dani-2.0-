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


def prioritize_tasks(arguments=None):
    """Return a numbered priority report from the order the LLM decided.

    The LLM reads the real tasks, decides their order, and sends them back
    here. This tool does NOT reorder and does NOT call the API: it only
    checks the shape of the input and adds a rank to each task.
    """
    if not isinstance(arguments, dict) or "order" not in arguments:
        return {"error": f"prioritize_tasks needs an 'order' list, got: {arguments!r}"}
    order = arguments["order"]
    if not isinstance(order, list) or len(order) == 0:
        return {"error": f"'order' must be a non-empty list, got: {order!r}"}
    priority = []
    for rank, item in enumerate(order, start=1):
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str) for key in ("id", "title", "reason")
        ):
            return {"error": f"each order item needs string id, title and reason, got: {item!r}"}
        priority.append(
            {"rank": rank, "id": item["id"], "title": item["title"], "reason": item["reason"]}
        )
    return {"priority": priority}


def validate_priority_result(arguments=None):
    """Check a priority report against the real task ids. Deterministic, no API.

    The report is valid only if every known id appears exactly once and no
    unknown (invented) id appears. The three failure kinds are reported
    separately: unknown, duplicate, missing.

    A malformed CALL (wrong shape) returns a structured {"error": ...}.
    A well-formed but wrong report returns {"valid": False, "error": ...}.
    A correct report returns {"valid": True}.
    """
    if (
        not isinstance(arguments, dict)
        or "priority" not in arguments
        or "known_ids" not in arguments
    ):
        return {
            "error": f"validate_priority_result needs 'priority' and 'known_ids', got: {arguments!r}"
        }
    priority = arguments["priority"]
    known_ids = arguments["known_ids"]
    if not isinstance(priority, list) or not isinstance(known_ids, list):
        return {"error": "'priority' and 'known_ids' must both be lists"}

    seen = []
    for row in priority:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            return {"error": f"each priority row needs a string id, got: {row!r}"}
        seen.append(row["id"])

    known = set(known_ids)
    unknown = [task_id for task_id in seen if task_id not in known]
    if unknown:
        return {"valid": False, "error": f"unknown (invented) ids: {unknown}"}

    duplicates = sorted({task_id for task_id in seen if seen.count(task_id) > 1})
    if duplicates:
        return {"valid": False, "error": f"duplicate ids: {duplicates}"}

    missing = [task_id for task_id in known_ids if task_id not in seen]
    if missing:
        return {"valid": False, "error": f"missing ids: {missing}"}

    return {"valid": True}


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


# The LLM decides the order and sends every task back, most important first.
# This schema has a real argument: an array of objects, each with id, title and
# reason. It mirrors exactly what the prioritize_tasks function validates.
PRIORITIZE_TASKS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "prioritize_tasks",
        "description": (
            "Record the tasks in the priority order you decided. "
            "Pass every task back, most important first, each with its id, title and a one-line reason."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order": {
                    "type": "array",
                    "description": "The tasks in priority order, most important first.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["id", "title", "reason"],
                    },
                },
            },
            "required": ["order"],
        },
    },
}


# The guard tool. The LLM passes the priority report it produced and the real
# task ids, and gets back a verdict. It mirrors what validate_priority_result
# checks: every known id once, no invented id.
VALIDATE_PRIORITY_RESULT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "validate_priority_result",
        "description": (
            "Validate a priority report against the real task ids. "
            "Returns valid: true only if every known id appears exactly once and none is invented."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "array",
                    "description": "The priority rows to check; each must have an id.",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    },
                },
                "known_ids": {
                    "type": "array",
                    "description": "The real task ids the report must cover exactly.",
                    "items": {"type": "string"},
                },
            },
            "required": ["priority", "known_ids"],
        },
    },
}


# --- Toolbox: what we hand to the LLM, and how we run a tool by name ----------
# TOOL_SCHEMAS is the list of descriptions we send to the LLM.
# TOOLS maps each tool name to the real Python function, so we can execute the
# tool the LLM asks for by looking it up here.
TOOL_SCHEMAS = [READ_TASKS_SCHEMA, PRIORITIZE_TASKS_SCHEMA, VALIDATE_PRIORITY_RESULT_SCHEMA]
TOOLS = {
    "read_tasks": read_tasks,
    "prioritize_tasks": prioritize_tasks,
    "validate_priority_result": validate_priority_result,
}
