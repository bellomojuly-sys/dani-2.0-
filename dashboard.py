"""Build ``dashboard.html``: Giulia's week from her real Notion tasks and her
real Google Calendars, with the LLM's verified priority and deterministic
study blocks.

This is the composition root of the dashboard, like main.py is for the
terminal run. The decisions are plain functions (testable without network or
API): which settings are required, how the real tasks are handed to the LLM,
in which order tasks are planned, and how the page is built. The wiring that
talks to the outside world (Notion, the calendar feeds, DeepSeek, the file) is
in ``run_dashboard`` and takes every outside piece as an argument, so a test
can pass fakes; only the ``__main__`` block builds the real ones.

    python3 dashboard.py          # real Notion + calendars (+ DeepSeek if key set)
    python3 dashboard.py --demo   # the saved fixtures instead of Notion/calendars
"""

import json
import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import OpenAI

from agent import final_outcome, run_tool_loop
from ical_client import read_calendars, split_urls
from models import AMSTERDAM
from notion_client import query_open_tasks, task_from_page
from planner import plan_study_blocks
from render import render_dashboard
from skill import TOOLBOX_SKILL
from tools import PRIORITIZE_TASKS_SCHEMA, READ_TASKS_SCHEMA, VALIDATE_PRIORITY_RESULT_SCHEMA
from tools import _check_no_arguments, prioritize_tasks, validate_priority_result
from tracing import end_run, start_run

DAYS_AHEAD = 7
OUTPUT_FILE = "dashboard.html"
REQUIRED = ("NOTION_TOKEN", "NOTION_TASKS_DB_ID", "GCAL_ICS_URL")

# The LLM's priority is sorted by these labels when there is no verified
# priority (fallback): earliest deadline first, then P1 before P2 before P3.
PRIORITY_RANK = {"P1 - Critical": 0, "P2 - Important": 1, "P3 - Nice to have": 2}


def load_settings(env=os.environ):
    """Return the settings, or {"error": ...} naming every missing variable.

    DEEPSEEK_API_KEY is optional here: without it the dashboard still shows
    tasks, events and blocks, honestly labelled "no verified priority".
    """
    missing = [name for name in REQUIRED if not env.get(name)]
    if missing:
        return {"error": "Missing in .env: " + ", ".join(missing)}
    return {
        "notion_token": env["NOTION_TOKEN"],
        "notion_database_id": env["NOTION_TASKS_DB_ID"],
        "ics_urls": split_urls(env["GCAL_ICS_URL"]),
        "deepseek_api_key": env.get("DEEPSEEK_API_KEY") or None,
    }


def make_read_tasks(tasks):
    """Return a ``read_tasks`` tool bound to the tasks already read from Notion.

    Same contract as tools.read_tasks (no arguments, structured error on bad
    input), but the data is real. The LLM sees each task's id, title and the
    planning fields; the id is the Notion page id, so validate_priority_result
    can check that every real task appears once and none is invented.
    """

    def read_tasks(arguments=None):
        error = _check_no_arguments("read_tasks", arguments)
        if error is not None:
            return error
        return [task.model_dump(mode="json") for task in tasks]

    return read_tasks


def build_messages(today, context=""):
    """The priority request. ``context`` is Giulia's own text from Settings
    (habits, rules): when it is not empty it becomes part of the system prompt."""
    about_giulia = f"\nWhat Giulia told you about herself and her rules:\n{context.strip()}\n" if context.strip() else ""
    return [
        {
            "role": "system",
            "content": (
                "You are Dani, a personal planning assistant. Today is "
                f"{today.isoformat()} ({today.strftime('%A')}).\n" + TOOLBOX_SKILL + "\n" + about_giulia +
                "Decide the order by deadline first, then by the priority label, then by "
                "whether the task is a next action. Keep each reason to one short line in Italian."
            ),
        },
        {"role": "user", "content": "Order my open tasks for this week, most important first."},
    ]


def ask_priority(client, tasks, today, context=""):
    """Run the bounded tool loop on the real tasks and return (outcome, run).

    If there is no client (no key) or the API fails, the outcome is an honest
    "not verified" and the dashboard still gets built.
    """
    tools = {
        "read_tasks": make_read_tasks(tasks),
        "prioritize_tasks": prioritize_tasks,
        "validate_priority_result": validate_priority_result,
    }
    schemas = [READ_TASKS_SCHEMA, PRIORITIZE_TASKS_SCHEMA, VALIDATE_PRIORITY_RESULT_SCHEMA]
    if client is None:
        run = end_run(start_run())
        return {"ok": False, "reason": "no DEEPSEEK_API_KEY", "priority": None}, run
    try:
        result = run_tool_loop(client, build_messages(today, context), schemas, model="deepseek-flash", tools=tools)
    except Exception as failure:  # the network or the provider, never our code
        run = end_run(start_run())
        return {"ok": False, "reason": f"model unavailable: {type(failure).__name__}", "priority": None}, run
    return final_outcome(result), result["run"]


def order_tasks(tasks, outcome):
    """Tasks in the verified priority order, or by deadline/label when none."""
    if outcome["ok"]:
        by_id = {task.id: task for task in tasks}
        return [by_id[row["id"]] for row in outcome["priority"] if row["id"] in by_id]
    return sorted(
        tasks,
        key=lambda task: (
            task.deadline is None,
            task.deadline or datetime.max.date(),
            PRIORITY_RANK.get(task.priority, 9),
            not task.next_action,
        ),
    )


def week_from(today):
    return [today + timedelta(days=offset) for offset in range(DAYS_AHEAD)]


def run_dashboard(today, fetch_tasks, fetch_events, client, write):
    """The whole run with every outside piece injected.

    fetch_tasks() -> [Task]; fetch_events(start, end) -> [Event];
    client -> the LLM client or None; write(html) -> saves the page.
    Returns a small summary dict (used by tests and printed by __main__).
    """
    days = week_from(today)
    tasks = fetch_tasks()
    events = fetch_events(days[0], days[-1] + timedelta(days=1))
    outcome, run = ask_priority(client, tasks, today)
    ordered = order_tasks(tasks, outcome)
    plan = plan_study_blocks(ordered, events, days)
    write(render_dashboard(today, days, tasks, events, plan, outcome, run))
    return {
        "tasks": len(tasks),
        "events": len(events),
        "blocks": len(plan["blocks"]),
        "unplaced": [task.title for task in plan["unplaced"]],
        "priority": outcome["ok"],
        "reason": outcome["reason"],
        "run_id": run.run_id,
    }


def demo_sources():
    """Fixture-backed fetchers for ``--demo``: no Notion, no calendar download."""
    with open("fixtures/notion_query.json") as handle:
        pages = json.load(handle)["results"]
    with open("fixtures/calendar.ics", "rb") as handle:
        ics = handle.read()
    fetch_tasks = lambda: [task_from_page(page) for page in pages]
    fetch_events = lambda start, end: read_calendars(["fixture"], start, end, fetch=lambda url: ics)
    return fetch_tasks, fetch_events


if __name__ == "__main__":  # pragma: no cover
    load_dotenv()
    demo = "--demo" in sys.argv
    today = datetime.now(AMSTERDAM).date()
    if demo:
        fetch_tasks, fetch_events = demo_sources()
        api_key = os.environ.get("DEEPSEEK_API_KEY")
    else:
        settings = load_settings()
        if "error" in settings:
            print(settings["error"])
            sys.exit(1)
        fetch_tasks = lambda: query_open_tasks(settings["notion_token"], settings["notion_database_id"])
        fetch_events = lambda start, end: read_calendars(settings["ics_urls"], start, end)
        api_key = settings["deepseek_api_key"]
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com") if api_key else None

    def write(html):
        with open(OUTPUT_FILE, "w") as handle:
            handle.write(html)

    summary = run_dashboard(today, fetch_tasks, fetch_events, client, write)
    print(f"{OUTPUT_FILE} written" + (" (demo data)" if demo else ""))
    for key, value in summary.items():
        print(f"  {key}: {value}")
