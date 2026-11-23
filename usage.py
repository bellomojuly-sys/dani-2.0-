"""Token monitoring (D2-057): how many input and output tokens Dani spends.

Every model answer carries ``usage`` (prompt_tokens = input, completion_tokens
= output). ``MeteredClient`` wraps the real client: it passes every call
through unchanged and adds the usage to a ``UsageLog``, so chat.py and
dashboard.py do not change and cannot forget to count.

The log keeps one total per (day, model, kind) — kind is what the call was
for: "chat" or "priority". It is saved in a Notion database ("Dani — consumo
token"), because the Render free disk is wiped on every restart: at start the
log reloads the recent rows, and ``flush`` writes only the totals that changed
(one row per day, model and kind, created once and then updated).
"""

import threading
from datetime import date, timedelta
from types import SimpleNamespace

from pydantic import BaseModel, Field


class UsageRow(BaseModel):
    day: date
    model: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    calls: int = Field(default=0, ge=0)

    @property
    def key(self):
        return (self.day, self.model, self.kind)


class UsageLog:
    """Totals in memory, safe to use from the server and the refresh thread."""

    def __init__(self, today):
        self.today = today  # a function returning today's date (Amsterdam)
        self.rows = {}      # key -> UsageRow
        self.page_ids = {}  # key -> Notion page id, once the row exists there
        self.dirty = set()  # keys changed since the last flush
        self.lock = threading.Lock()

    def load(self, rows_with_ids):
        """Start from what Notion already has: [(UsageRow, page_id), ...]."""
        with self.lock:
            for row, page_id in rows_with_ids:
                self.rows[row.key] = row
                self.page_ids[row.key] = page_id

    def record(self, model, kind, usage):
        """Add one call. ``usage`` without token counts still counts as a call."""
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        key = (self.today(), model, kind)
        with self.lock:
            row = self.rows.get(key) or UsageRow(day=key[0], model=model, kind=kind)
            self.rows[key] = row.model_copy(update={
                "input_tokens": row.input_tokens + input_tokens,
                "output_tokens": row.output_tokens + output_tokens,
                "calls": row.calls + 1,
            })
            self.dirty.add(key)

    def flush(self, save):
        """Write every changed total with ``save(row, page_id or None) -> page_id``.

        A failed save keeps that row dirty, so it is tried again next time and
        no count is lost while Render is running. Returns how many were saved.
        """
        with self.lock:
            pending = [(key, self.rows[key], self.page_ids.get(key)) for key in sorted(self.dirty)]
        saved = 0
        for key, row, page_id in pending:
            try:
                new_id = save(row, page_id)
            except Exception as failure:  # Notion down: keep it for the next flush
                print(f"usage not saved: {type(failure).__name__}")
                continue
            with self.lock:
                self.page_ids[key] = new_id
                if self.rows[key] == row:  # nothing new arrived while saving
                    self.dirty.discard(key)
            saved += 1
        return saved

    def summary(self, days=30):
        """Totals per day (newest first) and for today, 7 and 30 days."""
        today = self.today()
        first = today - timedelta(days=days - 1)
        with self.lock:
            rows = [row for row in self.rows.values() if first <= row.day <= today]
        per_day = {}
        for row in rows:
            entry = per_day.setdefault(row.day, {"day": row.day.isoformat(), "input": 0, "output": 0, "calls": 0})
            entry["input"] += row.input_tokens
            entry["output"] += row.output_tokens
            entry["calls"] += row.calls

        def total(since):
            chosen = [entry for day, entry in per_day.items() if day >= since]
            return {name: sum(entry[name] for entry in chosen) for name in ("input", "output", "calls")}

        by_kind = {}
        for row in rows:
            entry = by_kind.setdefault(f"{row.kind} · {row.model}", {"input": 0, "output": 0, "calls": 0})
            entry["input"] += row.input_tokens
            entry["output"] += row.output_tokens
            entry["calls"] += row.calls
        return {
            "today": total(today),
            "week": total(today - timedelta(days=6)),
            "month": total(first),
            "days": [per_day[day] for day in sorted(per_day, reverse=True)],
            "by_kind": by_kind,
        }


class MeteredClient:
    """An OpenAI-style client that counts the tokens of every chat completion.

    Only ``chat.completions.create`` is wrapped; the answer is returned as is.
    """

    def __init__(self, client, log, kind):
        self._client, self._log, self._kind = client, log, kind
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **arguments):
        response = self._client.chat.completions.create(**arguments)
        self._log.record(arguments.get("model", "?"), self._kind, getattr(response, "usage", None))
        return response
