"""The morning briefing (D2-061): one short message every morning.

"Giulia, questo è il programma di oggi" — the day's fixed events, the study
blocks the planner proposes, the three most important tasks, the cycle phase,
the week's focus, and the question "oggi come stai?". On Sunday it asks for
next week's focus instead of listing work (no work on Sunday).

A pure function of the dashboard state, without the model: it costs no
tokens, it is the same every time for the same day, and every line can be
checked against the dashboard. Sending it is separate (notify.py), so the
text is tested without any network.
"""

MAX_TASKS = 3
WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
          "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _clock(iso):
    return iso[11:16]


def _today_items(rows, today):
    return [row for row in rows if row["start"][:10] == today]


def build_briefing(state, focus=None):
    """Return {"title", "text"} for the morning of ``state["today"]``.

    ``state`` is Live.state(...); ``focus`` is WeekFocus.status(today) or None.
    """
    from datetime import date

    today = state["today"]
    day = date.fromisoformat(today)
    title = f"Buongiorno Giulia · {WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"
    lines = []
    if day.weekday() == 6:
        lines.append("Oggi è domenica: niente lavoro né studio.")
    events = _today_items(state["events"], today)
    if events:
        lines.append("Questo è il programma di oggi:")
        for event in events:
            when = "tutto il giorno" if event["all_day"] else f"{_clock(event['start'])}–{_clock(event['end'])}"
            lines.append(f"• {when} {event['title']}")
    elif day.weekday() != 6:
        lines.append("Oggi non hai impegni fissi in calendario.")
    blocks = _today_items(state.get("blocks", []), today)
    if blocks and day.weekday() != 6:
        lines.append("Blocchi proposti: " + "; ".join(
            f"{_clock(block['start'])} {block['title']}" for block in blocks) + ".")
    tasks = state.get("tasks", [])[:MAX_TASKS]
    if tasks and day.weekday() != 6:
        lines.append("Le priorità: " + "; ".join(task["title"] for task in tasks) + ".")
    cycle = state.get("cycle")
    if cycle:
        lines.append(f"Ciclo: fase {cycle['phase']}. {cycle['hint']}".strip())
    if focus:
        if focus.get("this_focus"):
            lines.append(f"Il focus della settimana: {focus['this_focus']}")
        if day.weekday() == 6 and not focus.get("next_focus"):
            lines.append("Su cosa ti vuoi concentrare la settimana prossima? Rispondimi nell'app.")
    lines.append("E tu, oggi come stai?")
    return {"title": title, "text": "\n".join(lines)}
