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
