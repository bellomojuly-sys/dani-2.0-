"""Place study blocks for the open tasks into the free time of the week.

A deterministic Python function, not the LLM (Decision Log 2026-11-05): the
same tasks and the same events always give the same plan, so it can be tested
and explained line by line. The rules it applies are Giulia's, written as
constants at the top so they are visible and changeable in one place:

  - no study on Sunday;
  - study starts at DAY_START (9:30): the morning routine, the gym and the
    commute end around then, whether or not they are in the calendar;
  - study ends at END_HOUR (20:00) — but at SHIFT_END_HOUR (16:00) on a day
    with a restaurant shift (an event in a work calendar, see WORK_CALENDAR_WORDS),
    because from 16:00 she gets ready for the 17:00 shift;
  - at most MAX_MINUTES_PER_DAY of study per day;
  - a block is never shorter than MIN_BLOCK_MINUTES;
  - timed calendar events block the time they occupy; all-day events do not.

Tasks are taken in the order given (the verified priority when there is one)
and each is placed whole in the first free slot that fits. A task that fits
nowhere in the week stays in ``unplaced``: it is reported, never squeezed in.
"""

from datetime import datetime, time, timedelta

from pydantic import BaseModel

from models import AMSTERDAM

DAY_START = time(9, 30)
END_HOUR = 20
SHIFT_END_HOUR = 16
# A day is a shift day when any of its events is in a calendar whose name
# contains one of these words (her Eitje shifts live in "lavoro").
WORK_CALENDAR_WORDS = ("lavoro", "eitje", "turno")
MAX_MINUTES_PER_DAY = 7 * 60
MIN_BLOCK_MINUTES = 30
DEFAULT_TASK_MINUTES = 60
SUNDAY = 6  # datetime.weekday(): Monday is 0


class StudyBlock(BaseModel):
    """One planned block: which task, from when to when."""

    task_id: str
    title: str
    start: datetime
    end: datetime


def is_work_event(event):
    """True when the event sits in a work calendar (a restaurant shift)."""
    name = event.calendar.casefold()
    return any(word in name for word in WORK_CALENDAR_WORDS)


def free_slots(day, events):
    """Return the free (start, end) pairs of ``day`` inside the study window.

    The window is DAY_START to END_HOUR — to SHIFT_END_HOUR when one of the
    day's events is a shift (is_work_event), even if the shift itself starts
    after the window. Only timed events of that day block time; all-day events
    are skipped. The events may overlap each other or spill over the window
    edges: we clip them to the window and walk through them in start order, so
    a gap shorter than MIN_BLOCK_MINUTES is never offered. Sunday has no slots
    at all.
    """
    if day.weekday() == SUNDAY:
        return []
    end_hour = SHIFT_END_HOUR if any(is_work_event(event) for event in events) else END_HOUR
    window_start = datetime.combine(day, DAY_START, tzinfo=AMSTERDAM)
    window_end = datetime.combine(day, time(end_hour), tzinfo=AMSTERDAM)
    busy = sorted(
        (max(event.start, window_start), min(event.end, window_end))
        for event in events
        if not event.all_day and event.start < window_end and event.end > window_start
    )
    slots = []
    cursor = window_start
    for start, end in busy:
        if start - cursor >= timedelta(minutes=MIN_BLOCK_MINUTES):
            slots.append((cursor, start))
        cursor = max(cursor, end)
    if window_end - cursor >= timedelta(minutes=MIN_BLOCK_MINUTES):
        slots.append((cursor, window_end))
    return slots


def plan_study_blocks(tasks, events, days):
    """Place each task, in the given order, in the first free slot that fits.

    ``days`` is the ordered list of dates to plan. Each day gives at most
    MAX_MINUTES_PER_DAY; a task without an estimate counts DEFAULT_TASK_MINUTES.
    Returns {"blocks": [StudyBlock...], "unplaced": [Task...]}.
    """
    slots_by_day = {day: free_slots(day, [e for e in events if e.start.date() == day]) for day in days}
    used_by_day = {day: 0 for day in days}
    blocks = []
    unplaced = []
    for task in tasks:
        minutes = task.duration_minutes or DEFAULT_TASK_MINUTES
        needed = timedelta(minutes=minutes)
        placed = False
        for day in days:
            if used_by_day[day] + minutes > MAX_MINUTES_PER_DAY:
                continue
            for index, (start, end) in enumerate(slots_by_day[day]):
                if end - start < needed:
                    continue
                block_end = start + needed
                blocks.append(StudyBlock(task_id=task.id, title=task.title, start=start, end=block_end))
                used_by_day[day] += minutes
                # What is left of the slot stays available (if still long enough).
                remaining = (block_end, end)
                if end - block_end >= timedelta(minutes=MIN_BLOCK_MINUTES):
                    slots_by_day[day][index] = remaining
                else:
                    del slots_by_day[day][index]
                placed = True
                break
            if placed:
                break
        if not placed:
            unplaced.append(task)
    return {"blocks": blocks, "unplaced": unplaced}
