"""The chat with Dani: build the prompt from Giulia's context and today's data,
ask the model, return its text.

The chat never writes. It can read more by itself through the read tools of
reader.py (D2-056, a bounded tool loop in ``chat_turn``) and it can only
*propose* a change: writing stays behind an explicit yes (roadmap M08). The data Dani can talk
about is exactly what the dashboard shows (``Live.state``), written into the
system prompt as short lines, so an answer can be checked against the page.

``speech_to_text`` is the voice side: it sends a recording to Whisper. It is a
separate provider (OpenAI) with its own key, so it is optional.
"""

import json

from persona import PERSONA

MODEL = "deepseek-flash"
MAX_HISTORY = 12  # older turns are dropped so the prompt stays small
MAX_TASKS = 20


def _clock(iso):
    return iso[11:16]


def describe_state(state):
    """Turn the dashboard data into the plain lines the model reads."""
    lines = [f"Now: {state['now']} (Europe/Amsterdam). The week shown: {state['days'][0]} to {state['days'][-1]}."]
    lines.append("Calendar events this week (the name in front, e1, e2..., is the event reference):")
    for number, event in enumerate(state["events"], 1):
        when = "all day" if event["all_day"] else f"{_clock(event['start'])}-{_clock(event['end'])}"
        lines.append(f"- e{number}: {event['start'][:10]} {when} [{event['calendar']}] {event['title']}")
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


NO_WRITE_RULE = (
    "You cannot change the calendar or Notion from this chat. If she asks for a change, say "
    "exactly what you would change and that writing from the chat is not connected yet; never say "
    "it is done and never offer to do it yourself."
)


PLAN_RULE = (
    "To plan a period (a day, a week, a month), work top-down like her own planner: "
    "1) start from her goals and active projects (her life page above, read_projects) and the deadlines "
    "(read_tasks); 2) read the calendar of the whole period (read_calendar); 3) for a month, say first the "
    "month's goals per area and project (AMEXIO, Betsy, Dani, job search, MG), then what each week is for; "
    "for a week or a day, go straight to the blocks; 4) follow her planning rules; lessons, shifts and "
    "appointments never move; 5) plan her free time too and invest it (reading, courses, ICT study, gym, "
    "personal projects), but leave real rest; 6) then call propose_plan with the blocks of the nearest "
    "days (at most 20) and say in one sentence what does not fit and slips, and by how much."
)


def write_rule(can_move, can_task, can_plan=False):
    """The paragraph that tells the model what it may propose (never do)."""
    if not can_move and not can_task and not can_plan:
        return NO_WRITE_RULE
    parts = ["You cannot change the calendar or Notion yourself."]
    if can_move:
        parts.append(
            "To move a calendar event, call the propose_move tool once: it only creates a proposal "
            "that she confirms with a button. Events in calendars she cannot tick (shifts, lessons) "
            "are fixed. You cannot create or delete events."
        )
    else:
        parts.append("You cannot move calendar events from this chat.")
    if can_task:
        parts.append(
            "When she asks for a new task, call the propose_task tool once: it only creates a "
            "proposal that she confirms with a button. Use an area only if it is one of hers."
        )
    else:
        parts.append("You cannot change Notion.")
    if can_plan:
        parts.append("To add new blocks to her calendar, call propose_plan: she confirms each block. " + PLAN_RULE)
    parts.append("Never say a change is done.")
    return " ".join(parts)


def build_chat_messages(context, state, history, message, can_move=False, can_task=False, can_plan=False):
    """Return the messages for the model: system prompt, recent turns, new message.

    ``can_move`` says whether the calendar is connected in writing: only then
    is the model told about the propose_move tool. ``can_task`` does the same
    for creating a Notion task with propose_task (D2-055).

    ``history`` is what the page sends back: a list of {"role", "content"}.
    Only "user" and "assistant" turns are kept (a "system" turn from the page
    would be a way to rewrite Dani's rules), and only the last MAX_HISTORY.
    """
    if not message.strip():
        raise ValueError("the message is empty")
    about_giulia = context.strip() or "(she has not written a context yet)"
    system = (
        PERSONA + "\n"
        "Use only the data below. If something is not in the data, say you do not know.\n"
        + write_rule(can_move, can_task, can_plan)
        + "\n\n"
        + f"What Giulia told you about herself and her rules:\n{about_giulia}\n\n"
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


MAX_ROUNDS = 5  # read rounds per turn: the loop always ends, even if the model keeps asking

READ_RULE = (
    "The data below is only the week shown. You can look up more yourself with the read tools: "
    "other days, weeks and months (read_calendar), all her open tasks in every area and project "
    "(read_tasks), her projects and 1/3/10-year goals (read_projects) and her life plan, area and "
    "project pages (read_page). Read before you answer about anything outside this week, and "
    "plan from her goals down to the day. Never invent what a tool did not return."
)


def _call_id(call, number):
    return getattr(call, "id", None) or f"call_{number}"


def chat_turn(client, context, state, history, message, move_schema=None, task_schema=None,
              model=MODEL, read_tools=None, max_rounds=MAX_ROUNDS, plan_schema=None):
    """One turn in which the model may read (D2-056), then answer or propose.

    ``read_tools`` is {name: (schema, function)} (see reader.build_read_tools).
    The tool loop: the model answers; if it asked for read tools, each one runs
    once with its arguments, the results go back as "tool" messages and the
    model is asked again. At most ``max_rounds`` rounds, then ValueError.

    Returns {"text", "move", "task", "plan", "reads"}. ``move`` / ``task`` /
    ``plan`` are the arguments of the first propose_move / propose_task /
    propose_plan call, still unchecked: propose.build_proposal,
    build_task_proposal and build_plan_proposals validate them.
    ``reads`` lists every read that ran ({"tool", "arguments"}), so the page
    and the tests can see what Dani looked up. Arguments that are not JSON
    raise ValueError; so does an answer with neither text nor a call. At least
    one schema or read tool must be given.
    """
    read_tools = read_tools or {}
    tools = [schema for schema in (move_schema, task_schema, plan_schema) if schema is not None]
    tools += [schema for schema, _ in read_tools.values()]
    if not tools:
        raise ValueError("chat_turn needs at least one tool schema")
    messages = build_chat_messages(
        context, state, history, message,
        can_move=move_schema is not None, can_task=task_schema is not None,
        can_plan=plan_schema is not None,
    )
    if read_tools:
        messages[0]["content"] = messages[0]["content"].replace("Use only the data below.", READ_RULE, 1)
    wanted = {"propose_move": "move", "propose_task": "task", "propose_plan": "plan"}
    reads = []
    for _ in range(max_rounds):
        response = client.chat.completions.create(model=model, messages=messages, tools=tools)
        answer = response.choices[0].message
        text = (answer.content or "").strip()
        calls = list(answer.tool_calls or [])
        parsed = []
        for call in calls:
            try:
                parsed.append((call, json.loads(call.function.arguments or "{}")))
            except ValueError:
                raise ValueError("the model sent arguments that are not JSON") from None
        for call, arguments in parsed:
            slot = wanted.get(call.function.name)
            if slot is not None:
                return {"text": text, "move": None, "task": None, "plan": None, slot: arguments, "reads": reads}
        asked = [(call, arguments) for call, arguments in parsed if call.function.name in read_tools]
        if not asked:
            if not text:
                raise ValueError("the model returned an empty answer")
            return {"text": text, "move": None, "task": None, "plan": None, "reads": reads}
        ids = [_call_id(call, len(reads) + n) for n, (call, _) in enumerate(asked)]
        messages.append({
            "role": "assistant",
            "content": text or None,
            "tool_calls": [
                {"id": call_id, "type": "function",
                 "function": {"name": call.function.name, "arguments": call.function.arguments or "{}"}}
                for call_id, (call, _) in zip(ids, asked)
            ],
        })
        for call_id, (call, arguments) in zip(ids, asked):
            name = call.function.name
            result = read_tools[name][1](arguments if isinstance(arguments, dict) else {})
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })
            reads.append({"tool": name, "arguments": arguments})
    raise ValueError(f"the model kept reading for more than {max_rounds} rounds")


def speech_to_text(client, audio, filename="voice.webm"):
    """Send one recording to Whisper and return the text. Empty raises ValueError."""
    if not audio:
        raise ValueError("the recording is empty")
    result = client.audio.transcriptions.create(model="whisper-1", file=(filename, audio), language="it")
    text = (result.text or "").strip()
    if not text:
        raise ValueError("no speech was recognised")
    return text
