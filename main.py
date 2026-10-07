import os
import sys
from openai import OpenAI

api_key = os.environ.get("DEEPSEEK_API_KEY")

if api_key is None:
    print("Missing DEEPSEEK_API_KEY")
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-flash",
    messages=[
        {"role": "user", "content": "Say hello in one sentence."}
    ],
)

print(response.choices[0].message.content)
