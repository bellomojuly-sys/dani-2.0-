from tools import read_tasks


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
