"""Giulia's private settings, kept in one JSON file outside git.

What lives here is what she edits on the Settings page and what the dashboard
must remember between refreshes:

  - ``context``            her own text (habits, rules) that goes into the
                           system prompt of the priority and of the chat;
  - ``cycle``              the cycle settings used by cycle.estimate_phase;
  - ``tickable_calendars`` the calendars whose events can be ticked off;
  - ``hidden_events``      events she ticked: hidden from the dashboard and
                           waiting to be deleted from Google Calendar.

The file is ``data/settings.json`` (``data/`` is in .gitignore);
``data.example/settings.json`` shows the shape with no private data. Everything
read from the file is validated with pydantic: a broken file raises a clear
ValueError instead of being half-used.
"""

import json
import os
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from cycle import CycleSettings

SETTINGS_FILE = "data/settings.json"


class HiddenEvent(BaseModel):
    """One ticked calendar occurrence. ``key`` is Event.key (UID + start)."""

    key: str = Field(min_length=1)
    title: str
    calendar: str
    start: datetime
    hidden_at: datetime


class UserSettings(BaseModel):
    context: str = ""
    cycle: Optional[CycleSettings] = None
    # Fixed commitments (restaurant shifts, lessons) are not here on purpose.
    tickable_calendars: list[str] = ["personale", "studio"]
    hidden_events: list[HiddenEvent] = []
    # Task ids whose planner block she rejected: the planner stops proposing
    # a block for them until she restores them (or the task is done).
    rejected_blocks: list[str] = []


def read_settings(path=SETTINGS_FILE):
    """Return the saved settings, or the defaults when the file does not exist."""
    if not os.path.exists(path):
        return UserSettings()
    try:
        with open(path) as handle:
            return UserSettings.model_validate(json.load(handle))
    except (json.JSONDecodeError, ValidationError) as problem:
        raise ValueError(f"{path} is not a valid settings file: {problem}") from None


def write_settings(settings, path=SETTINGS_FILE):
    """Save the settings. Written to a temporary file first and then renamed,
    so a crash in the middle never leaves a half-written settings file."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        handle.write(settings.model_dump_json(indent=2))
    os.replace(temporary, path)
    return settings


def hide_event(settings, event, now):
    """Return new settings with ``event`` hidden (once: ticking twice adds nothing)."""
    if any(hidden.key == event.key for hidden in settings.hidden_events):
        return settings
    entry = HiddenEvent(
        key=event.key, title=event.title, calendar=event.calendar, start=event.start, hidden_at=now
    )
    return settings.model_copy(update={"hidden_events": settings.hidden_events + [entry]})


def unhide_event(settings, key):
    """Return new settings without the hidden event ``key``."""
    kept = [hidden for hidden in settings.hidden_events if hidden.key != key]
    return settings.model_copy(update={"hidden_events": kept})


def reject_block(settings, task_id):
    """Return new settings with the task's planner block rejected (once)."""
    if task_id in settings.rejected_blocks:
        return settings
    return settings.model_copy(update={"rejected_blocks": settings.rejected_blocks + [task_id]})


def restore_block(settings, task_id):
    """Return new settings where the task may get a planner block again."""
    kept = [rejected for rejected in settings.rejected_blocks if rejected != task_id]
    return settings.model_copy(update={"rejected_blocks": kept})
