"""The week's focus (D2-060): what Giulia wants to concentrate on, week by week.

On Sunday Dani asks "su cosa ti vuoi concentrare questa settimana?" for the
week that starts the next day; on another day, if the current week has no
focus yet, it asks for the current week. Her answer is saved in the Notion
database "Dani — focus della settimana" (one row per week, keyed by its
Monday), because the Render disk is wiped on every restart. The focus of
this week and of the next one go into the chat prompt, so planning starts
from it.

Saving is her own action (she types the focus and presses Salva), so it
needs no preview: it writes only in Dani's own database, never in her
calendars or her Tasks.
"""

import threading
from datetime import timedelta

MAX_FOCUS = 600  # characters: a focus is a few sentences, not a plan


def monday_of(day):
    return day - timedelta(days=day.weekday())


def question_for(today):
    """Which week to ask about today, and with which words (None = no question).

    Sunday asks about the week that starts tomorrow; another day asks about
    the current week only when ``has_focus(this_monday)`` is false — the
    caller decides that, so this function just names the week.
    """
    if today.weekday() == 6:
        return monday_of(today) + timedelta(days=7), "Su cosa ti vuoi concentrare la settimana prossima?"
    return monday_of(today), "Su cosa ti vuoi concentrare questa settimana?"


class WeekFocus:
    """Focus texts by Monday, loaded from and saved to a store.

    ``load(since) -> {monday: (text, page_id)}`` and
    ``save(monday, text, page_id or None) -> page_id`` are injected (Notion
    in production, dicts in the tests). Without a store it keeps the focus in
    memory only.
    """

    def __init__(self, load=None, save=None):
        self._load, self._save = load, save
        self.weeks = {}  # monday -> (text, page_id)
        self.lock = threading.Lock()

    def refresh(self, since):
        if self._load is None:
            return
        loaded = self._load(since)
        with self.lock:
            self.weeks.update(loaded)

    def get(self, monday):
        with self.lock:
            entry = self.weeks.get(monday)
        return entry[0] if entry else ""

    def set(self, monday, text):
        text = (text or "").strip()
        if not text:
            raise ValueError("il focus è vuoto")
        if len(text) > MAX_FOCUS:
            raise ValueError(f"il focus è troppo lungo (al massimo {MAX_FOCUS} caratteri)")
        if monday.weekday() != 0:
            raise ValueError("la settimana si indica con il suo lunedì")
        with self.lock:
            page_id = self.weeks.get(monday, ("", None))[1]
        if self._save is not None:
            page_id = self._save(monday, text, page_id)
        with self.lock:
            self.weeks[monday] = (text, page_id)
        return text

    def status(self, today):
        """What the page and the prompt need: this week, next week, the question."""
        this, following = monday_of(today), monday_of(today) + timedelta(days=7)
        ask_week, question = question_for(today)
        ask = not self.get(ask_week)
        return {
            "this_week": this.isoformat(), "this_focus": self.get(this),
            "next_week": following.isoformat(), "next_focus": self.get(following),
            "ask": ask, "ask_week": ask_week.isoformat(), "question": question if ask else "",
        }


def focus_prompt(status):
    """The lines for the chat prompt (empty when no focus is set)."""
    lines = []
    if status["this_focus"]:
        lines.append(f"Her focus for this week (from {status['this_week']}): {status['this_focus']}")
    if status["next_focus"]:
        lines.append(f"Her focus for next week (from {status['next_week']}): {status['next_focus']}")
    if lines:
        lines.append("Plan from this focus first.")
    return "\n".join(lines)
