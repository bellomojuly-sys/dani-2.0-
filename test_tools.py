from tools import (
    read_tasks,
    prioritize_tasks,
    validate_priority_result,
    READ_TASKS_SCHEMA,
    PRIORITIZE_TASKS_SCHEMA,
    VALIDATE_PRIORITY_RESULT_SCHEMA,
    TOOL_SCHEMAS,
    TOOLS,
)


def _valid_order():
    return {"order": [
        {"id": "t2", "title": "Study MCP", "reason": "needed next"},
        {"id": "t1", "title": "Finish the AMEXIO case model", "reason": "deadline"},
        {"id": "t3", "title": "Answer the email", "reason": "quick"},
    ]}


def test_read_tasks_returns_three_tasks():
    tasks = read_tasks()
    assert len(tasks) == 3


def test_read_tasks_returns_the_exact_mvp_tasks():
    # Pin the actual fixture content (ids and titles), so a change to any
    # task value is caught, not only the count.
    assert read_tasks() == [
        {"id": "t1", "title": "Finish the AMEXIO case model"},
        {"id": "t2", "title": "Study MCP"},
        {"id": "t3", "title": "Answer the email from my teacher"},
    ]


def test_read_tasks_error_names_the_tool():
    # The structured error must name the tool it came from, at the start of the
    # message (an exact prefix, so a wrapped/altered name is caught).
    result = read_tasks({"x": 1})
    assert result["error"].startswith("read_tasks takes no arguments")


def test_read_tasks_accepts_empty_arguments():
    # "No arguments" may arrive as None or as an empty dict {}.
    assert len(read_tasks(None)) == 3
    assert len(read_tasks({})) == 3


def test_read_tasks_rejects_unexpected_arguments_with_structured_error():
    result = read_tasks({"task_id": "t1"})
    assert isinstance(result, dict)
    assert "error" in result


def test_read_tasks_rejects_non_dict_arguments_with_structured_error():
    result = read_tasks("oops")
    assert isinstance(result, dict)
    assert "error" in result


def test_wrong_arguments_do_not_return_an_invented_task_list():
    # The refusal must be a structured error, never the tasks anyway.
    result = read_tasks({"task_id": "t1"})
    assert not isinstance(result, list)


def test_every_task_has_id_and_title():
    tasks = read_tasks()
    for task in tasks:
        assert "id" in task
        assert "title" in task


def test_task_ids_are_unique():
    tasks = read_tasks()
    ids = [task["id"] for task in tasks]
    assert len(ids) == len(set(ids))


def test_read_tasks_schema_describes_a_function_with_no_arguments():
    assert READ_TASKS_SCHEMA["type"] == "function"
    assert READ_TASKS_SCHEMA["function"]["name"] == "read_tasks"
    assert READ_TASKS_SCHEMA["function"]["parameters"]["properties"] == {}


def test_every_schema_name_has_a_matching_callable_in_the_toolbox():
    for schema in TOOL_SCHEMAS:
        name = schema["function"]["name"]
        assert name in TOOLS
        assert callable(TOOLS[name])


def test_prioritize_tasks_returns_numbered_order():
    result = prioritize_tasks(_valid_order())
    ranks = [row["rank"] for row in result["priority"]]
    assert ranks == [1, 2, 3]


def test_prioritize_tasks_keeps_the_order_the_llm_decided():
    result = prioritize_tasks(_valid_order())
    assert result["priority"][0]["id"] == "t2"
    assert result["priority"][1]["id"] == "t1"
    assert result["priority"][2]["id"] == "t3"


def test_prioritize_tasks_row_carries_rank_id_title_and_reason():
    # The output row must keep every field, each tied to the right value.
    result = prioritize_tasks(_valid_order())
    assert result["priority"][0] == {
        "rank": 1,
        "id": "t2",
        "title": "Study MCP",
        "reason": "needed next",
    }


def test_prioritize_tasks_rejects_missing_order():
    result = prioritize_tasks({})
    assert isinstance(result, dict)
    assert "error" in result


def test_prioritize_tasks_rejects_empty_order():
    result = prioritize_tasks({"order": []})
    assert "error" in result


def test_prioritize_tasks_rejects_item_without_reason():
    result = prioritize_tasks({"order": [{"id": "t1", "title": "No reason here"}]})
    assert "error" in result


def test_bad_order_does_not_return_a_priority_list():
    result = prioritize_tasks({"order": []})
    assert "priority" not in result


def test_prioritize_tasks_schema_has_an_order_parameter():
    properties = PRIORITIZE_TASKS_SCHEMA["function"]["parameters"]["properties"]
    assert "order" in properties


def test_validate_priority_result_accepts_a_complete_report():
    result = validate_priority_result(
        {"priority": [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}], "known_ids": ["t1", "t2", "t3"]}
    )
    assert result == {"valid": True}


def test_validate_priority_result_rejects_a_missing_id():
    result = validate_priority_result(
        {"priority": [{"id": "t1"}, {"id": "t2"}], "known_ids": ["t1", "t2", "t3"]}
    )
    assert result["valid"] is False
    assert "missing" in result["error"]


def test_validate_priority_result_rejects_a_duplicate_id():
    result = validate_priority_result(
        {"priority": [{"id": "t1"}, {"id": "t1"}, {"id": "t2"}], "known_ids": ["t1", "t2"]}
    )
    assert result["valid"] is False
    assert "duplicate" in result["error"]


def test_validate_priority_result_rejects_an_invented_id():
    result = validate_priority_result(
        {"priority": [{"id": "t1"}, {"id": "t9"}], "known_ids": ["t1", "t2"]}
    )
    assert result["valid"] is False
    assert "unknown" in result["error"]


def test_validate_priority_result_rejects_a_malformed_call():
    result = validate_priority_result({"priority": [{"id": "t1"}]})
    assert "error" in result
    assert "valid" not in result


def test_validate_priority_result_schema_has_priority_and_known_ids():
    properties = VALIDATE_PRIORITY_RESULT_SCHEMA["function"]["parameters"]["properties"]
    assert "priority" in properties
    assert "known_ids" in properties


# --- D2-020a: tests added to cover the refusal paths left untested -----------

def test_prioritize_tasks_rejects_non_dict_arguments():
    # A non-dict argument must be a structured error, not a crash.
    result = prioritize_tasks("oops")
    assert isinstance(result, dict)
    assert "error" in result
    assert "priority" not in result


def test_prioritize_tasks_rejects_non_list_order():
    # 'order' present but not a list: refuse, do not iterate over it.
    result = prioritize_tasks({"order": "t1,t2"})
    assert "error" in result
    assert "priority" not in result


def test_prioritize_tasks_rejects_non_dict_item():
    # An item that is not a dict must be refused before .get() is called.
    result = prioritize_tasks({"order": [123]})
    assert "error" in result
    assert "priority" not in result


def test_prioritize_tasks_rejects_non_string_id():
    # id/title/reason must all be strings; a numeric id is refused.
    bad = {"order": [{"id": 1, "title": "t", "reason": "r"}]}
    result = prioritize_tasks(bad)
    assert "error" in result
    assert "priority" not in result


def test_validate_priority_result_rejects_non_dict_arguments():
    # A non-dict argument must not crash: structured error, no verdict.
    result = validate_priority_result(None)
    assert isinstance(result, dict)
    assert "error" in result
    assert "valid" not in result


def test_validate_priority_result_rejects_non_list_priority():
    # 'priority' must be a list; a string is a malformed call.
    result = validate_priority_result({"priority": "t1", "known_ids": ["t1"]})
    assert result["error"] == "'priority' and 'known_ids' must both be lists"
    assert "valid" not in result


def test_validate_priority_result_rejects_row_without_string_id():
    # Each priority row must carry a string id; a numeric id is malformed.
    result = validate_priority_result({"priority": [{"id": 1}], "known_ids": ["t1"]})
    assert "error" in result
    assert "valid" not in result


def test_validate_priority_result_rejects_non_list_known_ids():
    # 'known_ids' must be a list too, not just 'priority'.
    result = validate_priority_result({"priority": [{"id": "t1"}], "known_ids": "t1"})
    assert "error" in result
    assert "valid" not in result
