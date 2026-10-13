# Instructions for AI coding agents — Dani 2.0

Dani 2.0 is Giulia Bellomo's personal planning assistant, rebuilt from scratch for her Fontys MA-AAI portfolio. The first version (11 agents) became impossible to control and explain, so this version grows **one small, verifiable microphase at a time**.

Read `README.md` first: it holds the vision, the first MVP, the decisions taken and the status table.

## The current product

The first MVP is a terminal program where **one LLM chooses between at most three ordinary Python tools** and returns a validated answer to "what should I do first?".

- Input: three hardcoded tasks (later a local `tasks.json`).
- Output: the task IDs in priority order, each with a one-line reason.
- Validation: accepted only if every task ID appears exactly once and no ID is invented.

Provider: DeepSeek, model `deepseek-flash`, through the OpenAI Python SDK with `base_url="https://api.deepseek.com"`. Responses are parsed into pydantic models (`answer.py`).

## Scope rules

- The roadmap uses microphase IDs `D2-001` … `D2-190`. Giulia tells you which one is active. **Build only that one.** A new idea goes into a note for a later phase, not into the code.
- One new concept per microphase.
- Python first. One agent. Maximum three tools in the first MVP.
- Not in the MVP: web interface, cloud deployment, database, Notion, Google Calendar, voice, specialist agents, MCP. They come later, behind the same tool contracts.
- Tools are typed Python functions that work and are tested on their own before they are exposed to the LLM.
- Actions with money, bookings, cancellations or external messages are always ask-first.

## How Giulia wants to work

1. **She must understand everything.** She has to explain each mechanism to her teachers without reading generated text. Answer in Italian; code, comments, tests, README and commit messages are in English.
2. **Repetitive work: she writes the first two.** When a task repeats the same structure (for example a new tool function with its test, or a new message type), guide her step by step through the first two items of that kind. Only after she writes explicitly "ok, ho capito la logica" (or similar) do you write the remaining items yourself.
3. **Commits and pushes.** Since 2026-10-13 Giulia has authorized the agent to run `git commit` and `git push` on her behalf (see the Decision Log in `README.md`). Keep one commit per microphase and start every commit message with the microphase ID: `D2-011: <what changed>`. Giulia can still ask for the commands instead of a commit at any time.
4. A microphase is done only when: it has one visible output, an explicit check passes, and she can explain the mechanism. Update the status table in `README.md` when a microphase closes.

## Code rules

- **The API key is never written in code or committed.** It is read from the environment (`.env`, loaded with `python-dotenv`). `.env` stays in `.gitignore`; `.env.example` shows the variable name only.
- Every model response is validated with pydantic before it is used. An invalid response raises a clear `ValueError`; it is never silently accepted.
- **Tests never call the real API.** Test parsing, validation and tool functions with fixed strings or a fake client. Run `python3 -m pytest -v` before saying a step is done; all tests must pass.
- Every new check gets a test for the accepted case and one for each refusal.
- Keep files small and named after what they do (`answer.py`, `tools.py`, …). No framework until a microphase asks for one.

## Stop and ask Giulia before you

- add a dependency to `requirements.txt`;
- change the provider, the model or the SDK;
- add a fourth tool, a second agent, or anything listed as "not in the MVP";
- make a choice that could become a Decision Log (a design choice where another option would change the outcome of the project).
