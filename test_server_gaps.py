"""Server paths the main tests do not reach: refusals, missing channels, failures.

Every test pins one behaviour: what Giulia sees when something is missing or
fails, and that nothing is written when it should not be.
"""

import json
from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from models import Event, Task
from server import create_app
from test_server import NOW, FakeChat, FakeMemory, FakeTelegram, Rig, _caller, _post, _signed


def app_with(tmp_path, **extra):
    rig = Rig(tmp_path)
    chat = extra.pop("chat", None)
    pin = extra.pop("pin", None)
    voice = extra.pop("voice", None)
    return rig, TestClient(create_app(rig.live, rig.done.append, chat, voice, pin, rig.path, web_dir=None, **extra))


class Raising:
    """A model client whose call raises the given error."""

    def __init__(self, failure):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.failure = failure

    def _create(self, **kwargs):
        raise self.failure


def test_a_mail_or_fitbit_failure_leaves_the_briefing_working(tmp_path):
    def broken_mail(since):
        raise RuntimeError("Gmail refused the login")

    class BrokenFitbit:
        def read_day(self, day):
            raise RuntimeError("Fitbit is not connected yet")

    _, http = app_with(tmp_path, mail=broken_mail, fitbit=BrokenFitbit())
    text = http.get("/api/briefing").json()["text"]
    assert "Gmail" not in text and "Fitbit" not in text and text.endswith("oggi come stai?")


def test_a_fitbit_night_without_sleep_or_efficiency_is_never_invented(tmp_path):
    class Empty:
        def read_day(self, day):
            return {"sleep_hours": 7.5, "sleep_efficiency": None, "steps": None, "resting_hr": None}

    chat = FakeChat("ok")
    _, http = app_with(tmp_path, chat=chat, fitbit=Empty())
    http.post("/api/chat", json={"message": "ciao", "history": []})
    system = chat.seen["messages"][0]["content"]
    assert "Fitbit, last night: 7.5 h asleep." in system and "efficiency" not in system and "short night" not in system


def test_a_calendar_failure_in_the_forecast_is_reported_not_raised(tmp_path):
    rig, http = app_with(tmp_path)
    rig.live.tasks = [Task(id="a", title="A", status="Not Started", deadline=NOW.date() + timedelta(days=3))]

    def down(start, end):
        raise RuntimeError("calendar down")

    rig.live.fetch_events = down
    assert http.get("/api/forecast").json()["error"] == "calendar down"


def test_a_broken_settings_file_is_a_clear_500(tmp_path):
    rig, http = app_with(tmp_path)
    open(rig.path, "w").write("{not json")
    assert http.get("/api/settings").status_code == 500


def test_model_failures_are_502_with_a_short_reason(tmp_path):
    _, http = app_with(tmp_path, chat=Raising(ValueError("empty answer")), memory=FakeMemory())
    assert http.post("/api/chat", json={"message": "x", "history": []}).json()["detail"] == "empty answer"
    _, http = app_with(tmp_path, chat=Raising(ConnectionError("down")), memory=FakeMemory())
    assert "ConnectionError" in http.post("/api/chat", json={"message": "x", "history": []}).json()["detail"]


def test_a_mood_from_the_chat_that_cannot_be_saved_says_so(tmp_path):
    from mood import MoodLog
    from test_chat import ScriptedChat

    class Down(MoodLog):
        def set(self, day, mood):
            raise RuntimeError("Notion down")

    chat = ScriptedChat([("", [("record_mood", '{"energy": 9}')])])
    _, http = app_with(tmp_path, chat=chat, mood_log=MoodLog())
    assert http.post("/api/chat", json={"message": "x", "history": []}).json()["reply"].startswith("Non ho capito come stai")
    chat = ScriptedChat([("", [("record_mood", '{"energy": 3}')])])
    _, http = app_with(tmp_path, chat=chat, mood_log=Down())
    assert "Non riesco a salvare nel diario" in http.post("/api/chat", json={"message": "x", "history": []}).json()["reply"]


def test_a_plan_whose_calendar_cannot_be_read_writes_nothing(tmp_path):
    from test_chat import ScriptedChat

    plan = json.dumps({"blocks": [{"title": "A", "start": "2026-12-01T10:00", "end": "2026-12-01T11:00"}]})
    created = []
    rig, http = app_with(tmp_path, chat=ScriptedChat([("Ecco.", [("propose_plan", plan)])]),
                         create_block=lambda *a: created.append(a) or "x")

    def down(start, end):
        raise RuntimeError("calendar down")

    rig.live.fetch_events = down
    body = http.post("/api/chat", json={"message": "pianifica", "history": []}).json()
    assert "Non riesco a leggere il calendario" in body["reply"] and created == []


def test_a_clean_plan_has_no_warning_sentence(tmp_path):
    from test_chat import ScriptedChat

    plan = json.dumps({"blocks": [{"title": "A", "start": "2026-12-01T10:00", "end": "2026-12-01T11:00"}]})
    rig, http = app_with(tmp_path, chat=ScriptedChat([("", [("propose_plan", plan)])]), create_block=lambda *a: "x")
    rig.live.fetch_events = lambda s, e: []
    reply = http.post("/api/chat", json={"message": "pianifica", "history": []}).json()["reply"]
    assert reply == "Ti propongo 1 blocchi: confermali uno per uno."


def test_failed_scheduling_and_failed_wake_pushes_are_counted_not_raised(tmp_path):
    def flaky(title, text, at=None, priority=None, link=None):
        if at is not None:
            raise RuntimeError("ntfy down")

    rig, http = app_with(tmp_path, send_note=flaky)
    rig.live.events = [Event(calendar="personale", title="Dentista", start=NOW + timedelta(hours=2),
                             end=NOW + timedelta(hours=3))]
    body = http.post("/api/briefing/send").json()
    assert body["scheduled"] == 0 and body["not_scheduled"] >= 1
    assert http.post("/api/wake", json={"event": "snoozed"}).json()["sent"] == 1  # only the immediate one


def test_wake_without_any_channel_is_refused(tmp_path):
    _, http = app_with(tmp_path)
    assert http.post("/api/wake", json={"event": "snoozed"}).status_code == 503


def test_mood_and_focus_endpoints_without_a_store_or_with_a_failing_one(tmp_path):
    from focus import WeekFocus
    from mood import MoodLog

    _, http = app_with(tmp_path)
    assert http.get("/api/mood").json() == {"enabled": False}
    assert http.put("/api/mood", json={"energy": 3}).status_code == 503
    assert http.put("/api/focus", json={"week": "2026-11-09", "text": "x"}).status_code == 503

    class DownMood(MoodLog):
        def set(self, day, mood):
            raise RuntimeError("Notion down")

    class DownFocus(WeekFocus):
        def set(self, monday, text):
            raise RuntimeError("Notion down")

    _, http = app_with(tmp_path, mood_log=DownMood(), week_focus=DownFocus())
    assert http.put("/api/mood", json={"energy": 3}).status_code == 502
    assert http.put("/api/focus", json={"week": "2026-11-09", "text": "x"}).status_code == 502


def test_confirming_an_unknown_proposal_is_404(tmp_path):
    _, http = app_with(tmp_path)
    assert http.post("/api/confirm", json={"id": "never-proposed"}).status_code == 404


def test_whisper_errors(tmp_path):
    from test_chat import FakeWhisper

    _, http = app_with(tmp_path, voice=FakeWhisper(""))
    assert http.post("/api/transcribe", content=b"audio").status_code == 422
    broken = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=lambda **k: (_ for _ in ()).throw(OSError("x")))))
    _, http = app_with(tmp_path, voice=broken)
    assert "Whisper non disponibile" in http.post("/api/transcribe", content=b"audio").json()["detail"]


def test_a_failed_wake_call_and_the_last_message_after_ten_calls(tmp_path):
    from wake_call import MAX_CALLS

    sent = []
    caller = _caller([])

    def refuse(url):
        raise RuntimeError("Twilio answered HTTP 401")

    caller["call"] = refuse
    rig = Rig(tmp_path)
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, caller=caller,
                     send_note=lambda title, text, at=None, priority=None, link=None: sent.append(title))
    morning = NOW.replace(hour=6, minute=45)
    for minute in range(0, MAX_CALLS * 3 + 1):
        app.state.tick(morning + timedelta(minutes=minute))
    assert sent == ["Ti ho chiamata 10 volte"]


def test_the_phone_call_asks_a_question_when_none_is_open_then_wrong_and_again(tmp_path):
    rig = Rig(tmp_path)
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, caller=_caller([]))
    http = TestClient(app)
    assert "Quanto fa" in _signed(http, "/twilio/tw1/voice", {"CallSid": "C"}).text
    wrong = _signed(http, "/twilio/tw1/answer", {"CallSid": "C", "Digits": "1"}).text
    assert "sbagliato" in wrong
    _signed(http, "/twilio/tw1/answer", {"CallSid": "C", "Digits": "1"})
    assert "Ti richiamo" in _signed(http, "/twilio/tw1/answer", {"CallSid": "C", "Digits": "1"}).text


def test_telegram_cards_for_a_move_and_a_failing_chat(tmp_path):
    from test_chat import ScriptedChat

    tg = FakeTelegram()
    move = json.dumps({"event": "e1", "new_start": "2026-11-12T16:00"})
    rig, http = app_with(tmp_path, chat=ScriptedChat([("", [("propose_move", move)])]), telegram=tg,
                         move_event=lambda *a: None)
    http.put("/api/settings", json={"tickable_calendars": ["studio", "personale", "lavoro", "Università"]})
    _post(http, {"message": {"chat": {"id": 42}, "text": "sposta"}})
    assert any("→" in text for text, _ in tg.sent) or any("Non posso" in text for text, _ in tg.sent)
    tg2 = FakeTelegram()
    _, http = app_with(tmp_path, chat=Raising(ValueError("empty answer")), telegram=tg2)
    _post(http, {"message": {"chat": {"id": 42}, "text": "ciao"}})
    assert tg2.sent[-1][0].startswith("Non riesco a risponderti")


def test_telegram_ignores_stickers_answers_start_and_handles_voice_problems(tmp_path):
    from test_chat import FakeWhisper

    tg = FakeTelegram()
    _, http = app_with(tmp_path, chat=FakeChat("ok"), telegram=tg)
    _post(http, {"message": {"chat": {"id": 42}, "sticker": {}}})
    assert tg.sent == []
    _post(http, {"message": {"chat": {"id": 42}, "text": "/start"}})
    assert tg.sent[-1][0].startswith("Eccomi, July")
    _post(http, {"message": {"chat": {"id": 42}, "voice": {"file_id": "v"}}})
    assert "OPENAI_API_KEY" in tg.sent[-1][0]
    tg2 = FakeTelegram()
    _, http = app_with(tmp_path, chat=FakeChat("ok"), telegram=tg2, voice=FakeWhisper(""))
    _post(http, {"message": {"chat": {"id": 42}, "voice": {"file_id": "v"}}})
    assert tg2.sent[-1][0].startswith("Non ho capito il vocale")


def test_telegram_buttons_reject_confirm_errors_and_done(tmp_path):
    tg, memory = FakeTelegram(), FakeMemory()
    _, http = app_with(tmp_path, telegram=tg, memory=memory)
    _post(http, {"callback_query": {"id": "q", "data": "r:none", "message": {"chat": {"id": 42}}}})
    assert tg.answers[-1] == "Rifiutata: non ho scritto nulla."
    _post(http, {"callback_query": {"id": "q", "data": "c:none", "message": {"chat": {"id": 42}}}})
    assert tg.answers[-1].startswith("Non fatto")
    _post(http, {"callback_query": {"id": "q", "data": "e:3:done", "message": {"chat": {"id": 42}}}})
    assert memory.reacted == [(3, "done")] and tg.answers[-1] == "Segnato. Brava."
    _post(http, {"callback_query": {"id": "q", "data": "e:x:done", "message": {"chat": {"id": 42}}}})
    assert memory.reacted == [(3, "done")]  # a forged id records nothing


def test_a_telegram_send_failure_never_stops_the_clock(tmp_path):
    tg = FakeTelegram()

    def down(text, buttons=None):
        raise RuntimeError("Telegram could not be reached")

    tg["send"] = down
    rig = Rig(tmp_path)
    rig.live.events = [Event(calendar="personale", title="Dentista", start=NOW + timedelta(minutes=30),
                             end=NOW + timedelta(hours=1))]
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, telegram=tg)
    TestClient(app).post("/api/wake", json={"event": "snoozed"})  # queues follow-ups through telegram_note
    sent = sum(app.state.tick(NOW + timedelta(minutes=m)) for m in range(1, 30))
    assert sent >= 1  # counted even though every send failed


def test_fitbit_endpoints_when_not_configured_or_failing(tmp_path):
    _, http = app_with(tmp_path)
    assert http.get("/fitbit/connect").status_code == 503
    assert http.get("/api/memory/summary").json() == {"enabled": False}

    class Failing:
        client_id, redirect_uri = "C", "https://dani/fitbit/callback"

        def connect(self, code, redirect_uri):
            raise RuntimeError("Fitbit refused the token request (HTTP 400)")

    _, http = app_with(tmp_path, fitbit=Failing())
    state = http.get("/fitbit/connect", follow_redirects=False).headers["location"].split("state=")[1].split("&")[0]
    assert http.get(f"/fitbit/callback?code=C&state={state}").status_code == 502


def test_mail_is_read_once_per_ten_minutes(tmp_path):
    reads = []
    _, http = app_with(tmp_path, mail=lambda since: reads.append(since) or [])
    http.get("/api/briefing")
    http.get("/api/briefing")
    assert len(reads) == 1


def test_get_mood_with_a_diary(tmp_path):
    from mood import MoodLog
    _, http = app_with(tmp_path, mood_log=MoodLog())
    assert http.get("/api/mood").json()["enabled"] is True


def test_the_last_message_after_ten_calls_may_fail_without_stopping_dani(tmp_path):
    from wake_call import MAX_CALLS

    def down(title, text, at=None, priority=None, link=None):
        raise RuntimeError("Telegram down")

    rig = Rig(tmp_path)
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, caller=_caller([]), send_note=down)
    morning = NOW.replace(hour=6, minute=45)
    for minute in range(MAX_CALLS * 3 + 1):
        app.state.tick(morning + timedelta(minutes=minute))  # no exception escapes


def test_solving_the_call_records_awake_in_the_memory(tmp_path):
    memory = FakeMemory()
    rig = Rig(tmp_path)
    morning_time = NOW.replace(hour=6, minute=45)
    rig.live.clock = lambda: morning_time
    app = create_app(rig.live, rig.done.append, None, None, None, rig.path, web_dir=None, caller=_caller([]), memory=memory)
    http = TestClient(app)
    app.state.tick(morning_time)
    question = _signed(http, "/twilio/tw1/voice", {"CallSid": "C"}).text
    a, b = question.split("Quanto fa ")[1].split("?")[0].split(" per ")
    _signed(http, "/twilio/tw1/answer", {"CallSid": "C", "Digits": str(int(a) * int(b))})
    assert memory.reacted == [(1, "awake")] and memory.events[0][0] == "wake_call"


def test_a_move_card_on_telegram_shows_the_new_time(tmp_path):
    from test_chat import ScriptedChat

    tg = FakeTelegram()
    rig = Rig(tmp_path)
    events = rig.http.get("/api/state").json()["events"]
    ref = f"e{next(n for n, e in enumerate(events, 1) if not e['all_day'])}"
    chat = ScriptedChat([("", [("propose_move", json.dumps({"event": ref, "new_start": "2026-11-12T19:00"}))])])
    http = TestClient(create_app(rig.live, rig.done.append, chat, None, None, rig.path, web_dir=None,
                                 telegram=tg, move_event=lambda *a: None))
    http.put("/api/settings", json={"tickable_calendars": sorted({e["calendar"] for e in events})})
    _post(http, {"message": {"chat": {"id": 42}, "text": "sposta"}})
    card, buttons = tg.sent[-1]
    assert "→ 12/11 19:00" in card and buttons[0][0] == "Conferma"


def test_a_plan_on_telegram_comes_as_one_card_per_block(tmp_path):
    from test_chat import ScriptedChat

    tg = FakeTelegram()
    plan = json.dumps({"blocks": [{"title": "Betsy", "start": "2026-12-01T10:00", "end": "2026-12-01T12:00"}]})
    rig, http = app_with(tmp_path, telegram=tg, create_block=lambda *a: "x",
                         chat=ScriptedChat([("Ecco.", [("propose_plan", plan)])]))
    rig.live.fetch_events = lambda s, e: []
    _post(http, {"message": {"chat": {"id": 42}, "text": "pianifica martedì"}})
    card, buttons = tg.sent[-1]
    assert card == "Betsy · 01/12 10:00–12:00" and [b[0] for b in buttons] == ["Conferma", "Rifiuta"]


def test_the_home_shows_the_last_mail_in_amsterdam_time_and_gmail_status(tmp_path):
    messages = [{"from_name": "Olga", "from": "o@fontys.nl", "subject": "Feedback", "date": "2026-11-26T13:05:00+00:00",
                 "box": "scuola", "newsletter": False, "snippet": "..."}]
    reads = []
    _, http = app_with(tmp_path, mail=lambda since: reads.append(since) or messages)
    state = http.get("/api/state").json()
    assert state["mail"]["on"] is True
    assert state["mail"]["messages"] == [{"from_name": "Olga", "subject": "Feedback", "box": "scuola",
                                          "newsletter": False, "date": "2026-11-26T14:05+01:00"}]
    assert state["sources"]["gmail"]["ok"] is True
    http.post("/api/refresh", json={"source": "gmail"})  # "Aggiorna" reads again at once
    assert len(reads) == 2


def test_a_gmail_failure_is_shown_in_the_sources_not_hidden(tmp_path):
    def broken(since):
        raise RuntimeError("Gmail refused the login or the search: error")

    state = app_with(tmp_path, mail=broken)[1].get("/api/state").json()
    assert state["sources"]["gmail"] == {"ok": False, "at": state["sources"]["gmail"]["at"],
                                         "error": "Gmail refused the login or the search: error"}
    assert state["mail"]["messages"] == []


def test_without_gmail_the_home_says_it_is_not_connected(tmp_path):
    _, http = app_with(tmp_path)
    assert http.get("/api/state").json()["mail"] == {"on": False, "messages": []}
    assert http.post("/api/refresh", json={"source": "gmail"}).status_code == 409
