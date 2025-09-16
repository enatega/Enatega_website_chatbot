# ingest_qdrant.py
import os, re, json, pathlib, argparse
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain.schema import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

# --- CONFIG ---
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
MIN_WORDS = 40

# --- ENV ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("COLLECTION_NAME")


# --- HELPERS ---
def slug_to_url(slug: str) -> str:
    if slug in {"home", "home_rendered"}:
        return BASE_URL
    return f"{BASE_URL}{slug.strip('/')}/"


def guess_title(slug: str) -> str:
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
    return f"Enatega — {re.sub(r'[-_]+', ' ', slug).strip().title()}"


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
    return sorted(
        p for p in CLEAN_DIR.glob("*.txt")
        if p.name not in {OUT_TXT.name, OUT_JSONL.name}
    )


def load_text(p: pathlib.Path) -> str:
    txt = p.read_text(encoding="utf-8")
    return txt.replace("[countdown_timer]", " ").strip()


# --- MAIN ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true", help="Recreate collection in Qdrant")
    args = ap.parse_args()

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing in .env")

    files = collect_clean_files()
    if not files:
        print("No clean .txt files in data/clean. Run web_scraping.py first.")
        return

    splitter = get_splitter()
    all_docs: List[Document] = []
    per_file_counts = []

    # Step 1: Chunk all files
    for f in files:
        slug = f.stem
        url = slug_to_url(slug)
        title = guess_title(slug)

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

    # Step 2: Write chunks to disk
    with OUT_TXT.open("w", encoding="utf-8") as ftxt:
        ftxt.write(f"# chunks from {BASE_URL} and related pages\n")
        ftxt.write(f"# splitter = {'token' if USE_TOKENS else 'char'} | "
                   f"size={TOKEN_CHUNK_SIZE if USE_TOKENS else CHAR_CHUNK_SIZE} | "
                   f"overlap={TOKEN_CHUNK_OVERLAP if USE_TOKENS else CHAR_CHUNK_OVERLAP}\n\n")
        for i, d in enumerate(all_docs, start=1):
            meta = d.metadata
            content = d.page_content
            ftxt.write(f"----- chunk {i}/{len(all_docs)} -----\n")
            ftxt.write(f"url: {meta.get('url')} | title: {meta.get('title')}\n")
            ftxt.write(f"slug: {meta.get('slug')} | chars: {len(content)}\n\n")
            ftxt.write(content + "\n\n")

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
    for name, n_chunks, words in per_file_counts:
        print(f" - {name}: {words} words → {n_chunks} chunks")

    # Step 3: Push to Qdrant
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    if args.recreate:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
        client.recreate_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=1536, distance=qm.Distance.COSINE),
        )
    else:
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION not in collections:
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=qm.VectorParams(size=1536, distance=qm.Distance.COSINE),
            )

    emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
    vs = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=emb)
    vs.add_documents(all_docs)

    cnt = client.count(collection_name=COLLECTION, exact=True).count
    print(f"\nUpserted {len(all_docs)} chunks. Collection '{COLLECTION}' now has {cnt} points.")
    print("Sample metadata:", all_docs[0].metadata)


if __name__ == "__main__":
    main()
