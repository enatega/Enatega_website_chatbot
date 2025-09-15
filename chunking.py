# --- top of chunking.py (update these) ---
import pathlib, json
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter

CLEAN_TXT = pathlib.Path("data/clean/home_rendered.txt")
CHUNKS_TXT = pathlib.Path("data/clean/chunks_enatega_home.txt")
CHUNKS_JSONL = pathlib.Path("data/clean/chunks_enatega_home.jsonl")

USE_TOKENS = True
TOKEN_CHUNK_SIZE = 700
TOKEN_CHUNK_OVERLAP = 150

CHAR_CHUNK_SIZE = 4000
CHAR_CHUNK_OVERLAP = 500

URL = "https://enatega.com/"
TITLE = "Enatega — Homepage"


def get_splitter():
    if USE_TOKENS:
        # uses OpenAI tokenizer "cl100k_base"
        return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=TOKEN_CHUNK_SIZE,
            chunk_overlap=TOKEN_CHUNK_OVERLAP,
            # order matters
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    else:
        return RecursiveCharacterTextSplitter(
            chunk_size=CHAR_CHUNK_SIZE,
            chunk_overlap=CHAR_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

def main():
    text = CLEAN_TXT.read_text(encoding="utf-8")
    splitter = get_splitter()

    # make pseudo "Document" for splitter
    docs = splitter.create_documents([text], metadatas=[{"url": URL, "title": TITLE}])
    chunks: List[str] = [d.page_content for d in docs]

    # write human-readable .txt
    CHUNKS_TXT.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_TXT.open("w", encoding="utf-8") as f:
        f.write(f"# chunks from {URL}\n")
        f.write(f"# splitter = {'token' if USE_TOKENS else 'char'} | "
                f"size={TOKEN_CHUNK_SIZE if USE_TOKENS else CHAR_CHUNK_SIZE} | "
                f"overlap={TOKEN_CHUNK_OVERLAP if USE_TOKENS else CHAR_CHUNK_OVERLAP}\n\n")
        for i, d in enumerate(docs, start=1):
            content = d.page_content
            f.write(f"----- chunk {i}/{len(docs)} -----\n")
            f.write(f"url: {d.metadata.get('url')} | title: {d.metadata.get('title')}\n")
            f.write(f"chars: {len(content)}\n\n")
            f.write(content)
            f.write("\n\n")

    # machine-friendly jsonl
    with CHUNKS_JSONL.open("w", encoding="utf-8") as jf:
        for d in docs:
            jf.write(json.dumps({
                "url": d.metadata.get("url"),
                "title": d.metadata.get("title"),
                "text": d.page_content
            }, ensure_ascii=False) + "\n")

    print(f"Wrote {len(chunks)} chunks → {CHUNKS_TXT.resolve()}")
    print(f"Also JSONL → {CHUNKS_JSONL.resolve()}")

if __name__ == "__main__":
    main()
