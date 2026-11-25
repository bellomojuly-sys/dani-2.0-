"""Dani's memory store (V1): the REST calls, with a fake HTTP function."""

import io
from datetime import date, datetime
from urllib import error

import pytest

from memory_store import Memory, MemoryStoreError, reaction_summary, send
from models import AMSTERDAM


class FakeHTTP:
    def __init__(self, answers=None):
        self.calls, self.answers = [], list(answers or [])

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, headers, body))
        return self.answers.pop(0) if self.answers else None


def test_every_request_carries_the_key_and_logs_say_which_agent_wrote_them():
    http = FakeHTTP([[{"id": 7}]])
    memory = Memory("https://x.supabase.co/", "KEY", http)
    memory.log_message("telegram", "user", "sono stanca")
    method, url, headers, body = http.calls[0]
    assert (method, url) == ("POST", "https://x.supabase.co/rest/v1/conversations")
    assert headers["apikey"] == "KEY" and headers["Authorization"] == "Bearer KEY"
    assert body == [{"channel": "telegram", "role": "user", "content": "sono stanca", "agent": "dani"}]
    with pytest.raises(ValueError):
        memory.log_message("app", "system", "x")


def test_recent_messages_come_back_oldest_first_as_chat_history():
    http = FakeHTTP([[{"role": "assistant", "content": "b"}, {"role": "user", "content": "a"}]])
    history = Memory("https://x", "K", http).recent_messages("telegram", 2)
    assert history == [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    assert "channel=eq.telegram" in http.calls[0][1] and "order=at.desc" in http.calls[0][1] and "limit=2" in http.calls[0][1]


def test_events_and_reactions():
    http = FakeHTTP([[{"id": 12}], None])
    memory = Memory("https://x", "K", http)
    assert memory.log_event("reminder", "Dentista") == 12
    moment = datetime(2026, 11, 25, 9, 0, tzinfo=AMSTERDAM)
    memory.react(12, "done", moment)
    method, url, _, body = http.calls[1]
    assert (method, url) == ("PATCH", "https://x/rest/v1/events?id=eq.12")
    assert body == {"reaction": "done", "reacted_at": moment.isoformat()}
    with pytest.raises(ValueError, match="unknown reaction"):
        memory.react(12, "meh", moment)


def test_measures_and_kv_upsert_one_row_per_key():
    http = FakeHTTP([None, None, [{"value": "tok"}], []])
    memory = Memory("https://x", "K", http)
    memory.put_measure(date(2026, 11, 25), "sleep_hours", 6.5, "fitbit")
    assert http.calls[0][1].endswith("measures?on_conflict=day,name,source")
    assert http.calls[0][2]["Prefer"] == "resolution=merge-duplicates"
    assert http.calls[0][3] == [{"day": "2026-11-25", "name": "sleep_hours", "value": 6.5, "source": "fitbit"}]
    memory.put("fitbit_refresh_token", "tok")
    assert memory.get("fitbit_refresh_token") == "tok" and memory.get("missing") is None


def test_reaction_summary_counts_by_kind():
    rows = [{"kind": "reminder", "reaction": "done"}, {"kind": "reminder", "reaction": None},
            {"kind": "reminder", "reaction": "done"}, {"kind": "wake_call", "reaction": "awake"}]
    assert reaction_summary(rows) == {"reminder": {"sent": 3, "done": 2, "none": 1}, "wake_call": {"sent": 1, "awake": 1}}


def test_send_turns_http_errors_into_a_clear_error():
    def refuse(req, timeout):
        raise error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b"bad key"))

    with pytest.raises(MemoryStoreError, match="HTTP 401: bad key"):
        send("GET", "https://x/rest/v1/kv", {}, opener=refuse)

    def offline(req, timeout):
        raise error.URLError("down")

    with pytest.raises(MemoryStoreError, match="could not be reached"):
        send("GET", "https://x", {}, opener=offline)
