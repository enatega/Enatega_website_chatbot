# chunking.py
import pathlib, json, re
from typing import List
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter

BASE_DOMAIN = "enatega.com"
BASE_URL = f"https://{BASE_DOMAIN}/"

CLEAN_DIR = pathlib.Path("data/clean")
RAW_DIR = pathlib.Path("data/raw")

OUT_TXT = CLEAN_DIR / "chunks_all.txt"
OUT_JSONL = CLEAN_DIR / "chunks_all.jsonl"

USE_TOKENS = True
TOKEN_CHUNK_SIZE = 700
TOKEN_CHUNK_OVERLAP = 150

CHAR_CHUNK_SIZE = 4000
CHAR_CHUNK_OVERLAP = 500

# optional: skip empty or tiny pages
MIN_WORDS = 20


def slug_to_url(slug: str) -> str:
    if slug in {"home", "home_rendered"}:
        return BASE_URL
    return f"{BASE_URL}{slug.strip('/')}/"


def guess_title_from_html(slug: str) -> str:
    raw_html = RAW_DIR / f"{slug}.html"
    if raw_html.exists():
        try:
            soup = BeautifulSoup(raw_html.read_text(encoding="utf-8"), "lxml")
            t = soup.title.string if soup.title and soup.title.string else ""
            t = (t or "").strip()
            if t:
                return t
        except Exception:
            pass
    # fallback from slug
    nice = re.sub(r"[-_]+", " ", slug).strip().title()
    if slug in {"home", "home_rendered"}:
        return "Enatega — Homepage"
    return f"Enatega — {nice}"


def get_splitter():
    if USE_TOKENS:
        return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=TOKEN_CHUNK_SIZE,
            chunk_overlap=TOKEN_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    else:
        return RecursiveCharacterTextSplitter(
            chunk_size=CHAR_CHUNK_SIZE,
            chunk_overlap=CHAR_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )


def collect_clean_files() -> list[pathlib.Path]:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in CLEAN_DIR.glob("*.txt") if p.name != OUT_TXT.name and p.name != OUT_JSONL.name)
    return files


def load_text(p: pathlib.Path) -> str:
    txt = p.read_text(encoding="utf-8")
    # light cleanup to avoid stray placeholders
    txt = txt.replace("[countdown_timer]", " ").strip()
    return txt


def main():
    files = collect_clean_files()
    if not files:
        print("No clean .txt files found in data/clean. Run web_scraping.py first.")
        return

    splitter = get_splitter()
    all_docs: List = []
    per_file_counts = []

    for f in files:
        slug = f.stem
        url = slug_to_url(slug)
        title = guess_title_from_html(slug)

        text = load_text(f)
        if len(text.split()) < MIN_WORDS:
            print(f"Skip {f.name}: too few words ({len(text.split())}).")
            continue

        docs = splitter.create_documents(
            [text],
            metadatas=[{
                "url": url,
                "title": title,
                "slug": slug,
                "domain": BASE_DOMAIN,
                "is_active": True,
                "source": "web",
            }],
        )
        all_docs.extend(docs)
        per_file_counts.append((f.name, len(docs), len(text.split())))

    if not all_docs:
        print("No chunks produced. Check your cleaned files.")
        return

    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)

    with OUT_TXT.open("w", encoding="utf-8") as ftxt:
        ftxt.write(f"# chunks from {BASE_URL} and related pages\n")
        ftxt.write(f"# splitter = {'token' if USE_TOKENS else 'char'} | "
                   f"size={TOKEN_CHUNK_SIZE if USE_TOKENS else CHAR_CHUNK_SIZE} | "
                   f"overlap={TOKEN_CHUNK_OVERLAP if USE_TOKENS else CHAR_CHUNK_OVERLAP}\n\n")

        for i, d in enumerate(all_docs, start=1):
            content = d.page_content
            meta = d.metadata
            ftxt.write(f"----- chunk {i}/{len(all_docs)} -----\n")
            ftxt.write(f"url: {meta.get('url')} | title: {meta.get('title')}\n")
            ftxt.write(f"slug: {meta.get('slug')} | chars: {len(content)}\n\n")
            ftxt.write(content)
            ftxt.write("\n\n")

    with OUT_JSONL.open("w", encoding="utf-8") as jf:
        for d in all_docs:
            meta = d.metadata
            jf.write(json.dumps({
                "url": meta.get("url"),
                "title": meta.get("title"),
                "slug": meta.get("slug"),
                "domain": meta.get("domain"),
                "is_active": meta.get("is_active"),
                "source": meta.get("source"),
                "text": d.page_content,
            }, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_docs)} chunks → {OUT_TXT.resolve()}")
    print(f"Also JSONL → {OUT_JSONL.resolve()}")
    print("\nPer-page summary:")
    for name, n_chunks, words in per_file_counts:
        print(f" - {name}: {words} words → {n_chunks} chunks")


if __name__ == "__main__":
    main()
