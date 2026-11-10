# Decision Logs — live dashboard v2 (10 November 2026)

Four decisions taken while turning the static `dashboard.html` into a live,
multi-page dashboard with a chat. Steps D2-039 to D2-046 in `docs/ROADMAP.md`.

---

# [DL] Do I copy the first Dani's PWA, or write a new front-end?
Date: 2026-11-10 · Microphase: D2-044 · Study objective: F7

Context — Roadmap V5 (D2-036) planned to copy the PWA of the first Dani (the
`planner` repo) and replace its capture bar with a chat. Meanwhile the MVP of
10 Nov already had its own look (the "Dani 2.0 App" mockup) and I asked for
four pages (Home, Calendar, Meal prep, Settings) that the old PWA does not have.

Options
- Copy the old PWA. Pro: lock screen, day view and build already exist. Con: a
  TypeScript build I did not write in this project and cannot explain line by
  line; its pages do not match the four I need; two visual styles to merge.
- A new front-end in `web/`: one HTML file, one CSS file, one JavaScript file,
  no build step. Pro: I can read every line; the look is the mockup's; the
  server just serves the folder. Con: no offline mode and no lock screen yet;
  everything the old PWA already solved is written again when needed.

Decision — New front-end in `web/`, plain HTML/CSS/JS, no framework, no build.

Why — The rule of this project is that I can explain every mechanism. The page
is about 350 lines of JavaScript with one idea: ask `/api/state` every 5
seconds and redraw. Checked in the browser on the real data (45 tasks, 35
events, 4 calendars) at desktop width and at 375 px.

Consequences — D2-036 changes from "copy the PWA" to "the multi-page
front-end". Protection is a PIN header instead of the old lock screen. No
offline mode: without the server the page shows "server non raggiungibile".

Evidence — `web/index.html`, `web/app.css`, `web/app.js`; browser check of
10 Nov on demo and real data.

---

# [DL] Which server keeps the dashboard live, and where does it run?
Date: 2026-11-10 · Microphase: D2-042, D2-043 · Study objective: F7

Context — The static page was a photograph of the moment it was generated. I
want "aggiornato alle HH:MM:SS". Notion allows about 3 requests per second and
every LLM priority costs money, so the browser cannot simply ask the sources
every few seconds.

Options
- Standard library `http.server`. Pro: no new dependency. Con: routing, JSON
  bodies, validation and tests by hand; thrown away at D2-031/D2-038, which
  already plan FastAPI and Render.
- FastAPI + uvicorn. Pro: request bodies validated with pydantic (the rule of
  this repo), a test client that never opens a socket, already planned. Con:
  three new dependencies (`fastapi`, `uvicorn`, `httpx` for the tests).
- Keep the static file and regenerate it with a timer. Pro: stays on
  Cloudflare. Con: cannot tick, cannot save settings, cannot chat.

Decision — FastAPI. Behind it a small cache (`live.py`): a background thread
re-reads Notion and the calendars every 60 seconds; the page asks the server
every 5 seconds; the LLM priority is asked again only when the tasks or my
context text change. It runs on my Mac (127.0.0.1). It refuses to listen on
the network without `DANI_PIN`.

Why — One server to explain instead of two. With 60 s the server makes about
1 Notion request per minute instead of 12. `test_live.py` proves the priority
is asked once until something changes
(`test_priority_is_asked_once_until_tasks_or_context_change`), and that a
failing source keeps the last good data and shows the error.

Consequences — The Cloudflare page stays a snapshot until it is retired. To be
online the app needs a process that is always on (Render, D2-038) behind the
PIN, because the API can write to Notion. The calendar side is only as fresh
as Google's iCal address, which can lag by minutes.

Evidence — `live.py`, `server.py`, `test_live.py`, `test_server.py`.

---

# [DL] Is a tick on the dashboard a "yes" to write?
Date: 2026-11-10 · Microphase: D2-041, D2-043 · Study objective: D-F, F5

Context — The rule of M08 is preview → yes → write, through a confirm endpoint.
On the dashboard I want to tick a task and have it Done in Notion, and tick a
calendar block and have it deleted. Asking "are you sure?" for every tick would
make the dashboard useless. This widens Dani's authority (the Notion token now
updates pages), so it is a stop condition and I said yes explicitly.

Options
- Every tick opens a confirmation. Pro: same rule everywhere. Con: two clicks
  for the most frequent action.
- The tick is the yes, with safeguards. Pro: one click. Con: a wrong click
  writes to my real data.
- Ticks only hide locally, nothing is written. Pro: no risk. Con: Notion and
  the dashboard disagree; I tick everything twice.

Decision — The tick is my yes, with four safeguards: (1) 5 seconds of "Annulla"
in the page before anything is sent; (2) the server writes only `Status = Done`
on a task that is in the current open list, and checks Notion's answer really
says Done; (3) events of fixed calendars (shifts, lessons) cannot be ticked,
the list is in Settings and is checked on the server, not only in the page;
(4) the chat cannot write at all.

Why — The action is done by me, on one named item, and is reversible (a Done
task can be reopened in Notion; a hidden event can be restored in Settings).
The preview → yes rule exists for changes proposed by the model; here there is
no model in the path. Tests: unknown task → 404 and no write; fixed calendar →
403; Notion failure → 502 and the task stays; answer not "Done" → error.

Consequences — The Notion integration needs the "Update content" capability.
Calendar events cannot be deleted yet: the iCal address is read-only, so a
ticked event is hidden, saved in `data/settings.json` and listed as "to delete"
until the Calendar API is connected with a service account (D2-046). A task
and a calendar event are not linked by data, so each tick writes only to its
own source: I do not match by title.

Evidence — `notion_client.mark_done`, `server.py` (`/api/tick`),
`test_server.py`, `test_notion_client.py`.

---

# [DL] Voice: the browser's dictation or Whisper?
Date: 2026-11-10 · Microphase: D2-045 · Study objective: F7

Context — I want to talk with Dani: I speak, she answers, also by voice.
Roadmap V5 planned Whisper (D2-037), which adds OpenAI as a second provider
with a second key.

Options
- Browser only (Web Speech API for dictation, `speechSynthesis` for the
  answer). Pro: no provider, no key, no cost. Con: dictation depends on the
  browser (Chrome and Safari), the audio is transcribed by Google or Apple,
  and it is less reliable on the phone.
- Whisper only. Pro: same quality everywhere, a real recording. Con: second
  provider, second key, cost per minute; nothing works until the key exists.
- Both, chosen by configuration.

Decision — Both. If `OPENAI_API_KEY` is set, the microphone records and the
server sends the recording to Whisper (`POST /api/transcribe`); if not, the
page uses the browser's dictation. Dani's answer is read aloud by the browser
(`speechSynthesis`), switched on with the speaker button.

Why — The chat works today with no new key, and Whisper is one variable away.
The OpenAI SDK is already a dependency (it is the client for DeepSeek), so no
new package. Tests use a fake Whisper client.

Consequences — Outside `localhost` a browser gives the microphone only to an
https page, so voice on the phone needs the app online (Render) or a tunnel.
With Whisper, my voice recordings go to OpenAI. The spoken answer uses the
device's Italian voice, not a chosen one.

Evidence — `chat.speech_to_text`, `server.py` (`/api/transcribe`),
`web/app.js` (`toggleMic`, `sayAloud`), `test_chat.py`.

---

# [DL] How does Dani get into Google Calendar: service account or my own OAuth login?
Date: 2026-11-10 · Microphase: D2-046 · Study objective: D-F

Context — The iCal addresses are read-only and Google refreshes them with a
delay. To delete or move an event Dani needs the Calendar API, and the API
needs an identity.

Options
- OAuth with my own Google account (a "client ID"). Pro: Dani sees exactly
  what I see, nothing to share. Con: a consent screen in the browser, a
  refresh token to store, and in Google's testing mode the permission expires
  every 7 days; on a server (Render) there is no browser to log in again.
- A service account: a robot account with its own e-mail, to which I share
  each calendar. Pro: no expiry, no browser, works the same on my Mac and on
  a server; I decide calendar by calendar what it may do (see only / change
  events). Con: a key file that must never be committed; one more thing to
  share when I create a calendar.

Decision — Service account. The key is a JSON file outside the repository;
`.env` holds only its path (`GOOGLE_SERVICE_ACCOUNT_FILE`). One new dependency,
`google-auth` (with `requests`), used only to turn the key into an access
token; every Calendar request is plain `urllib`, like the Notion client.
Calendars shared with the account are read through the API; a calendar that is
not shared stays on its iCal address.

Why — Tested on 10 Nov: the account reads 6 of my 7 calendars, and Google
reports its role per calendar (writer on personale, reader on lavoro,
Università and studio). So the sharing setting, not Dani's code, is the outer
limit of what can be written. I first downloaded an OAuth client file by
mistake: the two are easy to confuse, a service-account key has
`"type": "service_account"`.

Consequences — Reading through the API makes the calendar side live too (no
iCal delay). The scopes are `calendar.events` and `calendar.readonly`. If the
key leaks, I delete it in Google Cloud and create another. A calendar shared
as "see only" answers HTTP 403 to a write, and the dashboard shows that error.

Evidence — `gcal_client.py`, `test_gcal_client.py`; real read of 10 Nov
(35 events, the same as through iCal).

---

# [DL] May Dani write in my real calendars, and how is it kept safe?
Date: 2026-11-10 · Microphase: D2-046 · Study objective: D-F, F5

Context — "Move this session" is the core use, and my sessions live in my real
calendars (studio, personale), not in a separate "Dani" calendar. Writing there
widens Dani's authority: a stop condition of the roadmap, decided by me.

Options
- A separate Dani calendar, the only one Dani may write. Pro: my calendars
  cannot be damaged. Con: Dani cannot move the sessions that already exist.
- Write in my real calendars with a path of checks.
- Let the model write directly with a tool. Pro: fewer steps. Con: one wrong
  tool call changes my week with nobody looking.

Decision — Dani writes in my real calendars, only on this path:
1. the model can only call `propose_move`; it has no tool that writes;
2. `propose.py` checks the request in code: the event must be one of those
   shown, in a calendar I marked as tickable (shifts and lessons are refused),
   not all-day, with an end after the start; an overlap or a Sunday is flagged
   in the preview, never silently accepted;
3. nothing changes until I press Conferma (`POST /api/confirm`); a proposal is
   applied once, and is refused if the event changed in the meantime;
4. the write touches one occurrence, sends only start and end, uses
   `sendUpdates=none` (no e-mails), and is read back.
Deleting follows the tick rule of the earlier Decision Log.

Why — Each refusal has a test (`test_propose.py`, `test_server.py`): a shift
cannot be moved; a move onto a shift carries the warning; the calendar is
unchanged after a proposal; confirming twice changes nothing more. On the real
data the model proposed moving "Upper body" from 07:30 to 18:00 and, asked to
move a restaurant shift that is not in the week, answered that it could not
find it instead of inventing one.

Consequences — Only moves for now: creating events and Notion tasks from the
chat are not built. Proposals live in memory and are lost when the server
restarts. The real confirm has not been run by the agent: the first real write
is mine, in the app.

Evidence — `propose.py`, `server.py` (`/api/chat`, `/api/confirm`,
`/api/reject`), `test_propose.py`, `test_server.py`.
