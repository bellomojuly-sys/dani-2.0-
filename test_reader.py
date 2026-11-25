"""The read tools of D2-056 with fake sources: accepted case and each refusal."""

from datetime import date, datetime

import pytest

from models import AMSTERDAM, Event, Project, Task
from reader import MAX_DAYS, build_read_tools, parse_pages

TASKS = [
    Task(id="1", title="AMX-16 preview", area="University", status="Not Started", deadline=date(2026, 11, 28)),
    Task(id="2", title="D2-056 read tools", area="University", status="In Progress"),
    Task(id="3", title="CV in inglese", area="Carriera / ICT", status="Not Started", deadline=date(2026, 12, 20)),
]
EVENTS = [
    Event(calendar="lavoro", title="Turno", start=datetime(2026, 12, 4, 17, 0, tzinfo=AMSTERDAM),
          end=datetime(2026, 12, 4, 23, 0, tzinfo=AMSTERDAM)),
    Event(calendar="Fontys", title="Deadline Betsy", start=datetime(2026, 12, 5, 0, 0, tzinfo=AMSTERDAM),
          end=datetime(2026, 12, 6, 0, 0, tzinfo=AMSTERDAM), all_day=True),
]
PROJECTS = [Project(id="p", name="Lavoro part-time in AI", type="1-Year Goal", area="Carriera / ICT",
                    status="Active", due=date(2026, 12, 31), target="un contratto firmato")]
PAGES = {"piano di vita": "page-1", "Betsy roadmap": "page-2"}


@pytest.fixture
def tools():
    seen = {"events": [], "pages": []}

    def fetch_events(start, end):
        seen["events"].append((start, end))
        return EVENTS

    def fetch_text(page_id):
        seen["pages"].append(page_id)
        return "## Obiettivi\n- lavoro entro dicembre"

    built = build_read_tools(fetch_events, lambda: TASKS, lambda: PROJECTS, PAGES, fetch_text)
    run = {name: function for name, (_, function) in built.items()}
    run["seen"] = seen
    run["schemas"] = {name: schema for name, (schema, _) in built.items()}
    return run


def test_read_calendar_reads_any_period_with_the_end_day_included(tools):
    rows = tools["read_calendar"]({"start": "2026-12-01", "end": "2026-12-31"})
    assert tools["seen"]["events"] == [(date(2026, 12, 1), date(2027, 1, 1))]
    assert rows[0] == {"date": "2026-12-04", "time": "17:00-23:00", "calendar": "lavoro", "title": "Turno"}
    assert rows[1]["time"] == "all day"


@pytest.mark.parametrize("arguments, message", [
    ({"start": "2026-12-01"}, "YYYY-MM-DD"),
    ({"start": "1 dicembre", "end": "2026-12-31"}, "YYYY-MM-DD"),
    ({"start": "2026-12-31", "end": "2026-12-01"}, "before start"),
    ({"start": "2026-01-01", "end": "2026-12-31"}, f"at most {MAX_DAYS} days"),
    ({"start": "2026-12-01", "end": "2027-03-03"}, f"at most {MAX_DAYS} days"),  # 93 days
    ({"start": "2026-12-01", "end": "2026-12-02", "calendar": "x"}, "unknown arguments: calendar"),
])
def test_read_calendar_refusals_read_nothing(tools, arguments, message):
    assert message in tools["read_calendar"](arguments)["error"]
    assert tools["seen"]["events"] == []


def test_read_calendar_accepts_exactly_max_days(tools):
    assert isinstance(tools["read_calendar"]({"start": "2026-12-01", "end": "2027-03-02"}), list)  # 92 days


def test_read_tasks_without_filters_gives_every_open_task(tools):
    rows = tools["read_tasks"]({})
    assert [row["title"] for row in rows] == ["AMX-16 preview", "D2-056 read tools", "CV in inglese"]
    assert rows[0] == {"title": "AMX-16 preview", "area": "University", "status": "Not Started",
                       "deadline": "2026-11-28", "minutes": None, "priority": None}


def test_read_tasks_filters_combine(tools):
    assert [r["title"] for r in tools["read_tasks"]({"area": "university"})] == ["AMX-16 preview", "D2-056 read tools"]
    assert [r["title"] for r in tools["read_tasks"]({"contains": "amx"})] == ["AMX-16 preview"]
    assert [r["title"] for r in tools["read_tasks"]({"due_before": "2026-12-01"})] == ["AMX-16 preview"]
    assert tools["read_tasks"]({"area": "University", "contains": "CV"}) == []


@pytest.mark.parametrize("arguments, message", [
    ({"area": 3}, "area must be text"),
    ({"contains": ["x"]}, "contains must be text"),
    ({"due_before": "presto"}, "due_before must be a date"),
    ({"project": "Betsy"}, "unknown arguments: project"),
])
def test_read_tasks_refusals(tools, arguments, message):
    assert message in tools["read_tasks"](arguments)["error"]


def test_read_projects_gives_goals_without_the_notion_id(tools):
    assert tools["read_projects"]({}) == [{
        "name": "Lavoro part-time in AI", "type": "1-Year Goal", "area": "Carriera / ICT", "status": "Active",
        "due": "2026-12-31", "target": "un contratto firmato", "notes": ""}]
    assert "unknown arguments" in tools["read_projects"]({"all": True})["error"]


def test_read_page_reads_only_allowed_pages(tools):
    answer = tools["read_page"]({"name": "Piano di Vita"})
    assert answer == {"name": "Piano di Vita", "text": "## Obiettivi\n- lavoro entro dicembre"}
    assert tools["seen"]["pages"] == ["page-1"]
    refused = tools["read_page"]({"name": "Diario segreto"})
    assert "unknown page" in refused["error"] and "Betsy roadmap" in refused["error"]
    assert "unknown page" in tools["read_page"]({})["error"]
    assert tools["seen"]["pages"] == ["page-1"]  # a refusal reads nothing
    assert tools["schemas"]["read_page"]["function"]["parameters"]["properties"]["name"]["enum"] == sorted(PAGES)


def test_tools_without_a_source_are_not_offered():
    built = build_read_tools(lambda s, e: [], lambda: [])
    assert set(built) == {"read_calendar", "read_tasks"}
    assert set(build_read_tools(lambda s, e: [], lambda: [], pages=PAGES)) == {"read_calendar", "read_tasks"}


def test_parse_pages_reads_env_and_refuses_typos():
    assert parse_pages(" piano di vita = abc ; Betsy=def; ") == {"piano di vita": "abc", "Betsy": "def"}
    assert parse_pages(None) == {}
    for bad in ("piano di vita", "=abc", "nome="):
        with pytest.raises(ValueError, match="name=page_id"):
            parse_pages(bad)


def test_due_before_includes_the_day_itself(tools):
    # Mutation testing (25 Nov) found that "<=" could become "<" unnoticed.
    assert [r["title"] for r in tools["read_tasks"]({"due_before": "2026-11-28"})] == ["AMX-16 preview"]
