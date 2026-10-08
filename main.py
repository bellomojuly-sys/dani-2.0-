import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.environ.get("DEEPSEEK_API_KEY")
if api_key is None:
    print("Missing DEEPSEEK_API_KEY")
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

messages = [
    {"role": "system", "content": "You are Dani, a personal planning assistant. Answer in one or two sentences."},
    {"role": "user", "content": "What should I do first today?"},
]

print("Request summary:")
for message in messages:
    print(f"- {message['role']}: {message['content']}")
print()

response = client.chat.completions.create(model="deepseek-flash", messages=messages)
print(response.choices[0].message.content)
