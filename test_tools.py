from tools import (
    read_tasks,
    prioritize_tasks,
    READ_TASKS_SCHEMA,
    PRIORITIZE_TASKS_SCHEMA,
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
