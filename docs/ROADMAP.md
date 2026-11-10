# Dani 2.0 roadmap — V5 (source of truth)

This file is the **source of truth** for the roadmap. The Notion page
"Dani 2.0 roadmap" is a copy that the agent updates every time a step closes
(see `AGENTS.md`).

**V5, 4 November 2026.** V4 still had 26 steps, and the thing I actually need
(I talk to Dani and it organises my week) arrived only in mid-December, after a
free-time algorithm, a memory document and an idempotency layer. V5 builds Dani
the way a planning assistant already works in a chat: a system prompt with my
rules, a few typed tools that read and write Notion and Google Calendar, and the
model doing the reasoning. The code checks what the model proposes, and nothing
is written without my yes. Ruud's feedback of 3 November still holds: real
Notion data first, plain tool descriptions first, a skill only if measured to
help (now M12).

## What Dani is for

**Final goal.** Dani is my own AI, trained on my needs and my life goals. It
organises my tasks, does the ones it can do itself, writes and calls for me,
keeps my shopping list, keeps me on track, and has a personality I can chat
with.

**Goal for 13 November (Sprint 3 demo).** A working app I can talk to, by text
or by voice. Dani reads my plan (my Tasks in Notion) and all my Google
calendars, follows my planning rules, and organises things for me: "move
Thursday's call to 4 pm", "plan my free time on Wednesday", "new task: …". It
always shows me the change first and writes it only after my yes.

**December goal.** The same app, reliable on a real week: it respects all my
rules, says what slips and how far when something moves, and I can prove with
an evaluation set that it still works after every change.

**Why this is worth building.** The same pattern — an assistant that reads a
company's own tools, follows its rules and asks before it writes — is a service
I can offer to small companies (MG Integration). Every step below is a skill I
can sell: API integrations, typed data models, tool design, confirmation and
read-back, evaluations, deploy.

## How the IDs work

- Every step has one change, one output and one pass/fail check. It is marked
  ✅ only with a date and a commit.
- Steps are numbered in the order they are built: D2-024, D2-025, D2-026 …
  No letter suffixes.
- **Done IDs never change** (commits and evidence point to them).
- To add a step, insert it where it belongs and renumber only the ⬜ steps
  after it. Record the change in "Changes" at the bottom.
- Steps of Sprint 4–5 get IDs when the sprint starts, after the demo.

## How I study now

The theory comes inside the build, not before it. Each step starts with 20–30
minutes on exactly the concept the step needs (NotebookLM, notes by hand), then
the build, then 10 minutes in which I explain it out loud. The rest of each
topic — the parts the project does not use but a teacher can ask about — goes
into one review-and-quiz slot per week. A step closes when the code works; the
study objective closes when I pass its oral check. `docs/STUDY-PLAN.md` will be
rewritten on this model after F5 and the pending quizzes.

## Status

| Field | Value |
|---|---|
| Done | D2-001 to D2-023 (7 Oct–3 Nov 2026). Gates M01, M02, M03 passed in code |
| **Active** | **D2-051 — Fontys timetable as a fixed calendar** (needs the link) |
| Then | D2-052–D2-053 (planner blocks), D2-054 (Whisper), D2-032 (evaluations), D2-038 (online) |
| Target | Gate M09, the app demo, by Friday 13 November |
| Study objectives to review | F1 Testing (oral check pending), D-A on M01–M03, F2, F3 |
| Built outside the order | 5 Nov: MVP `dashboard.html` on real Notion and iCal data. 10 Nov: live dashboard v2, D2-039 to D2-045 (built and tested, review with me pending) |

## Done (7 October – 3 November)

| Milestone | What works | Steps | Commits |
|---|---|---|---|
| M00 — Product contract | New repository, vision, first MVP; December/later split confirmed by Olga | D2-001–D2-005 | `b74f59f` |
| M01 — LLM bootstrap | One request to DeepSeek; key in `.env`; the answer is validated with pydantic | D2-006–D2-010 | `b74f59f` `2a0d23f` `75d461a` `60634bc` `52ab164` |
| M02 — A Python function as an LLM tool | The model asks for `read_tasks`, my code runs it once, the result goes back; wrong arguments return an error | D2-011, D2-011a, D2-012–D2-015 | `3e5b345` `a756c88` `f860948` `5254892` `5bd7d7e` `6da6130` |
| M03 — First three-tool agent | Read → prioritise → validate in a bounded loop, behind a written skill; honest failure, nothing invented | D2-016, D2-017, D2-017a, D2-018–D2-020 | `cda5ca0` `4e40ec6` `42ebe5c` `c97aa5e` `7ee4b32` `e308727` |
| M03 — Test review | Every test says what it proves; 100% line and branch coverage; 432/433 mutants killed | D2-020a | `1600df5` |
| M04 — Trace | Each run has a run ID and timestamps; each tool call is recorded; secrets are redacted | D2-021–D2-023 | `a319f85` `3696a21` `b1563af` |

## Sprint 3 (5–13 November) — the working app

Order of build: read first, then chat, then write, then the app around it.
Each milestone is usable on its own from the terminal before the next starts.

### M05 — Dani reads my plan from Notion · study: D-F, F2

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-024 | Task model with the fields planning needs: title, area, status, deadline, duration | Typed Task objects | A task with a missing or wrong field fails with a clear error | ↪ MVP 5 Nov (`models.py`) |
| D2-025 | Notion integration shared only with my Tasks database, token in `.env`; `notion_client.py` reads my open tasks; one real answer saved, with private data removed, as a test fixture | Real tasks + offline fixture | Tests run without internet; the secret scan passes | ↪ MVP 5 Nov (`notion_client.py`) |
| D2-026 | `read_tasks` reads Notion instead of the three fake tasks; its description stays the same | Answers on my real tasks | "What do I have to do this week?" is answered on my real tasks; the trace shows the model picked the tool from its description | ↪ MVP 5 Nov + D2-042 |

**Gate M05:** Dani answers on my real Notion tasks.

### M06 — Dani reads my calendars · study: D-F

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-027 | Google service account, key in `.env`; my calendars shared with it; `gcal_client.py` lists the events of all my calendars in a time range | My real events | The events of one real day match Google Calendar | ↪ D2-046 |
| D2-028 | Amsterdam time and repeating events expanded one by one over 14 days; one real answer saved as a fixture | Event list | A weekly event appears every week in the window; times are right across the winter-time change | ↪ MVP 5 Nov (`ical_client.py`) |
| D2-029 | `read_calendar(start, end)` tool for the model | Answers on my calendar | "What do I have on Tuesday?" lists lessons, shifts and blocks correctly | ↪ D2-045 (week in the prompt, no tool yet) |

**Gate M06:** Dani knows my real week.

### M07 — I chat with Dani, with my rules · study: D-A, F6

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-030 | `rules.md` — my planning rules (days, fixed commitments, load, cycle phase, how to move things) — loaded into the system prompt | Rules in the prompt | A test checks the prompt is built from the file; changing the file changes the prompt | ↪ D2-040, D2-045 (context from Settings) |
| D2-031 | FastAPI server: `POST /api/chat` keeps the conversation and runs the tool loop | Chat over HTTP | A request returns Dani's answer; tests use a fake client, never the real API | ↪ D2-043, D2-045 (no tool loop yet) |
| D2-032 | Five test questions with the facts Dani must give, and one command that runs them | Pass/fail summary | A deliberate break makes it fail | ⬜ |

**Gate M07:** I can chat with Dani about my real week from the terminal, and
one command tells me whether it still works.

### M08 — Dani changes things after my yes · study: D-F, F5

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-033 | `propose_change` tool: create, move or delete a calendar event, or create a Notion task. It only saves a pending proposal and shows it to me | Proposal preview | Calendar and Notion are unchanged after a proposal | ↪ D2-046 |
| D2-034 | Overlap check in code: a proposal that falls on a fixed commitment (lesson, shift, appointment, Sunday) is flagged, never silently accepted | Flagged conflicts | A move onto a shift is flagged in a test | ↪ D2-046 |
| D2-035 | `POST /api/confirm` applies the proposal — no notifications, only the single occurrence of a repeating event — then reads it back | Real change after my yes | The read-back matches the preview; confirming twice changes nothing more | ↪ D2-046 |

**Gate M08:** "move the call to 4 pm" moves it, only after I said yes.

### M09 — The app, with voice · study: F7

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-036 | The PWA front-end of the first Dani (`planner` repo, `web/`) copied into `web/`: lock screen, day view and styles kept; the capture bar replaced by a chat that calls `/api/chat` and shows Confirm / Reject | App running locally | Build is green; a full conversation with a confirmed move works in the browser | ↪ D2-044 (new front-end) |
| D2-037 | Voice: `POST /api/transcribe` sends the recording to Whisper; a microphone button in the chat | Voice request | A test recording gives the right text; the text goes into the chat | ↪ D2-045, D2-051 |
| D2-038 | Online on Render: one service serves the API and the built front-end, protected by a PIN/key | Online Dani | Without the key there is no answer; the five M07 cases pass online | ⬜ |

**Gate M09 — the demo (13 November):** from the app on my phone I say "move
Thursday's call to 4 pm" or "plan my free time on Wednesday"; Dani reads Notion
and my calendars, proposes, and after my yes the change is in my calendar.

### Dashboard v2 — live, multi-page, with chat (10 November, my decision)

Built on the Notion and iCal links of the 5 Nov MVP, before closing D2-024.
🟡 = built, tests green, checked in the browser; closed only after I have
walked through the code and can explain it.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-039 | `cycle.py`: phase estimate from start date, mean cycle and period length; "in arrivo" when the expected start has passed unconfirmed | Phase on the Home page | One test per phase, per refusal, and for cycles after a confirmed one | 🟡 |
| D2-040 | `store.py`: my private settings (context, cycle, tickable calendars, hidden events) in `data/settings.json`, outside git | Settings that survive a restart | A broken file is refused; write then read gives the same settings | 🟡 |
| D2-041 | `notion_client.mark_done`: PATCH Status = Done on one page, with read-back | A ticked task is Done in Notion | Fake HTTP: only Status is sent; an answer that is not Done raises | 🟡 |
| D2-042 | `live.py`: cache of tasks and events, refresh with time and ok/error per source, LLM priority only when tasks or context change | "aggiornato alle HH:MM:SS" | A failing source keeps the last data; the priority is asked once | 🟡 |
| D2-043 | `server.py` (FastAPI): state, refresh, tick, settings, cycle, PIN | The API behind the page | Every endpoint tested with fake sources, accepted case and each refusal | 🟡 |
| D2-044 | `web/`: Home, Calendar (week grid), Meal prep (placeholder), Settings; tick with 5 s of undo | The dashboard on Mac and phone | Browser check on real data at desktop and 375 px width | 🟡 |
| D2-045 | Chat bubble: `POST /api/chat` with my context and the week's data, read-only; voice in (Whisper if a key is set, else browser dictation) and spoken answers | I talk with Dani | Fake model: context and data are in the prompt; the chat never writes | 🟡 |
| D2-046 | Google Calendar through the API with a service account (`gcal_client.py`): events read live; a ticked event is deleted; the chat proposes a move (`propose.py`) and `POST /api/confirm` applies it after my yes | Real calendar changes | Fake HTTP: only the single occurrence, no notifications, read-back; a shift cannot be moved; the calendar is unchanged after a proposal. Real read checked; the first real write is mine | 🟡 |

Overlap with the Sprint 3 rows: D2-030 (my context in the prompt, edited from
Settings instead of `rules.md`), D2-031 (chat over HTTP, without the tool loop
yet), D2-036 (a new front-end instead of the old PWA) and D2-037 (Whisper
endpoint, inactive until `OPENAI_API_KEY` exists) are partly covered. D2-046
merges D2-027 and D2-033–D2-035. Decision Logs:
`docs/DECISION-LOG-dashboard-v2.md`.

### Sprint 3 finish (10–13 November) — what is still missing for the demo

Revised on 10 Nov after the dashboard v2: most ⬜ rows of M05–M09 are now
covered (marked ↪ above). What the demo still needs, in build order. Every
🟡 row of D2-039–D2-046 also gets a 15-minute walk-through with me each day.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-047 | Work shifts from Eitje: its `webcal://` subscription link in `GCAL_ICS_URL` (`.env`), `ical_client.to_https` swaps the scheme; the calendar is fixed (not tickable) | My shifts in the week | Tests: a webcal link is downloaded over https, https unchanged. Real: 4 shifts this week read, 0 planner blocks on a shift | 🟡 |
| D2-048 | Day rules in the planner: blocks start at 09:30 (morning routine, gym and commute end then, in calendar or not); on a day with a shift (an event in a work calendar, `lavoro`/Eitje) blocks end at 16:00 — from 16:00 she gets ready for the 17:00 shift — otherwise at 20:00 | Blocks that respect my real day | Tests: a shift day has no block after 16:00; a day without a shift keeps 20:00; no block before 09:30; a lesson does not cut the day to 16:00 | 🟡 10 Nov `09a1562` |
| D2-049 | Saving the Settings acts at once: `PUT /api/settings` re-asks the priority with the new context, so the dashboard shows the new priorities and blocks without waiting for the periodic refresh | New context, new plan, immediately | Tests: the save re-asks the priority with the new context; a priority failure does not lose the save | 🟡 10 Nov `a1e125a` |
| D2-050 | Click an event in the dashboard to act on it: the click opens the chat with the event reference and time prefilled, so I can say "riprogrammalo" or "questo blocco mi serve libero"; a move stays proposal → my yes → write; fixed calendars (shifts, lessons) stay fixed | Event actions from the calendar | Browser check: a click fills the chat with the right event; a move of a shift is still refused (existing propose tests) | 🟡 10 Nov `1c740f7` |
| D2-051 | Fontys timetable the same way, if the timetable gives a subscription link | My lessons in the week | Real lessons of one day match the timetable; no block on a lesson | ⬜ |
| D2-052 | A planner block can be accepted or rejected: Accept shows a preview, after my yes the event is created in the study calendar and read back; Reject hides the block | Blocks in my calendar | Calendar unchanged after a preview; read-back matches; a rejected block is not proposed again | ⬜ |
| D2-053 | A proposed block can be moved before I accept it; the new time goes through the same checks as `propose.py` (Sunday, overlap, fixed calendars) | Blocks where I want them | A move onto a shift is flagged in a test | ⬜ |
| D2-054 | Whisper live: `OPENAI_API_KEY` in `.env`, the existing `/api/transcribe` used with a real recording | I talk to Dani | A real recording gives the right text in the chat | ⬜ |

Then D2-032 (five evaluation cases, one command) and D2-038 (online with a
PIN, replacing the static Cloudflare snapshot) close Sprint 3.

## Sprint 4–5 (16 November – 18 December) — Dani on a real week

Milestones only; steps get IDs when the sprint starts.

- **M10 — Dani follows all my rules.** The evaluation set grows to about 20
  real cases (no Sundays, max 7 hours, one free hour during lessons, stop by
  20:00, **on restaurant days stop by 16:00** — the shift starts at 17:00 and
  she gets ready from 16:00, so the hour before a shift is never planned —
  cycle phase, "I'm tired"). Her morning routine (5:45–9:00: routine, travel,
  gym, travel) comes from the calendar and the context; mornings start at
  9:30–10:00 when there is no lesson. Study: F6, D-D.
- **M11 — Dani says what slips.** When something moves, Dani moves the next
  roadmap tasks in order into the first free slot and lists what slips and how
  far. Study: D-D.
- **M12 — Skill or descriptions (Ruud, 3 Nov).** Run the evaluation with tool
  descriptions only, then with a skill; keep the skill only if the numbers
  improve. Decision Log. Study: D-A.
- **M13 — Priority written back to Notion** (old V4 M06), if there is time.
- **Real-week test:** one week planned only with Dani, measured against what I
  actually did. This is the portfolio proof.

### Additions confirmed 10 November — toward the real assistant

Confirmed by Giulia on 10 November. After the dashboard core, in this order.
Milestones only; steps get IDs when each one starts. These pull parts of
"Later" #2 and #5 forward and add the integrations the final goal needs that
no version named yet (Gmail, body signals).

- **M14 — Context under my control** (pulls "Later" #2 forward, builds on
  D2-030). Everything Dani knows about me lives in files I own: `rules.md`
  (planning rules, already D2-030) plus a memory document (goals, preferences,
  standing facts) that I can read, correct and delete, versioned in git,
  loaded into the system prompt. Nothing about me is stored anywhere else.
  Gate: I can point at every sentence of context Dani uses, change it, and the
  next answer reflects the change. Study: D-A.
- **M15 — Dani reads my mail (Gmail, read-only).** A Gmail scope that can only
  read; triage and a short summary of what needs me in the morning briefing.
  No reply, no send, no label changes. Mail content is data, never
  instructions. Gate: the morning summary names the real mails that need an
  action, verified against the inbox. Decision Log: personal OAuth (a service
  account cannot read a personal Gmail) — a new credential class, so it is a
  stop condition. Study: D-F.
- **M16 — Dani knows my energy (body signals).** Phase 1: manual input (cycle
  phase, "I'm tired") already in the M10 rules — no new integration. Phase 2:
  automatic through the **Fitbit Web API** (my device is a Fitbit; the Google
  Fit API is shut down and Health Connect has no cloud API). Fitbit needs its
  own OAuth app and token — a new credential class, so a Decision Log on the
  exact scopes (sleep, activity; read-only) when the step starts. Gate: the
  plan for a low-energy day is visibly
  lighter, and I can see which signal caused it. Study: D-F.

**Drafting mails (preview → yes → send) stays in "Later" #5:** writing on my
behalf to other people is a wider authority than writing in my own calendar,
and comes only after M14 (context) and M15 (read) are solid.

## Later (after December)

In the order that moves Dani toward the final goal.

1. **Dani never stops working:** a rule-based answer when the model or the key
   fails, and the route (model or rules) shown in every answer.
2. **Dani remembers me:** my goals, preferences and history, which I can read,
   correct and delete; Dani's personality. (Partly pulled forward as M14.)
3. **Dani starts by itself:** a morning briefing, reminders for recurring
   duties (rent, DUO, insurance), triggers on time and on events.
4. **Rules for what Dani may do alone:** limits I set and can revoke.
5. **Dani does things for me:** writes emails, keeps the shopping list, buys,
   books and calls — always within my rules. (Reading mail pulled forward as
   M15; writing mail stays here.)
6. **More agents:** MCP toolboxes, a supervisor and specialist agents, when one
   agent is no longer enough.
7. **Dani for others:** the same app configured for a small company's tools
   and rules (MG Integration).

The full V3 rows stay in git history (commit `a3e346d`) and in the September
portfolio page "Dani roadmap evolution: phases → versions → Dani 2.0". V4 is in
git history (commit `f687d37`).

## Decisions to record (Decision Logs for Sprint 3)

- **Python back-end + the old PWA front-end**, instead of reviving the old
  TypeScript Worker or building a new UI. (D2-031, D2-036)
- **Google service account instead of personal OAuth**, already used in the
  first Dani: no token that expires every 7 days in testing mode. (D2-027)
- **Dani may write in my real calendars, not only in a Dani calendar**, because
  "move this call" is the core use; the safeguard is preview → yes → read-back.
  This widens Dani's authority, so it is a stop condition and needs my explicit
  yes. (D2-033–D2-035)
- **Whisper through the OpenAI API** for voice: a second provider and a second
  key, next to DeepSeek for the chat. (D2-037)

## Old ID → new ID (V4 → V5)

| V5 | V4 | Note |
|---|---|---|
| D2-024 | D2-026 | Task model; energy and priority dropped, area added |
| D2-025 | D2-027, D2-028, D2-029 | token, fixture and mapping in one step |
| D2-026 | D2-030 | `read_tasks` on Notion |
| D2-027–D2-029 | D2-038, D2-039 | calendar via service account instead of the iCal address; all calendars |
| D2-030 | D2-036, D2-037 | rules in a file in the prompt instead of a memory document and a store tool |
| D2-031 | D2-047 (part) | HTTP chat, now local first |
| D2-032 | D2-024, D2-025 | evaluation set and one command |
| D2-033–D2-035 | D2-031–D2-033, D2-044–D2-046 | one preview → yes → read-back path for calendar and Notion |
| D2-036 | — | new: the first Dani's front-end, reused |
| D2-037 | D2-054 | Whisper |
| D2-038 | D2-047 | Render, behind a key |
| M10–M11 | D2-040–D2-043 | free time and planning are done by the model and checked by code and evaluations |
| M12 | D2-034, D2-035 | skill vs descriptions, after the demo |
| M13 | D2-031–D2-033 | priority write-back |

Moved to "Later" or dropped: the free-time algorithm (D2-040), the memory
document (D2-036), the phone shortcut (D2-049, the PWA replaces it).

## Global stop conditions

Stop and ask me (and propose a Decision Log) if a change:

- adds more than one new concept to the active step;
- expands data, credentials, retention or authority (for example a token that can write);
- sends, books, cancels or pays without my explicit yes;
- cannot be externally verified;
- cannot be explained by me after the session.

## Changes

| Date | Change |
|---|---|
| 2026-11-03 | V4 after Ruud's feedback: Notion first, skill after; December scope cut to the planning product; steps renumbered in build order; no letter suffixes |
| 2026-11-04 | V5: a working chat app by 13 Nov (Notion, all Google calendars, rules in the prompt, preview → yes → write, the first Dani's PWA, Whisper, Render); theory inside the steps; planning by the model, checked by code and evaluations; Sprint 4–5 as milestones |
| 2026-11-10 | Dashboard v2 built outside the order, by my decision: new rows D2-039 to D2-046 appended (no renumbering of D2-024–D2-038); they partly cover D2-030, D2-031, D2-036, D2-037; D2-046 merges D2-027 and D2-033–D2-035. Six Decision Logs in `docs/DECISION-LOG-dashboard-v2.md` |
| 2026-11-10 | Revision after the dashboard v2: M05–M09 rows covered by the MVP and D2-039–D2-046 marked ↪; new rows D2-047 (Eitje shifts), D2-048 (Fontys), D2-049–D2-050 (accept, reject and move planner blocks), D2-051 (Whisper live); D2-032 and D2-038 keep their IDs and close Sprint 3 |
| 2026-11-10 | Giulia's feedback on the live dashboard: the pasted context alone did not change the plan. New rows D2-048 (day rules in the planner: 09:30 start, 16:00 on shift days), D2-049 (settings act at once) and D2-050 (event actions from the dashboard) inserted after D2-047; the ⬜ rows after them renumbered: Fontys → D2-051, planner blocks → D2-052/D2-053, Whisper live → D2-054 |
| 2026-11-10 | Proposed M14–M16 (to confirm): context under my control (memory file next to `rules.md`, pulls Later #2 forward), Gmail read-only (new OAuth credential, Decision Log), body signals (manual first; automatic source needs a Decision Log — Google Fit API is shut down). Mail writing stays in Later #5 |
| 2026-11-10 | M14–M16 confirmed by Giulia. Her device is a Fitbit, so M16 phase 2 goes through the Fitbit Web API (read-only scopes, own OAuth app, Decision Log at step start) |
