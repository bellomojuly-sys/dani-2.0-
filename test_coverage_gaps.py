"""Tests for the branches the other test files did not reach (coverage to 100%).

Each test names the behaviour it pins, so a mutant in these lines is caught.
"""

from urllib.parse import parse_qs

import io
import json
import random
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from urllib import error

import pytest

from models import AMSTERDAM, Event, Task


class Answer(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(code, body=b""):
    def opener(req, timeout=None):
        raise error.HTTPError(getattr(req, "full_url", str(req)), code, "x", {}, io.BytesIO(body))
    return opener


def offline(req, timeout=None):
    raise error.URLError("down")


# --- small pure modules -------------------------------------------------------------------

def test_a_week_without_events_says_none():
    from chat import describe_state
    state = {"now": "2026-11-25T08:00:00+01:00", "days": ["2026-11-25", "2026-12-01"], "events": [], "blocks": [], "tasks": []}
    assert "- none" in describe_state(state)


def test_focus_and_mood_without_a_store_refresh_nothing():
    from focus import WeekFocus
    from mood import MoodLog
    WeekFocus().refresh(date(2026, 11, 23))
    MoodLog().refresh(date(2026, 11, 23))


def test_the_forecast_stops_after_the_maximum_number_of_deadlines():
    from forecast import forecast
    now = datetime(2026, 11, 30, 8, tzinfo=AMSTERDAM)
    tasks = [Task(id=str(n), title=f"T{n}", status="Not Started", deadline=date(2026, 12, n + 1), duration_minutes=30)
             for n in range(8)]
    assert len(forecast(tasks, [], now, max_deadlines=3)) == 3


def test_read_page_refuses_unknown_arguments():
    from reader import make_read_page
    assert "unknown arguments" in make_read_page({"a": "1"}, lambda p: "")({"name": "a", "x": 1})["error"]


def test_the_dashboard_greeting_on_sunday():
    from render import _greeting
    assert _greeting(date(2026, 11, 29), [], [], {"blocks": []}).count("Domenica") == 1


def test_an_answer_before_any_question_gets_a_question():
    from wake_call import Morning
    morning = Morning(date(2026, 11, 25), random.Random(1))
    result, question = morning.answer("1", None)
    assert result == "again" and question["text"].startswith("Quanto fa")


def test_ticking_a_fresh_task_drops_it_from_a_verified_priority():
    from live import Live
    task = Task(id="t1", title="A", status="Not Started")
    other = Task(id="t2", title="B", status="Not Started")
    outcome = {"ok": True, "reason": "", "priority": [{"id": "t1"}, {"id": "t2"}]}
    live = Live(lambda: [task, other], lambda s, e: [], lambda t, d, c: outcome,
                clock=lambda: datetime(2026, 11, 25, 9, tzinfo=AMSTERDAM))
    live.refresh("notion")
    live.update_priority("")
    live.drop_task("t1")
    assert [row["id"] for row in live.outcome["priority"]] == ["t2"]


def test_settings_can_be_written_to_a_file_in_the_current_folder(tmp_path, monkeypatch):
    from store import UserSettings, read_settings, write_settings
    monkeypatch.chdir(tmp_path)
    write_settings(UserSettings(context="x"), "settings.json")
    assert read_settings("settings.json").context == "x"


def test_a_usage_total_changed_while_saving_stays_dirty():
    from types import SimpleNamespace

    from usage import UsageLog
    log = UsageLog(lambda: date(2026, 11, 25))
    log.record("m", "chat", SimpleNamespace(prompt_tokens=1, completion_tokens=1))

    def save(row, page_id):
        log.record("m", "chat", SimpleNamespace(prompt_tokens=1, completion_tokens=1))  # a new call during the save
        return "p"

    assert log.flush(save) == 1 and log.dirty  # saved, but the newer total is still to write


def test_calendar_addresses_are_fetched_and_errors_are_clear():
    from ical_client import _to_amsterdam, fetch_bytes
    assert fetch_bytes("webcal://x/cal.ics", opener=lambda url, timeout: Answer(b"BEGIN")) == b"BEGIN"
    with pytest.raises(RuntimeError, match="HTTP 404"):
        fetch_bytes("https://x", opener=http_error(404))
    with pytest.raises(RuntimeError, match="could not be reached"):
        fetch_bytes("https://x", opener=offline)
    assert _to_amsterdam(datetime(2026, 11, 25, 9)).tzinfo == AMSTERDAM


# --- Twilio and Telegram clients --------------------------------------------------------

def test_twilio_start_call_posts_the_call_and_returns_its_sid():
    from twilio_client import start_call
    seen = {}

    def opener(req, timeout):
        seen.update(url=req.full_url, data=req.data.decode(), auth=req.get_header("Authorization"))
        return Answer(b'{"sid": "CA123"}')

    assert start_call("AC1", "TOKEN", "+3110", "+3161", "https://dani/voice", opener) == "CA123"
    assert seen["url"].endswith("/Accounts/AC1/Calls.json") and "To=%2B3161" in seen["data"]
    assert seen["auth"].startswith("Basic ") and "TOKEN" not in seen["auth"]
    # A trial account accepts only the basic parameters (HTTP 400 otherwise).
    assert sorted(parse_qs(seen["data"])) == ["From", "To", "Url"]


def test_twilio_errors_are_clear_and_never_show_the_token():
    from twilio_client import start_call
    with pytest.raises(RuntimeError) as caught:
        start_call("AC1", "TOKEN", "+1", "+2", "u", http_error(401, b'{"message": "Authenticate"}'))
    assert "401 Authenticate" in str(caught.value) and "TOKEN" not in str(caught.value)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        start_call("AC1", "T", "+1", "+2", "u", http_error(500, b"not json"))
    with pytest.raises(RuntimeError, match="could not be reached"):
        start_call("AC1", "T", "+1", "+2", "u", offline)


def test_telegram_buttons_voice_and_webhook():
    from telegram_client import answer_button, download_voice, set_webhook
    seen = []

    def opener(req, timeout):
        seen.append((req.full_url, req.data))
        if "/file/bot" in req.full_url:
            return Answer(b"OGG")
        if req.full_url.endswith("getFile"):
            return Answer(b'{"ok": true, "result": {"file_path": "voice/1.oga"}}')
        return Answer(b'{"ok": true, "result": true}')

    assert answer_button("T", "q1", "ok", opener) is True
    assert download_voice("T", "f1", opener) == b"OGG"
    assert seen[-1][0].endswith("/file/botT/voice/1.oga")
    set_webhook("T", "https://dani/telegram/s", "s", opener)
    assert json.loads(seen[-1][1])["secret_token"] == "s"


def test_telegram_errors_without_a_json_body_and_a_failed_download():
    from telegram_client import call, download_voice
    with pytest.raises(RuntimeError, match="HTTP 502"):
        call("T", "getMe", opener=http_error(502, b"<html>"))
    with pytest.raises(RuntimeError, match="could not be reached"):
        call("T", "getMe", opener=offline)

    def file_missing(req, timeout):
        if "/file/bot" in req.full_url:
            raise error.HTTPError(req.full_url, 404, "x", {}, io.BytesIO(b""))
        return Answer(b'{"ok": true, "result": {"file_path": "v.oga"}}')

    with pytest.raises(RuntimeError, match="could not be downloaded"):
        download_voice("T", "f", file_missing)


# --- Fitbit, mail and memory error paths ------------------------------------------------

def test_fitbit_token_and_api_errors():
    from fitbit_client import day_summary, exchange_code
    with pytest.raises(RuntimeError, match="without tokens"):
        exchange_code("C", "S", "code", "u", lambda req, timeout: Answer(b'{"errors": []}'))
    with pytest.raises(RuntimeError, match="could not be reached"):
        exchange_code("C", "S", "code", "u", offline)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        day_summary("AT", date(2026, 11, 25), http_error(429))
    with pytest.raises(RuntimeError, match="could not be reached"):
        day_summary("AT", date(2026, 11, 25), offline)


def test_a_night_without_data_gives_none_not_a_guess():
    from fitbit_client import day_summary
    empty = lambda req, timeout: Answer(b"{}")
    assert day_summary("AT", date(2026, 11, 25), empty) == {
        "sleep_hours": None, "sleep_efficiency": None, "steps": None, "resting_hr": None}


def _message(body=None, html=None, charset="utf-8", subject="Ciao"):
    message = EmailMessage()
    message["From"], message["Subject"] = "A <a@x.it>", subject
    if body is not None:
        message.set_content(body, charset=charset)
    if html is not None:
        message.add_alternative(html, subtype="html") if body is not None else message.set_content(html, subtype="html")
    return message.as_bytes()


def test_mail_parsing_edge_cases():
    from mail_client import parse_message
    assert parse_message(_message(html="<p>solo html</p>"))["snippet"] == ""
    no_date = parse_message(_message(body="x"))
    assert no_date["date"] is None
    raw = _message(body="ciao").replace(b"charset=\"utf-8\"", b"charset=\"x-unknown\"")
    assert parse_message(raw)["snippet"] == "ciao"
    broken = b"From: =?x-unknown?q?abc?=\r\nSubject: s\r\nDate: not a date\r\n\r\nbody"
    item = parse_message(broken)
    assert item["date"] is None and item["subject"] == "s"


def test_mail_search_failure_and_skipped_fetches():
    from mail_client import read_recent

    class Box:
        def __init__(self, search_status="OK"):
            self.search_status = search_status

        def login(self, *a):
            pass

        def select(self, *a, **k):
            return "OK", []

        def search(self, *a):
            return self.search_status, [b"1 2"]

        def fetch(self, message_id, parts):
            return ("NO", []) if message_id == b"2" else ("OK", [(b"x", _message(body="hi"))])

        def logout(self):
            raise OSError("already closed")

    since = datetime(2026, 11, 24, tzinfo=timezone.utc)
    with pytest.raises(RuntimeError, match="search failed"):
        read_recent("me", "pw", since, imap=lambda host: Box("NO"))
    assert [m["subject"] for m in read_recent("me", "pw", since, imap=lambda host: Box())] == ["Ciao"]


def test_memory_send_handles_get_without_body_and_empty_answers():
    from memory_store import Memory, send
    seen = {}

    def opener(req, timeout):
        seen.update(method=req.get_method(), data=req.data)
        return Answer(b"")

    assert send("GET", "https://x", {}, opener=opener) is None and seen == {"method": "GET", "data": None}
    assert Memory("https://x", "k", lambda *a: None).log_message("app", "user", "x") is None
    assert Memory("https://x", "k", lambda *a: None).log_event("reminder") is None


# --- last branches --------------------------------------------------------------------------

def test_memory_reads_measures_and_reactions_with_a_date_filter():
    from memory_store import Memory
    calls = []
    memory = Memory("https://x", "k", lambda method, url, headers, body=None: calls.append(url) or [])
    assert memory.measures(date(2026, 11, 1)) == [] and "day=gte.2026-11-01" in calls[-1]
    assert memory.reactions(datetime(2026, 11, 1, tzinfo=AMSTERDAM)) == [] and calls[-1].startswith("https://x/rest/v1/events?")


def test_a_free_slot_entirely_in_the_past_counts_nothing():
    from forecast import free_minutes
    late = datetime(2026, 11, 30, 21, 0, tzinfo=AMSTERDAM)  # after the 20:00 window end
    assert free_minutes(late.date(), [], late) == 0


def test_dropping_a_task_when_the_priority_was_not_verified_keeps_the_rule_order():
    from live import Live
    a = Task(id="a", title="A", status="Not Started")
    live = Live(lambda: [a], lambda s, e: [], lambda t, d, c: {"ok": False, "reason": "x", "priority": None},
                clock=lambda: datetime(2026, 11, 25, tzinfo=AMSTERDAM))
    live.refresh("notion")
    live.update_priority("")
    live.drop_task("a")
    assert live.outcome["ok"] is False and live.tasks == []


def test_a_telegram_message_without_buttons_has_no_keyboard():
    from telegram_client import send_message
    seen = {}

    def opener(req, timeout):
        seen.update(json.loads(req.data))
        return Answer(b'{"ok": true, "result": {}}')

    send_message("T", "1", "ciao", opener=opener)
    assert "reply_markup" not in seen and seen["disable_notification"] is False


def test_notion_post_and_pagination_of_projects_usage_focus_and_mood():
    from notion_client import post_json, query_focus, query_mood, query_projects, query_usage, save_focus
    assert post_json("https://x", {}, {}, opener=lambda req, timeout: Answer(b'{"ok": 1}')) == {"ok": 1}
    pages = {"projects": {"id": "p", "properties": {"Name": {"title": [{"plain_text": "Betsy"}]}}},
             "usage": {"id": "u", "properties": {"Day": {"date": {"start": "2026-11-25"}}, "Model": {"rich_text": [{"plain_text": "m"}]},
                                                 "Kind": {"rich_text": [{"plain_text": "chat"}]}, "Input tokens": {"number": 1},
                                                 "Output tokens": {"number": 1}, "Calls": {"number": 1}}},
             "focus": {"id": "f", "properties": {"Week": {"date": {"start": "2026-11-23"}}, "Focus": {"rich_text": []}}},
             "mood": {"id": "m", "properties": {"Day": {"date": {"start": "2026-11-25"}}, "Energy": {"number": 3},
                                                "Sleep": {"number": None}, "Note": {"rich_text": []}}}}

    def paged(kind):
        bodies = []

        def http(url, headers, body):
            bodies.append(body)
            first = "start_cursor" not in body
            return {"results": [pages[kind]], "has_more": first, "next_cursor": "c2"}
        return http, bodies

    for kind, query in (("projects", lambda h: query_projects("t", "db", http=h)),
                        ("usage", lambda h: query_usage("t", "db", date(2026, 11, 1), http=h)),
                        ("focus", lambda h: query_focus("t", "db", date(2026, 11, 1), http=h)),
                        ("mood", lambda h: query_mood("t", "db", date(2026, 11, 1), http=h))):
        http, bodies = paged(kind)
        result = query(http)
        assert len(result) >= 1 and bodies[1]["start_cursor"] == "c2", kind
    updated = []
    save_focus("t", "db", date(2026, 11, 23), "x", "f1", create=None,
               update=lambda url, h, body: updated.append(url) or {"id": "f1"})
    assert updated[0].endswith("/pages/f1")


def test_page_text_stops_inside_a_long_toggle():
    from notion_client import page_text
    long = {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "x" * 50}]}}
    tree = {"p": [{"type": "toggle", "toggle": {"rich_text": [{"plain_text": "T"}]}, "id": "t", "has_children": True},
                  long], "t": [long, long]}
    text = page_text("tok", "p", http=lambda url, headers: {"results": tree[url.split("/blocks/")[1].split("/")[0]],
                                                              "has_more": False}, limit=60)
    assert text.endswith("[... page cut here]")


def test_a_mood_row_is_updated_in_place_and_a_row_without_a_day_is_skipped():
    from mood import Mood
    from notion_client import query_mood, save_mood
    updated = []
    save_mood("t", "db", date(2026, 11, 25), Mood(energy=2), "m1", create=None,
              update=lambda url, h, body: updated.append((url, body)) or {"id": "m1"})
    assert updated[0][0].endswith("/pages/m1") and updated[0][1]["properties"]["Note"] == {"rich_text": []}
    rows = {"results": [{"id": "x", "properties": {"Day": {"date": None}, "Energy": {"number": 3},
                                                   "Sleep": {"number": None}, "Note": {"rich_text": []}}}]}
    assert query_mood("t", "db", date(2026, 11, 1), http=lambda url, h, body: rows) == {}
