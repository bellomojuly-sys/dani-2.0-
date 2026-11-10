"""The chat with Dani: build the prompt from Giulia's context and today's data,
ask the model, return its text.

The chat only reads. It has no tools, so it cannot change Notion or a calendar:
writing stays behind an explicit yes (roadmap M08). The data Dani can talk
about is exactly what the dashboard shows (``Live.state``), written into the
system prompt as short lines, so an answer can be checked against the page.

``speech_to_text`` is the voice side: it sends a recording to Whisper. It is a
separate provider (OpenAI) with its own key, so it is optional.
"""

MODEL = "deepseek-flash"
MAX_HISTORY = 12  # older turns are dropped so the prompt stays small
MAX_TASKS = 20


def _clock(iso):
    return iso[11:16]


def describe_state(state):
    """Turn the dashboard data into the plain lines the model reads."""
    lines = [f"Now: {state['now']} (Europe/Amsterdam). The week shown: {state['days'][0]} to {state['days'][-1]}."]
    lines.append("Calendar events this week:")
    for event in state["events"]:
        when = "all day" if event["all_day"] else f"{_clock(event['start'])}-{_clock(event['end'])}"
        lines.append(f"- {event['start'][:10]} {when} [{event['calendar']}] {event['title']}")
    if not state["events"]:
        lines.append("- none")
    lines.append("Planned study blocks (proposed by the planner, not in the calendar):")
    for block in state["blocks"]:
        lines.append(f"- {block['start'][:10]} {_clock(block['start'])}-{_clock(block['end'])} {block['title']}")
    lines.append(f"Open tasks, most important first (showing {min(len(state['tasks']), MAX_TASKS)} of {len(state['tasks'])}):")
    for task in state["tasks"][:MAX_TASKS]:
        deadline = task["deadline"] or "no deadline"
        lines.append(f"- {task['title']} ({task['area'] or 'no area'}, {deadline}, {task['priority'] or 'no priority'})")
    cycle = state.get("cycle")
    if cycle:
        lines.append(f"Cycle phase (estimate): {cycle['phase']}. {cycle['hint']}")
    return "\n".join(lines)


def build_chat_messages(context, state, history, message):
    """Return the messages for the model: system prompt, recent turns, new message.

    ``history`` is what the page sends back: a list of {"role", "content"}.
    Only "user" and "assistant" turns are kept (a "system" turn from the page
    would be a way to rewrite Dani's rules), and only the last MAX_HISTORY.
    """
    if not message.strip():
        raise ValueError("the message is empty")
    about_giulia = context.strip() or "(she has not written a context yet)"
    system = (
        "You are Dani, Giulia's personal planning assistant. Answer in Italian, short and warm, "
        "like a spoken answer: no tables, no markdown.\n"
        "Use only the data below. If something is not in the data, say you do not know.\n"
        "You cannot change the calendar or Notion from this chat. If she asks for a change, say "
        "exactly what you would change and that writing from the chat is not connected yet; never say "
        "it is done and never offer to do it yourself.\n\n"
        f"What Giulia told you about herself and her rules:\n{about_giulia}\n\n"
        f"{describe_state(state)}"
    )
    turns = [
        {"role": turn["role"], "content": turn["content"]}
        for turn in history
        if turn.get("role") in ("user", "assistant") and isinstance(turn.get("content"), str)
    ]
    return [{"role": "system", "content": system}] + turns[-MAX_HISTORY:] + [
        {"role": "user", "content": message.strip()}
    ]


def chat_reply(client, context, state, history, message, model=MODEL):
    """Ask the model and return its text. An empty answer raises ValueError."""
    messages = build_chat_messages(context, state, history, message)
    response = client.chat.completions.create(model=model, messages=messages)
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("the model returned an empty answer")
    return text


def speech_to_text(client, audio, filename="voice.webm"):
    """Send one recording to Whisper and return the text. Empty raises ValueError."""
    if not audio:
        raise ValueError("the recording is empty")
    result = client.audio.transcriptions.create(model="whisper-1", file=(filename, audio), language="it")
    text = (result.text or "").strip()
    if not text:
        raise ValueError("no speech was recognised")
    return text
