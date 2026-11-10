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
