# Dani 2.0 roadmap (source of truth)

This file is the **source of truth** for the roadmap. The Notion page
"Dani 2.0 roadmap (V3): progress tracking — October 2026" is a copy that the
agent updates every time a microphase closes (see `AGENTS.md`).

Every microphase has one change, one output and one pass/fail check. A row is
marked ✅ only with a date and a commit. IDs never change; a new microphase is
inserted where it belongs with a letter suffix (e.g. `D2-011a`), never appended
after D2-190.

Study objective column: each milestone is a learning objective in
`docs/STUDY-PLAN.md`. A microphase closes when the code works; the objective
closes only when Giulia passes its oral check ("Prova").

## Status

| Field | Value |
|---|---|
| Completed | D2-001 to D2-003, D2-005 to D2-020 (7–14 Oct 2026). Gates M01, M02 and M03 passed in code |
| Open from earlier | D2-004 — teacher confirmation of the MVP scope |
| **Active** | **D2-020a — critical review of every test** (feedback 15 Oct 2026). Blocks M04 |
| Then | D2-021 (M04) |
| Study objectives to review (ripasso) | F1 Testing (now), D-A on M01–M03, F2, F3 |

## In scope by December

### Sprint 2 (5–16 Oct) — M00 to M03

#### M00 — Product contract · study: —

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-001 | Create the new project | Project in the new repository | All project links open | ✅ 7 Oct · `b74f59f` |
| D2-002 | Record the final operating model | Vision in the README | The December product is described | ✅ 7 Oct · `b74f59f` |
| D2-003 | Define first local task MVP | Example input and output | Explain demo in one sentence | ✅ 7 Oct · `b74f59f` |
| D2-004 | Present MVP and evidence method to professor | Dated feedback | Feedback confirms or corrects scope | ⬜ open |
| D2-005 | Create clean Python repository | README and file tree | No old Dani code exists | ✅ 7 Oct · `b74f59f` |

**Gate M00:** professor feedback and clean boundary exist.

#### M01 — LLM bootstrap · study: F3, D-A (review)

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-006 | Choose provider, model and SDK | Decision record | Tool calling and structured output supported | ✅ 7 Oct · `b74f59f` |
| D2-007 | Send fixed Python model request | Terminal reply | Missing-key failure is distinct | ✅ 7 Oct · `2a0d23f` |
| D2-008 | Move secret to environment | Redacted config | Secret scan passes | ✅ 7 Oct · `75d461a` |
| D2-009 | Add minimal system and user messages | Request summary | Only intended messages are sent | ✅ 8 Oct · `60634bc` |
| D2-010 | Validate structured model response | Parsed object | Invalid response fails | ✅ 8 Oct · `52ab164` |

**Gate M01:** Giulia explains request, response, secret and validation.

#### M02 — First Python function as an LLM tool · study: D-A (review)

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-011 | Write read_tasks returning three hardcoded tasks | Python list | Direct unit test passes | ✅ 13 Oct · `3e5b345` |
| D2-011a | Validate arguments inside the body of the tool function — added after feedback, 13 Oct | Structured tool error | Wrong arguments return an error, not a crash or an invented result | ✅ 13 Oct · `a756c88` |
| D2-012 | Describe function as a tool schema | Tool definition | Schema matches function | ✅ 13 Oct · `f860948` |
| D2-013 | Let LLM request read_tasks | Tool-call request | Trace names correct tool | ✅ 13 Oct · `5254892` |
| D2-014 | Dispatch requested Python function | Tool-result event | Function runs once | ✅ 13 Oct · `5bd7d7e` |
| D2-015 | Return tool result to LLM | Three task titles | No invented title appears | ✅ 13 Oct · `6da6130` |

**Gate M02:** Giulia narrates the complete LLM-to-function loop.

#### M03 — First three-tool agent · study: D-A (review), F1

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-016 | Add prioritize_tasks | Ordered IDs and reasons | Direct test passes | ✅ 14 Oct · `cda5ca0` |
| D2-017 | Add validate_priority_result | Validation status | Missing, duplicate and unknown IDs fail | ✅ 14 Oct · `4e40ec6` |
| D2-017a | Skill for the task toolbox — added after feedback, 13 Oct | Skill text loaded with the toolbox | The model calls the tools in the described order | ✅ 14 Oct · `42ebe5c` |
| D2-018 | Implement bounded tool loop | Ordered call trace | Iteration limit works | ✅ 14 Oct · `c97aa5e` |
| D2-019 | Ask what to do first | Priority report | Every source ID appears once | ✅ 14 Oct · `7ee4b32` |
| D2-020 | Simulate task-source failure | Honest failure | No result is fabricated | ✅ 14 Oct · `e308727` |
| D2-020a | Review every test critically: what it checks, whether it fails when the code is broken on purpose, what is missing — added after feedback, 15 Oct | Test review note (good, weak, missing) and fixed weak tests | For each test Giulia says in one sentence what it proves; a deliberate break makes the right test fail | ⬜ **active** |

**Gate M03:** one LLM selects three Python tools and returns a validated result. D2-020a must close before M04 starts.

### Sprint 3 (26 Oct–13 Nov) — M04 to M06

> Re-planned on 26 Oct 2026: AMEXIO Part A (pipeline contract by 30 Oct, backend integration for Review 2 on 13 Nov) comes first, so Sprint 3 keeps only M04–M06. M06b, M12 and M13 move to Sprint 4; MCP (M16–M17) moves to Sprint 5 with M18–M20. Study order: `docs/STUDY-PLAN.md` and the "Piano NotebookLM" doc.

#### M04 — Trace and evaluation · study: F6

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-021 | Add run ID and timestamps | Trace envelope | Events share run ID | ⬜ |
| D2-022 | Record tool name, arguments, status and duration | JSON trace | Trace schema passes | ⬜ |
| D2-023 | Redact sensitive fields | Safe trace | Test secret is absent | ⬜ |
| D2-024 | Create five representative cases | Evaluation dataset | Expected facts are complete | ⬜ |
| D2-025 | Add evaluation command | Pass/fail summary | Deliberate regression fails | ⬜ |
| D2-025a | Rule-based fallback when the model call fails or the key is missing: deadline, then energy, then ID — added 20 Oct | Fallback priority report | With the key removed, "what should I do first?" still answers, no crash, no invented task | ⬜ |
| D2-025b | Record the route of every answer (model or fallback) in the trace and report — added 20 Oct | Route field in trace and report | A fallback answer is never shown as a model answer | ⬜ |

**Gate M04:** a third person reconstructs one run from evidence.

#### M05 — Persistent local tasks · study: D-B, F2, F4

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-026 | Move tasks to tasks.json | Visible fixture | Agent result remains valid | ⬜ |
| D2-027 | Add typed Task model | Task objects | Missing fields fail | ⬜ |
| D2-027a | Energy field on Task (high or low) — added 18 Oct | Tasks with an energy level | A task without a valid energy value fails | ⬜ |
| D2-028 | Enforce stable unique IDs | Duplicate error | Duplicate fixture fails | ⬜ |
| D2-029 | Add task-create preview | Draft task | Store remains unchanged | ⬜ |
| D2-030 | Confirm, write and reread task | Persisted task | Fields match after restart | ⬜ |
| D2-030a | Create and pre-register memory.json at start-up — added 13 Oct | Valid empty memory document | The file exists and is valid after a restart | ⬜ |
| D2-030b | Store tool that writes only to the pre-registered document — added 13 Oct | Stored and reread entry | No other path can be written; reread matches | ⬜ |
| D2-030c | Capture tool: one free sentence → task, calendar event or memory note, against a fixed list of destinations — added 20 Oct | Validated capture proposal | An unknown destination is rejected and falls back to rules | ⬜ |
| D2-030d | Write a capture through preview, confirm and reread — added 20 Oct | Persisted capture with its route | Nothing is written before confirmation; reread matches | ⬜ |

**Gate M05:** task state survives restart and every write is verified.

#### M06 — Projects and dependencies · study: D-B

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-031 | Add Project model | Project with tasks | Relationships validate | ⬜ |
| D2-032 | Add task dependencies | Dependency graph | Unknown dependency fails | ⬜ |
| D2-033 | Detect dependency cycles | Cycle error | A-B-A fails | ⬜ |
| D2-034 | Add task status transitions | Updated state | Illegal transition fails | ⬜ |
| D2-035 | Derive next available task | Task 3 after Task 2 | Hand calculation matches | ⬜ |

**Gate M06:** Dani knows exactly where Project X is.

### Sprint 4 (16–27 Nov) — M06b, M12, M13 · study: A-F, D-C, D-D

#### M06b — Read-only local dashboard (added 21 Oct) · study: F8

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-035a | Decision Log (why a dashboard, stack, read-only boundary) and one local page showing the tasks from tasks.json | Decision Log and local page | The page shows exactly the tasks in tasks.json; no write route exists | ⬜ |
| D2-035b | Show projects and the next available task | Project panel | The next task shown equals the result of D2-035 | ⬜ |
| D2-035c | Show the latest run trace, including the route | Trace panel | The panel matches the trace file of that run | ⬜ |
| D2-035d | Loading the page never calls the model | Model-call counter | Ten reloads leave the number of model calls unchanged | ⬜ |

**Gate M06b:** one page on the computer shows tasks and projects, with no model call.

#### M12 — Local calendar availability · study: D-C

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-061 | Add CalendarEvent model | Typed events | Task cannot parse as event | ⬜ |
| D2-062 | Normalise timezones | Local interval | DST test passes | ⬜ |
| D2-063 | Calculate busy intervals | Busy list | Manual result matches | ⬜ |
| D2-064 | Calculate free slots | Slot list | No fixed-event overlap | ⬜ |
| D2-064a | Read the real calendar read-only from the secret iCal address (in .env) — added 20 Oct | Real events as CalendarEvent | Secret scan passes; events match Google Calendar for one day | ⬜ |
| D2-064b | Expand recurring events over a bounded 14-day window — added 20 Oct | Expanded event list | A weekly event appears every week in the window and nowhere after it | ⬜ |

**Gate M12:** Dani derives availability from calendar facts. D2-065 is outside December.

#### M13 — Planner and replanner · study: D-D

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-066 | Mark fixed and movable blocks | Classified plan | Fixed block cannot move | ⬜ |
| D2-067 | Add duration, deadline and window constraints | Candidate placement | Violation fails | ⬜ |
| D2-067a | Daily capacity budget by cycle phase (full / low; low = half budget, low-energy tasks only) — added 18 Oct | Daily budget per date | On a low day the plan stays within half the budget, no high-energy task | ⬜ |
| D2-068 | Add replan_after_event | Before and after plan | Unaffected work stays | ⬜ |
| D2-069 | Add move, defer and ask outcomes | Overflow decisions | Nothing is silently dropped | ⬜ |
| D2-070 | Generate explanation after validation | Plan summary | Matches actual diff | ⬜ |

**Gate M13:** a new commitment safely replans only movable work.

### Sprint 5 (30 Nov–18 Dec) — M16 to M20 · study: D-E, F5, D-F, F7


#### M16 — MCP fundamentals

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-081 | Draw LLM host, MCP client and server | Architecture note | Giulia explains model location | ⬜ |
| D2-082 | Map read_tasks to MCP schema | Tool definition | Matches local contract | ⬜ |
| D2-083 | Run minimal local MCP server | Running server | List-tools succeeds | ⬜ |
| D2-084 | Discover tools from client | Tool inventory | Expected tool appears once | ⬜ |
| D2-085 | Call harmless tool through MCP | Structured result | Equals direct call | ⬜ |

**Gate M16:** Giulia explains the difference between function calling and MCP.

#### M17 — Task toolbox MCP server

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-086 | Expose read, prioritise and validate | MCP toolbox | Only intended tools appear | ⬜ |
| D2-087 | Separate read, propose and write capabilities | Proposal tool | Store remains unchanged | ⬜ |
| D2-088 | Require authority for writes | Denied write | Missing authority fails | ⬜ |
| D2-089 | Return structured domain errors | Tool error | Client distinguishes failures | ⬜ |
| D2-090 | Run MVP through MCP | Priority report | Shared contract tests pass | ⬜ |

**Gate M17:** migration to MCP changes boundary, not behaviour.


#### M18 — Supervisor using MCP

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-091 | Define SupervisorRequest | Structured goal | Ambiguity requests input | ⬜ |
| D2-092 | Load capability inventory | Tool snapshot | Unknown tool cannot run | ⬜ |
| D2-093 | Let LLM select MCP capability | Supervisor trace | Correct tool selected | ⬜ |
| D2-094 | Validate tool result before synthesis | Final result | Invalid result is withheld | ⬜ |
| D2-095 | Return one Dani response | Coherent answer | Internal protocol stays optional | ⬜ |

**Gate M18:** one supervisor completes the first MVP entirely through MCP.

#### M19 — Notion adapter

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-096 | Select test database and read-only scope | Scope record | Token cannot write | ⬜ |
| D2-097 | Save redacted provider fixture | Offline fixture | Parser works offline | ⬜ |
| D2-098 | Map Notion to Task and Project models | Domain objects | Shared tests pass | ⬜ |
| D2-099 | Add proposal, authority, write and read-back | Test page ID | Reread matches | ⬜ |
| D2-100 | Add idempotency | One page | Retry does not duplicate | ⬜ |

**Gate M19:** JSON and Notion satisfy the same contracts.

#### M20 — Google Calendar adapter

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| D2-101 | Connect read-only test calendar | Event list | Other calendars unavailable | ⬜ |
| D2-102 | Map provider event to Event model | Normalised events | Shared tests pass | ⬜ |
| D2-103 | Add freshness rule | Freshness status | Stale data blocks action | ⬜ |
| D2-104 | Create one authorised test event | Provider ID | Reread matches | ⬜ |
| D2-105 | Reconcile generated events idempotently | Clean calendar | Retry has no duplicates | ⬜ |

**Gate M20:** real availability and Dani-created writes are verified.

## Outside December

Not planned this semester. The full rows (D2-036 to D2-190) are in the Notion
page under "Outside December — all microphases". To pull one forward, copy its
row into the right milestone here first, then work on it.

| Milestones | IDs | What stays out |
|---|---|---|
| M07–M11 | D2-036–D2-060, D2-065 | Event stream, operational memory, recurring obligations, triggers, standing mandates |
| M14–M15 | D2-071–D2-080 | Autonomous project execution, proactive communication |
| M21–M27 | D2-106–D2-140 | Real recurring obligations, unexpected commitments on real data, email, purchases, web and travel |
| M28–M29 | D2-141–D2-150 | Memory governance, monitoring and recovery |
| M30–M33 | D2-151–D2-170 | Specialist agents, A2A, multi-agent cooperation |
| M34–M37 | D2-171–D2-190 | Voice and mobile, autonomous daily briefing, booking lifecycle, production and final proof |
| Front-end | — | Only the read-only dashboard of M06b is in scope |

## Global stop conditions

Stop and ask Giulia (and propose a Decision Log) if a change:

- adds more than one new concept to the active microphase;
- expands data, credentials, retention or authority;
- creates an MCP or A2A boundary;
- sends, books, renews, submits, cancels or pays without proven authority;
- cannot be externally verified;
- cannot be explained by Giulia after the session.
