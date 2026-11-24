"""The wake-up guard (D2-067): stronger at each snooze, with the first appointment."""

from datetime import datetime

from models import AMSTERDAM, Event
from wake import FOLLOW_UPS, snooze_messages, stopped_message

NOW = datetime(2026, 11, 24, 6, 0, tzinfo=AMSTERDAM)
LESSON = Event(calendar="Università", title="Applied GenAI", start=datetime(2026, 11, 24, 9, 0, tzinfo=AMSTERDAM),
               end=datetime(2026, 11, 24, 12, 0, tzinfo=AMSTERDAM))


def test_a_snooze_pushes_now_at_max_priority_and_schedules_two_follow_ups():
    first, *later = snooze_messages(1, NOW, [LESSON])
    assert first["at"] is None and first["priority"] == 5
    assert "Alle 09:00 hai «Applied GenAI»" in first["text"]
    assert [m["at"] for m in later] == [NOW.replace(minute=m) for m in FOLLOW_UPS]
    assert all("ignora" in m["text"] for m in later)  # they cannot be withdrawn


def test_the_third_snooze_is_the_chief_line():
    assert snooze_messages(2, NOW, [])[0]["text"].startswith("July, è la seconda volta")
    third = snooze_messages(3, NOW, [])[0]
    assert third["title"] == "Chief. Alzati." and "ignorato la sveglia 3 volte" in third["text"]
    assert "La giornata ti aspetta" in third["text"]  # no appointment: never invented


def test_stopping_says_brava_only_after_a_snooze():
    assert stopped_message(0) is None
    assert stopped_message(2)["title"] == "Brava, July"
