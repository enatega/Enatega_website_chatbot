# rewrite_texts.py
import os, pathlib
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

CLEAN_DIR = pathlib.Path("data/clean")

def rewrite_text(text: str, filename: str) -> str:
    """Send text to OpenAI for structured rewriting (headings + paragraphs)."""
    prompt = f"""
You are a careful rewriting assistant.
Your task is to restructure the following text into clean headings and paragraphs.

⚠️ Rules:
- Do NOT add any new information, numbers, or claims.
- If text is already structured, keep it as it is.
- Dont add meaningless headings like "Case Studies", "Use Cases", "Documentation", "Blog", "Features", "Pricing", "Get A Quote".
- Text should be meaningful so relevant chunks can be made.
- Do NOT hallucinate or invent content.
- Only rewrite what is present.
- Organize into logical sections with headings and paragraphs.
- Maintain factual consistency.

Here is the text (from {filename}):
{text}
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a precise rewriting assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content.strip()

def main():
    files = sorted(
        p for p in CLEAN_DIR.glob("*.txt")
        if p.name not in {"chunks_all.txt", "chunks_enatega_home.txt"}
    )

    for f in files:
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            print(f"Skip {f.name}: empty file.")
            continue

        print(f"Rewriting {f.name} …")
        rewritten = rewrite_text(text, f.name)

        # Overwrite the same file
        f.write_text(rewritten, encoding="utf-8")
        print(f" → Updated {f.name} with rewritten version.")

if __name__ == "__main__":
    main()
