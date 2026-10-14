import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOL_SCHEMAS
from agent import run_tool_loop, final_outcome
from skill import TOOLBOX_SKILL

load_dotenv()

api_key = os.environ.get("DEEPSEEK_API_KEY")
if api_key is None:
    print("Missing DEEPSEEK_API_KEY")
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

messages = [
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

# Run the bounded tool loop: following the toolbox skill, the LLM reads the
# tasks, prioritises them and validates the result, then answers (D2-018).
result = run_tool_loop(client, messages, TOOL_SCHEMAS, model="deepseek-flash")

print("Tool call order:", [entry["name"] for entry in result["trace"]])

# Present the answer only if it was validated; never a bare guess (D2-019).
outcome = final_outcome(result)
if outcome["ok"]:
    print("Validated priority — what to do first:")
    for row in outcome["priority"]:
        print(f'  {row["rank"]}. {row["id"]} — {row["title"]} ({row["reason"]})')
else:
    print("No verified answer:", outcome["reason"])

if result["final"] is not None:
    print("Dani says:", result["final"].content)
