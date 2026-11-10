"""The cycle estimate, one test per phase and per refusal. No clock: today is
always passed in."""

from datetime import date

import pytest
from pydantic import ValidationError

from cycle import HINTS, CycleSettings, estimate_phase

CONFIRMED = CycleSettings(start=date(2026, 11, 11), cycle_length=28, period_length=5, confirmed=True)


def test_expected_start_already_past_is_in_arrivo_with_days_late():
    settings = CycleSettings(start=date(2026, 11, 8))
    result = estimate_phase(date(2026, 11, 10), settings)
    assert result["phase"] == "in arrivo"
    assert result["day"] is None  # no cycle day is invented
    assert result["late_days"] == 2
    assert result["estimated"] is True
    assert result["hint"] == HINTS["in arrivo"]


def test_expected_start_today_is_in_arrivo_zero_days_late():
    result = estimate_phase(date(2026, 11, 8), CycleSettings(start=date(2026, 11, 8)))
    assert (result["phase"], result["late_days"]) == ("in arrivo", 0)


@pytest.mark.parametrize(
    "today, day, phase",
    [
        (date(2026, 11, 11), 1, "mestruale"),
        (date(2026, 11, 15), 5, "mestruale"),  # last day of the period
        (date(2026, 11, 16), 6, "follicolare"),
        (date(2026, 11, 22), 12, "follicolare"),
        (date(2026, 11, 23), 13, "ovulatoria"),
        (date(2026, 11, 25), 15, "ovulatoria"),
        (date(2026, 11, 26), 16, "luteale"),
        (date(2026, 12, 5), 25, "luteale"),
        (date(2026, 12, 6), 26, "in arrivo"),  # the last three days
        (date(2026, 12, 8), 28, "in arrivo"),
    ],
)
def test_each_phase_of_a_confirmed_cycle(today, day, phase):
    result = estimate_phase(today, CONFIRMED)
    assert (result["day"], result["phase"]) == (day, phase)
    assert result["estimated"] is False  # the confirmed cycle itself is a fact
    assert result["next_start"] == date(2026, 12, 9)
    assert result["late_days"] == 0


def test_cycles_after_the_confirmed_one_are_estimates_again():
    result = estimate_phase(date(2026, 12, 15), CONFIRMED)
    assert (result["day"], result["phase"]) == (7, "follicolare")
    assert result["estimated"] is True
    assert result["next_start"] == date(2027, 1, 6)


def test_future_expected_start_counts_back_one_cycle():
    result = estimate_phase(date(2026, 11, 10), CycleSettings(start=date(2026, 11, 20)))
    assert (result["day"], result["phase"]) == (19, "luteale")
    assert result["estimated"] is True
    assert result["next_start"] == date(2026, 11, 20)


@pytest.mark.parametrize("field, value", [("cycle_length", 19), ("cycle_length", 46), ("period_length", 1), ("period_length", 11)])
def test_impossible_lengths_are_refused(field, value):
    with pytest.raises(ValidationError):
        CycleSettings(start=date(2026, 11, 8), **{field: value})
