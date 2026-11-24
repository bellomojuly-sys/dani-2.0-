"""The week's focus and the Sunday check-in (D2-060), with a fake store."""

from datetime import date

import pytest

from focus import MAX_FOCUS, WeekFocus, focus_prompt, monday_of, question_for

SUNDAY, WEDNESDAY = date(2026, 11, 29), date(2026, 11, 25)
THIS, NEXT = date(2026, 11, 23), date(2026, 11, 30)


def test_sunday_asks_about_the_week_that_starts_tomorrow_and_other_days_about_this_one():
    assert question_for(SUNDAY) == (NEXT, "Su cosa ti vuoi concentrare la settimana prossima?")
    assert question_for(WEDNESDAY) == (THIS, "Su cosa ti vuoi concentrare questa settimana?")
    assert monday_of(SUNDAY) == THIS


def test_the_question_disappears_once_the_week_has_a_focus():
    focus = WeekFocus()
    assert focus.status(SUNDAY)["ask"] is True
    focus.set(NEXT, "  chiudere AMX-08  ")
    status = focus.status(SUNDAY)
    assert status["ask"] is False and status["question"] == "" and status["next_focus"] == "chiudere AMX-08"


def test_set_saves_once_then_updates_the_same_row_and_refresh_loads_the_store():
    rows = {}

    def save(monday, text, page_id):
        rows[monday] = (text, page_id or f"page-{monday}")
        return rows[monday][1]

    focus = WeekFocus(lambda since: {m: v for m, v in rows.items() if m >= since}, save)
    focus.set(THIS, "Betsy")
    focus.set(THIS, "Betsy e CV")
    assert rows == {THIS: ("Betsy e CV", f"page-{THIS}")}
    again = WeekFocus(lambda since: dict(rows), save)  # a restart reads it back
    again.refresh(THIS)
    assert again.get(THIS) == "Betsy e CV"


@pytest.mark.parametrize("monday, text, message", [
    (THIS, "   ", "vuoto"),
    (THIS, "x" * (MAX_FOCUS + 1), "troppo lungo"),
    (WEDNESDAY, "Betsy", "lunedì"),
])
def test_a_bad_focus_is_refused_and_nothing_is_saved(monday, text, message):
    saved = []
    focus = WeekFocus(save=lambda *args: saved.append(args) or "p")
    with pytest.raises(ValueError, match=message):
        focus.set(monday, text)
    assert saved == []


def test_focus_prompt_names_both_weeks_or_is_empty():
    focus = WeekFocus()
    assert focus_prompt(focus.status(WEDNESDAY)) == ""
    focus.set(THIS, "AMEXIO")
    focus.set(NEXT, "Betsy")
    text = focus_prompt(focus.status(WEDNESDAY))
    assert "this week (from 2026-11-23): AMEXIO" in text and "next week (from 2026-11-30): Betsy" in text
