# Test review — D2-020a

Study objective: **F1 — Testing.** This note is the visible output of microphase
D2-020a: a critical review of every test (what it proves, whether it fails when
the code is broken on purpose, what was missing), plus the weak tests fixed.

## Method

A good test fails for the right reason, checks one thing, is deterministic and
independent, and never calls the real API. We checked the suite three ways:

1. **Read each test** and wrote, in one line, what it proves.
2. **Coverage** (`pytest --cov --cov-branch`): every line and every branch of
   the product modules must be exercised.
3. **Mutation testing** (`mutmut`): the tool breaks the code on purpose, one
   change at a time, and runs the suite. A *survived* mutant is a break no test
   caught — i.e. a weak or missing test. We drove survivors to zero.

Mutation is the automated, exhaustive version of the Verify rule "a deliberate
break makes the right test fail": every mutant is a deliberate break.

## Result

| Measure | Before | After |
|---|---|---|
| Tests | 40 | 64 |
| Line coverage (tools, agent, answer, skill) | 97% | 100% |
| Branch coverage | — | 100% |
| Mutants killed / total | 291 / 342 | **342 / 342** |
| Mutants survived | 51 | **0** |

`main.py` is not covered or mutated: it is the real-API entry point (network +
secret key), so it is exercised by hand, not by unit tests. This boundary is
why the logic lives in `tools.py`, `agent.py`, `answer.py`, `skill.py`, which
are testable without the API.

### Reproduce

```bash
python3 -m pip install pytest pytest-cov mutmut
python3 -m pytest -q --cov=tools --cov=agent --cov=answer --cov=skill --cov-branch --cov-report=term-missing
mutmut run && mutmut results
```

`mutmut` writes a `mutants/` working copy; it is git-ignored. Remove it before
running pytest again (`rm -rf mutants`), or pytest reports a collection clash.

## What was weak, and why (the 51 survivors)

Three kinds of weakness were hiding behind "97% coverage" — proof that coverage
is not the same as quality:

1. **Values never pinned.** `read_tasks` was checked for *count* (three tasks)
   but never for *content*: breaking a task id or title survived. `prioritize_tasks`
   output rows were checked for order but not that each row still carries
   `title` and `reason`. → Added exact-value assertions.
2. **Refusal paths never reached.** Passing a non-dict to `prioritize_tasks` or
   `validate_priority_result`, a non-list `order`/`priority`, a row with a
   non-string id, and the `final_outcome` branch "read fine but never validated"
   were all untested — three of them were also the only uncovered lines. →
   Added one test per path.
3. **The request and the transcript never inspected.** The fake client ignored
   the `model`, `messages` and `tools` it received, and no test looked at the
   messages the loop feeds back to the model, the `final` key, or the default
   iteration cap (5). Mutations there survived. → The fake client now records
   its call; tests assert the request, the tool-result transcript, `final`, and
   the default cap.

Two last survivors were error-message mutants that slipped past an `in` check
(`"read_tasks"` is a substring of `"XXread_tasksXX"`). Fixed by asserting the
exact message, which also pins the error contract.

## Deliberate-break demonstration

Change the duplicate check in `validate_priority_result` from `> 1` to `> 2`
and run the suite: exactly `test_validate_priority_result_rejects_a_duplicate_id`
fails (`assert True is False`), nothing else. The right test, and only the right
test, catches the break.

## Every test, one line each

### test_tools.py — the three Python tools

| Test | What it proves |
|---|---|
| read_tasks_returns_three_tasks | read_tasks yields three tasks |
| read_tasks_returns_the_exact_mvp_tasks | the exact ids and titles are the MVP fixture |
| read_tasks_error_names_the_tool | a bad-args error message names read_tasks |
| read_tasks_accepts_empty_arguments | None and {} both count as "no arguments" |
| read_tasks_rejects_unexpected_arguments_with_structured_error | extra args return an error dict |
| read_tasks_rejects_non_dict_arguments_with_structured_error | a non-dict arg returns an error dict |
| wrong_arguments_do_not_return_an_invented_task_list | a refused call never returns the task list anyway |
| every_task_has_id_and_title | each task has an id and a title |
| task_ids_are_unique | task ids do not repeat |
| read_tasks_schema_describes_a_function_with_no_arguments | the schema declares no parameters |
| every_schema_name_has_a_matching_callable_in_the_toolbox | every advertised tool is a real callable |
| prioritize_tasks_returns_numbered_order | ranks come out 1,2,3 |
| prioritize_tasks_keeps_the_order_the_llm_decided | the LLM's order is preserved, not re-sorted |
| prioritize_tasks_row_carries_rank_id_title_and_reason | each output row keeps all four fields with the right values |
| prioritize_tasks_rejects_missing_order | a call with no `order` is refused |
| prioritize_tasks_rejects_empty_order | an empty `order` is refused |
| prioritize_tasks_rejects_item_without_reason | an item missing `reason` is refused |
| prioritize_tasks_rejects_non_dict_arguments | a non-dict argument is refused, not crashed on |
| prioritize_tasks_rejects_non_list_order | a non-list `order` is refused, not iterated |
| prioritize_tasks_rejects_non_dict_item | a non-dict item is refused before `.get()` |
| prioritize_tasks_rejects_non_string_id | a numeric id is refused |
| bad_order_does_not_return_a_priority_list | a refused call returns no priority list |
| prioritize_tasks_schema_has_an_order_parameter | the schema exposes the `order` parameter |
| validate_priority_result_accepts_a_complete_report | a complete, correct report is valid |
| validate_priority_result_rejects_a_missing_id | a missing id fails with "missing" |
| validate_priority_result_rejects_a_duplicate_id | a duplicate id fails with "duplicate" |
| validate_priority_result_rejects_an_invented_id | an unknown id fails with "unknown" |
| validate_priority_result_rejects_a_malformed_call | a call missing `known_ids` is a structured error, no verdict |
| validate_priority_result_rejects_non_dict_arguments | a non-dict argument is refused, not crashed on |
| validate_priority_result_rejects_non_list_priority | a non-list `priority` gives the exact "must both be lists" error |
| validate_priority_result_rejects_row_without_string_id | a row with a non-string id is malformed |
| validate_priority_result_rejects_non_list_known_ids | a non-list `known_ids` is malformed |
| validate_priority_result_schema_has_priority_and_known_ids | the schema exposes both parameters |

### test_agent.py — reading calls, running tools, the loop, the outcome

| Test | What it proves |
|---|---|
| read_tool_calls_names_the_requested_tool | a requested tool is read out with its name and args |
| read_tool_calls_is_empty_when_no_tool_requested | `tool_calls=None` means no calls |
| read_tool_calls_treats_missing_arguments_as_empty_dict | None/""/whitespace args parse to {} |
| read_tool_calls_parses_json_arguments | a JSON arg string is parsed to the matching dict |
| read_tool_calls_handles_a_message_without_the_attribute | a message with no tool_calls attribute gives [] |
| run_tool_call_executes_the_tool_exactly_once | the tool body runs once per call |
| run_tool_call_runs_the_real_read_tasks_tool | dispatch reaches the real read_tasks |
| run_tool_call_rejects_unknown_tool_with_structured_error | an unknown tool is a structured error, not a crash |
| tool_result_message_carries_the_three_real_titles | the tool message carries the real task titles |
| tool_result_message_does_not_contain_an_invented_title | the tool message contains no invented title |
| run_tool_loop_records_the_call_trace_in_order | the trace lists tools in call order and ends "answered" with a final message |
| run_tool_loop_stops_at_the_iteration_limit | past the cap the loop stops, trace length = cap, final is None |
| run_tool_loop_default_iteration_cap_is_five | with no cap given, the default cap is 5 |
| run_tool_loop_sends_the_model_messages_and_tools | the request carries the right model, the messages list, the schemas |
| run_tool_loop_feeds_each_tool_result_back_into_the_messages | each tool result returns as a `tool` message tied to the call id |
| full_run_covers_every_source_id_exactly_once | a full run validates and every source id appears once |
| honest_failure_when_the_task_source_fails | a source failure yields ok=False, no priority |
| no_fabricated_priority_after_a_source_failure | after a source failure no priority is presented, even if a bogus check passed |
| final_outcome_refuses_a_result_that_was_never_validated | a priority with no validation step is refused |
| final_outcome_does_not_treat_a_non_error_read_as_a_failure | a dict read result without an error key is not a source failure |
| final_outcome_validated_without_a_prioritize_entry_has_no_priority | validated but no prioritize → ok with priority None, no crash |
| final_outcome_refuses_when_validation_returned_false | a failed validation is refused with the right reason |

### test_answer.py — pydantic validation of the model reply

| Test | What it proves |
|---|---|
| valid_response_is_accepted | a well-formed JSON reply is accepted |
| missing_field_fails | a reply missing a field raises ValueError |
| plain_text_fails | non-JSON text raises ValueError |
| non_string_input_fails | a non-string input (TypeError inside) still raises ValueError |
| both_fields_are_parsed | both `answer` and `reason` are read back |
| error_message_is_explicit | the raised ValueError carries an explaining message |

### test_skill.py — the written tool-order policy

| Test | What it proves |
|---|---|
| skill_names_the_three_tools_in_the_right_order | the policy text names the tools in order |
| tool_order_covers_exactly_the_registered_tools | the declared order matches the registered tools |
| skill_forbids_inventing_tasks | the policy forbids inventing tasks |
