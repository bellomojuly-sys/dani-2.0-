import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOL_SCHEMAS
from agent import read_tool_calls, build_tool_result_message
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

# 1) First call: hand the LLM the toolbox and let it request a tool (D2-013).
response = client.chat.completions.create(
    model="deepseek-flash",
    messages=messages,
    tools=TOOL_SCHEMAS,
)
message = response.choices[0].message
messages.append(message)

calls = read_tool_calls(message)
print("The LLM requested:", [call["name"] for call in calls])

# 2) Run each requested tool once (D2-014) and return the result (D2-015).
for call in calls:
    result_message = build_tool_result_message(call)
    print("Tool result:", result_message["content"])
    messages.append(result_message)

# 3) Second call: the LLM answers using the real tool results.
final = client.chat.completions.create(
    model="deepseek-flash",
    messages=messages,
)
print("Dani says:", final.choices[0].message.content)
