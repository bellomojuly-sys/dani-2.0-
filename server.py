"""The live dashboard server: a small FastAPI app in front of ``Live``.

    python3 server.py            # real Notion + calendars, http://127.0.0.1:8000
    python3 server.py --demo     # the saved fixtures; ticking writes nowhere
    python3 server.py --host 0.0.0.0   # reachable from the phone; needs DANI_PIN

``create_app`` takes every outside piece as an argument (the cache, the Notion
write, the chat model, Whisper), so the tests build the app with fakes and
never touch the network. Only ``__main__`` builds the real ones.

What can write (always after an action of Giulia's):
  - POST /api/tick  with a task  -> Notion Status = Done (after the page's
    "Annulla" seconds have passed);
  - POST /api/tick  with an event -> deleted from Google Calendar when the
    Calendar API is connected and the event was read through it; otherwise
    hidden locally and listed as "to delete";
  - POST /api/confirm -> applies one move proposal she saw in the chat.
The chat itself never writes: it can only create a proposal.
"""

import os
import sys
import threading
import time
import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from propose import PROPOSE_MOVE_SCHEMA, build_proposal, describe, event_refs

from chat import chat_reply, chat_turn, speech_to_text
from cycle import CycleSettings
from store import SETTINGS_FILE, UserSettings, hide_event, read_settings, unhide_event, write_settings

REFRESH_SECONDS = 60


class TickBody(BaseModel):
    kind: Literal["task", "event"]
    id: str = Field(min_length=1)


class KeyBody(BaseModel):
    key: str = Field(min_length=1)


class ProposalBody(BaseModel):
    id: str = Field(min_length=1)


class RefreshBody(BaseModel):
    source: Literal["all", "notion", "calendar", "gmail"] = "all"


class SettingsBody(BaseModel):
    """What the Settings page may change. Hidden events are not here: they
    change only through tick / unhide."""

    context: str = Field(default="", max_length=8000)
    cycle: CycleSettings | None = None
    tickable_calendars: list[str] = []


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict] = []


def create_app(live, mark_done, chat_client=None, voice_client=None, pin=None,
               settings_path=SETTINGS_FILE, web_dir="web", delete_event=None, move_event=None):
    """Build the app. mark_done(task_id) performs the Notion write;
    chat_client / voice_client are OpenAI-style clients or None (= not set up);
    pin, when set, must come in the X-Dani-Pin header of every /api request;
    delete_event(event) and move_event(event, start, end) perform the Google
    Calendar writes, or are None while the calendar is read-only."""
    proposals = {}  # id -> Proposal waiting for her Confirm; lost at restart on purpose

    def check_pin(x_dani_pin: str | None = Header(default=None)):
        if pin and x_dani_pin != pin:
            raise HTTPException(status_code=401, detail="PIN mancante o sbagliato")

    app = FastAPI(title="Dani")
    # Only /api is behind the PIN: the page itself must load to ask for it.
    api = APIRouter(prefix="/api", dependencies=[Depends(check_pin)])

    def settings():
        try:
            return read_settings(settings_path)
        except ValueError as problem:
            raise HTTPException(status_code=500, detail=str(problem))

    def full_state():
        current = settings()
        state = live.state(current)
        state["hidden_events"] = [entry.model_dump(mode="json") for entry in current.hidden_events]
        state["chat"] = {"text": chat_client is not None, "whisper": voice_client is not None}
        state["calendar_write"] = {"delete": delete_event is not None, "move": move_event is not None}
        return state

    @api.get("/state")
    def get_state():
        return full_state()

    @api.post("/refresh")
    def post_refresh(body: RefreshBody):
        if body.source == "gmail":
            raise HTTPException(status_code=409, detail="Gmail non è ancora collegato")
        live.refresh(body.source)
        return full_state()

    @api.post("/tick")
    def post_tick(body: TickBody):
        current = settings()
        if body.kind == "task":
            task = live.find_task(body.id)
            if task is None:
                raise HTTPException(status_code=404, detail="task non trovato fra quelli aperti")
            try:
                mark_done(task.id)
            except RuntimeError as failure:
                raise HTTPException(status_code=502, detail=str(failure))
            live.drop_task(task.id)
            return {"ok": True, "notion": "done", "title": task.title}
        event = live.find_event(body.id)
        if event is None:
            raise HTTPException(status_code=404, detail="evento non trovato in questa settimana")
        allowed = {name.casefold() for name in current.tickable_calendars}
        if event.calendar.casefold() not in allowed:
            raise HTTPException(status_code=403, detail=f"gli eventi di '{event.calendar}' non si spuntano")
        if delete_event is not None and event.api_id:
            try:
                delete_event(event)
            except RuntimeError as failure:
                raise HTTPException(status_code=502, detail=str(failure))
            live.refresh("calendar")
            return {"ok": True, "calendar": "deleted", "title": event.title}
        write_settings(hide_event(current, event, live.clock()), settings_path)
        return {"ok": True, "calendar": "hidden, delete pending", "title": event.title}

    @api.post("/unhide")
    def post_unhide(body: KeyBody):
        write_settings(unhide_event(settings(), body.key), settings_path)
        return {"ok": True}

    @api.get("/settings")
    def get_settings():
        return settings().model_dump(mode="json")

    @api.put("/settings")
    def put_settings(body: SettingsBody):
        current = settings()
        updated = UserSettings(
            context=body.context,
            cycle=body.cycle,
            tickable_calendars=[name.strip() for name in body.tickable_calendars if name.strip()],
            hidden_events=current.hidden_events,
        )
        write_settings(updated, settings_path)
        return updated.model_dump(mode="json")

    @api.post("/cycle/started")
    def post_cycle_started():
        """The "è iniziato oggi" button: today becomes the confirmed start."""
        current = settings()
        lengths = current.cycle.model_dump(exclude={"start", "confirmed"}) if current.cycle else {}
        cycle = CycleSettings(start=live.clock().date(), confirmed=True, **lengths)
        write_settings(current.model_copy(update={"cycle": cycle}), settings_path)
        return cycle.model_dump(mode="json")

    @api.post("/chat")
    def post_chat(body: ChatBody):
        if chat_client is None:
            raise HTTPException(status_code=503, detail="chat non configurata: manca DEEPSEEK_API_KEY")
        current = settings()
        state = live.state(current)
        try:
            if move_event is None:
                return {"reply": chat_reply(chat_client, current.context, state, body.history, body.message)}
            turn = chat_turn(chat_client, current.context, state, body.history, body.message, PROPOSE_MOVE_SCHEMA)
        except ValueError as problem:
            raise HTTPException(status_code=502, detail=str(problem))
        except Exception as failure:  # the provider or the network
            raise HTTPException(status_code=502, detail=f"modello non disponibile: {type(failure).__name__}")
        if turn["move"] is None:
            return {"reply": turn["text"]}
        # The model asked for a move: check it in code and show it. Nothing is written here.
        shown = [live.find_event(row["key"]) for row in state["events"]]
        refs = {ref: event for ref, event in event_refs(shown).items() if event is not None}
        try:
            proposal = build_proposal(turn["move"], refs, current.tickable_calendars, uuid.uuid4().hex[:8])
        except ValueError as problem:
            return {"reply": f"Non posso proporre questo spostamento: {problem}."}
        proposals[proposal.id] = proposal
        return {"reply": describe(proposal), "proposal": proposal.model_dump(mode="json")}

    @api.post("/confirm")
    def post_confirm(body: ProposalBody):
        """Her yes: apply one proposal, once, then read the calendar back."""
        proposal = proposals.get(body.id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="proposta non trovata (già confermata o rifiutata)")
        if move_event is None:
            raise HTTPException(status_code=503, detail="il calendario non è collegato in scrittura")
        event = live.find_event(proposal.event_key)
        if event is None or (event.start, event.end) != (proposal.old_start, proposal.old_end):
            del proposals[body.id]
            raise HTTPException(status_code=409, detail="l'evento è cambiato dopo la proposta: richiedila di nuovo")
        if not event.api_id:
            raise HTTPException(status_code=409, detail="questo calendario è letto via iCal: non si può scrivere")
        try:
            move_event(event, proposal.new_start, proposal.new_end)
        except (RuntimeError, ValueError) as failure:
            raise HTTPException(status_code=502, detail=str(failure))
        del proposals[body.id]  # confirming twice changes nothing more
        live.refresh("calendar")
        moved = [e for e in live.events if e.api_id == event.api_id and e.start == proposal.new_start]
        return {"ok": True, "title": proposal.title, "read_back": bool(moved)}

    @api.post("/reject")
    def post_reject(body: ProposalBody):
        proposals.pop(body.id, None)
        return {"ok": True}

    @api.post("/transcribe")
    async def post_transcribe(request: Request):
        """The body is the raw recording (no form), its type in Content-Type."""
        if voice_client is None:
            raise HTTPException(status_code=503, detail="Whisper non configurato: manca OPENAI_API_KEY")
        audio = await request.body()
        kind = request.headers.get("content-type", "")
        filename = "voice.mp4" if "mp4" in kind else "voice.webm"
        try:
            return {"text": speech_to_text(voice_client, audio, filename)}
        except ValueError as problem:
            raise HTTPException(status_code=422, detail=str(problem))
        except Exception as failure:
            raise HTTPException(status_code=502, detail=f"Whisper non disponibile: {type(failure).__name__}")

    app.include_router(api)
    if web_dir and os.path.isdir(web_dir):
        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(os.path.join(web_dir, "index.html"))

        app.mount("/", StaticFiles(directory=web_dir), name="web")
    return app


def refresh_forever(live, settings_path, sleep=time.sleep, seconds=REFRESH_SECONDS):  # pragma: no cover
    """The background loop: re-read the sources, then the priority if needed."""
    while True:
        live.refresh("all")
        try:
            live.update_priority(read_settings(settings_path).context)
        except Exception as failure:
            print(f"priority not updated: {type(failure).__name__}")
        sleep(seconds)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    from dotenv import load_dotenv
    from openai import OpenAI

    import gcal_client
    from dashboard import ask_priority, demo_sources, load_settings
    from ical_client import read_calendars
    from live import Live
    from models import AMSTERDAM
    from notion_client import mark_done as notion_mark_done
    from notion_client import query_open_tasks

    load_dotenv(".env")
    demo = "--demo" in sys.argv
    host = sys.argv[sys.argv.index("--host") + 1] if "--host" in sys.argv else "127.0.0.1"
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
    pin = os.environ.get("DANI_PIN") or None
    if host != "127.0.0.1" and not pin:
        print("Refusing to listen outside this Mac without DANI_PIN in .env.")
        sys.exit(1)

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    chat_client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com") if deepseek_key else None
    voice_client = OpenAI(api_key=openai_key) if openai_key else None

    delete_event = move_event = None
    if demo:
        fetch_tasks, fetch_events = demo_sources()
        clock = lambda: datetime.combine(date(2026, 11, 10), datetime.now(AMSTERDAM).time(), tzinfo=AMSTERDAM)
        mark_done = lambda task_id: True  # demo: nothing is written to Notion
        settings_path = "data/demo-settings.json"
    else:
        env = load_settings()
        if "error" in env:
            print(env["error"])
            sys.exit(1)
        fetch_tasks = lambda: query_open_tasks(env["notion_token"], env["notion_database_id"])
        fetch_events = lambda start, end: read_calendars(env["ics_urls"], start, end)
        clock = lambda: datetime.now(AMSTERDAM)
        mark_done = lambda task_id: notion_mark_done(env["notion_token"], task_id)
        settings_path = SETTINGS_FILE
        key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        if key_file:
            # Calendars shared with the service account are read (and written)
            # through the API; the others stay on their read-only iCal address.
            token = gcal_client.token_source(key_file)
            through_api, ical_only = {}, []
            for url in env["ics_urls"]:
                try:
                    calendar_id = gcal_client.calendar_id_from_ics_url(url)
                    through_api[calendar_id] = gcal_client.calendar_name(token(), calendar_id)
                except (ValueError, RuntimeError):
                    ical_only.append(url)
            print(f"Calendar API: {sorted(through_api.values())}; iCal only: {len(ical_only)}")

            def fetch_events(start, end):
                events = read_calendars(ical_only, start, end)
                for calendar_id, name in through_api.items():
                    events += gcal_client.read_events(token(), calendar_id, name, start, end)
                return sorted(events, key=lambda event: event.start)

            delete_event = lambda event: gcal_client.delete_event(token(), event.calendar_id, event.api_id)
            move_event = lambda event, start, end: gcal_client.move_event(token(), event.calendar_id, event.api_id, start, end)

    prioritize = lambda tasks, today, context: ask_priority(chat_client, tasks, today, context)[0]
    live = Live(fetch_tasks, fetch_events, prioritize, clock)
    threading.Thread(target=refresh_forever, args=(live, settings_path), daemon=True).start()
    app = create_app(live, mark_done, chat_client, voice_client, pin, settings_path,
                     delete_event=delete_event, move_event=move_event)
    print(f"Dani dashboard on http://{host}:{port}" + (" (demo data)" if demo else ""))
    uvicorn.run(app, host=host, port=port, log_level="warning")
