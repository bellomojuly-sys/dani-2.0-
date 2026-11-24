"""Read Giulia's open tasks from her Notion Tasks database.

Plain HTTPS + JSON with the standard library (urllib), no Notion SDK: one
visible request we can read and explain (Decision Log 2026-11-05). The token
comes from the environment and travels only in the Authorization header; it is
never part of a URL or of an error message.

Two writes exist, both behind an action of Giulia's:
  - ``mark_done``   sets Status = Done on a single page, after she ticks it
                    (Decision Log 2026-11-10);
  - ``create_task`` creates one task page, after she confirms a proposal from
                    the chat (D2-055).

Two layers, so each can be tested on its own:
  - ``task_from_page``    turns one Notion page (a dict) into a typed Task;
  - ``query_open_tasks``  calls the API (through an injectable ``http``
                          function) and maps every page it returns.
"""

import json
from urllib import error, request

from pydantic import ValidationError

from models import Project, Task

API = "https://api.notion.com/v1"
# Pinned on purpose: a new Notion API version cannot silently change the shape
# of the pages we read.
VERSION = "2022-06-28"

# Everything that is not Done is open. A "Done" filter in the query means we
# never download finished tasks only to drop them here.
OPEN_FILTER = {"property": "Status", "select": {"does_not_equal": "Done"}}


def send_json(method, url, headers, body, opener=request.urlopen, timeout=20):
    """Send a JSON body with ``method`` and return the decoded JSON answer.

    A failed request raises RuntimeError with the status code and the start of
    the body. The headers (where the token lives) are never in the message.
    ``opener`` is injectable so tests never touch the network.
    """
    data = None if body is None else json.dumps(body).encode()
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener(req, timeout=timeout) as response:
            return json.loads(response.read())
    except error.HTTPError as failure:
        detail = failure.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Notion answered HTTP {failure.code}: {detail}") from None
    except error.URLError as failure:
        raise RuntimeError(f"Notion could not be reached: {failure.reason}") from None


def post_json(url, headers, body, opener=request.urlopen, timeout=20):
    """POST: used to query the database (a read)."""
    return send_json("POST", url, headers, body, opener, timeout)


def get_json(url, headers, body=None, opener=request.urlopen, timeout=20):
    """GET: used to read the blocks of a page (a read, no body)."""
    return send_json("GET", url, headers, None, opener, timeout)


def patch_json(url, headers, body, opener=request.urlopen, timeout=20):
    """PATCH: used to change one page (a write)."""
    return send_json("PATCH", url, headers, body, opener, timeout)


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }


def _plain_text(rich_text):
    """Join the plain_text parts of a Notion rich-text / title array."""
    return "".join(part.get("plain_text", "") for part in rich_text or [])


def _select_name(prop):
    """The chosen option name of a select property, or None when empty."""
    return (prop.get("select") or {}).get("name")


def task_from_page(page):
    """Map one Notion page of the Tasks database to a typed Task.

    Property names are the real ones of Giulia's database ("Task Name",
    "Area", "Status", "Due Date", "Estimated Time", "Priority", "Next Action").
    A page with a missing or wrong field raises ValueError naming the page, so
    a bad row is never silently turned into a task.
    """
    props = page.get("properties", {})
    due = (props.get("Due Date") or {}).get("date") or {}
    try:
        return Task(
            id=page["id"],
            title=_plain_text(props["Task Name"]["title"]),
            area=_select_name(props.get("Area") or {}),
            status=_select_name(props.get("Status") or {}),
            deadline=(due.get("start") or None) and due["start"][:10],
            duration_minutes=(props.get("Estimated Time") or {}).get("number"),
            priority=_select_name(props.get("Priority") or {}),
            next_action=bool((props.get("Next Action") or {}).get("checkbox", False)),
        )
    except (KeyError, ValidationError) as problem:
        raise ValueError(f"Notion page {page.get('id')!r} is not a valid task: {problem}")


def query_open_tasks(token, database_id, http=post_json):
    """Return every open task of the database as typed Task objects.

    Notion answers 100 pages at a time; while ``has_more`` is true we ask for
    the next page with ``start_cursor``. Every page is validated by
    task_from_page, so one bad row stops the run with a clear error instead
    of producing a half-wrong task list.
    """
    tasks = []
    cursor = None
    while True:
        body = {"filter": OPEN_FILTER, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        answer = http(f"{API}/databases/{database_id}/query", _headers(token), body)
        tasks.extend(task_from_page(page) for page in answer.get("results", []))
        if not answer.get("has_more"):
            return tasks
        cursor = answer["next_cursor"]


def create_task(token, database_id, title, area=None, deadline=None, duration_minutes=None, http=post_json):
    """Create one task page in the Tasks database and return it as a typed Task.

    Only the fields that were given are sent, plus Status = "Not Started" and
    Type = "Task" so the new page is a normal open task. The answer is Notion's
    own copy of the page: mapping it through ``task_from_page`` is the
    read-back — a page Notion reports differently from what was asked raises
    instead of reporting a success that did not happen.
    """
    title = (title or "").strip()
    if not title:
        raise ValueError("a task needs a title")
    properties = {
        "Task Name": {"title": [{"text": {"content": title}}]},
        "Status": {"select": {"name": "Not Started"}},
        "Type": {"select": {"name": "Task"}},
    }
    if area:
        properties["Area"] = {"select": {"name": area}}
    if deadline:
        properties["Due Date"] = {"date": {"start": deadline.isoformat()}}
    if duration_minutes:
        properties["Estimated Time"] = {"number": duration_minutes}
    body = {"parent": {"database_id": database_id}, "properties": properties}
    answer = http(f"{API}/pages", _headers(token), body)
    made = task_from_page(answer)
    if made.title != title:
        raise RuntimeError(f"Notion did not confirm the new task (it says {made.title!r})")
    return made


def mark_done(token, page_id, http=patch_json):
    """Set Status = Done on one task page, and check Notion really did it.

    The only field sent is Status, so nothing else on the page can change.
    Notion answers with the updated page: if its Status is not "Done" we raise
    instead of reporting a success that did not happen (read-back).
    """
    body = {"properties": {"Status": {"select": {"name": "Done"}}}}
    answer = http(f"{API}/pages/{page_id}", _headers(token), body)
    status = _select_name((answer.get("properties") or {}).get("Status") or {})
    if status != "Done":
        raise RuntimeError(f"Notion did not confirm Status = Done (it says {status!r})")
    return True


# --- D2-056: the rest of the picture (projects and goals, life-plan pages) ----

# Projects and goals that are still alive; Done and Missed ones are history.
LIVE_PROJECTS_FILTER = {"and": [
    {"property": "Status", "select": {"does_not_equal": "Done"}},
    {"property": "Status", "select": {"does_not_equal": "Missed"}},
]}


def project_from_page(page):
    """Map one page of the Projects & Goals database to a typed Project.

    A page with a missing or wrong field raises ValueError naming the page.
    """
    props = page.get("properties", {})
    due = (props.get("Due Date") or {}).get("date") or {}
    try:
        return Project(
            id=page["id"],
            name=_plain_text(props["Name"]["title"]),
            type=_select_name(props.get("Type") or {}),
            area=_select_name(props.get("Area") or {}),
            status=_select_name(props.get("Status") or {}),
            due=(due.get("start") or None) and due["start"][:10],
            target=_plain_text((props.get("Target Metric") or {}).get("rich_text")),
            notes=_plain_text((props.get("Notes") or {}).get("rich_text")),
        )
    except (KeyError, ValidationError) as problem:
        raise ValueError(f"Notion page {page.get('id')!r} is not a valid project: {problem}")


def query_projects(token, database_id, http=post_json):
    """Return every live project and goal as typed Project objects (all pages)."""
    projects, cursor = [], None
    while True:
        body = {"filter": LIVE_PROJECTS_FILTER, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        answer = http(f"{API}/databases/{database_id}/query", _headers(token), body)
        projects.extend(project_from_page(page) for page in answer.get("results", []))
        if not answer.get("has_more"):
            return projects
        cursor = answer["next_cursor"]


MAX_PAGE_CHARS = 16000  # a long page is cut, so one read cannot flood the prompt


def block_text(block):
    """The plain text of one block, with a marker for headings and list items.

    Blocks without text (images, dividers, databases) give an empty string.
    """
    kind = block.get("type", "")
    text = _plain_text((block.get(kind) or {}).get("rich_text"))
    if not text:
        return ""
    if kind.startswith("heading_"):
        return "#" * int(kind[-1]) + " " + text
    if kind in ("bulleted_list_item", "numbered_list_item", "to_do"):
        return "- " + text
    return text


# Blocks whose children belong to the same page (a toggle's content, list
# sub-items, columns). A sub-page or a database inside is never opened.
NESTED = {"toggle", "callout", "quote", "column_list", "column", "synced_block",
          "bulleted_list_item", "numbered_list_item", "to_do", "heading_1", "heading_2", "heading_3"}
MAX_DEPTH = 3


def page_text(token, page_id, http=get_json, limit=MAX_PAGE_CHARS):
    """Return the text of a page, at most ``limit`` characters.

    Read-only: only GET requests. Content inside toggles, callouts, columns
    and nested lists is read too (D2-058: the life plan is written in
    toggles), down to MAX_DEPTH levels and indented by level; sub-pages and
    databases are never opened, so one call is one page.
    """
    lines = []

    def full():
        return len("\n".join(lines)) > limit

    def read(block_id, depth):
        cursor = None
        while True:
            url = f"{API}/blocks/{block_id}/children?page_size=100"
            if cursor:
                url += f"&start_cursor={cursor}"
            answer = http(url, _headers(token))
            for block in answer.get("results", []):
                line = block_text(block)
                if line:
                    lines.append("  " * depth + line)
                if full():
                    return
                if block.get("has_children") and block.get("type") in NESTED and depth + 1 < MAX_DEPTH:
                    read(block["id"], depth + 1)
                    if full():
                        return
            if not answer.get("has_more"):
                return
            cursor = answer["next_cursor"]

    read(page_id, 0)
    text = "\n".join(lines)
    if len(text) > limit:
        return text[:limit] + "\n[... page cut here]"
    return text


# --- D2-057: token usage, one row per day, model and kind -----------------------


def _usage_properties(row):
    return {
        "Name": {"title": [{"text": {"content": f"{row.day.isoformat()} {row.kind} {row.model}"}}]},
        "Day": {"date": {"start": row.day.isoformat()}},
        "Model": {"rich_text": [{"text": {"content": row.model}}]},
        "Kind": {"rich_text": [{"text": {"content": row.kind}}]},
        "Input tokens": {"number": row.input_tokens},
        "Output tokens": {"number": row.output_tokens},
        "Calls": {"number": row.calls},
    }


def usage_from_page(page):
    """Map one page of the usage database to (UsageRow, page_id)."""
    from usage import UsageRow  # usage.py does not import Notion; the link goes one way

    props = page.get("properties", {})
    try:
        row = UsageRow(
            day=props["Day"]["date"]["start"][:10],
            model=_plain_text(props["Model"]["rich_text"]),
            kind=_plain_text(props["Kind"]["rich_text"]),
            input_tokens=props["Input tokens"]["number"] or 0,
            output_tokens=props["Output tokens"]["number"] or 0,
            calls=props["Calls"]["number"] or 0,
        )
    except (KeyError, TypeError, ValidationError) as problem:
        raise ValueError(f"Notion page {page.get('id')!r} is not a valid usage row: {problem}")
    return row, page["id"]


def query_usage(token, database_id, since, http=post_json):
    """Every usage row from ``since`` (a date) on, as [(UsageRow, page_id)]."""
    rows, cursor = [], None
    while True:
        body = {"filter": {"property": "Day", "date": {"on_or_after": since.isoformat()}}, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        answer = http(f"{API}/databases/{database_id}/query", _headers(token), body)
        rows.extend(usage_from_page(page) for page in answer.get("results", []))
        if not answer.get("has_more"):
            return rows
        cursor = answer["next_cursor"]


def save_usage(token, database_id, row, page_id=None, create=post_json, update=patch_json):
    """Create the row (page_id None) or overwrite its totals; return the page id.

    Only the usage database is touched: a new page always has it as parent.
    """
    properties = _usage_properties(row)
    if page_id is None:
        page = create(f"{API}/pages", _headers(token),
                      {"parent": {"database_id": database_id}, "properties": properties})
    else:
        page = update(f"{API}/pages/{page_id}", _headers(token), {"properties": properties})
    return page["id"]
