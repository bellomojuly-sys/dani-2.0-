"""Forecasts (D2-065): what will slip, before it slips.

For every deadline of her open tasks, in deadline order (earliest first, the
classic feasibility test for deadlines), Dani compares:
  - the work due by that day: the estimated time of every open task with a
    deadline on or before it (a task without an estimate counts
    DEFAULT_MINUTES, and the forecast says how many were guessed);
  - the free study time from now to that day: the planner's own free slots
    (her rules: no Sunday, from 09:30, until 16:00 on shift days or 20:00,
    at most 7 hours a day), counting only what is still ahead today.

ratio = work / free time → "in linea" (≤ 0.7), "stretta" (≤ 1.0), "a rischio"
(> 1.0), with the hours missing. A pure function of tasks, events and now:
the same data always gives the same forecast, so it is tested line by line.
"""

from datetime import datetime, timedelta

from planner import MAX_MINUTES_PER_DAY, free_slots

DEFAULT_MINUTES = 60
ON_TRACK, TIGHT = 0.7, 1.0
MAX_DEADLINES = 5


def free_minutes(day, events, now):
    """Free study minutes of ``day`` from ``now`` on, capped at the daily maximum."""
    day_events = [e for e in events if e.start.date() == day]
    total = 0
    for start, end in free_slots(day, day_events):
        start = max(start, now)
        if end > start:
            total += int((end - start).total_seconds() // 60)
    return min(total, MAX_MINUTES_PER_DAY)


def forecast(tasks, events, now, max_deadlines=MAX_DEADLINES):
    """Return one row per upcoming deadline, earliest first.

    Each row: deadline, titles due, work_minutes, free_minutes, guessed (tasks
    without an estimate), status, missing_minutes. Past deadlines are
    reported as "scaduta" with no free time.
    """
    dated = sorted((t for t in tasks if t.deadline is not None), key=lambda t: t.deadline)
    if not dated:
        return []
    today = now.date()
    capacity_by_day = {}
    rows, work, guessed = [], 0, 0
    deadlines = sorted({t.deadline for t in dated})
    for deadline in deadlines:
        due = [t for t in dated if t.deadline == deadline]
        work += sum(t.duration_minutes or DEFAULT_MINUTES for t in due)
        guessed += sum(1 for t in due if not t.duration_minutes)
        if deadline < today:
            rows.append({"deadline": deadline.isoformat(), "titles": [t.title for t in due], "work_minutes": work,
                         "free_minutes": 0, "guessed": guessed, "status": "scaduta", "missing_minutes": work})
            continue
        day = today
        free = 0
        while day <= deadline:
            if day not in capacity_by_day:
                capacity_by_day[day] = free_minutes(day, events, now)
            free += capacity_by_day[day]
            day += timedelta(days=1)
        ratio = work / free if free else float("inf")
        status = "in linea" if ratio <= ON_TRACK else "stretta" if ratio <= TIGHT else "a rischio"
        rows.append({"deadline": deadline.isoformat(), "titles": [t.title for t in due], "work_minutes": work,
                     "free_minutes": free, "guessed": guessed, "status": status,
                     "missing_minutes": max(0, work - free)})
        if len([r for r in rows if r["status"] != "scaduta"]) >= max_deadlines:
            break
    return rows


def _hours(minutes):
    return f"{minutes / 60:.1f}".rstrip("0").rstrip(".") + " h"


def describe(rows):
    """Short Italian lines for the briefing, the chat prompt and the Home."""
    lines = []
    for row in rows:
        what = ", ".join(row["titles"][:2]) + (f" e altri {len(row['titles']) - 2}" if len(row["titles"]) > 2 else "")
        if row["status"] == "scaduta":
            lines.append(f"Scaduto il {row['deadline']}: {what}.")
            continue
        line = (f"Entro il {row['deadline']} ({what}): {_hours(row['work_minutes'])} di lavoro, "
                f"{_hours(row['free_minutes'])} libere → {row['status']}")
        if row["missing_minutes"]:
            line += f", mancano {_hours(row['missing_minutes'])}"
        if row["guessed"]:
            line += f" ({row['guessed']} task senza stima contati {DEFAULT_MINUTES} min)"
        lines.append(line + ".")
    return lines


def at_risk(rows):
    return [r for r in rows if r["status"] in ("a rischio", "scaduta")]
