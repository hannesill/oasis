"""Quick test: verify OpenAI API key works."""
import os

key = os.environ.get("OPENAI_API_KEY", "")
if not key:
    print("[FAIL] OPENAI_API_KEY is not set.")
    print('Run:  $env:OPENAI_API_KEY = "sk-proj-..."')
    exit(1)

print(f"[OK] OPENAI_API_KEY is set ({key[:8]}...{key[-4:]})")

from openai import OpenAI

client = OpenAI()

try:
    resp = client.chat.completions.create(
        model=os.environ.get("OASIS_LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": "Say hello in one word."}],
        max_tokens=5,
    )
    print(f"[OK] Model: {resp.model}")
    print(f"[OK] Response: {resp.choices[0].message.content}")
    print(f"[OK] Tokens used: {resp.usage.total_tokens}")
    print("\nOpenAI connection is working!")
except Exception as e:
    print(f"[FAIL] API call failed: {e}")
    exit(1)

