import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOL_SCHEMAS
from agent import run_tool_loop, final_outcome
from skill import TOOLBOX_SKILL

# --- Testable logic -----------------------------------------------------------
# main.py is the composition root: it wires together pieces that are already
# tested (run_tool_loop, final_outcome) and talks to the outside world (the
# real DeepSeek client, stdin/stdout). We keep the two real DECISIONS it makes
# in plain functions below, so they can be tested without ever calling the API:
#   - require_api_key: fail loud and clear when the key is missing (D2-007);
#   - format_report:   how a finished run is presented to the user.
# The thin wiring that builds the real client and exits the process stays in
# the __main__ block, marked "no cover", because a test must never construct
# the real client or kill the test process.


def build_messages():
    """Return the initial system+user messages for the planning question.

    Kept as a function so the exact messages we send can be asserted in a test
    (only the intended messages, D2-009), not hidden inside module top-level.
    """
    return [
        {
            "role": "system",
            "content": (
                "You are Dani, a personal planning assistant.\n"
                + TOOLBOX_SKILL
                + "\nAfter the result is validated, tell the user in plain text what to do first and why."
            ),
        },
        {"role": "user", "content": "What should I do first today?"},
    ]


def require_api_key(env=os.environ):
    """Return the API key, or a structured 'missing key' signal.

    No print and no sys.exit here, so the check can be tested directly. The
    __main__ wrapper turns a missing key into the message and a non-zero exit.
    A missing key must fail loudly, never fall back to a fake or empty key.
    """
    key = env.get("DEEPSEEK_API_KEY")
    if not key:
        return {"error": "Missing DEEPSEEK_API_KEY"}
    return {"api_key": key}


def format_report(result):
    """Turn a loop result into the lines to show the user. No I/O, deterministic.

    The priority is shown ONLY if final_outcome verified it; otherwise we show
    the honest reason and no priority (D2-019, D2-020). This is pure string
    building, so a test can check exactly what the user would see.
    """
    lines = ["Tool call order: " + str([entry["name"] for entry in result["trace"]])]

    outcome = final_outcome(result)
    if outcome["ok"]:
        lines.append("Validated priority — what to do first:")
        for row in outcome["priority"]:
            lines.append(f'  {row["rank"]}. {row["id"]} — {row["title"]} ({row["reason"]})')
    else:
        lines.append("No verified answer: " + outcome["reason"])

    if result["final"] is not None:
        lines.append("Dani says: " + result["final"].content)
    return lines


def run(client, out=print):
    """Run the bounded tool loop with a given client and print the report.

    The client is passed in, so a test can hand in a fake client (no network)
    and capture the output through `out`. The real client is built only in the
    __main__ wrapper below.
    """
    result = run_tool_loop(client, build_messages(), TOOL_SCHEMAS, model="deepseek-flash")
    for line in format_report(result):
        out(line)
    return result


# --- Real wiring: builds the real client and runs once ------------------------
if __name__ == "__main__":  # pragma: no cover
    load_dotenv()
    auth = require_api_key()
    if "error" in auth:
        print(auth["error"])
        sys.exit(1)
    client = OpenAI(api_key=auth["api_key"], base_url="https://api.deepseek.com")
    run(client)
