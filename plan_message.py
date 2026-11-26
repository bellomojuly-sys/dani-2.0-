"""D2-071: a plan she reads in one look and confirms once.

Before, a plan from the chat (D2-059) came as one card per block, each with
its own Conferma: with 15-20 blocks it was unreadable and her appointments
were not in it. Now a plan is one PlanProposal:

  - one message, day by day: every event of the day (lessons, shifts,
    appointments, gym) and the new blocks marked with 🆕;
  - on top, a verdict computed by code, never by the model: "Tranquilla,
    riesci a fare tutto" only when no block of the plan has a warning and the
    forecast (D2-065) has no deadline at risk or past; otherwise what is wrong;
  - one "Conferma tutto" that creates every block (server.py).

Pure functions: the same blocks, events and forecast always give the same text.
"""

from pydantic import BaseModel

from forecast import _hours
from propose import BlockProposal

WEEKDAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
TITLE_CHARS = 32
NOTE_CHARS = 300
MESSAGE_CHARS = 3800  # Telegram refuses a message over 4096 characters


class PlanProposal(BaseModel):
    """A whole plan waiting for one yes."""

    kind: str = "plan"
    id: str
    blocks: list[BlockProposal]
    fine: bool
    verdict: str


def short_title(title, limit=TITLE_CHARS):
    """A title that fits one line on the phone."""
    title = " ".join(title.split())
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def verdict(blocks, forecast_rows, forecast_error=None):
    """(fine, sentence): the code's answer to "do I manage everything?"."""
    problems = []
    flagged = sum(1 for block in blocks if block.warnings)
    if flagged:
        problems.append(f"{flagged} {'blocco ha' if flagged == 1 else 'blocchi hanno'} un problema (segnato ⚠)")
    for row in forecast_rows:
        what = ", ".join(short_title(title) for title in row["titles"][:2])
        if row["status"] == "scaduta":
            problems.append(f"{what} è già scaduto")
        elif row["status"] == "a rischio":
            problems.append(f"entro il {row['deadline'][8:10]}/{row['deadline'][5:7]} ({what}) "
                            f"mancano {_hours(row['missing_minutes'])}")
    if problems:
        return False, "⚠️ Attenta: " + "; ".join(problems) + "."
    if forecast_error:
        return True, "✅ Il piano non ha conflitti (le scadenze non le ho potute controllare)."
    return True, "✅ Tranquilla, riesci a fare tutto."


def _day_label(day):
    return f"{WEEKDAYS[day.weekday()]} {day.day}/{day.month}"


def describe_plan(blocks, events, verdict_line, note=""):
    """The whole plan as one message: verdict, then each day of the plan."""
    days = sorted({block.start.date() for block in blocks})
    lines = [verdict_line]
    for day in days:
        lines += ["", _day_label(day)]
        whole_day = [event for event in events if event.all_day and event.start.date() <= day < event.end.date()]
        lines += [f"tutto il giorno · {short_title(event.title)}" for event in whole_day]
        rows = [(event.start, f"{event.start:%H:%M}–{event.end:%H:%M} {short_title(event.title)}", [])
                for event in events if not event.all_day and event.start.date() == day]
        rows += [(block.start, f"{block.start:%H:%M}–{block.end:%H:%M} 🆕 {short_title(block.title)}", block.warnings)
                 for block in blocks if block.start.date() == day]
        for _, line, warnings in sorted(rows, key=lambda row: row[0]):
            lines.append(line)
            lines += [f"   ⚠ {warning}" for warning in warnings]
    note = " ".join(note.split())
    if note:
        lines += ["", short_title(note, NOTE_CHARS)]
    text = "\n".join(lines)
    return text if len(text) <= MESSAGE_CHARS else text[: MESSAGE_CHARS - 1] + "…"
