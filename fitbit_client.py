"""Dani reads Giulia's Fitbit (M16, V1): last night's sleep and yesterday's activity.

The Fitbit Web API with OAuth 2.0 (authorization code), read-only scopes
"sleep activity heartrate". She registers a "Personal" app on dev.fitbit.com
once and presses "Consenti" once; Dani keeps the refresh token in its memory
store (Fitbit rotates it at every refresh, so the new one is saved each time).
Standard library only. Errors never repeat the tokens.
"""

import base64
import json
from urllib import error, parse, request

AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
TOKEN_URL = "https://api.fitbit.com/oauth2/token"
API = "https://api.fitbit.com"
SCOPES = "sleep activity heartrate"
TOKEN_KEY = "fitbit_refresh_token"


def authorize_url(client_id, redirect_uri, state):
    return AUTH_URL + "?" + parse.urlencode({"response_type": "code", "client_id": client_id, "scope": SCOPES,
                                             "redirect_uri": redirect_uri, "state": state})


def _post_token(client_id, client_secret, form, opener):
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = request.Request(TOKEN_URL, data=parse.urlencode(form).encode(), method="POST",
                          headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener(req, timeout=20) as response:
            answer = json.loads(response.read())
    except error.HTTPError as failure:
        raise RuntimeError(f"Fitbit refused the token request (HTTP {failure.code})") from None
    except error.URLError as failure:
        raise RuntimeError(f"Fitbit could not be reached: {failure.reason}") from None
    if "access_token" not in answer or "refresh_token" not in answer:
        raise RuntimeError("Fitbit answered without tokens")
    return answer


def exchange_code(client_id, client_secret, code, redirect_uri, opener=request.urlopen):
    return _post_token(client_id, client_secret, {"grant_type": "authorization_code", "code": code,
                                                  "redirect_uri": redirect_uri, "client_id": client_id}, opener)


def refresh(client_id, client_secret, refresh_token, opener=request.urlopen):
    return _post_token(client_id, client_secret, {"grant_type": "refresh_token", "refresh_token": refresh_token}, opener)


def _get(access_token, path, opener):
    req = request.Request(API + path, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with opener(req, timeout=20) as response:
            return json.loads(response.read())
    except error.HTTPError as failure:
        raise RuntimeError(f"Fitbit answered HTTP {failure.code}") from None
    except error.URLError as failure:
        raise RuntimeError(f"Fitbit could not be reached: {failure.reason}") from None


def day_summary(access_token, day, opener=request.urlopen):
    """Sleep of the night ending on ``day`` and activity of ``day``; None for what is missing."""
    sleep = _get(access_token, f"/1.2/user/-/sleep/date/{day.isoformat()}.json", opener)
    activity = _get(access_token, f"/1/user/-/activities/date/{day.isoformat()}.json", opener)
    main = [s for s in sleep.get("sleep", []) if s.get("isMainSleep")]
    minutes = (sleep.get("summary") or {}).get("totalMinutesAsleep")
    summary = activity.get("summary") or {}
    return {
        "sleep_hours": round(minutes / 60, 2) if minutes else None,
        "sleep_efficiency": main[0].get("efficiency") if main else None,
        "steps": summary.get("steps"),
        "resting_hr": summary.get("restingHeartRate"),
    }


class Fitbit:
    """Keeps the rotating refresh token in the memory store and reads a day."""

    def __init__(self, client_id, client_secret, store, opener=request.urlopen):
        self.client_id, self.client_secret, self.store, self.opener = client_id, client_secret, store, opener

    def connected(self):
        return bool(self.store.get(TOKEN_KEY))

    def connect(self, code, redirect_uri):
        tokens = exchange_code(self.client_id, self.client_secret, code, redirect_uri, self.opener)
        self.store.put(TOKEN_KEY, tokens["refresh_token"])

    def read_day(self, day):
        token = self.store.get(TOKEN_KEY)
        if not token:
            raise RuntimeError("Fitbit is not connected yet")
        tokens = refresh(self.client_id, self.client_secret, token, self.opener)
        self.store.put(TOKEN_KEY, tokens["refresh_token"])  # Fitbit rotates it: save the new one first
        return day_summary(tokens["access_token"], day, self.opener)
