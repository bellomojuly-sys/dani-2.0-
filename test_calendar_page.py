"""D2-072: the calendar page — any week, and a drag that becomes a preview."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from models import AMSTERDAM, Event
from server import create_app
from test_server import CalendarRig, at


def later(day, hour):
    return datetime(2026, 12, day, hour, tzinfo=AMSTERDAM)


def rig_with_december(tmp_path):
    """A rig whose calendar gets an event after the refresh: it is not in this week's events."""
    rig = CalendarRig(tmp_path)
    rig.http.put("/api/settings", json={"tickable_calendars": ["personale", "studio"]})
    rig.calendar.append(Event(calendar="personale", title="Parrucchiera", uid="hair", api_id="hair-1",
                              calendar_id="c-p", start=later(3, 10), end=later(3, 11)))
    return rig


def test_events_of_any_period_are_listed_with_what_can_be_moved(tmp_path):
    rig = rig_with_december(tmp_path)
    asked = []
    fetch = rig.live.fetch_events
    rig.live.fetch_events = lambda start, end: asked.append((start, end)) or fetch(start, end)
    events = rig.http.get("/api/events?start=2026-11-30&days=7").json()["events"]
    assert asked == [(later(1, 0).date() - timedelta(days=1), later(7, 0).date())]
    by_title = {e["title"]: e for e in events}
    assert by_title["Parrucchiera"]["tickable"] is True and by_title["Turno ristorante"]["tickable"] is False
    assert [e["start"] for e in events] == sorted(e["start"] for e in events)


def test_hidden_events_stay_hidden_and_bad_ranges_are_refused(tmp_path):
    rig = CalendarRig(tmp_path)
    app = create_app(rig.live, lambda task_id: None, None, None, None, rig.path, web_dir=None)  # no calendar writes
    http = TestClient(app)
    http.put("/api/settings", json={"tickable_calendars": ["personale"]})
    http.post("/api/tick", json={"kind": "event", "id": rig.key("Palestra")})  # hidden, delete pending
    titles = [e["title"] for e in http.get("/api/events?start=2026-11-09&days=7").json()["events"]]
    assert "Palestra" not in titles and "Call con Ruud" in titles
    assert http.get("/api/events?start=2026-11-09&days=0").status_code == 422
    assert http.get("/api/events?start=2026-11-09&days=43").status_code == 422


def test_a_calendar_that_cannot_be_read_is_an_error_not_an_empty_week(tmp_path):
    rig = CalendarRig(tmp_path)

    def down(start, end):
        raise RuntimeError("Google down")

    rig.live.fetch_events = down
    answer = rig.http.get("/api/events?start=2026-11-09&days=7")
    assert answer.status_code == 502 and "Google down" in answer.json()["detail"]


def test_a_drag_in_another_week_is_a_preview_and_is_written_only_after_yes(tmp_path):
    rig = rig_with_december(tmp_path)
    key = rig.key("Parrucchiera")
    answer = rig.http.post("/api/move", json={"key": key, "start": "2026-12-03T14:00:00+01:00"}).json()
    proposal = answer["proposal"]
    assert proposal["new_start"] == "2026-12-03T14:00:00+01:00" and proposal["new_end"] == "2026-12-03T15:00:00+01:00"
    assert rig.moved == []  # a preview writes nothing
    done = rig.http.post("/api/confirm", json={"id": proposal["id"]}).json()
    assert done["ok"] is True and done["read_back"] is True
    assert rig.moved == [("hair-1", later(3, 14), later(3, 15))]


def test_a_drag_onto_another_event_carries_the_warning(tmp_path):
    rig = rig_with_december(tmp_path)
    body = {"key": rig.key("Palestra"), "start": "2026-11-12T15:00:00+01:00", "end": "2026-11-12T16:00:00+01:00"}
    proposal = rig.http.post("/api/move", json=body).json()["proposal"]
    assert any("Call con Ruud" in warning for warning in proposal["warnings"])


def test_drag_refusals(tmp_path):
    rig = rig_with_december(tmp_path)
    shift = {"key": rig.key("Turno ristorante"), "start": "2026-11-12T18:00:00+01:00"}
    assert rig.http.post("/api/move", json=shift).status_code == 422  # a fixed calendar
    unknown = {"key": "nope|2026-11-12T10:00:00+01:00", "start": "2026-11-12T18:00:00+01:00"}
    assert rig.http.post("/api/move", json=unknown).status_code == 404
    broken_key = {"key": "no-time-in-it", "start": "2026-11-12T18:00:00+01:00"}
    assert rig.http.post("/api/move", json=broken_key).status_code == 404
    same = {"key": rig.key("Palestra"), "start": at(11, 7, 30).isoformat()}
    assert rig.http.post("/api/move", json=same).status_code == 422  # already at that time
    read_only = TestClient(create_app(rig.live, lambda task_id: None, None, None, None, rig.path, web_dir=None))
    assert read_only.post("/api/move", json=shift).status_code == 503


def test_a_drag_whose_calendar_cannot_be_read_writes_nothing(tmp_path):
    rig = rig_with_december(tmp_path)
    key = rig.key("Palestra")

    def down(start, end):
        raise RuntimeError("Google down")

    rig.live.fetch_events = down
    answer = rig.http.post("/api/move", json={"key": key, "start": "2026-11-11T10:00:00+01:00"})
    assert answer.status_code == 502 and rig.moved == []


def test_an_event_of_another_week_can_be_ticked_from_the_calendar_page(tmp_path):
    rig = rig_with_december(tmp_path)
    answer = rig.http.post("/api/tick", json={"kind": "event", "id": rig.key("Parrucchiera")})
    assert answer.json()["calendar"] == "deleted" and rig.deleted == ["hair-1"]
