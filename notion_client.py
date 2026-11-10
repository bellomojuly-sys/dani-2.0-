"""Read Giulia's open tasks from her Notion Tasks database.

Plain HTTPS + JSON with the standard library (urllib), no Notion SDK: one
visible request we can read and explain (Decision Log 2026-11-05). The token
comes from the environment and travels only in the Authorization header; it is
never part of a URL or of an error message.

Two layers, so each can be tested on its own:
  - ``task_from_page``    turns one Notion page (a dict) into a typed Task;
  - ``query_open_tasks``  calls the API (through an injectable ``http``
                          function) and maps every page it returns.
"""

import json
from urllib import error, request

from pydantic import ValidationError

from models import Task

API = "https://api.notion.com/v1"
# Pinned on purpose: a new Notion API version cannot silently change the shape
# of the pages we read.
VERSION = "2022-06-28"

# Everything that is not Done is open. A "Done" filter in the query means we
# never download finished tasks only to drop them here.
OPEN_FILTER = {"property": "Status", "select": {"does_not_equal": "Done"}}


def post_json(url, headers, body, opener=request.urlopen, timeout=20):
    """POST a JSON body and return the decoded JSON answer.

    A failed request raises RuntimeError with the status code and the start of
    the body. The headers (where the token lives) are never in the message.
    ``opener`` is injectable so tests never touch the network.
    """
    data = json.dumps(body).encode()
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with opener(req, timeout=timeout) as response:
            return json.loads(response.read())
    except error.HTTPError as failure:
        detail = failure.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Notion answered HTTP {failure.code}: {detail}") from None


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
