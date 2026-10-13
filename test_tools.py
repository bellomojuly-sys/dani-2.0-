from tools import read_tasks, READ_TASKS_SCHEMA, TOOL_SCHEMAS, TOOLS


def test_read_tasks_returns_three_tasks():
    tasks = read_tasks()
    assert len(tasks) == 3


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
