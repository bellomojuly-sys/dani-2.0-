"""Forecasts (D2-065): known tasks and events give a known verdict."""

from datetime import date, datetime

from forecast import DEFAULT_MINUTES, at_risk, describe, forecast, free_minutes
from models import AMSTERDAM, Event, Task

MONDAY = datetime(2026, 11, 30, 8, 0, tzinfo=AMSTERDAM)  # before the 09:30 window


def task(title, deadline, minutes=None):
    return Task(id=title, title=title, status="Not Started", deadline=deadline, duration_minutes=minutes)


def test_a_free_weekday_has_seven_hours_and_a_shift_day_ends_at_16():
    assert free_minutes(MONDAY.date(), [], MONDAY) == 7 * 60  # 09:30–20:00 is 10.5 h, capped at 7
    shift = Event(calendar="lavoro", title="Turno", start=datetime(2026, 11, 30, 17, tzinfo=AMSTERDAM),
                  end=datetime(2026, 11, 30, 23, tzinfo=AMSTERDAM))
    assert free_minutes(MONDAY.date(), [shift], MONDAY) == 6 * 60 + 30  # 09:30–16:00
    noon = MONDAY.replace(hour=12)
    assert free_minutes(MONDAY.date(), [], noon) == 7 * 60  # 12:00–20:00 is 8 h, still capped
    assert free_minutes(MONDAY.date(), [], MONDAY.replace(hour=18)) == 120  # only what is left today
    assert free_minutes(date(2026, 12, 6), [], MONDAY) == 0  # Sunday


def test_earliest_deadline_first_accumulates_the_work():
    tasks = [task("AMX-08", date(2026, 11, 30), 180), task("Betsy", date(2026, 12, 1), 600)]
    rows = forecast(tasks, [], MONDAY)
    assert [(r["deadline"], r["work_minutes"], r["free_minutes"], r["status"]) for r in rows] == [
        ("2026-11-30", 180, 420, "in linea"),       # 3 h of 7
        ("2026-12-01", 780, 840, "stretta"),        # 13 h of 14: tight
    ]


def test_too_much_work_is_at_risk_with_the_hours_missing_and_guesses_are_said():
    tasks = [task("Grande", date(2026, 11, 30), 600), task("Senza stima", date(2026, 11, 30))]
    row = forecast(tasks, [], MONDAY)[0]
    assert row["status"] == "a rischio" and row["missing_minutes"] == 600 + DEFAULT_MINUTES - 420
    assert row["guessed"] == 1
    line = describe([row])[0]
    assert "a rischio, mancano 4 h" in line and "1 task senza stima" in line
    assert at_risk([row]) == [row]


def test_a_past_deadline_is_overdue_and_no_dates_means_no_forecast():
    rows = forecast([task("Vecchio", date(2026, 11, 20), 30)], [], MONDAY)
    assert rows[0]["status"] == "scaduta" and describe(rows)[0].startswith("Scaduto il 2026-11-20")
    assert forecast([task("Senza data", None, 30)], [], MONDAY) == []
