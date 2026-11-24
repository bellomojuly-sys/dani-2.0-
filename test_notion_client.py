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


# --- the other write: create_task (D2-055) ---------------------------------------

def _created_page(title="comprare le lenti"):
    """The page Notion answers with after a create (the read-back source)."""
    return {
        "id": "page-new",
        "properties": {
            "Task Name": {"title": [{"plain_text": title}]},
            "Status": {"select": {"name": "Not Started"}},
            "Area": {"select": {"name": "Personal"}},
            "Due Date": {"date": {"start": "2026-11-20"}},
            "Estimated Time": {"number": 30},
            "Priority": {"select": None},
            "Next Action": {"checkbox": False},
        },
    }


def test_create_task_sends_the_given_fields_and_returns_the_typed_read_back():
    from notion_client import create_task

    seen = {}

    def http(url, headers, body):
        seen.update(url=url, headers=headers, body=body)
        return _created_page()

    made = create_task("tok", "db-1", "comprare le lenti", area="Personal",
                       deadline=date(2026, 11, 20), duration_minutes=30, http=http)
    assert seen["url"] == "https://api.notion.com/v1/pages"
    assert seen["body"]["parent"] == {"database_id": "db-1"}
    assert seen["body"]["properties"]["Task Name"] == {"title": [{"text": {"content": "comprare le lenti"}}]}
    assert seen["body"]["properties"]["Status"] == {"select": {"name": "Not Started"}}
    assert seen["body"]["properties"]["Due Date"] == {"date": {"start": "2026-11-20"}}
    assert seen["headers"]["Authorization"] == "Bearer tok"
    assert made.id == "page-new" and made.title == "comprare le lenti" and made.deadline == date(2026, 11, 20)


def test_create_task_without_extras_sends_no_empty_properties():
    from notion_client import create_task

    seen = {}

    def http(url, headers, body):
        seen.update(body=body)
        page = _created_page("solo titolo")
        for name in ("Area", "Due Date", "Estimated Time"):
            del page["properties"][name]
        return page

    made = create_task("tok", "db-1", "solo titolo", http=http)
    assert set(seen["body"]["properties"]) == {"Task Name", "Status", "Type"}
    assert made.area is None and made.deadline is None


def test_create_task_refuses_an_empty_title_without_calling_notion():
    from notion_client import create_task

    with pytest.raises(ValueError, match="needs a title"):
        create_task("tok", "db-1", "   ", http=lambda url, headers, body: pytest.fail("must not call Notion"))


def test_create_task_refuses_an_answer_with_another_title():
    from notion_client import create_task

    with pytest.raises(RuntimeError, match="did not confirm the new task"):
        create_task("tok", "db-1", "comprare le lenti",
                    http=lambda url, headers, body: _created_page("altro titolo"))


# --- D2-056: projects, goals and page text ---------------------------------------

from notion_client import LIVE_PROJECTS_FILTER, block_text, page_text, project_from_page, query_projects  # noqa: E402


def _project_page(name="Betsy", **extra):
    props = {"Name": {"title": [{"plain_text": name}]}, "Type": {"select": {"name": "Project"}},
             "Area": {"select": {"name": "University"}}, "Status": {"select": {"name": "Active"}},
             "Due Date": {"date": {"start": "2027-01-20"}},
             "Target Metric": {"rich_text": [{"plain_text": "demo"}]}, "Notes": {"rich_text": []}}
    props.update(extra)
    return {"id": "p1", "properties": props}


def test_project_from_page_maps_the_real_property_names():
    project = project_from_page(_project_page())
    assert (project.name, project.type, project.area, project.status) == ("Betsy", "Project", "University", "Active")
    assert project.due.isoformat() == "2027-01-20" and project.target == "demo" and project.notes == ""


def test_a_project_without_name_or_with_an_unknown_type_is_refused():
    with pytest.raises(ValueError, match="not a valid project"):
        project_from_page({"id": "p1", "properties": {}})
    with pytest.raises(ValueError, match="not a valid project"):
        project_from_page(_project_page(Type={"select": {"name": "Wish"}}))


def test_query_projects_filters_out_done_and_missed_and_follows_pages():
    sent = []

    def http(url, headers, body):
        sent.append((url, body))
        if "start_cursor" not in body:
            return {"results": [_project_page("A")], "has_more": True, "next_cursor": "c2"}
        return {"results": [_project_page("B")], "has_more": False}

    projects = query_projects("tok", "db", http=http)
    assert [p.name for p in projects] == ["A", "B"]
    assert sent[0][0].endswith("/databases/db/query") and sent[0][1]["filter"] == LIVE_PROJECTS_FILTER
    assert sent[1][1]["start_cursor"] == "c2"


def test_block_text_marks_headings_and_lists_and_skips_empty_blocks():
    def block(kind, text):
        return {"type": kind, kind: {"rich_text": [{"plain_text": text}]}}
    assert block_text(block("heading_2", "Obiettivi")) == "## Obiettivi"
    assert block_text(block("bulleted_list_item", "lavoro")) == "- lavoro"
    assert block_text(block("paragraph", "testo")) == "testo"
    assert block_text({"type": "divider", "divider": {}}) == ""


def test_page_text_only_gets_and_cuts_a_long_page():
    asked = []

    def http(url, headers):
        asked.append(url)
        if "start_cursor" not in url:
            return {"results": [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "a" * 30}]}}],
                    "has_more": True, "next_cursor": "n2"}
        return {"results": [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "b"}]}}],
                "has_more": False}

    assert page_text("tok", "pg", http=http) == "a" * 30 + "\nb"
    assert asked[0].endswith("/blocks/pg/children?page_size=100") and asked[1].endswith("&start_cursor=n2")
    assert page_text("tok", "pg", http=http, limit=10) == "a" * 10 + "\n[... page cut here]"


def test_get_json_sends_a_get_without_a_body():
    from notion_client import get_json
    seen = {}

    class Answer:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"results": []}'

    def opener(req, timeout):
        seen["method"], seen["data"] = req.get_method(), req.data
        return Answer()

    assert get_json("https://x", {}, opener=opener) == {"results": []}
    assert seen == {"method": "GET", "data": None}


# --- D2-057: token usage rows -----------------------------------------------------

from notion_client import query_usage, save_usage, usage_from_page  # noqa: E402
from usage import UsageRow  # noqa: E402

ROW = UsageRow(day=date(2026, 11, 23), model="deepseek-flash", kind="chat", input_tokens=120, output_tokens=30, calls=2)


def test_save_usage_creates_in_the_usage_database_then_updates_by_page():
    created, updated = [], []
    new_id = save_usage("tok", "usage-db", ROW, None,
                        create=lambda url, h, body: created.append((url, body)) or {"id": "p1"},
                        update=lambda url, h, body: updated.append(url) or {"id": "x"})
    assert new_id == "p1" and updated == []
    url, body = created[0]
    assert url.endswith("/pages") and body["parent"] == {"database_id": "usage-db"}
    assert body["properties"]["Input tokens"] == {"number": 120}
    assert body["properties"]["Day"] == {"date": {"start": "2026-11-23"}}
    save_usage("tok", "usage-db", ROW, "p1", create=None,
               update=lambda url, h, body: updated.append((url, body)) or {"id": "p1"})
    assert updated[0][0].endswith("/pages/p1") and "parent" not in updated[0][1]


def test_a_saved_row_reads_back_the_same():
    from notion_client import _usage_properties
    page = {"id": "p1", "properties": _usage_properties(ROW)}
    for name in ("Model", "Kind"):
        page["properties"][name]["rich_text"][0]["plain_text"] = page["properties"][name]["rich_text"][0]["text"]["content"]
    assert usage_from_page(page) == (ROW, "p1")


def test_a_broken_usage_row_is_refused_and_query_filters_by_day():
    with pytest.raises(ValueError, match="not a valid usage row"):
        usage_from_page({"id": "p", "properties": {"Day": {"date": None}}})
    sent = []
    assert query_usage("tok", "db", date(2026, 10, 24),
                       http=lambda url, h, body: sent.append(body) or {"results": []}) == []
    assert sent[0]["filter"] == {"property": "Day", "date": {"on_or_after": "2026-10-24"}}


def test_page_text_opens_toggles_and_nested_lists_but_not_sub_pages():
    def para(text, kind="paragraph", **extra):
        return {"type": kind, kind: {"rich_text": [{"plain_text": text}]}, **extra}

    tree = {
        "page": [para("FASE 1", "toggle", id="t1", has_children=True),
                 {"type": "child_page", "child_page": {"title": "secret"}, "id": "sub", "has_children": True}],
        "t1": [para("21 anni", "heading_3", id="h"), para("risparmio 600", "bulleted_list_item", id="b", has_children=True)],
        "b": [para("fondo 1000", "bulleted_list_item", id="deep", has_children=True)],
        "deep": [para("too deep")],
        "sub": [para("never read")],
    }
    asked = []

    def http(url, headers):
        block_id = url.split("/blocks/")[1].split("/")[0]
        asked.append(block_id)
        return {"results": tree[block_id], "has_more": False}

    text = page_text("tok", "page", http=http)
    assert text.splitlines() == ["FASE 1", "  ### 21 anni", "  - risparmio 600", "    - fondo 1000"]
    assert "sub" not in asked and "deep" not in asked  # sub-pages and a 4th level are never opened


# --- D2-060: week focus rows ------------------------------------------------------

from notion_client import query_focus, save_focus  # noqa: E402


def test_save_focus_creates_then_updates_and_query_reads_it_back():
    created = []
    page_id = save_focus("tok", "focus-db", date(2026, 11, 30), "Betsy", None,
                         create=lambda url, h, body: created.append(body) or {"id": "f1"}, update=None)
    assert page_id == "f1" and created[0]["parent"] == {"database_id": "focus-db"}
    assert created[0]["properties"]["Week"] == {"date": {"start": "2026-11-30"}}
    updated = []
    save_focus("tok", "focus-db", date(2026, 11, 30), "Betsy e CV", "f1", create=None,
               update=lambda url, h, body: updated.append(url) or {"id": "f1"})
    assert updated[0].endswith("/pages/f1")
    rows = {"results": [
        {"id": "f1", "properties": {"Week": {"date": {"start": "2026-11-30"}},
                                    "Focus": {"rich_text": [{"plain_text": "Betsy e CV"}]}}},
        {"id": "f2", "properties": {"Week": {"date": None}, "Focus": {"rich_text": []}}}]}
    assert query_focus("tok", "db", date(2026, 11, 16), http=lambda url, h, body: rows) == {
        date(2026, 11, 30): ("Betsy e CV", "f1")}  # a row without a week is ignored


def test_mood_rows_save_and_read_back_and_a_hand_broken_row_is_skipped():
    from mood import Mood
    from notion_client import query_mood, save_mood

    created = []
    save_mood("tok", "diary", date(2026, 11, 24), Mood(energy=3, sleep=6.5, note="ok"), None,
              create=lambda url, h, body: created.append(body) or {"id": "m1"}, update=None)
    props = created[0]["properties"]
    assert props["Energy"] == {"number": 3} and props["Sleep"] == {"number": 6.5}
    rows = {"results": [
        {"id": "m1", "properties": {"Day": {"date": {"start": "2026-11-24"}}, "Energy": {"number": 3},
                                    "Sleep": {"number": 6.5}, "Note": {"rich_text": [{"plain_text": "ok"}]}}},
        {"id": "m2", "properties": {"Day": {"date": {"start": "2026-11-23"}}, "Energy": {"number": 11},
                                    "Sleep": {"number": None}, "Note": {"rich_text": []}}}]}
    read = query_mood("tok", "db", date(2026, 11, 10), http=lambda url, h, body: rows)
    assert list(read) == [date(2026, 11, 24)] and read[date(2026, 11, 24)][0].note == "ok"
