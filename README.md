# Dani 2.0

Dani 2.0 is my personal planning assistant, rebuilt from scratch. The first version (11 agents) became impossible for me to control, so this version grows one small, verifiable step at a time.

## Vision

**Final goal:** Dani is my own AI, trained on my needs and life goals. It organises my tasks, does the ones it can, writes and calls for me, keeps my shopping list, keeps me on track, and has a personality I can chat with.

**By 13 November 2026 (Sprint 3 demo):** a working app I can talk to, by text or voice (Whisper). Dani reads my plan (my Tasks in Notion) and all my Google calendars, follows my planning rules, and organises things for me ("move Thursday's call to 4 pm", "plan my free time on Wednesday", "new task: …"). It shows every change first and writes it only after my yes. The front-end is the PWA of the first Dani, reused (roadmap V5, 4 November 2026).

**By December 2026:** the same app, reliable on a real week: it respects all my rules, says what slips and how far when something moves, and an evaluation set proves it still works after every change.

**Why it is worth building:** an assistant that reads a company's own tools, follows its rules and asks before it writes is a service I can offer to small companies (MG Integration).

## First MVP (Sprint 2, 5–16 October 2026)

A terminal program where one LLM chooses between three Python tools and returns a validated answer to "what should I do first?".

- **Input:** three hardcoded tasks and the question "what should I do first?"
- **Output:** the task IDs in priority order, each with a one-line reason
- **Validation:** the answer is accepted only if every task ID appears exactly once and no ID is invented

## Scope confirmation

- The roadmap, split into "by December" and "outside December", has been shown to my teachers and accepted, on the condition that it stays feasible and that I present concrete results.
- Confirmation of the first MVP scope: planned for 8 October 2026. *To be updated with the dated feedback.*

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-10-07 | Provider: DeepSeek, model `deepseek-flash` | Cheapest option, I already have an account with credit, and it supports tool calls and JSON output, which the next steps need |
| 2026-10-07 | SDK: OpenAI Python SDK | The DeepSeek API is OpenAI-compatible (base URL `https://api.deepseek.com`) |
| 2026-10-07 | The API key is never written in the code | The key is read from the environment, so it cannot end up in the repository |
| 2026-10-13 | The agent may run `git commit` and `git push` | The repeated stop-hook reminder made the manual-commands flow slow; I keep one commit per microphase and can still ask for the commands when I want to type them myself |
| 2026-10-13 | Every tool takes one `arguments` dict and validates it at the top of its body, returning `{"error": ...}` on bad input | Keeps a single, predictable calling convention for all tools; a wrong call never crashes and never invents a result, and the structured error can be handed back to the LLM (D2-011a) |
| 2026-10-29 | Test quality is measured by mutation testing (target: no surviving non-equivalent mutants) and 100% line+branch coverage; `main.py`'s real decisions are refactored into tested functions while only its `__main__` wiring is excluded; dev-only tools live in `requirements-dev.txt` | Coverage alone passed at 97% while 51 mutants survived — mutation testing is what proves a test fails when the code is broken; testing `main.py`'s decisions (not just excluding the file) answers the teacher's point, and `mutate_only_covered_lines` keeps the untestable wiring out (D2-020a) |
| 2026-11-03 | Roadmap V4: connect my real Notion tasks first (M05), write the priority back (M06), and only then write a skill, measured against tool descriptions alone (M07); December scope cut to the planning product (Notion → free time → calendar); steps renumbered in build order | Ruud's feedback (3 Nov): the model picks a tool from its description, so a skill is worth adding only when a workflow is too complex for the plain prompt. V3 (190 steps) aimed at the final vision and left real data for December; V4 builds the product I use every day first. Old → new IDs in `docs/ROADMAP.md` |
| 2026-11-04 | Roadmap V5: a working chat app by 13 Nov — Notion, all my Google calendars, my rules in the system prompt, preview → yes → write, the first Dani's PWA as front-end, Whisper for voice, Render for hosting; the model does the planning, code checks it (overlaps, rules) and evaluations prove it | V4 delivered the thing I use every day only in mid-December, after a free-time algorithm and a memory layer. A system prompt with rules and a few typed tools already plans well in a chat; what needs engineering is the integrations, the safety of writes and the evaluation. Four Decision Logs to write during Sprint 3 are listed in `docs/ROADMAP.md` |
| 2026-11-05 | Direction towards V6: the main surface becomes a **dashboard** (PC + phone, like the first Dani) instead of a chat — opens in the morning, shows today/week, project timeline and areas of attention; for now only Notion + Google Calendar | Giulia wants to see her day at a glance, not only ask for it. M05 (Notion) and M06 (Calendar) are unchanged and stay the next work; M07–M09 are reworked as the dashboard UI at the Sprint 3 design review. Project timeline (needs the D-B project/dependency model) and mail (needs Gmail credentials → a new scope, so a stop condition needing a Decision Log and teacher awareness of feasibility) are proposed December targets after the dashboard core. Full V6 rewrite in `docs/ROADMAP.md` after the design review |
| 2026-11-03 | Trace redaction decides a field is sensitive by its NAME (explicit list: `api_key`, `token`, `secret`, `password`, `authorization`), not by scanning values, and hides it with the marker `[REDACTED]` instead of removing the field | By-name is deterministic, explainable in one sentence and easy to test; the marker keeps the trace reconstructable (Gate M04). The accepted limit — a secret under an innocent field name is not caught — is recorded, with value-pattern scanning left as a future roadmap row (D2-023; full text in `docs/DECISION-LOG-D2-023-redaction.md`) |

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="your-key"
python main.py
```

For the tests, coverage and mutation testing, install the dev tools too:
`pip install -r requirements-dev.txt`.

## Status

Full roadmap with every microphase: [`docs/ROADMAP.md`](docs/ROADMAP.md). Study objectives: [`docs/STUDY-PLAN.md`](docs/STUDY-PLAN.md). Active now: **D2-025 — Notion integration: `notion_client.py` reads my open tasks (M05)**.

| Step | What | State |
|---|---|---|
| D2-001 | New project created | Done |
| D2-002 | Vision recorded | Done |
| D2-003 | First MVP defined | Done |
| D2-004 | Scope confirmed by teacher | Planned 8 Oct |
| D2-005 | Clean Python repository | Done |
| D2-006 | Provider, model and SDK chosen | Done |
| D2-007 | First fixed request to the model | Done |
| D2-008 | Secret moved to the environment | Done |
| D2-009 | Minimal system and user messages | Done |
| D2-010 | Structured model response validated | Done |
| D2-011 | `read_tasks` returns three hardcoded tasks | Done |
| D2-011a | Tool validates its arguments, returns a structured error | Done |
| D2-012 | `read_tasks` described as a tool schema and registered in the toolbox | Done |
| D2-013 | The LLM requests `read_tasks`; the trace names the right tool | Done |
| D2-014 | The requested tool runs exactly once via the toolbox | Done |
| D2-015 | The tool result is returned to the LLM (three real titles, none invented) | Done |
| M02 | Gate: the full round LLM → tool → LLM works end to end | Done |
| D2-016 | `prioritize_tasks` returns a numbered priority report from the order the LLM decided | Done |
| D2-017 | `validate_priority_result` fails on missing, duplicate and invented ids | Done |
| D2-017a | Toolbox skill: written policy for the tool order read → prioritize → validate | Done |
| D2-018 | Bounded tool loop with an ordered call trace and an iteration cap | Done |
| D2-019 | Full "what should I do first?" run; every source id appears exactly once | Done |
| D2-020 | Simulated task-source failure: honest failure, no fabricated result | Done |
| M03 | Gate: one LLM selects three Python tools and returns a validated result | Done |
| D2-020a | Critical test review: `main.py` decisions tested, 100% coverage, 432/433 mutants killed (1 equivalent) | Done |
| D2-021 | Trace envelope: a run has a unique run ID and timestamps; every event shares the run ID | Done |
| D2-022 | Each trace event is a typed record of the tool call: name, arguments, status and duration | Done |
| D2-023 | `safe_trace` redacts sensitive fields by name (`[REDACTED]`), so a secret in a traced field is absent from the saved trace | Done |
| D2-024 | Typed `Task` model for my Notion tasks; `Area`/`Status` enums from the real Notion DB | Done |

## Traceability

Every closed microphase can be traced to one commit and checked from the terminal. Run a check with `python3 -m pytest -v -k "<selector>"`; open the commit with `git show <commit> --stat`.

| Step | Commit | Proof | Check in the terminal |
|---|---|---|---|
| D2-001 → D2-006 | `b74f59f` | README (vision, MVP, decisions) | `git show b74f59f --stat` |
| D2-007 | `2a0d23f` | Missing key gives "Missing DEEPSEEK_API_KEY" | run `python3 main.py` without `.env` |
| D2-008 | `75d461a` | Key only in `.env`, which git ignores | `git ls-files \| grep env` → only `.env.example` |
| D2-009 | `60634bc` | Only the system and user message are sent | `git show 60634bc` |
| D2-010 | `52ab164` | Valid answer passes; missing field and plain text fail | `-k "test_answer"` (3 tests) |
| D2-011 | `3e5b345` | Three tasks, each with id and title, ids unique | `-k "read_tasks_returns or every_task_has or task_ids_are_unique"` (3) |
| D2-011a | `a756c88`, `6447a97` | Wrong arguments return a structured error, never a task list | `-k "rejects_unexpected or rejects_non_dict or wrong_arguments"` (3) |
| D2-012 | `f860948` | Schema matches the function in the toolbox | `-k "read_tasks_schema or every_schema_name"` (2) |
| D2-013 | `5254892` | The trace names the tool the LLM requested | `-k "read_tool_calls"` (2) |
| D2-014 | `5bd7d7e` | The requested tool runs exactly once; unknown tool is refused | `-k "run_tool_call"` (3) |
| D2-015 | `6da6130` | The LLM gets the three real titles, none invented | `-k "tool_result_message"` (2) |
| D2-016 | `cda5ca0` | Numbered priority in the order the LLM decided | `-k "prioritize"` (6) |
| D2-017 | `4e40ec6` | Missing, duplicate and invented ids fail | `-k "validate_priority"` (6) |
| D2-017a | `42ebe5c` | Skill names the three tools in order and forbids invented tasks | `-k "test_skill"` (3) |
| D2-018 | `c97aa5e` | Ordered call trace; the loop stops at the iteration limit | `-k "run_tool_loop"` (2) |
| D2-019 | `7ee4b32` | Every source id appears exactly once | `-k "full_run"` (1); live: `python3 main.py` |
| D2-020 | `e308727` | Task source fails → honest failure, no priority invented | `-k "failure or fabricated"` (2) |
| D2-020a | `1600df5` | Test review note; `main.py` decisions tested, 100% line+branch coverage, 432/433 mutants killed (1 equivalent) | `docs/TEST-REVIEW-D2-020a.md`; `pytest --cov ... --cov-branch` and `mutmut run` |
| D2-021 | `a319f85` | A run has one run ID and timestamps; every event shares the run ID | `-k "trace"` (10) |
| D2-022 | `3696a21` | Each event is a typed TraceEvent (tool, arguments, status, duration); a malformed event is refused | `-k "trace"` (15) |
| D2-023 | `b1563af` | A fake key in a traced field is absent from `safe_trace`; `[REDACTED]` takes its place; a secret under an innocent name is deliberately not caught | `-k "redact or safe_trace or sensitive"` (6) |
| D2-024 | `5a32d61` | A valid task is accepted and typed; a missing or wrong field (empty title, unknown area/status, non-positive duration, bad date, unknown field name) fails with a clear error | `python3 -m pytest test_task.py` (15) |

All 107 tests: `python3 -m pytest -v`. The tests never call the real API; `python3 main.py` is the only live run.

Coverage and mutation testing (D2-020a) need the dev tools in
`requirements-dev.txt` (`pip install -r requirements-dev.txt`):

```bash
python3 -m pytest -q --cov=tools --cov=agent --cov=answer --cov=task --cov=skill --cov=tracing --cov-branch --cov-report=term-missing
mutmut run && mutmut results   # writes a git-ignored mutants/ dir; rm -rf mutants before pytest
```
