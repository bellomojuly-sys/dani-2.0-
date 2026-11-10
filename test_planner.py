"""The planner is deterministic: same tasks + same events = same blocks.
Every rule (Sunday, window, daily cap, minimum block, all-day events) has a
test that fails when the rule is removed."""

from datetime import date, datetime

from datetime import time

from models import AMSTERDAM, Event, Task
from planner import (
    DAY_START,
    DEFAULT_TASK_MINUTES,
    END_HOUR,
    MAX_MINUTES_PER_DAY,
    SHIFT_END_HOUR,
    free_slots,
    is_work_event,
    plan_study_blocks,
)

MONDAY = date(2026, 11, 9)
SUNDAY = date(2026, 11, 15)


def _at(day, hour, minute=0):
    return datetime.combine(day, datetime.min.time(), tzinfo=AMSTERDAM).replace(hour=hour, minute=minute)


def _event(day, start_hour, end_hour, title="busy", all_day=False, calendar="c"):
    return Event(calendar=calendar, title=title, start=_at(day, start_hour), end=_at(day, end_hour), all_day=all_day)


def _task(task_id, minutes=None, title=None):
    return Task(id=task_id, title=title or task_id, status="Not Started", duration_minutes=minutes)


def test_empty_day_is_one_slot_from_day_start_to_the_evening():
    start = _at(MONDAY, DAY_START.hour, DAY_START.minute)
    assert free_slots(MONDAY, []) == [(start, _at(MONDAY, END_HOUR))]


def test_no_slot_begins_before_half_past_nine():
    # Even with an empty calendar (no routine or gym events), the morning is
    # taken by the routine: the first possible block starts at 09:30.
    plan = plan_study_blocks([_task("a", 60)], [], [MONDAY])
    assert plan["blocks"][0].start == _at(MONDAY, 9, 30)


def test_a_shift_day_has_no_slot_after_sixteen():
    shift = _event(MONDAY, 17, 23, title="turno", calendar="lavoro")
    slots = free_slots(MONDAY, [shift])
    assert slots == [(_at(MONDAY, 9, 30), _at(MONDAY, SHIFT_END_HOUR))]


def test_the_shift_cuts_the_day_even_when_it_starts_after_the_window():
    # 6 hours fit between 09:30 and 16:00; 7 would spill past 16:00 and must not.
    shift = _event(MONDAY, 17, 23, title="turno", calendar="Lavoro")  # case-insensitive
    plan = plan_study_blocks([_task("a", 6 * 60), _task("b", 7 * 60)], [shift], [MONDAY])
    assert [block.task_id for block in plan["blocks"]] == ["a"]
    assert plan["blocks"][0].end == _at(MONDAY, 15, 30)
    assert [task.id for task in plan["unplaced"]] == ["b"]


def test_a_day_without_a_shift_keeps_the_evening_until_twenty():
    lesson = _event(MONDAY, 10, 12, title="Lezione", calendar="Università")
    slots = free_slots(MONDAY, [lesson])
    assert slots[-1][1] == _at(MONDAY, END_HOUR)


def test_is_work_event_knows_the_work_calendars():
    assert is_work_event(_event(MONDAY, 17, 23, calendar="lavoro"))
    assert is_work_event(_event(MONDAY, 17, 23, calendar="Eitje turni"))
    assert not is_work_event(_event(MONDAY, 10, 12, calendar="studio"))
    assert not is_work_event(_event(MONDAY, 10, 12, calendar="Università"))


def test_sunday_has_no_free_slots():
    assert free_slots(SUNDAY, []) == []


def test_a_timed_event_splits_the_day_in_two_slots():
    slots = free_slots(MONDAY, [_event(MONDAY, 12, 13)])
    assert slots == [(_at(MONDAY, 9, 30), _at(MONDAY, 12)), (_at(MONDAY, 13), _at(MONDAY, 20))]


def test_an_all_day_event_does_not_block_time():
    assert free_slots(MONDAY, [_event(MONDAY, 0, 23, all_day=True)]) == free_slots(MONDAY, [])


def test_events_outside_the_window_are_ignored_and_edges_are_clipped():
    slots = free_slots(MONDAY, [_event(MONDAY, 6, 8), _event(MONDAY, 19, 23)])
    assert slots == [(_at(MONDAY, 9, 30), _at(MONDAY, 19))]


def test_a_gap_shorter_than_the_minimum_block_is_not_offered():
    slots = free_slots(MONDAY, [_event(MONDAY, 9, 10), _event(MONDAY, 10, 20)])
    # 09:00-10:00 and 10:00-20:00 touch each other and leave no gap at all.
    assert slots == []
    slots = free_slots(MONDAY, [_event(MONDAY, 9, 12), _event(MONDAY, 12, 13), _event(MONDAY, 13, 20)])
    assert slots == []


def test_tasks_are_placed_in_the_given_order_in_the_first_slot_that_fits():
    plan = plan_study_blocks([_task("a", 60), _task("b", 90)], [_event(MONDAY, 9, 10)], [MONDAY])
    assert [(block.task_id, block.start, block.end) for block in plan["blocks"]] == [
        ("a", _at(MONDAY, 10), _at(MONDAY, 11)),
        ("b", _at(MONDAY, 11), _at(MONDAY, 12, 30)),
    ]
    assert plan["unplaced"] == []


def test_a_task_without_estimate_takes_the_default_length():
    plan = plan_study_blocks([_task("a")], [], [MONDAY])
    block = plan["blocks"][0]
    assert (block.end - block.start).total_seconds() == DEFAULT_TASK_MINUTES * 60


def test_daily_cap_pushes_work_to_the_next_day():
    tasks = [_task("a", MAX_MINUTES_PER_DAY), _task("b", 60)]
    plan = plan_study_blocks(tasks, [], [MONDAY, date(2026, 11, 10)])
    assert plan["blocks"][0].start.date() == MONDAY
    assert plan["blocks"][1].start.date() == date(2026, 11, 10)


def test_a_task_that_fits_nowhere_is_reported_not_squeezed():
    plan = plan_study_blocks([_task("huge", 10 * 60)], [], [MONDAY])
    assert plan["blocks"] == []
    assert [task.id for task in plan["unplaced"]] == ["huge"]


def test_nothing_is_planned_on_sunday():
    plan = plan_study_blocks([_task("a", 60)], [], [SUNDAY])
    assert plan["blocks"] == [] and [t.id for t in plan["unplaced"]] == ["a"]


def test_same_input_gives_the_same_plan():
    tasks = [_task("a", 45), _task("b", 120), _task("c")]
    events = [_event(MONDAY, 11, 14), _event(MONDAY, 16, 17)]
    first = plan_study_blocks(tasks, events, [MONDAY])
    second = plan_study_blocks(tasks, events, [MONDAY])
    assert first == second
