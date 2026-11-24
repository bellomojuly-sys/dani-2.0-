"""Keep Notion tasks and calendar events in memory and say how fresh they are.

The page asks the server every few seconds; the server must not ask Notion
every few seconds (Notion allows about 3 requests per second and the LLM costs
money). So ``Live`` is a small cache:

  - ``refresh`` re-reads a source and records when it happened and whether it
    worked. When a source fails, the last good data stays and the error is
    shown, so the page never goes blank;
  - ``update_priority`` asks the LLM again only when the tasks or Giulia's
    context changed since the last time;
  - ``state`` builds the JSON the page shows, from the cache and the settings.

Every outside piece (the two fetchers, the LLM priority, the clock) is passed
in, so tests use fakes and a fixed time.
"""

import threading
from datetime import datetime, time, timedelta

from cycle import estimate_phase
from dashboard import order_tasks, week_from
from models import Event
from planner import plan_study_blocks

NOT_ASKED = {"ok": False, "reason": "priority not calculated yet", "priority": None}


def _message(failure):
    """A short error for the page. Our own clients raise RuntimeError/ValueError
    with messages that never contain secrets; anything else shows only its type."""
    if isinstance(failure, (RuntimeError, ValueError)):
        return str(failure)[:300]
    return type(failure).__name__


def _time_already_gone(now):
    """Today up to now (rounded up to the next quarter of an hour) as one busy
    interval, so the planner never proposes a study block in the past."""
    midnight = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    quarters = -(-(now - midnight) // timedelta(minutes=15))  # ceiling division
    until = midnight + quarters * timedelta(minutes=15)
    if until <= midnight:
        return []
    return [Event(calendar="", title="(already past)", start=midnight, end=until)]


class Live:
    def __init__(self, fetch_tasks, fetch_events, prioritize, clock):
        """fetch_tasks() -> [Task]; fetch_events(start, end) -> [Event];
        prioritize(tasks, today, context) -> outcome dict (see agent.final_outcome);
        clock() -> the current Amsterdam datetime."""
        self.fetch_tasks = fetch_tasks
        self.fetch_events = fetch_events
        self.prioritize = prioritize
        self.clock = clock
        self.tasks = []
        self.events = []
        self.outcome = NOT_ASKED
        self.priority_signature = None
        self.sources = {
            "notion": {"ok": None, "at": None, "error": None},
            "calendar": {"ok": None, "at": None, "error": None},
        }
        self.lock = threading.Lock()

    # --- reading the sources -------------------------------------------------

    def _record(self, source, failure=None):
        self.sources[source] = {
            "ok": failure is None,
            "at": self.clock().isoformat(timespec="seconds"),
            "error": None if failure is None else _message(failure),
        }

    def refresh_tasks(self):
        try:
            tasks = self.fetch_tasks()
        except Exception as failure:  # keep the last good tasks, show the error
            with self.lock:
                self._record("notion", failure)
            return False
        with self.lock:
            self.tasks = tasks
            self._record("notion")
        return True

    def refresh_events(self):
        days = week_from(self.clock().date())
        try:
            events = self.fetch_events(days[0], days[-1] + timedelta(days=1))
        except Exception as failure:
            with self.lock:
                self._record("calendar", failure)
            return False
        with self.lock:
            self.events = events
            self._record("calendar")
        return True

    def refresh(self, source="all"):
        """Re-read "notion", "calendar" or "all". Unknown names raise ValueError."""
        if source not in ("all", "notion", "calendar"):
            raise ValueError(f"unknown source {source!r}")
        if source in ("all", "notion"):
            self.refresh_tasks()
        if source in ("all", "calendar"):
            self.refresh_events()

    # --- the LLM priority ----------------------------------------------------

    def _signature(self, context):
        """What the priority depends on. Same signature = no new LLM call."""
        rows = sorted(
            (t.id, t.title, str(t.deadline), t.priority, t.status, t.next_action, t.duration_minutes)
            for t in self.tasks
        )
        return (tuple(rows), context.strip())

    def update_priority(self, context):
        """Ask the LLM only if tasks or context changed. Returns True if it asked."""
        with self.lock:
            signature = self._signature(context)
            if signature == self.priority_signature:
                return False
            tasks = list(self.tasks)
        outcome = self.prioritize(tasks, self.clock().date(), context)
        with self.lock:
            self.outcome = outcome
            self.priority_signature = signature
        return True

    # --- looking things up and ticking --------------------------------------

    def find_task(self, task_id):
        return next((task for task in self.tasks if task.id == task_id), None)

    def find_event(self, key):
        return next((event for event in self.events if event.key == key), None)

    def drop_task(self, task_id):
        """Forget a task that was just marked Done, without waiting for Notion.

        The verified priority stays valid without that task (removing a row
        does not change the order of the others), so no new LLM call is made.
        """
        with self.lock:
            context = self.priority_signature[1] if self.priority_signature else None
            was_fresh = context is not None and self.priority_signature == self._signature(context)
            self.tasks = [task for task in self.tasks if task.id != task_id]
            if was_fresh:
                if self.outcome["ok"]:
                    rows = [row for row in self.outcome["priority"] if row["id"] != task_id]
                    self.outcome = {**self.outcome, "priority": rows}
                self.priority_signature = self._signature(context)

    # --- what the page shows -------------------------------------------------

    def state(self, settings):
        """The whole dashboard as plain JSON-ready data."""
        now = self.clock()
        today = now.date()
        days = week_from(today)
        with self.lock:
            tasks, all_events, sources = list(self.tasks), list(self.events), dict(self.sources)
            fresh = self.priority_signature == self._signature(settings.context)
            outcome = self.outcome if fresh else NOT_ASKED

        hidden = {entry.key for entry in settings.hidden_events}
        tickable = {name.casefold() for name in settings.tickable_calendars}
        events = [event for event in all_events if event.key not in hidden]
        ordered = order_tasks(tasks, outcome)
        # A task whose block she rejected keeps its place in the list, but the
        # planner stops proposing a block for it (D2-052).
        rejected = set(settings.rejected_blocks)
        plannable = [task for task in ordered if task.id not in rejected]
        plan = plan_study_blocks(plannable, events + _time_already_gone(now), days)
        reasons = {row["id"]: row["reason"] for row in outcome["priority"]} if outcome["ok"] else {}

        def event_row(event):
            return {
                "key": event.key,
                "calendar": event.calendar,
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
                "all_day": event.all_day,
                "tickable": event.calendar.casefold() in tickable,
            }

        cycle = None
        if settings.cycle is not None:
            cycle = estimate_phase(today, settings.cycle)
            cycle["next_start"] = cycle["next_start"].isoformat()

        return {
            "now": now.isoformat(timespec="seconds"),
            "today": today.isoformat(),
            "days": [day.isoformat() for day in days],
            "sources": {**sources, "gmail": {"ok": None, "at": None, "error": "non collegato"}},
            "events": [event_row(event) for event in events],
            "blocks": [block.model_dump(mode="json") for block in plan["blocks"]],
            "unplaced": [task.id for task in plan["unplaced"]],
            "rejected_blocks": sorted(rejected),
            "tasks": [
                {**task.model_dump(mode="json"), "reason": reasons.get(task.id)} for task in ordered
            ],
            "priority": {"ok": outcome["ok"], "reason": outcome["reason"]},
            "cycle": cycle,
            "calendars": sorted({event.calendar for event in all_events}),
        }
