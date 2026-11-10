"""Notion is read offline here: a saved query answer stands in for the API.

No test calls the network. The fixture has the shape of a Notion
/databases/{id}/query answer with the real property names of the Tasks DB.
"""

import json
from datetime import date

import pytest

from notion_client import OPEN_FILTER, VERSION, query_open_tasks, task_from_page

with open("fixtures/notion_query.json") as handle:
    FIXTURE = json.load(handle)


def test_fixture_pages_become_three_typed_tasks():
    tasks = query_open_tasks("tok", "db", http=lambda url, headers, body: FIXTURE)
    assert [task.title for task in tasks] == [
        "Finish the Notion client",
        "Write the feedback brief",
        "Book the dentist",
    ]


def test_task_from_page_maps_every_planning_field():
    task = task_from_page(FIXTURE["results"][0])
    assert task.id == "11111111-1111-1111-1111-111111111111"
    assert task.area == "University"
    assert task.status == "In Progress"
    assert task.deadline == date(2026, 11, 12)
    assert task.duration_minutes == 90
    assert task.priority == "P1 - Critical"
    assert task.next_action is True


def test_empty_optional_properties_become_none():
    task = task_from_page(FIXTURE["results"][1])
    assert task.deadline is None and task.duration_minutes is None


def test_a_datetime_deadline_is_cut_to_its_date():
    assert task_from_page(FIXTURE["results"][2]).deadline == date(2026, 11, 20)


def test_a_page_without_status_is_refused_with_its_id():
    page = json.loads(json.dumps(FIXTURE["results"][0]))
    page["properties"]["Status"]["select"] = None
    with pytest.raises(ValueError, match="11111111-1111-1111-1111-111111111111"):
        task_from_page(page)


def test_a_page_without_the_title_property_is_refused():
    page = json.loads(json.dumps(FIXTURE["results"][0]))
    del page["properties"]["Task Name"]
    with pytest.raises(ValueError, match="not a valid task"):
        task_from_page(page)


def test_query_sends_token_version_and_open_filter():
    seen = {}

    def fake_http(url, headers, body):
        seen.update(url=url, headers=headers, body=body)
        return {"results": [], "has_more": False}

    query_open_tasks("secret-token", "db-123", http=fake_http)
    assert seen["url"].endswith("/databases/db-123/query")
    assert seen["headers"]["Authorization"] == "Bearer secret-token"
    assert seen["headers"]["Notion-Version"] == VERSION
    assert seen["body"]["filter"] == OPEN_FILTER


def test_query_follows_the_cursor_until_has_more_is_false():
    page_one = {"results": FIXTURE["results"][:2], "has_more": True, "next_cursor": "c2"}
    page_two = {"results": FIXTURE["results"][2:], "has_more": False, "next_cursor": None}
    answers = [page_one, page_two]
    cursors = []

    def fake_http(url, headers, body):
        cursors.append(body.get("start_cursor"))
        return answers.pop(0)

    tasks = query_open_tasks("tok", "db", http=fake_http)
    assert len(tasks) == 3
    assert cursors == [None, "c2"]


def test_one_bad_page_stops_the_whole_query():
    broken = json.loads(json.dumps(FIXTURE))
    broken["results"][1]["properties"]["Task Name"]["title"] = []
    with pytest.raises(ValueError):
        query_open_tasks("tok", "db", http=lambda url, headers, body: broken)


# --- the one write: mark_done ---------------------------------------------------

def test_mark_done_patches_only_the_status_of_that_page():
    from notion_client import mark_done

    seen = {}

    def http(url, headers, body):
        seen.update(url=url, headers=headers, body=body)
        return {"properties": {"Status": {"select": {"name": "Done"}}}}

    assert mark_done("tok", "page-1", http=http) is True
    assert seen["url"] == "https://api.notion.com/v1/pages/page-1"
    assert seen["body"] == {"properties": {"Status": {"select": {"name": "Done"}}}}
    assert seen["headers"]["Authorization"] == "Bearer tok"


def test_mark_done_refuses_an_answer_that_is_not_done():
    from notion_client import mark_done

    with pytest.raises(RuntimeError, match="did not confirm Status = Done"):
        mark_done("tok", "page-1", http=lambda url, headers, body: {"properties": {"Status": {"select": {"name": "In Progress"}}}})
    with pytest.raises(RuntimeError, match="did not confirm"):
        mark_done("tok", "page-1", http=lambda url, headers, body: {})


def test_patch_json_uses_the_patch_method_and_hides_the_token_on_failure():
    import io
    from urllib import error

    from notion_client import patch_json

    methods = []

    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def opener(req, timeout):
        methods.append(req.get_method())
        return Answer(b'{"ok": true}')

    assert patch_json("https://x", {"Authorization": "Bearer secret"}, {}, opener=opener) == {"ok": True}
    assert methods == ["PATCH"]

    def failing(req, timeout):
        raise error.HTTPError("https://x", 403, "Forbidden", {}, io.BytesIO(b"no update capability"))

    with pytest.raises(RuntimeError) as caught:
        patch_json("https://x", {"Authorization": "Bearer secret"}, {}, opener=failing)
    assert "403" in str(caught.value) and "secret" not in str(caught.value)

    def unreachable(req, timeout):
        raise error.URLError("no route")

    with pytest.raises(RuntimeError, match="could not be reached"):
        patch_json("https://x", {}, {}, opener=unreachable)
