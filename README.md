# Dani 2.0

Dani 2.0 is my personal planning assistant, rebuilt from scratch. The first version (11 agents) became impossible for me to control, so this version grows one small, verifiable step at a time.

## Vision (by December 2026)

One supervisor LLM reaches my real tasks and my real calendar through an MCP toolbox, builds a feasible day, replans it when a commitment changes, and shows the plan in the front-end I already have.

Specialist agents, voice, proactive messages and a finished front-end design are outside the December scope.

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
| 2026-10-28 | Cover `main.py` by extracting its real decisions into testable functions (`require_api_key`, `format_report`, `run`) and marking only the real client-building wiring `# pragma: no cover`, instead of excluding the file | Chasing 100% on glue hides nothing useful, but `main.py`'s one real decision — fail loud on a missing key — deserves a test without ever calling the real API (D2-020a; full text in `docs/TEST-REVIEW-D2-020a.md`) |

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install openai
export DEEPSEEK_API_KEY="your-key"
python main.py
```

## Status

Full roadmap with every microphase: [`docs/ROADMAP.md`](docs/ROADMAP.md). Study objectives: [`docs/STUDY-PLAN.md`](docs/STUDY-PLAN.md). Active now: **D2-020a — critical review of every test**.

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
| D2-020a | Critical review of every test; refusal paths and `main.py` now tested | Done |

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
| D2-020a | `1db5f19` | Refusal paths tested; `main.py` decisions tested; 100% product coverage | `-k "not_validated or non_list or string_id or non_dict_row or require_api_key or format_report or run_uses"` (13) |

All 53 tests: `python3 -m pytest -v`. Coverage on the product code:
`python3 -m pytest --cov --cov-report=term-missing` (100%, config in `.coveragerc`;
needs `pip install pytest-cov`). The tests never call the real API; `python3 main.py`
is the only live run.
