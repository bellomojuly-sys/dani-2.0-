# D2-020a — Critical review of every test

Microphase D2-020a asks three questions of every test: **what does it prove?**,
**does it fail when the code is broken on purpose?**, and **what is missing?**
This note records the answers, the weak/missing tests that were fixed, and the
mutation evidence. It closes the "Review" (Correzione) step of study objective
**F1 — Testing**; the oral Prova for F1 is still open.

## Method

- `python3 -m pytest -v` — all tests must pass.
- Coverage on the product code (`agent`, `answer`, `main`, `skill`, `tools`):
  `python3 -m pytest --cov --cov-report=term-missing` (config in `.coveragerc`).
- Mutation check: break one line on purpose, run the test that should catch it,
  confirm it fails, then restore and confirm all green again.

## What each test proves (one line each)

### answer.py (parse + validate the model's structured reply)
- `test_valid_response_is_accepted` — a well-formed JSON reply parses into a `DaniAnswer`.
- `test_missing_field_fails` — a reply missing `reason` raises `ValueError`, not silently accepted.
- `test_plain_text_fails` — non-JSON text raises `ValueError`.

### tools.py (the three typed tools and their schemas)
- `test_read_tasks_returns_three_tasks` — `read_tasks` returns the three MVP tasks.
- `test_read_tasks_accepts_empty_arguments` — `None` and `{}` both count as "no arguments".
- `test_read_tasks_rejects_unexpected_arguments_with_structured_error` — extra args → structured error.
- `test_read_tasks_rejects_non_dict_arguments_with_structured_error` — a non-dict arg → structured error.
- `test_wrong_arguments_do_not_return_an_invented_task_list` — a refusal is never the task list anyway.
- `test_every_task_has_id_and_title` — every task has an `id` and a `title`.
- `test_task_ids_are_unique` — task ids are unique.
- `test_read_tasks_schema_describes_a_function_with_no_arguments` — the schema matches the function.
- `test_every_schema_name_has_a_matching_callable_in_the_toolbox` — every advertised tool is really callable.
- `test_prioritize_tasks_returns_numbered_order` — ranks are 1,2,3 in the order given.
- `test_prioritize_tasks_keeps_the_order_the_llm_decided` — it does not reorder.
- `test_prioritize_tasks_rejects_missing_order` / `_empty_order` / `_item_without_reason` — the three malformed calls.
- `test_bad_order_does_not_return_a_priority_list` — a refusal is never a priority list.
- `test_prioritize_tasks_schema_has_an_order_parameter` — schema has `order`.
- `test_validate_priority_result_accepts_a_complete_report` — a complete report is valid.
- `test_validate_priority_result_rejects_a_missing_id` / `_duplicate_id` / `_invented_id` — the three wrong reports.
- `test_validate_priority_result_rejects_a_malformed_call` — missing keys → structured error, no verdict.
- `test_validate_priority_result_schema_has_priority_and_known_ids` — schema has both arguments.

### agent.py (read calls, run a tool, the bounded loop, the verified outcome)
- `test_read_tool_calls_names_the_requested_tool` — a requested tool is read out with its name and args.
- `test_read_tool_calls_is_empty_when_no_tool_requested` — no tool requested → empty list.
- `test_run_tool_call_executes_the_tool_exactly_once` — one call runs the tool exactly once.
- `test_run_tool_call_runs_the_real_read_tasks_tool` — dispatch reaches the real tool.
- `test_run_tool_call_rejects_unknown_tool_with_structured_error` — unknown tool → structured error, no crash.
- `test_tool_result_message_carries_the_three_real_titles` — the LLM gets the real titles.
- `test_tool_result_message_does_not_contain_an_invented_title` — no invented title leaks in.
- `test_run_tool_loop_records_the_call_trace_in_order` — the trace keeps the call order; status `answered`.
- `test_run_tool_loop_stops_at_the_iteration_limit` — the loop stops at the cap; status `stopped`.
- `test_full_run_covers_every_source_id_exactly_once` — a full run covers every id exactly once.
- `test_honest_failure_when_the_task_source_fails` — a source failure gives an honest refusal.
- `test_no_fabricated_priority_after_a_source_failure` — no fabricated priority survives a source failure.

### main.py (the composition root's real decisions)
- `test_require_api_key_returns_the_key_when_present` — a present key is returned.
- `test_require_api_key_reports_a_missing_key` — a missing key is reported, not guessed.
- `test_require_api_key_treats_an_empty_key_as_missing` — an empty key fails loud.
- `test_build_messages_is_system_then_user_with_the_skill` — only the intended system+user messages are built.
- `test_format_report_shows_the_validated_priority` — a verified run shows the priority and the plain-text answer.
- `test_format_report_shows_honest_failure_and_no_priority` — an unverified run shows the reason and no priority.
- `test_run_uses_the_injected_client_and_prints_the_validated_report` — a full run works through a fake client, never the real API.

## Weak and missing tests found and fixed

The review found **refusal paths with no test** — exactly what rule F1 forbids
("every check gets a test for the accepted case and one for each refusal").

| Gap (before) | Risk | Fix (test added) |
|---|---|---|
| `agent.py` `final_outcome`: the "result not validated" branch was never hit | an unverified priority could be presented as an answer and no test would notice | `test_outcome_refuses_when_the_result_was_not_validated`, `test_outcome_refuses_when_validation_returned_not_valid` |
| `tools.py` `validate_priority_result`: `priority`/`known_ids` not a list was never hit | a wrong-shaped call could crash later instead of a clean error | `test_validate_priority_result_rejects_non_list_priority`, `..._rejects_non_list_known_ids` |
| `tools.py` `validate_priority_result`: a priority row without a string id was never hit | a malformed row could be read as a valid report | `test_validate_priority_result_rejects_a_row_without_a_string_id`, `..._rejects_a_non_dict_row` |
| `main.py` had **no tests at all** (0% coverage) | the "missing key" guard and the "show a priority only if verified" rule were only checked by hand | `test_main.py` (7 tests), after the refactor in the Decision Log below |

After the fixes: **53 tests pass; product-code coverage is 100%** (target was 95%).

## Mutation evidence (a deliberate break fails the right test)

| Broken on purpose | Test that caught it |
|---|---|
| `final_outcome` never refuses an unvalidated result | `test_outcome_refuses_when_the_result_was_not_validated` + `..._validation_returned_not_valid` |
| `validate_priority_result` accepts a non-list `priority`/`known_ids` | `..._rejects_non_list_priority` + `..._rejects_non_list_known_ids` |
| `validate_priority_result` accepts a row without a string id | `..._rejects_a_row_without_a_string_id` + `..._rejects_a_non_dict_row` |
| `require_api_key` accepts an empty key | `test_require_api_key_treats_an_empty_key_as_missing` |
| `format_report` shows a priority even when not verified | `test_format_report_shows_honest_failure_and_no_priority` |
| `run` stops printing the report | `test_run_uses_the_injected_client_and_prints_the_validated_report` |

Each break was reverted and the full suite returned to green.

---

# [DL] How do we cover main.py without calling the real LLM?

Date: 2026-10-28 · Microphase: D2-020a · Study objective: F1 (Testing)

**Context** — Every logic module was at 100% coverage, but `main.py` sat at 0%.
The session goal was 95% coverage of the code. `main.py` is the composition
root: it wires already-tested pieces (`run_tool_loop`, `final_outcome`) and
talks to the outside world — it loads `.env`, builds the **real** DeepSeek
client and prints. The project rule is that tests never call the real API, so
`main.py` could not be covered as written.

**Options**
- **A — Refactor and test the real decisions.** Pull the two decisions
  `main.py` actually makes (fail loud on a missing key; show a priority only
  when it was verified) into plain functions (`require_api_key`,
  `format_report`, plus `build_messages`/`run`), test them with a fake client,
  and exclude only the thin client-building wiring under `__main__` with
  `# pragma: no cover`.
  *Pros:* honest coverage; the "missing key" behaviour (D2-007) and the output
  rule gain real automated tests; no API call. *Cons:* a small change to
  product code, not just to tests.
- **B — Exclude main.py from the coverage target.** Declare the entry-point
  script out of scope in `.coveragerc`; measure 95% on the logic modules only.
  *Pros:* no code change. *Cons:* the one file at 0% is simply hidden; the
  missing-key guard stays untested; it redefines "the code".

**Decision** — Option A.

**Why** — Chasing 100% on a glue file is the textbook reason "100% coverage is
not enough" (F1): it raises the number without raising confidence. But `main.py`
holds one genuine, previously untested decision — "if the key is missing, say
so and stop" — which is a loud-failure case worth a test (F5). Refactoring
isolates that decision from the un-testable wiring, so the test is honest and
the real client is never built in a test. Giulia chose A after we compared both.

**Consequences** — `main.py` now exposes `build_messages`, `require_api_key`,
`format_report` and `run(client, out=print)`; the real client is built only
under `if __name__ == "__main__":`, marked `# pragma: no cover`. New file
`test_main.py` (7 tests). New dev tooling: `pytest-cov` is used to measure
coverage (not yet added to `requirements.txt` — pending Giulia's approval, see
the closing note). It rules out "cover the file by calling the real API", which
the project forbids.

**Evidence** — this commit; `python3 -m pytest -v` (53 passed);
`python3 -m pytest --cov --cov-report=term-missing` → 100% on product code;
mutation table above.
