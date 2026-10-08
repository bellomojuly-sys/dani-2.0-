import os
import sys
from dotenv import load_dotenv
from openai import OpenAI
from answer import parse_answer

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
            "You are Dani, a personal planning assistant. "
            "Reply only with a JSON object with two keys: "
            '"answer" (what to do first, one sentence) and "reason" (why, one sentence). '
            'Example: {"answer": "Finish the report", "reason": "It is due today"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "I have three tasks today: finish the AMEXIO case model, "
            "study MCP, answer an email from my teacher. What should I do first?"
        ),
    },
]

print("Request summary:")
for message in messages:
    print(f"- {message['role']}: {message['content']}")
print()

response = client.chat.completions.create(
    model="deepseek-flash",
    messages=messages,
    response_format={"type": "json_object"},
)

raw = response.choices[0].message.content
print("Raw response:", raw)
print()

try:
    result = parse_answer(raw)
except ValueError as error:
    print(error)
    sys.exit(2)

print("First:", result.answer)
print("Why:", result.reason)
