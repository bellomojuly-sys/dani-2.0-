"""The read tools Dani can call itself during a chat (D2-056).

When Giulia plans with Claude, Claude looks things up: other weeks and months,
all her tasks, her projects and goals, her life plan. These four tools give
Dani the same reach, read-only:

  - read_calendar(start, end)  events of every calendar in any period (max 92 days);
  - read_tasks(area?, contains?, due_before?)  all her open tasks, filtered;
  - read_projects()            her live projects and 1/3/10-year goals;
  - read_page(name)            the text of one page from an allow-list
                               (life plan, area pages, project roadmaps).

Same calling convention as tools.py: each tool takes one ``arguments`` dict,
checks it first, and returns {"error": ...} on bad input instead of raising,
so the model can read the error and try again. The data sources are injected,
so the tests never touch Notion or Google.
"""

from datetime import date, timedelta

MAX_DAYS = 92  # about three months per call; longer periods take more calls


def _day(arguments, name):
    value = arguments.get(name)
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _unknown(arguments, allowed):
    extra = sorted(set(arguments) - set(allowed))
    return {"error": f"unknown arguments: {', '.join(extra)}"} if extra else None


def _clock(moment):
    return moment.strftime("%H:%M")


def make_read_calendar(fetch_events):
    """``fetch_events(start, end)`` returns Event objects with start in [start, end)."""

    def read_calendar(arguments):
        problem = _unknown(arguments, ("start", "end"))
        if problem:
            return problem
        start, end = _day(arguments, "start"), _day(arguments, "end")
        if start is None or end is None:
            return {"error": "start and end must be dates as YYYY-MM-DD"}
        if end < start:
            return {"error": "end is before start"}
        if (end - start).days + 1 > MAX_DAYS:
            return {"error": f"at most {MAX_DAYS} days per call: split the period"}
        events = fetch_events(start, end + timedelta(days=1))
        return [
            {
                "date": event.start.date().isoformat(),
                "time": "all day" if event.all_day else f"{_clock(event.start)}-{_clock(event.end)}",
                "calendar": event.calendar,
                "title": event.title,
            }
            for event in events
        ]

    return read_calendar


def make_read_tasks(current_tasks):
    """``current_tasks()`` returns the open Task objects already read from Notion."""

    def read_tasks(arguments):
        problem = _unknown(arguments, ("area", "contains", "due_before"))
        if problem:
            return problem
        tasks = current_tasks()
        area = arguments.get("area")
        if area is not None:
            if not isinstance(area, str):
                return {"error": "area must be text"}
            tasks = [task for task in tasks if (task.area or "").casefold() == area.casefold()]
        contains = arguments.get("contains")
        if contains is not None:
            if not isinstance(contains, str):
                return {"error": "contains must be text"}
            tasks = [task for task in tasks if contains.casefold() in task.title.casefold()]
        if "due_before" in arguments:
            limit = _day(arguments, "due_before")
            if limit is None:
                return {"error": "due_before must be a date as YYYY-MM-DD"}
            tasks = [task for task in tasks if task.deadline is not None and task.deadline <= limit]
        return [
            {
                "title": task.title,
                "area": task.area,
                "status": task.status,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "minutes": task.duration_minutes,
                "priority": task.priority,
            }
            for task in tasks
        ]

    return read_tasks


def make_read_projects(fetch_projects):
    """``fetch_projects()`` returns the live Project objects of Projects & Goals."""

    def read_projects(arguments):
        problem = _unknown(arguments, ())
        if problem:
            return problem
        return [project.model_dump(mode="json", exclude={"id"}) for project in fetch_projects()]

    return read_projects


def make_read_page(pages, fetch_text):
    """``pages`` maps a page name to its Notion id: only these can be read.

    ``fetch_text(page_id)`` returns the page text. Names are matched without
    caring about upper or lower case.
    """
    by_name = {name.casefold(): page_id for name, page_id in pages.items()}

    def read_page(arguments):
        problem = _unknown(arguments, ("name",))
        if problem:
            return problem
        name = arguments.get("name")
        if not isinstance(name, str) or name.casefold() not in by_name:
            return {"error": "unknown page; the pages you can read are: " + ", ".join(sorted(pages))}
        return {"name": name, "text": fetch_text(by_name[name.casefold()])}

    return read_page


def _schema(name, description, properties, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(required),
                "additionalProperties": False,
            },
        },
    }


DATE = {"type": "string", "description": "a date as YYYY-MM-DD"}

READ_CALENDAR_SCHEMA = _schema(
    "read_calendar",
    "Read the events of all of Giulia's calendars (lessons, shifts, appointments, deadlines) "
    f"between two dates, both included, at most {MAX_DAYS} days per call. Use it for any period "
    "that is not in the week already shown.",
    {"start": DATE, "end": DATE},
    ("start", "end"),
)
READ_TASKS_SCHEMA = _schema(
    "read_tasks",
    "Read all of Giulia's open tasks from Notion, in every area and project (University: "
    "AMEXIO tasks start with AMX, Dani tasks with D2; Betsy; Carriera / ICT; Personal). "
    "Every filter is optional.",
    {
        "area": {"type": "string", "description": "only tasks of this area"},
        "contains": {"type": "string", "description": "only tasks whose title contains this text"},
        "due_before": {**DATE, "description": "only tasks with a deadline on or before this date"},
    },
)
READ_PROJECTS_SCHEMA = _schema(
    "read_projects",
    "Read Giulia's live projects and her 1-year, 3-year and 10-year goals, with area, status, "
    "due date and target. Use it to plan from her goals down to weeks and days.",
    {},
)


def read_page_schema(names):
    """The read_page schema lists the allowed page names, so the model knows them."""
    return _schema(
        "read_page",
        "Read the text of one of Giulia's Notion pages: her life plan, her area pages and her "
        "project roadmaps. Allowed names: " + ", ".join(sorted(names)) + ".",
        {"name": {"type": "string", "enum": sorted(names)}},
        ("name",),
    )


def build_read_tools(fetch_events, current_tasks, fetch_projects=None, pages=None, fetch_text=None):
    """Return {name: (schema, function)} for the tools whose source is set up."""
    tools = {
        "read_calendar": (READ_CALENDAR_SCHEMA, make_read_calendar(fetch_events)),
        "read_tasks": (READ_TASKS_SCHEMA, make_read_tasks(current_tasks)),
    }
    if fetch_projects is not None:
        tools["read_projects"] = (READ_PROJECTS_SCHEMA, make_read_projects(fetch_projects))
    if pages and fetch_text is not None:
        tools["read_page"] = (read_page_schema(pages), make_read_page(pages, fetch_text))
    return tools


def parse_pages(value):
    """Read NOTION_PAGES from .env: "name=page_id; name=page_id; ...".

    A piece without "=" or with an empty side raises ValueError, so a typo in
    .env is seen at start and not as a silent missing page.
    """
    pages = {}
    for piece in (value or "").split(";"):
        if not piece.strip():
            continue
        name, sep, page_id = piece.partition("=")
        if not sep or not name.strip() or not page_id.strip():
            raise ValueError(f"NOTION_PAGES: {piece.strip()!r} is not name=page_id")
        pages[name.strip()] = page_id.strip()
    return pages
