import os, sys
from pathlib import Path
from google import genai

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = os.environ.get("ENV_FILE", str(BASE_DIR / ".env"))
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key and os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.strip().split("=", 1)[1]

client = genai.Client(api_key=api_key)

try:
    res = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input="1+1=?",
        generation_config={"thinking_level": "low"},
        store=False
    )
    print("Success with generation_config:", res.output_text)
except Exception as e:
    print("Failed with generation_config:", e)
