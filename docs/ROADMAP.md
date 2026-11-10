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
| **Active** | **D2-024 — Task model for my Notion tasks (M05)** |
| Then | D2-025, D2-026 (M05), then M06 — my calendars |
| Target | Gate M09, the app demo, by Friday 13 November |
| Study objectives to review | F1 Testing (oral check pending), D-A on M01–M03, F2, F3 |

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
| D2-024 | Task model with the fields planning needs: title, area, status, deadline, duration | Typed Task objects | A task with a missing or wrong field fails with a clear error | ⬜ |
| D2-025 | Notion integration shared only with my Tasks database, token in `.env`; `notion_client.py` reads my open tasks; one real answer saved, with private data removed, as a test fixture | Real tasks + offline fixture | Tests run without internet; the secret scan passes | ⬜ |
| D2-026 | `read_tasks` reads Notion instead of the three fake tasks; its description stays the same | Answers on my real tasks | "What do I have to do this week?" is answered on my real tasks; the trace shows the model picked the tool from its description | ⬜ |

**Gate M05:** Dani answers on my real Notion tasks.

### M06 — Dani reads my calendars · study: D-F

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-027 | Google service account, key in `.env`; my calendars shared with it; `gcal_client.py` lists the events of all my calendars in a time range | My real events | The events of one real day match Google Calendar | ⬜ |
| D2-028 | Amsterdam time and repeating events expanded one by one over 14 days; one real answer saved as a fixture | Event list | A weekly event appears every week in the window; times are right across the winter-time change | ⬜ |
| D2-029 | `read_calendar(start, end)` tool for the model | Answers on my calendar | "What do I have on Tuesday?" lists lessons, shifts and blocks correctly | ⬜ |

**Gate M06:** Dani knows my real week.

### M07 — I chat with Dani, with my rules · study: D-A, F6

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-030 | `rules.md` — my planning rules (days, fixed commitments, load, cycle phase, how to move things) — loaded into the system prompt | Rules in the prompt | A test checks the prompt is built from the file; changing the file changes the prompt | ⬜ |
| D2-031 | FastAPI server: `POST /api/chat` keeps the conversation and runs the tool loop | Chat over HTTP | A request returns Dani's answer; tests use a fake client, never the real API | ⬜ |
| D2-032 | Five test questions with the facts Dani must give, and one command that runs them | Pass/fail summary | A deliberate break makes it fail | ⬜ |

**Gate M07:** I can chat with Dani about my real week from the terminal, and
one command tells me whether it still works.

### M08 — Dani changes things after my yes · study: D-F, F5

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-033 | `propose_change` tool: create, move or delete a calendar event, or create a Notion task. It only saves a pending proposal and shows it to me | Proposal preview | Calendar and Notion are unchanged after a proposal | ⬜ |
| D2-034 | Overlap check in code: a proposal that falls on a fixed commitment (lesson, shift, appointment, Sunday) is flagged, never silently accepted | Flagged conflicts | A move onto a shift is flagged in a test | ⬜ |
| D2-035 | `POST /api/confirm` applies the proposal — no notifications, only the single occurrence of a repeating event — then reads it back | Real change after my yes | The read-back matches the preview; confirming twice changes nothing more | ⬜ |

**Gate M08:** "move the call to 4 pm" moves it, only after I said yes.

### M09 — The app, with voice · study: F7

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-036 | The PWA front-end of the first Dani (`planner` repo, `web/`) copied into `web/`: lock screen, day view and styles kept; the capture bar replaced by a chat that calls `/api/chat` and shows Confirm / Reject | App running locally | Build is green; a full conversation with a confirmed move works in the browser | ⬜ |
| D2-037 | Voice: `POST /api/transcribe` sends the recording to Whisper; a microphone button in the chat | Voice request | A test recording gives the right text; the text goes into the chat | ⬜ |
| D2-038 | Online on Render: one service serves the API and the built front-end, protected by a PIN/key | Online Dani | Without the key there is no answer; the five M07 cases pass online | ⬜ |

**Gate M09 — the demo (13 November):** from the app on my phone I say "move
Thursday's call to 4 pm" or "plan my free time on Wednesday"; Dani reads Notion
and my calendars, proposes, and after my yes the change is in my calendar.

## Sprint 4–5 (16 November – 18 December) — Dani on a real week

Milestones only; steps get IDs when the sprint starts.

- **M10 — Dani follows all my rules.** The evaluation set grows to about 20
  real cases (no Sundays, max 7 hours, one free hour during lessons, stop by
  20:00, cycle phase, "I'm tired"). Study: F6, D-D.
- **M11 — Dani says what slips.** When something moves, Dani moves the next
  roadmap tasks in order into the first free slot and lists what slips and how
  far. Study: D-D.
- **M12 — Skill or descriptions (Ruud, 3 Nov).** Run the evaluation with tool
  descriptions only, then with a skill; keep the skill only if the numbers
  improve. Decision Log. Study: D-A.
- **M13 — Priority written back to Notion** (old V4 M06), if there is time.
- **Real-week test:** one week planned only with Dani, measured against what I
  actually did. This is the portfolio proof.

### Proposed additions (10 November, to confirm) — toward the real assistant

After the dashboard core, in this order. Milestones only; steps get IDs when
each one starts. These pull parts of "Later" #2 and #5 forward and add the
integrations the final goal needs that no version named yet (Gmail, body
signals).

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
  automatic only after a Decision Log on the source, because the Google Fit
  API is shut down and Health Connect has no cloud API; the real options
  depend on my device (Fitbit/Oura/Garmin web APIs, an Apple Health export, a
  Health Connect bridge app). Gate: the plan for a low-energy day is visibly
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
| D2-037 | D2-048 | Whisper |
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
| 2026-11-10 | Proposed M14–M16 (to confirm): context under my control (memory file next to `rules.md`, pulls Later #2 forward), Gmail read-only (new OAuth credential, Decision Log), body signals (manual first; automatic source needs a Decision Log — Google Fit API is shut down). Mail writing stays in Later #5 |
