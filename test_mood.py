"""The mood diary (D2-064): validation, store, the low-day rule in the prompt."""

from datetime import date

import pytest

from mood import MoodLog, mood_prompt

TODAY = date(2026, 11, 24)


def test_a_mood_is_saved_once_then_updated_and_read_back_after_a_restart():
    rows = {}

    def save(day, mood, page_id):
        rows[day] = (mood, page_id or "p1")
        return rows[day][1]

    log = MoodLog(lambda since: dict(rows), save)
    log.set(TODAY, {"energy": 4})
    log.set(TODAY, {"energy": 2, "sleep": 5, "note": "notte storta"})
    assert rows[TODAY][1] == "p1" and rows[TODAY][0].energy == 2
    again = MoodLog(lambda since: dict(rows), save)
    again.refresh(TODAY)
    assert again.status(TODAY)["mood"] == {"energy": 2, "sleep": 5.0, "note": "notte storta"}


@pytest.mark.parametrize("bad", [{}, {"energy": 0}, {"energy": 6}, {"energy": 3, "sleep": 30}, {"energy": "tanta"}])
def test_a_wrong_value_is_refused_never_guessed(bad):
    saved = []
    with pytest.raises(ValueError):
        MoodLog(save=lambda *a: saved.append(a) or "p").set(TODAY, bad)
    assert saved == []


def test_a_low_day_or_a_short_night_adds_the_bare_minimum_rule():
    log = MoodLog()
    assert "has not said" in mood_prompt(log.status(TODAY))
    log.set(TODAY, {"energy": 4, "sleep": 8})
    assert "low day" not in mood_prompt(log.status(TODAY))
    log.set(TODAY, {"energy": 4, "sleep": 4})
    assert "bare minimum" in mood_prompt(log.status(TODAY))
    log.set(TODAY, {"energy": 2})
    text = mood_prompt(log.status(TODAY))
    assert "energy 2/5" in text and "bare minimum" in text
