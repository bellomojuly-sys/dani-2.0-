"""The five evaluation questions of gate M07 (D2-032), in one command.

Each case is a question Giulia would really ask, with the facts the answer
must contain. The facts come from the saved fixtures (the same week the demo
uses, 10-16 November 2026), so a right answer is checkable by a human and by
this script. A fact is a list of acceptable spellings: the answer passes the
fact when it contains any of them, case-insensitively.

    python3 evals.py        # asks the real model once per question

The command builds the prompt exactly like the dashboard chat (chat_reply on
Live.state), asks the model, checks the facts and prints PASS or FAIL per
case; the exit code is 0 only when all five pass. It needs DEEPSEEK_API_KEY
in ``.env`` and refuses clearly without it.

``run_evals`` takes the asking function as an argument, so the tests run the
whole harness with a fake model and never call the real API.
"""

from datetime import datetime

from models import AMSTERDAM

# The clock the fixtures were written for: a Tuesday with a lesson.
NOW = datetime(2026, 11, 10, 13, 21, 5, tzinfo=AMSTERDAM)
CONTEXT = "Niente studio la domenica. Max 7 ore di studio al giorno."

CASES = [
    {
        "question": "Che impegni ho oggi in calendario?",
        "facts": [["Lezione MA-AAI"]],
    },
    {
        "question": "Quando è la call con Ruud?",
        "facts": [["12 novembre", "12/11", "mercoledì", "2026-11-12"], ["15:00", "15.00", "alle 15", "le 15"]],
    },
    {
        "question": "Qual è il mio task più urgente?",
        "facts": [["Notion client"]],
    },
    {
        "question": "Entro quando devo prenotare il dentista?",
        "facts": [["20 novembre", "20/11", "2026-11-20"]],
    },
    {
        "question": "Che giorno è la demo dello Sprint 3?",
        "facts": [["13 novembre", "13/11", "venerdì", "2026-11-13"]],
    },
]


def check_answer(answer, facts):
    """Return the facts the answer misses (empty list = the answer passes)."""
    found = answer.casefold()
    return [spellings for spellings in facts if not any(one.casefold() in found for one in spellings)]


def run_evals(ask, cases=CASES):
    """Ask every question and check its facts. ``ask(question) -> answer``.

    Returns one row per case: question, answer, passed, missing.
    """
    results = []
    for case in cases:
        answer = ask(case["question"])
        missing = check_answer(answer, case["facts"])
        results.append(
            {"question": case["question"], "answer": answer, "passed": not missing, "missing": missing}
        )
    return results


def fixture_state():
    """The dashboard state built from the saved fixtures at the fixed clock."""
    from dashboard import demo_sources
    from live import Live
    from store import UserSettings

    fetch_tasks, fetch_events = demo_sources()
    live = Live(
        fetch_tasks,
        fetch_events,
        lambda tasks, today, context: {"ok": False, "reason": "evals run without the priority model", "priority": None},
        clock=lambda: NOW,
    )
    live.refresh("all")
    return live.state(UserSettings(context=CONTEXT))


def main():  # pragma: no cover - the command calls the real model on purpose
    import os
    import sys

    from dotenv import load_dotenv
    from openai import OpenAI

    from chat import chat_reply

    load_dotenv(".env")
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("DEEPSEEK_API_KEY is missing in .env: the evaluations ask the real model.")
        sys.exit(2)
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    state = fixture_state()
    results = run_evals(lambda question: chat_reply(client, CONTEXT, state, [], question))
    for row in results:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"{mark}  {row['question']}")
        if not row["passed"]:
            wanted = "; ".join(" / ".join(spellings) for spellings in row["missing"])
            print(f"      missing: {wanted}")
            print(f"      answer:  {row['answer']}")
    passed = sum(row["passed"] for row in results)
    print(f"{passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":  # pragma: no cover
    main()
