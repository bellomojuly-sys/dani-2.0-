"""The morning briefing text (D2-061): a pure function of the dashboard state."""

from datetime import date

from briefing import build_briefing
from persona import MORNING_LINES, morning_line


def _state(today, **extra):
    base = {
        "today": today,
        "events": [
            {"title": "Lezione MA-AAI", "start": f"{today}T09:00:00+01:00", "end": f"{today}T12:45:00+01:00", "all_day": False},
            {"title": "Deadline Betsy", "start": f"{today}T00:00:00+01:00", "end": f"{today}T23:59:00+01:00", "all_day": True},
            {"title": "Domani", "start": "2030-01-01T09:00:00+01:00", "end": "2030-01-01T10:00:00+01:00", "all_day": False},
        ],
        "blocks": [{"title": "AMX-08", "start": f"{today}T13:00:00+01:00", "end": f"{today}T14:00:00+01:00"}],
        "tasks": [{"title": f"T{n}"} for n in range(1, 6)],
        "cycle": {"phase": "follicolare", "hint": "energia in salita"},
    }
    base.update(extra)
    return base


def test_a_weekday_briefing_has_the_programme_blocks_priorities_cycle_focus_and_the_question():
    note = build_briefing(_state("2026-11-24"), {"this_focus": "AMEXIO e CV", "next_focus": ""})
    assert note["title"] == "Buongiorno July · martedì 24 novembre"
    lines = note["text"].splitlines()
    assert lines[0] == "Chief, questa è la tua giornata:"
    assert "• 09:00–12:45 Lezione MA-AAI" in lines and "• tutto il giorno Deadline Betsy" in lines
    assert "Domani" not in note["text"]  # only today's events
    assert "Blocchi proposti: 13:00 AMX-08." in lines
    assert "Le priorità: T1; T2; T3." in lines  # three, not five
    assert "Ciclo: fase follicolare. energia in salita" in lines
    assert "Il focus della settimana: AMEXIO e CV" in lines
    assert lines[-1] == "E tu, July, oggi come stai?"


def test_sunday_has_no_work_and_asks_for_next_weeks_focus():
    text = build_briefing(_state("2026-11-29", events=[]), {"this_focus": "", "next_focus": ""})["text"]
    assert text.startswith("Oggi è domenica")
    assert "Blocchi" not in text and "priorità" not in text
    assert "Su cosa ti vuoi concentrare la settimana prossima?" in text
    answered = build_briefing(_state("2026-11-29", events=[]), {"this_focus": "", "next_focus": "Betsy"})["text"]
    assert "settimana prossima?" not in answered


def test_an_empty_day_says_so_and_missing_parts_are_left_out():
    text = build_briefing(_state("2026-11-25", events=[], blocks=[], tasks=[], cycle=None))["text"]
    assert text.splitlines() == ["Oggi non hai impegni fissi in calendario.", morning_line(date(2026, 11, 25)),
                                 "E tu, July, oggi come stai?"]


def test_the_closing_line_is_dannis_and_changes_from_day_to_day():
    first = build_briefing(_state("2026-11-24"))["text"].splitlines()[-2]
    second = build_briefing(_state("2026-11-25"))["text"].splitlines()[-2]
    assert first in MORNING_LINES and second in MORNING_LINES and first != second
    assert build_briefing(_state("2026-11-24"))["text"] == build_briefing(_state("2026-11-24"))["text"]  # same day, same text


def test_a_low_yesterday_is_named_in_the_morning():
    low = build_briefing(_state("2026-11-24"), None, {"yesterday": {"energy": 2, "sleep": 5, "note": ""}})["text"]
    assert "Ieri eri a 2/5" in low
    fine = build_briefing(_state("2026-11-24"), None, {"yesterday": {"energy": 4, "sleep": 8, "note": ""}})["text"]
    assert "Ieri" not in fine
