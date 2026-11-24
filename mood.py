"""The mood diary (D2-064): how Giulia feels, day by day.

Her answer to "come stai?" — an energy level from 1 to 5, the hours she
slept and a sentence — is saved in the Notion database "Dani — diario"
(one row per day). Today's entry goes into the chat prompt with her own rules
(page "Dani — chi è Dani"): a low day is planned at the bare minimum with the
big tasks moved to the strong hours, and a bad night lowers expectations.
Nothing is ever guessed: no entry means Dani asks.
"""

import threading
from datetime import timedelta

from pydantic import BaseModel, Field

LOW_ENERGY = 2   # 1–2: a low day
SHORT_NIGHT = 6  # under 6 hours: a bad night


class Mood(BaseModel):
    energy: int = Field(ge=1, le=5)
    sleep: float | None = Field(default=None, ge=0, le=16)
    note: str = Field(default="", max_length=500)


class MoodLog:
    """Entries by day; ``load(since) -> {day: (Mood, page_id)}`` and
    ``save(day, Mood, page_id or None) -> page_id`` are injected."""

    def __init__(self, load=None, save=None):
        self._load, self._save = load, save
        self.days = {}
        self.lock = threading.Lock()

    def refresh(self, since):
        if self._load is not None:
            loaded = self._load(since)
            with self.lock:
                self.days.update(loaded)

    def get(self, day):
        with self.lock:
            entry = self.days.get(day)
        return entry[0] if entry else None

    def set(self, day, mood):
        mood = Mood.model_validate(mood)  # a wrong value raises, never guessed
        with self.lock:
            page_id = self.days.get(day, (None, None))[1]
        if self._save is not None:
            page_id = self._save(day, mood, page_id)
        with self.lock:
            self.days[day] = (mood, page_id)
        return mood

    def status(self, today):
        current, before = self.get(today), self.get(today - timedelta(days=1))
        return {
            "today": today.isoformat(),
            "mood": current.model_dump() if current else None,
            "yesterday": before.model_dump() if before else None,
        }


def mood_prompt(status):
    """The lines for the chat prompt, with the rule a low day or a short night triggers."""
    mood = status.get("mood")
    if not mood:
        return "She has not said how she feels today yet: if it fits, ask her (\"come stai?\")."
    line = f"Today she said: energy {mood['energy']}/5"
    if mood.get("sleep") is not None:
        line += f", slept {mood['sleep']:g} hours"
    if mood.get("note"):
        line += f", \"{mood['note']}\""
    lines = [line + "."]
    if mood["energy"] <= LOW_ENERGY or (mood.get("sleep") is not None and mood["sleep"] < SHORT_NIGHT):
        lines.append("It is a low day: plan the bare minimum, keep only what cannot move, put small tasks "
                     "in the weak hours and lower expectations without guilt.")
    return " ".join(lines)


RECORD_MOOD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "record_mood",
        "description": (
            "Save in her diary how Giulia feels today, when she tells you (\"sono stanca\", \"ho dormito 5 ore\", "
            "\"oggi sto benissimo\"). Energy from 1 (empty) to 5 (full), hours of sleep only if she said them, "
            "and her words in short. Never guess a value she did not give."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "energy": {"type": "integer", "minimum": 1, "maximum": 5},
                "sleep": {"type": "number", "description": "hours slept last night, only if she said it"},
                "note": {"type": "string", "description": "her words, short"},
            },
            "required": ["energy"],
            "additionalProperties": False,
        },
    },
}
