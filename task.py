"""The typed Task model for my Notion tasks (D2-024, milestone M05).

This is the DOMAIN model: the shape every task has once it is inside Dani,
independent of how Notion stores it. D2-025 will map a real Notion row onto
this model; here we only define the model and its validation.

A Task is valid only if it has the fields planning needs, each with the right
type and an allowed value. An invalid task never becomes a half-built object:
pydantic raises a ValidationError (a subclass of ValueError) with a clear
message, so a wrong or missing field is never silently accepted.

The values of the two Enums are the EXACT strings used in my Notion Tasks
database, read from the database itself on 2026-11-05. The Python member names
are cleaned up (uppercase, no spaces), but the value is what Notion sends, so a
comparison against the Notion string just works.
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Area(str, Enum):
    """The life area a task belongs to (the Notion "Area" select).

    `str, Enum` means every member is also its string value, so `Area.UNIVERSITY
    == "University"` is True and the JSON form is the plain string.
    """

    HEEMIA = "Heemia"
    MG_INTEGRATION = "MG Integration"
    UNIVERSITY = "University"
    CARRIERA_ICT = "Carriera / ICT"
    PERSONAL = "Personal"
    HEALTH = "health"


class Status(str, Enum):
    """Where the task is in its life (the Notion "Status" select)."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    WAITING = "Waiting"
    DONE = "Done"


class Task(BaseModel):
    """One task, with the fields planning needs.

    Required: title, area, status.
    Optional (may be missing, then None): deadline, duration.

    Rules enforced by the model:
    - title is a non-empty string (surrounding spaces are trimmed first, so a
      blank or spaces-only title fails);
    - area and status must be one of the allowed Enum values;
    - deadline, when present, is a calendar date (ISO 8601, e.g. 2026-11-13);
    - duration, when present, is a whole number of minutes greater than 0;
    - an unknown field name is refused (extra="forbid"), so a typo like
      "titel" fails loudly instead of being quietly dropped.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    area: Area
    status: Status
    deadline: date | None = None
    duration: int | None = Field(default=None, gt=0)  # minutes
