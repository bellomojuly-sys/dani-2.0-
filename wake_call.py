"""The wake-up call (D2-070): Dani calls until Giulia proves she is awake.

At her wake time (WAKE_TIME, Monday to Saturday), or as soon as she snoozes
the alarm, Dani calls. On the phone Dani asks a mental calculation; she
answers by voice or on the keypad. Right: "Brava July" and the first
appointment of the day; she is awake for today. Wrong: a new calculation.
No answer: Dani calls again every RETRY_MINUTES, at most MAX_CALLS times,
then writes to her.

This module is pure (no network): the questions, the check of her answer,
the TwiML Dani speaks, and the state of one morning. The server wires it to
Twilio.
"""

import random
import re
from datetime import datetime, time, timedelta
from xml.sax.saxutils import escape

RETRY_MINUTES = 3
MAX_CALLS = 10
MAX_WRONG_PER_CALL = 3
VOICE = "Polly.Bianca"  # an Italian voice
LANGUAGE = "it-IT"
ITALIAN_NUMBERS = {
    "zero": 0, "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8,
    "nove": 9, "dieci": 10, "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
    "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19, "venti": 20,
}


def new_question(rng):
    """A calculation hard enough to need a working brain: two digits times one digit."""
    a, b = rng.randint(12, 49), rng.randint(3, 9)
    return {"text": f"Quanto fa {a} per {b}?", "answer": a * b}


def heard_number(digits, speech):
    """The number she gave: keypad digits first, else the first number in the speech."""
    if digits and digits.strip().isdigit():
        return int(digits.strip())
    words = (speech or "").casefold().replace(".", " ").replace(",", " ")
    found = re.search(r"\d+", words)
    if found:
        return int(found.group())
    for word in words.split():
        if word in ITALIAN_NUMBERS:
            return ITALIAN_NUMBERS[word]
    return None


def _say(text):
    return f'<Say voice="{VOICE}" language="{LANGUAGE}">{escape(text)}</Say>'


def twiml_question(intro, question, action):
    """Say the intro, ask the question, wait for voice or keypad; silence → hang up (she is called again)."""
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Gather input="speech dtmf" language="{LANGUAGE}" timeout="8" speechTimeout="auto" '
            f'action="{escape(action)}" method="POST">{_say(intro + " " + question)}</Gather>'
            f'{_say("Non ti ho sentita. Ti richiamo tra poco.")}</Response>')


def twiml_done(text):
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{_say(text)}<Hangup/></Response>'


def wake_time_today(setting, now):
    """Today's wake-up moment from "HH:MM", or None on Sunday or with no setting."""
    if not setting or now.weekday() == 6:
        return None
    hour, minute = (int(part) for part in setting.split(":"))
    return datetime.combine(now.date(), time(hour, minute), tzinfo=now.tzinfo)


class Morning:
    """One morning's state: calls made, the open question, whether she is awake."""

    def __init__(self, day, rng=None):
        self.day = day
        self.rng = rng or random.Random()
        self.calls = 0
        self.next_call = None
        self.awake = False
        self.question = None
        self.wrong = 0
        self.gave_up = False

    def due(self, now, wake_at):
        """True when a call should start now."""
        if self.awake or self.gave_up or now.date() != self.day:
            return False
        if self.next_call is not None:
            return now >= self.next_call
        # Only within an hour of the wake time: a restart later in the day must not ring her again.
        return wake_at is not None and wake_at <= now < wake_at + timedelta(hours=1)

    def calling(self, now):
        """A call starts: count it and plan the next one in case she does not get up."""
        self.calls += 1
        self.wrong = 0
        self.question = new_question(self.rng)
        if self.calls >= MAX_CALLS:
            self.gave_up = True
            self.next_call = None
        else:
            self.next_call = now + timedelta(minutes=RETRY_MINUTES)

    def snoozed(self, now):
        """The alarm was snoozed: call now, whatever the plan said."""
        self.awake = False
        self.gave_up = False
        self.next_call = now

    def answer(self, digits, speech):
        """Check her answer. Returns ("awake" | "wrong" | "again", next question or None)."""
        if self.question is None:
            self.question = new_question(self.rng)
            return "again", self.question
        heard = heard_number(digits, speech)
        if heard == self.question["answer"]:
            self.awake = True
            self.next_call = None
            return "awake", None
        self.wrong += 1
        self.question = new_question(self.rng)
        return ("wrong" if self.wrong < MAX_WRONG_PER_CALL else "again"), self.question
