"""Dani's memory (V1): what she says, what Dani suggests and how Giulia reacts.

Notion keeps what Giulia writes (character, life plan, focus). This store
keeps what Dani records to learn: every conversation (app, Telegram, phone),
every suggestion / reminder / call with her reaction, and daily measures
(energy, sleep). It is a Postgres database on Supabase (EU), reached through
its REST interface with the standard library, so there is no new dependency.
The tables are in docs/memory.sql. Every row says which agent wrote it, so the
agent team of M20 can share the same memory later.

Without SUPABASE_URL the server keeps the in-process behaviour (a restart
forgets), so nothing breaks before it is set up.
"""

import json
from urllib import error, parse, request


class MemoryStoreError(RuntimeError):
    pass


def send(method, url, headers, body=None, opener=request.urlopen, timeout=20):
    data = None if body is None else json.dumps(body, default=str).encode()
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except error.HTTPError as failure:
        detail = failure.read().decode(errors="replace")[:200]
        raise MemoryStoreError(f"memory answered HTTP {failure.code}: {detail}") from None
    except error.URLError as failure:
        raise MemoryStoreError(f"memory could not be reached: {failure.reason}") from None


class Memory:
    def __init__(self, url, key, http=send, agent="dani"):
        self.base = url.rstrip("/") + "/rest/v1"
        # A legacy service_role key is a JWT and also goes in Authorization. The new
        # secret keys (sb_secret_...) are not JWTs: they go in the apikey header only.
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if not key.startswith("sb_"):
            self.headers["Authorization"] = f"Bearer {key}"
        self.http = http
        self.agent = agent

    # --- the three tables -------------------------------------------------------
    def _insert(self, table, row, prefer="return=representation"):
        answer = self.http("POST", f"{self.base}/{table}", {**self.headers, "Prefer": prefer}, [row])
        return answer[0] if answer else None

    def _select(self, table, **query):
        url = f"{self.base}/{table}?" + parse.urlencode(query)
        return self.http("GET", url, self.headers) or []

    def log_message(self, channel, role, content):
        if role not in ("user", "assistant"):
            raise ValueError("role is user or assistant")
        return self._insert("conversations", {"channel": channel, "role": role, "content": content, "agent": self.agent})

    def recent_messages(self, channel, limit=24):
        """The last ``limit`` turns of a channel, oldest first, as chat history."""
        rows = self._select("conversations", select="role,content", channel=f"eq.{channel}",
                            order="at.desc", limit=str(limit))
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def log_event(self, kind, ref="", detail=None):
        """Record something Dani did on her own; returns the event id."""
        row = self._insert("events", {"kind": kind, "ref": ref, "detail": detail or {}, "agent": self.agent})
        return row["id"] if row else None

    def react(self, event_id, reaction, at):
        allowed = ("answered", "ignored", "done", "snoozed", "confirmed", "rejected", "awake", "no_answer")
        if reaction not in allowed:
            raise ValueError(f"unknown reaction {reaction!r}")
        self.http("PATCH", f"{self.base}/events?id=eq.{int(event_id)}", self.headers,
                  {"reaction": reaction, "reacted_at": at.isoformat()})

    def put_measure(self, day, name, value, source):
        """One value per day, name and source; a second write replaces the first."""
        self.http("POST", f"{self.base}/measures?on_conflict=day,name,source",
                  {**self.headers, "Prefer": "resolution=merge-duplicates"},
                  [{"day": day.isoformat(), "name": name, "value": float(value), "source": source}])

    def measures(self, since):
        return self._select("measures", select="day,name,value,source", day=f"gte.{since.isoformat()}", order="day.asc")

    def reactions(self, since):
        """Events since a moment, with their reaction: the raw material to learn from."""
        return self._select("events", select="at,kind,ref,reaction,reacted_at",
                            at=f"gte.{since.isoformat()}", order="at.asc")

    # --- a small key-value store (the Fitbit token) --------------------------------
    def get(self, key):
        rows = self._select("kv", select="value", key=f"eq.{key}")
        return rows[0]["value"] if rows else None

    def put(self, key, value):
        self.http("POST", f"{self.base}/kv?on_conflict=key", {**self.headers, "Prefer": "resolution=merge-duplicates"},
                  [{"key": key, "value": value}])


def reaction_summary(rows):
    """Per kind: how many were sent, and how many got each reaction (None = no reaction yet)."""
    summary = {}
    for row in rows:
        entry = summary.setdefault(row["kind"], {"sent": 0})
        entry["sent"] += 1
        reaction = row.get("reaction") or "none"
        entry[reaction] = entry.get(reaction, 0) + 1
    return summary
