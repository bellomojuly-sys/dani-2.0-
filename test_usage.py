"""Token monitoring (D2-057): counting, saving, summary. No API, no Notion."""

from datetime import date
from types import SimpleNamespace

from usage import MeteredClient, UsageLog, UsageRow

DAY = date(2026, 11, 23)


def usage(i, o):
    return SimpleNamespace(prompt_tokens=i, completion_tokens=o)


def test_record_adds_tokens_and_calls_per_day_model_and_kind():
    log = UsageLog(lambda: DAY)
    log.record("deepseek-flash", "chat", usage(100, 20))
    log.record("deepseek-flash", "chat", usage(50, 5))
    log.record("deepseek-flash", "priority", usage(7, 3))
    chat = log.rows[(DAY, "deepseek-flash", "chat")]
    assert (chat.input_tokens, chat.output_tokens, chat.calls) == (150, 25, 2)
    assert log.rows[(DAY, "deepseek-flash", "priority")].calls == 1


def test_a_call_without_usage_still_counts_as_a_call():
    log = UsageLog(lambda: DAY)
    log.record("m", "chat", None)
    assert log.rows[(DAY, "m", "chat")] == UsageRow(day=DAY, model="m", kind="chat", calls=1)


def test_metered_client_passes_the_call_through_and_counts_it():
    response = SimpleNamespace(usage=usage(11, 4), choices=["answer"])
    sent = {}

    def create(**arguments):
        sent.update(arguments)
        return response

    raw = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    log = UsageLog(lambda: DAY)
    client = MeteredClient(raw, log, "chat")
    assert client.chat.completions.create(model="m", messages=[1], tools=[2]) is response
    assert sent == {"model": "m", "messages": [1], "tools": [2]}
    assert log.rows[(DAY, "m", "chat")].input_tokens == 11


def test_flush_creates_once_then_updates_and_skips_unchanged_rows():
    log = UsageLog(lambda: DAY)
    saves = []

    def save(row, page_id):
        saves.append((row.calls, page_id))
        return page_id or "page-1"

    log.record("m", "chat", usage(1, 1))
    assert log.flush(save) == 1 and saves == [(1, None)]
    assert log.flush(save) == 0  # nothing changed, nothing written
    log.record("m", "chat", usage(1, 1))
    log.flush(save)
    assert saves == [(1, None), (2, "page-1")]  # same row, updated


def test_a_failed_save_keeps_the_row_for_the_next_flush():
    log = UsageLog(lambda: DAY)
    log.record("m", "chat", usage(5, 5))

    def down(row, page_id):
        raise RuntimeError("Notion could not be reached")

    assert log.flush(down) == 0
    assert log.flush(lambda row, page_id: "p") == 1
    assert log.dirty == set()


def test_loaded_history_continues_and_keeps_its_page():
    log = UsageLog(lambda: DAY)
    log.load([(UsageRow(day=DAY, model="m", kind="chat", input_tokens=100, output_tokens=10, calls=3), "old")])
    log.record("m", "chat", usage(1, 1))
    saves = []
    log.flush(lambda row, page_id: saves.append((row.input_tokens, row.calls, page_id)) or page_id)
    assert saves == [(101, 4, "old")]


def test_summary_totals_today_week_month_and_by_kind():
    log = UsageLog(lambda: DAY)
    log.load([
        (UsageRow(day=date(2026, 11, 23), model="m", kind="chat", input_tokens=10, output_tokens=1, calls=1), "a"),
        (UsageRow(day=date(2026, 11, 23), model="m", kind="priority", input_tokens=5, output_tokens=5, calls=1), "b"),
        (UsageRow(day=date(2026, 11, 17), model="m", kind="chat", input_tokens=100, output_tokens=10, calls=2), "c"),
        (UsageRow(day=date(2026, 11, 16), model="m", kind="chat", input_tokens=1000, output_tokens=100, calls=4), "d"),
        (UsageRow(day=date(2026, 10, 24), model="m", kind="chat", input_tokens=9999, output_tokens=9, calls=9), "e"),
    ])
    summary = log.summary()
    assert summary["today"] == {"input": 15, "output": 6, "calls": 2}
    assert summary["week"] == {"input": 115, "output": 16, "calls": 4}   # 17-23 Nov
    assert summary["month"] == {"input": 1115, "output": 116, "calls": 8}  # 24 Oct is day 31: out
    assert [d["day"] for d in summary["days"]] == ["2026-11-23", "2026-11-17", "2026-11-16"]
    assert summary["by_kind"]["chat · m"] == {"input": 1110, "output": 111, "calls": 7}
