"""The typed objects Dani works with: a Task read from Notion and an Event read
from a Google Calendar iCal feed.

Both are pydantic models, so data from outside is validated before it is used:
a missing or wrong field raises a clear ValidationError instead of being
silently accepted (the same rule as DaniAnswer in answer.py).
"""

from datetime import date, datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

# Giulia lives in the Netherlands: every time Dani shows is Amsterdam time.
AMSTERDAM = ZoneInfo("Europe/Amsterdam")


class Task(BaseModel):
    """One row of the Notion Tasks database, with only the fields planning needs.

    ``status`` is a closed set (the four options of the Notion Status property),
    so a page with an unknown or empty status is refused, never guessed.
    ``duration_minutes`` is Notion's "Estimated Time" and must be positive.
    """

    id: str
    title: str = Field(min_length=1)
    area: Optional[str] = None
    status: Literal["Not Started", "In Progress", "Waiting", "Done"]
    deadline: Optional[date] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    priority: Optional[str] = None
    next_action: bool = False


class Event(BaseModel):
    """One occurrence of a calendar event, in Amsterdam time.

    A repeating event becomes one Event per occurrence in the window we read,
    so a weekly lesson shows up every week. ``all_day`` events have no clock
    time: they are shown but they do not block study time.
    """

    calendar: str
    title: str
    start: datetime
    end: datetime
    all_day: bool = False

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.end <= self.start:
            raise ValueError("event end must be after its start")
        return self
