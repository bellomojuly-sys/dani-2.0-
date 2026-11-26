"""D2-071: the plan as one message, with a verdict computed by code."""

from datetime import datetime

from models import AMSTERDAM, Event
from plan_message import MESSAGE_CHARS, describe_plan, short_title, verdict
from propose import BlockProposal


def at(day, hour, minute=0):
    return datetime(2026, 12, day, hour, minute, tzinfo=AMSTERDAM)


def block(title, day, hour, end_hour, warnings=()):
    return BlockProposal(id=title, title=title, start=at(day, hour), end=at(day, end_hour), warnings=list(warnings))


ROW_FINE = {"deadline": "2026-12-04", "titles": ["Betsy"], "status": "in linea", "missing_minutes": 0}


def test_everything_fits_says_tranquilla():
    assert verdict([block("A", 1, 10, 11)], [ROW_FINE]) == (True, "✅ Tranquilla, riesci a fare tutto.")


def test_a_tight_deadline_still_fits():
    assert verdict([block("A", 1, 10, 11)], [{**ROW_FINE, "status": "stretta"}])[0] is True


def test_a_block_with_a_warning_is_not_fine():
    fine, line = verdict([block("A", 1, 10, 11, ["si sovrappone a «Turno»"]), block("B", 1, 12, 13)], [])
    assert fine is False and line == "⚠️ Attenta: 1 blocco ha un problema (segnato ⚠)."


def test_two_flagged_blocks_use_the_plural():
    blocks = [block("A", 1, 10, 11, ["x"]), block("B", 1, 12, 13, ["y"])]
    assert "2 blocchi hanno un problema" in verdict(blocks, [])[1]


def test_a_deadline_at_risk_says_how_much_is_missing():
    row = {**ROW_FINE, "status": "a rischio", "missing_minutes": 90}
    assert verdict([block("A", 1, 10, 11)], [row]) == (False, "⚠️ Attenta: entro il 04/12 (Betsy) mancano 1.5 h.")


def test_a_past_deadline_is_not_fine():
    row = {**ROW_FINE, "status": "scaduta", "titles": ["Report", "Slide", "Terzo"]}
    assert verdict([], [row]) == (False, "⚠️ Attenta: Report, Slide è già scaduto.")


def test_without_the_forecast_the_verdict_does_not_promise_the_deadlines():
    fine, line = verdict([block("A", 1, 10, 11)], [], forecast_error="calendar down")
    assert fine is True and "Tranquilla" not in line and "non le ho potute controllare" in line


def test_short_title_cuts_long_titles_and_keeps_short_ones():
    assert short_title("  AMEXIO   report ") == "AMEXIO report"
    long = short_title("Studiare il capitolo tre del libro di machine learning")
    assert len(long) == 32 and long.endswith("…")


def test_the_message_lists_every_day_with_her_events_and_the_new_blocks_in_time_order():
    events = [
        Event(calendar="lavoro", title="Turno", start=at(2, 17), end=at(2, 23)),
        Event(calendar="personale", title="Palestra", start=at(2, 8), end=at(2, 9)),
        Event(calendar="personale", title="Compleanno mamma", start=at(2, 0), end=at(3, 0), all_day=True),
        Event(calendar="personale", title="Dentista", start=at(5, 9), end=at(5, 10)),  # a day without blocks
    ]
    blocks = [block("Lettura", 2, 14, 15, ["finisce dopo le 16:00"]), block("Betsy", 1, 10, 12)]
    text = describe_plan(blocks, events, "✅ ok", note="Ecco  la settimana.")
    assert text == (
        "✅ ok\n\n"
        "Mar 1/12\n10:00–12:00 🆕 Betsy\n\n"
        "Mer 2/12\ntutto il giorno · Compleanno mamma\n08:00–09:00 Palestra\n14:00–15:00 🆕 Lettura\n"
        "   ⚠ finisce dopo le 16:00\n17:00–23:00 Turno\n\n"
        "Ecco la settimana.")


def test_a_very_long_plan_is_cut_under_the_telegram_limit():
    blocks = [block("x" * 30 + str(i), 1 + i % 28, 10, 11, ["un avviso lungo " * 5]) for i in range(60)]
    text = describe_plan(blocks, [], "v")
    assert len(text) == MESSAGE_CHARS and text.endswith("…")
