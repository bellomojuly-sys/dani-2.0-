def read_tasks():
    """Return the three hardcoded tasks for the first MVP.

    This is an ordinary Python function: no LLM, no API call.
    Each task is a dict with a stable short "id" and a readable "title".
    The "id" is what later validation will check (each id appears once,
    no id is invented).
    """
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
