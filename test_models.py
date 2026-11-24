"""Task and Event are validated at the border: a wrong field fails loudly."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from models import AMSTERDAM, Event, Task


def _task(**overrides):
    fields = {"id": "p1", "title": "Study", "status": "Not Started"}
    fields.update(overrides)
    return Task(**fields)


def test_task_accepts_the_planning_fields():
    task = _task(area="University", deadline="2026-11-12", duration_minutes=90, priority="P1 - Critical")
    assert task.deadline == date(2026, 11, 12)
    assert task.duration_minutes == 90
    assert task.next_action is False


def test_task_refuses_an_empty_title():
    with pytest.raises(ValidationError):
        _task(title="")


def test_task_refuses_an_unknown_status():
    # Status is a closed set: the four options of the Notion property.
    with pytest.raises(ValidationError):
        _task(status="Maybe")


def test_task_refuses_a_missing_status():
    with pytest.raises(ValidationError):
        Task(id="p1", title="Study")


def test_task_refuses_a_non_positive_duration():
    with pytest.raises(ValidationError):
        _task(duration_minutes=0)


def test_task_refuses_a_malformed_deadline():
    with pytest.raises(ValidationError):
        _task(deadline="next week")


def test_event_refuses_an_end_before_its_start():
    start = datetime(2026, 11, 10, 10, 0, tzinfo=AMSTERDAM)
    with pytest.raises(ValidationError):
        Event(calendar="c", title="x", start=start, end=start)
