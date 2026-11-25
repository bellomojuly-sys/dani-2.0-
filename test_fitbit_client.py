"""Fitbit (V1): the authorization link, the rotating token, last night's sleep."""

import io
import json
from datetime import date
from urllib import error
from urllib.parse import parse_qs, urlparse

import pytest

from fitbit_client import TOKEN_KEY, Fitbit, authorize_url, day_summary


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Store(dict):
    def put(self, key, value):
        self[key] = value


SLEEP = {"sleep": [{"isMainSleep": True, "efficiency": 91}], "summary": {"totalMinutesAsleep": 390}}
ACTIVITY = {"summary": {"steps": 8123, "restingHeartRate": 58}}


def fake_api(seen):
    def opener(req, timeout):
        seen.append((req.full_url, req.data, dict(req.header_items())))
        if req.full_url.endswith("/oauth2/token"):
            return Answer(json.dumps({"access_token": "AT", "refresh_token": f"RT{len(seen)}"}).encode())
        return Answer(json.dumps(SLEEP if "/sleep/" in req.full_url else ACTIVITY).encode())
    return opener


def test_the_link_asks_only_read_scopes():
    query = parse_qs(urlparse(authorize_url("CID", "https://dani/fitbit/callback", "st")).query)
    assert query["scope"] == ["sleep activity heartrate"] and query["state"] == ["st"] and query["client_id"] == ["CID"]


def test_a_day_summary_reads_sleep_and_activity():
    seen = []
    assert day_summary("AT", date(2026, 11, 25), fake_api(seen)) == {
        "sleep_hours": 6.5, "sleep_efficiency": 91, "steps": 8123, "resting_hr": 58}
    assert seen[0][0].endswith("/1.2/user/-/sleep/date/2026-11-25.json")
    assert seen[0][2]["Authorization"] == "Bearer AT"


def test_connect_then_every_read_saves_the_new_rotated_token():
    seen, store = [], Store()
    fitbit = Fitbit("CID", "SECRET", store, fake_api(seen))
    assert not fitbit.connected()
    with pytest.raises(RuntimeError, match="not connected"):
        fitbit.read_day(date(2026, 11, 25))
    fitbit.connect("CODE", "https://dani/fitbit/callback")
    first = store[TOKEN_KEY]
    fitbit.read_day(date(2026, 11, 25))
    assert store[TOKEN_KEY] != first  # rotated and saved
    assert seen[0][2]["Authorization"].startswith("Basic ")


def test_a_refused_token_never_shows_the_secret():
    def refuse(req, timeout):
        raise error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b""))

    store = Store({TOKEN_KEY: "old"})
    with pytest.raises(RuntimeError) as caught:
        Fitbit("CID", "SECRET", store, refuse).read_day(date(2026, 11, 25))
    assert "401" in str(caught.value) and "SECRET" not in str(caught.value) and "old" not in str(caught.value)
