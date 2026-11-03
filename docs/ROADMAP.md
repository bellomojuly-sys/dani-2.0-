# Dani 2.0 roadmap — V4 (source of truth)

This file is the **source of truth** for the roadmap. The Notion page
"Dani 2.0 roadmap (V4)" is a copy that the agent updates every time a step
closes (see `AGENTS.md`).

**V4, 3 November 2026.** Rewritten after Ruud's feedback of 3 November: connect
the real task list in Notion first, make it work with plain tool descriptions,
and only then write a skill. V3 had grown to 190 steps aimed at the final
vision; V4 keeps only what builds the December product, in the order it is
built. The V3 rows are archived (see "Old ID → new ID" at the bottom).

## What Dani is for

**Final goal.** Dani is my own AI, trained on my needs and my life goals. It
organises my tasks, does the ones it can do itself, writes and calls for me,
keeps my shopping list, keeps me on track, and has a personality I can chat
with.

**December goal.** I tell Dani what changed in my day, and Dani plans my real
tasks from Notion into the free time in my real calendar, asking me before it
writes anything.

## How the IDs work

- Every step has one change, one output and one pass/fail check. It is marked
  ✅ only with a date and a commit.
- Steps are numbered in the order they are built: D2-024, D2-025, D2-026 …
  No letter suffixes from V4 on.
- **Done IDs never change** (commits and evidence point to them).
- To add a step, insert it where it belongs and renumber only the ⬜ steps
  after it. Record the change in "Changes" at the bottom.
- Each milestone is a study objective in `docs/STUDY-PLAN.md`. A step closes
  when the code works; the objective closes only when I pass its oral check.

## Status

| Field | Value |
|---|---|
| Done | D2-001 to D2-003, D2-005 to D2-023 (7 Oct–3 Nov 2026). Gates M01, M02, M03 passed in code |
| **Active** | **D2-024 — five test questions with expected answers (M04)** |
| Then | D2-025 (M04), then M05 — real tasks from Notion |
| Open | D2-004 — a teacher confirms the December scope (V4) |
| Study objectives to review | F1 Testing (oral check pending), D-A on M01–M03, F2, F3 |

## Done (7 October – 3 November)

| Milestone | What works | Steps | Commits |
|---|---|---|---|
| M00 — Product contract | New repository, vision, first MVP | D2-001–D2-003, D2-005 (D2-004 open) | `b74f59f` |
| M01 — LLM bootstrap | One request to DeepSeek; key in `.env`; the answer is validated with pydantic | D2-006–D2-010 | `b74f59f` `2a0d23f` `75d461a` `60634bc` `52ab164` |
| M02 — A Python function as an LLM tool | The model asks for `read_tasks`, my code runs it once, the result goes back; wrong arguments return an error | D2-011, D2-011a, D2-012–D2-015 | `3e5b345` `a756c88` `f860948` `5254892` `5bd7d7e` `6da6130` |
| M03 — First three-tool agent | Read → prioritise → validate in a bounded loop, behind a written skill; honest failure, nothing invented | D2-016, D2-017, D2-017a, D2-018–D2-020 | `cda5ca0` `4e40ec6` `42ebe5c` `c97aa5e` `7ee4b32` `e308727` |
| M03 — Test review | Every test says what it proves; 100% line and branch coverage; 432/433 mutants killed | D2-020a | `1600df5` |
| M04 — Trace (first half) | Each run has a run ID and timestamps; each tool call is recorded; secrets are redacted | D2-021–D2-023 | `a319f85` `3696a21` `b1563af` |

## December plan

Sprint 3 ends on 13 November and AMEXIO comes first in it, so Dani gets M04
and M05. Sprints 4 and 5 are for Dani and AMEXIO in turn.

### Sprint 3 (to 13 Nov) — M04, M05

#### M04 — Know whether Dani still works · study: F6

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-021 | Run ID and timestamps | Trace envelope | Events share the run ID | ✅ 2 Nov · `a319f85` |
| D2-022 | Record tool name, arguments, status and duration | JSON trace | Trace schema passes | ✅ 3 Nov · `3696a21` |
| D2-023 | Redact sensitive fields | Safe trace | A test secret is absent | ✅ 3 Nov · `b1563af` |
| D2-024 | Five test questions, each with the answer Dani must give | Evaluation set | Every case lists its expected facts | ⬜ |
| D2-025 | One command that runs the five cases | Pass/fail summary | A deliberate break makes it fail | ⬜ |

**Gate M04:** one command tells me whether Dani still works. This is the safety
net for every later change.

#### M05 — Dani reads my real tasks from Notion · study: D-F, F2

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-026 | Task model with the fields planning needs: title, deadline, priority, duration, energy | Typed Task objects | A task with a missing or wrong field fails | ⬜ |
| D2-027 | Notion connection with a read-only token, shared only with my Tasks database; token in `.env` | One real API answer | The token cannot write; the secret scan passes | ⬜ |
| D2-028 | Save one real Notion answer, with private data removed, as a test file | Offline fixture | The tests run without internet | ⬜ |
| D2-029 | Turn Notion pages into Task objects | List of Tasks | A page with a missing property gives a clear error | ⬜ |
| D2-030 | `read_tasks` reads from Notion instead of the three fake tasks; its description stays the same | Priority on my real tasks | The M04 cases still pass; the trace shows the model picked the tool from its description alone | ⬜ |

**Gate M05:** "what should I do first?" is answered on my real Notion tasks.

### Sprint 4 (16–27 Nov) — M06, M07, M08

#### M06 — Dani writes the priority back to Notion · study: D-F, F5

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-031 | Show what Dani would change in Notion, without changing it | Change preview | Notion is unchanged | ⬜ |
| D2-032 | Write the priority after my yes, then read it back | Updated Notion pages | The read-back matches the preview | ⬜ |
| D2-033 | Running it twice changes nothing more | Same Notion state | A retry makes no extra change | ⬜ |

**Gate M06:** the priority appears in Notion, only after I said yes.

#### M07 — Skill for the Notion workflow (Ruud, 3 Nov) · study: D-A

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-034 | Run the evaluation with tool descriptions only, without the D2-017a skill | Baseline numbers | Results are saved with the trace | ⬜ |
| D2-035 | Write the skill for the read → prioritise → propose → write workflow and run the evaluation again | Comparison table and Decision Log | The skill stays only if the numbers improve | ⬜ |

**Gate M07:** I can show with data whether the skill helps.

#### M08 — Dani knows my free time · study: D-C, F4

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-036 | Create one memory document at start-up | Valid empty memory file | It exists and is valid after a restart | ⬜ |
| D2-037 | Store tool that writes my planning rules (no Sundays, lessons, shifts, stop by 20:00) only into that document | Stored rules | No other path can be written; the read-back matches | ⬜ |
| D2-038 | Read my Google Calendar read-only through its secret iCal address in `.env` | My real events | Events for one day match Google Calendar; secret scan passes | ⬜ |
| D2-039 | Correct times in Amsterdam (summer/winter time) and repeating events over 14 days | Event list | A weekly event appears every week in the window and nowhere after it | ⬜ |
| D2-040 | Free time = calendar gaps minus my rules | Free slots | My hand calculation for one week matches | ⬜ |

**Gate M08:** Dani lists my real free slots for next week.

### Sprint 5 (30 Nov–18 Dec) — M09, M10, extra M11

#### M09 — Dani plans my tasks into free time · study: D-D

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-041 | Place tasks into free slots by priority, duration and deadline | Week plan | Fixed events never move; nothing overlaps | ⬜ |
| D2-042 | Tasks that do not fit are reported: move, postpone or ask me | Overflow list | No task disappears silently | ⬜ |
| D2-043 | Dani explains the plan after it has been checked | Plan summary | The explanation matches the actual plan | ⬜ |

**Gate M09:** a checked week plan built from my real tasks and my real calendar.

#### M10 — Dani puts the plan in my calendar · study: D-F, F5

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-044 | Show the calendar blocks Dani would create, without creating them | Block preview | The calendar is unchanged | ⬜ |
| D2-045 | Create the blocks after my yes, only in a calendar made for Dani, then read them back | Events in Google Calendar | The read-back matches; no other calendar is touched | ⬜ |
| D2-046 | Running it twice creates no duplicates | Same calendar | A retry adds nothing | ⬜ |

**Gate M10 — the December demo:** I ask Dani to plan my week; it reads Notion
and my calendar, proposes a plan, and after my yes the plan is in my calendar.

#### M11 — Talk to Dani from my phone (extra, only if Gate M10 passes by 11 Dec) · study: F7

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-047 | Put Dani online behind one chat address (Render), protected by a key | Online Dani | Without the key there is no answer; the M04 cases pass online | ⬜ |
| D2-048 | Turn a voice note into text with Whisper and send it to Dani | Text request | The transcript of a test recording is correct | ⬜ |
| D2-049 | Phone shortcut: record, send, read Dani's answer | Phone demo | The same request gives the same plan as on the computer | ⬜ |

**Gate M11:** I tell Dani my day from my phone and get the plan back.

## Later (after December)

In the order that moves Dani toward the final goal. Steps get IDs only when they
are pulled into the plan.

1. **Dani never stops working:** a rule-based answer when the model or the key
   fails, and the route (model or rules) shown in every answer.
2. **Dani reacts to changes:** "I have a call tomorrow at 3" replans only what
   is affected.
3. **Projects and order of tasks:** Dani knows that task 3 comes after task 2.
4. **Dani remembers me:** my goals, preferences and history, which I can read,
   correct and delete; Dani's personality.
5. **Dani starts by itself:** a morning briefing, reminders for recurring
   duties (rent, DUO, insurance), triggers on time and on events.
6. **Rules for what Dani may do alone:** limits I set and can revoke.
7. **Dani does things for me:** writes emails, keeps the shopping list, buys,
   books and calls — always within my rules.
8. **More agents:** MCP toolboxes, a supervisor and specialist agents, when one
   agent is no longer enough.
9. **The app:** the designed front-end, production hosting and the final proof.

The full V3 rows for these (D2-036 to D2-190) stay in git history and in the
archived V3 Notion page.

## Old ID → new ID

V3 rows that are still in the plan, under their new number. V3 rows not listed
here moved to "Later".

| V4 | V3 | Note |
|---|---|---|
| D2-024 | D2-024 | unchanged |
| D2-025 | D2-025 | unchanged |
| D2-026 | D2-027, D2-027a | Task model and energy field in one step; duration added for planning |
| D2-027 | D2-096 | read-only scope, now on my real Tasks database |
| D2-028 | D2-097 | |
| D2-029 | D2-098 | |
| D2-030 | — | new (Ruud): `read_tasks` on Notion; replaces D2-026 tasks.json |
| D2-031–D2-032 | D2-029, D2-030, D2-099 | preview, confirm, write and read back, on Notion instead of tasks.json |
| D2-033 | D2-100 | |
| D2-034–D2-035 | — | new (Ruud): skill only after the plain version works, with a measured comparison |
| D2-036 | D2-030a | feedback of 13 Oct |
| D2-037 | D2-030b | feedback of 13 Oct; now stores my planning rules |
| D2-038 | D2-064a | |
| D2-039 | D2-062, D2-064b | |
| D2-040 | D2-063, D2-064 | |
| D2-041 | D2-066, D2-067 | |
| D2-042 | D2-069 | |
| D2-043 | D2-070 | |
| D2-044–D2-046 | D2-104, D2-105 | write path of the Google Calendar adapter |
| D2-047–D2-049 | D2-171, D2-175 | voice and phone, as an extra |

Moved to "Later": D2-025a/b (fallback), D2-026 and D2-028 (tasks.json),
D2-030c/d (capture), M06 (projects and dependencies), M06b (dashboard: Notion
already shows my tasks), D2-061, D2-065, D2-067a, D2-068, M16–M18 (MCP and
supervisor), D2-101–D2-103, and all of D2-036–D2-190 not listed above.

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
