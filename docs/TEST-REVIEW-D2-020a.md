# Test review — D2-020a

Critical review of every test in Dani 2.0, closing microphase **D2-020a**
(study objective **F1 — Testing**).

For each test we asked three questions:

1. **What does it prove**, in one sentence?
2. **Deliberate break (mutation):** break on purpose the line that test should
   protect — does the right test fail?
3. **Classify:** good / weak / missing.

Method: a mutation harness applied one tiny break at a time to the production
code (`tools.py`, `agent.py`, `answer.py`, `skill.py`), ran the test(s) that
should catch it, and restored the file. A break that leaves the targeted test
green is a *surviving* mutation — the test did not really protect that
behaviour. Nothing in the harness is committed; it only edits working copies
and restores them with `git checkout`.

Result: **26 mutations applied, 25 killed, 1 survived.** Reading the code then
found **4 untested branches** (missing cases). One weak test was strengthened
and four tests were added. Final suite: **43 tests green**, every fixed/added
test verified to fail under a truly-breaking mutation.

## tools.py — read_tasks

| Test | What it proves | Break used | Verdict |
|---|---|---|---|
| `test_read_tasks_returns_three_tasks` | `read_tasks` returns exactly the three MVP tasks | return only 2 tasks | ✅ good |
| `test_read_tasks_accepts_empty_arguments` | "no arguments" is accepted as both `None` and `{}` | (covered with the guard mutation below) | ✅ good |
| `test_read_tasks_rejects_unexpected_arguments_with_structured_error` | a non-empty argument dict is refused with a structured error | remove the argument guard | ✅ good |
| `test_read_tasks_rejects_non_dict_arguments_with_structured_error` | a non-dict argument is refused with a structured error | remove the argument guard | ✅ good |
| `test_wrong_arguments_do_not_return_an_invented_task_list` | a wrong call never returns the task list anyway | remove the argument guard | ✅ good |
| `test_every_task_has_id_and_title` | every task carries both `id` and `title` | drop a title | ✅ good |
| `test_task_ids_are_unique` | the three ids are distinct | duplicate an id | ✅ good |

## tools.py — prioritize_tasks

| Test | What it proves | Break used | Verdict |
|---|---|---|---|
| `test_prioritize_tasks_returns_numbered_order` | each kept task gets a rank 1, 2, 3 in sequence | set every rank to 0 | ✅ good |
| `test_prioritize_tasks_keeps_the_order_the_llm_decided` | the tool does not reorder; it keeps the order the LLM sent | sort the order by id | ✅ good |
| `test_prioritize_tasks_rejects_missing_order` | a call without `order` is a structured error | accept a missing `order` | ✅ good |
| `test_prioritize_tasks_rejects_empty_order` | an empty `order` list is a structured error | accept an empty list | ✅ good |
| `test_bad_order_does_not_return_a_priority_list` | a bad call never returns a `priority` list | accept an empty list | ✅ good |
| `test_prioritize_tasks_rejects_item_without_reason` | an item missing `reason` is refused | drop `reason` from the required keys | ✅ good (note: break fails via crash on `item["reason"]`, not via the `assert`; the guard and the use are coupled) |
| `test_prioritize_tasks_rejects_non_dict_arguments_with_structured_error` | `None`/str/list arguments give a structured error, never a crash | remove the `isinstance(dict)` guard → `prioritize_tasks(None)` crashes | 🟢 **added in D2-020a** (gap: whole suite stayed green without the guard) |

## tools.py — validate_priority_result

| Test | What it proves | Break used | Verdict |
|---|---|---|---|
| `test_validate_priority_result_accepts_a_complete_report` | a correct report returns `{"valid": True}` | always return invalid | ✅ good |
| `test_validate_priority_result_rejects_a_missing_id` | a report missing a known id is invalid, reason "missing" | disable the missing check | ✅ good |
| `test_validate_priority_result_rejects_a_duplicate_id` | a repeated id is invalid, reason "duplicate" | disable the duplicate check | ✅ good |
| `test_validate_priority_result_rejects_an_invented_id` | an id not among the real tasks is invalid, reason "unknown" | disable the invented-id check | ✅ good |
| `test_validate_priority_result_rejects_a_malformed_call` | a call missing `priority`/`known_ids` is a structured error, no verdict | stop requiring `known_ids` | ✅ good |
| `test_validate_priority_result_rejects_non_list_fields` | `known_ids` as a string (with a valid priority) is a malformed call, not a verdict | remove the list guard → string is iterated into a `valid:false` | 🟢 **added in D2-020a** (gap: the list guard had no test) |
| `test_validate_priority_result_rejects_a_row_without_a_string_id` | a priority row whose `id` is not a string is a structured error | remove the row-id guard | 🟢 **added in D2-020a** (gap: the row-id guard had no test) |

## tools.py — schemas

| Test | What it proves | Break used | Verdict |
|---|---|---|---|
| `test_read_tasks_schema_describes_a_function_with_no_arguments` | the `read_tasks` schema declares no parameters | add a property | ✅ good |
| `test_every_schema_name_has_a_matching_callable_in_the_toolbox` | every schema name maps to a real callable tool | rename a schema's function name | ✅ good |
| `test_prioritize_tasks_schema_has_an_order_parameter` | the `prioritize_tasks` schema exposes an `order` parameter | rename `order` | ✅ good |
| `test_validate_priority_result_schema_has_priority_and_known_ids` | the `validate` schema exposes `priority` and `known_ids` | rename `known_ids` | ✅ good |

## agent.py

| Test | What it proves | Break used | Verdict |
|---|---|---|---|
| `test_read_tool_calls_names_the_requested_tool` | a requested tool is read out as `{id, name, arguments}` | make it always return `[]` | ✅ good |
| `test_read_tool_calls_is_empty_when_no_tool_requested` | no tool request → empty list | (symmetric to the above) | ✅ good |
| `test_run_tool_call_executes_the_tool_exactly_once` | one call runs the tool exactly once (no loop, no retry) | run the tool twice | ✅ good |
| `test_run_tool_call_runs_the_real_read_tasks_tool` | dispatch by name reaches the real `read_tasks` | return a wrong count | ✅ good |
| `test_run_tool_call_rejects_unknown_tool_with_structured_error` | an unknown tool name is a structured error, not a crash | stop returning the error (fall through) | ✅ good |
| `test_tool_result_message_carries_the_three_real_titles` | the tool-result message carries exactly the real titles, in order | drop a real title | ✅ good |
| `test_tool_result_message_does_not_contain_an_invented_title` | no title outside the real set appears, whatever the string | add an invented title | ⚠️ **was weak → strengthened in D2-020a** |
| `test_run_tool_loop_records_the_call_trace_in_order` | the trace records tool calls in the order they ran | insert trace entries at the front | ✅ good |
| `test_run_tool_loop_stops_at_the_iteration_limit` | the loop stops at `max_iterations` (safety cap) | raise the range past the cap | ✅ good |
| `test_full_run_covers_every_source_id_exactly_once` | a full run returns every source id exactly once | (integration; covered by the unit breaks above) | ✅ good |
| `test_honest_failure_when_the_task_source_fails` | a source failure gives `ok:false`, reason, and no priority | ignore the source-failure short-circuit | ✅ good |
| `test_no_fabricated_priority_after_a_source_failure` | even a bogus pass after a source failure yields no priority | ignore the source-failure short-circuit | ✅ good |

## answer.py

| Test | What it proves | Break used | Verdict |
|---|---|---|---|
| `test_valid_response_is_accepted` | a complete JSON response parses **both** `answer` and `reason` | parse but blank `reason` | ⚠️ **was weak (checked only `answer`) → strengthened in D2-020a** |
| `test_missing_field_fails` | a response missing `reason` raises `ValueError` | make `reason` optional | ✅ good |
| `test_plain_text_fails` | non-JSON plain text raises `ValueError` | swallow the parse error | ✅ good |

## skill.py

| Test | What it proves | Break used | Verdict |
|---|---|---|---|
| `test_skill_names_the_three_tools_in_the_right_order` | the policy text names the three tools in `read → prioritize → validate` order | reorder `TOOL_ORDER` | ✅ good |
| `test_tool_order_covers_exactly_the_registered_tools` | `TOOL_ORDER` is exactly the set of registered tools | drop a tool from `TOOL_ORDER` | ✅ good |
| `test_skill_forbids_inventing_tasks` | the policy forbids inventing a task | remove "never invent" | ✅ good |

## What changed

Weak tests strengthened (now fail under a truly-breaking mutation):

- `test_valid_response_is_accepted` — now asserts `reason` too, not only `answer`.
- `test_tool_result_message_does_not_contain_an_invented_title` — now asserts
  every returned title is in the real set (subset), instead of checking one
  hardcoded string.

Missing tests added (each pins a guard that no test touched):

- `test_prioritize_tasks_rejects_non_dict_arguments_with_structured_error`
- `test_validate_priority_result_rejects_non_list_fields`
- `test_validate_priority_result_rejects_a_row_without_a_string_id`

## How to reproduce

- Full suite: `python3 -m pytest -v` → 43 passed.
- One deliberate break, by hand: edit the line named in the "Break used" column,
  run `python3 -m pytest -q -k "<test name fragment>"`, confirm it fails, then
  `git checkout -- <file>` to restore.
