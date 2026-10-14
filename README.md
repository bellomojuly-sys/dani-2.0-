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

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install openai
export DEEPSEEK_API_KEY="your-key"
python main.py
```

## Status

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
