"""Tests for the Task domain model (D2-024).

The model is the single place that decides what a valid task is, so each test
pins down one rule: it either proves a correct task is accepted, or proves a
specific wrong task is refused. pydantic raises ValidationError, which is a
subclass of ValueError, so "fails with a clear error" is exactly this.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from task import Area, Status, Task

# A full, correct task reused as the starting point. Each refusal test copies
# it and breaks exactly one thing, so the test can only fail because of that
# one change.
VALID = {
    "title": "Finish the AMEXIO case model",
    "area": "University",
    "status": "In Progress",
    "deadline": "2026-11-13",
    "duration": 90,
}


def test_full_task_is_accepted():
    """A task with every field, all correct, is accepted and typed."""
    task = Task.model_validate(VALID)
    assert task.title == "Finish the AMEXIO case model"
    assert task.area is Area.UNIVERSITY
    assert task.status is Status.IN_PROGRESS
    assert task.deadline == date(2026, 11, 13)  # the ISO string became a date
    assert task.duration == 90


def test_minimal_task_is_accepted():
    """Only title, area and status are required; deadline and duration may be
    missing, and are then None (not an error)."""
    task = Task.model_validate({"title": "Study MCP", "area": "University", "status": "Not Started"})
    assert task.deadline is None
    assert task.duration is None


def test_enum_values_are_the_exact_notion_strings():
    """The Enum values must be the exact Notion option names (read from the
    database on 2026-11-05). If one value is changed, the mapping in D2-025
    would reject a real task, so this test guards every option."""
    assert {a.value for a in Area} == {
        "Heemia",
        "MG Integration",
        "University",
        "Carriera / ICT",
        "Personal",
        "health",
    }
    assert {s.value for s in Status} == {"Not Started", "In Progress", "Waiting", "Done"}


def test_title_is_required():
    """A task without a title is not a task; it must fail."""
    data = {k: v for k, v in VALID.items() if k != "title"}
    with pytest.raises(ValidationError) as exc:
        Task.model_validate(data)
    assert "title" in str(exc.value)


def test_area_is_required():
    data = {k: v for k, v in VALID.items() if k != "area"}
    with pytest.raises(ValidationError) as exc:
        Task.model_validate(data)
    assert "area" in str(exc.value)


def test_status_is_required():
    data = {k: v for k, v in VALID.items() if k != "status"}
    with pytest.raises(ValidationError) as exc:
        Task.model_validate(data)
    assert "status" in str(exc.value)


def test_empty_title_fails():
    """An empty title has the field but no content: refused by min_length."""
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "title": ""})


def test_whitespace_only_title_fails():
    """Spaces are trimmed first, so a spaces-only title becomes empty and is
    refused. Proves str_strip_whitespace + min_length work together."""
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "title": "   "})


def test_unknown_area_fails():
    """An Area that is not one of the allowed options is refused, not stored."""
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "area": "Universty"})  # typo on purpose


def test_unknown_status_fails():
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "status": "Almost done"})


def test_zero_duration_fails():
    """duration is a positive number of minutes; 0 minutes is meaningless."""
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "duration": 0})


def test_negative_duration_fails():
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "duration": -30})


def test_non_numeric_duration_fails():
    """A duration that is not a number ("soon") cannot be minutes."""
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "duration": "soon"})


def test_bad_deadline_fails():
    """A deadline that is not a real date is refused, not guessed."""
    with pytest.raises(ValidationError):
        Task.model_validate({**VALID, "deadline": "not-a-date"})


def test_unknown_field_is_refused():
    """A field name the model does not know (e.g. a typo 'titel') is refused by
    extra='forbid', so it is never silently dropped."""
    with pytest.raises(ValidationError) as exc:
        Task.model_validate({**VALID, "titel": "oops"})
    assert "titel" in str(exc.value)
