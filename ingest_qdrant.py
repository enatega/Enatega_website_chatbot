# reingest_qdrant.py
import os, json, pathlib, argparse
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain.schema import Document

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("COLLECTION_NAME")

def read_docs(path: pathlib.Path):
    docs = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            docs.append(Document(
                page_content=r["text"],
                metadata={"url": r.get("url"), "title": r.get("title"),
                          "domain": "enatega.com", "is_active": True}
            ))
    return docs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", default="data/clean/chunks_enatega_home.jsonl")
    ap.add_argument("--recreate", action="store_true")
    args = ap.parse_args()

    if not OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY missing")
    p = pathlib.Path(args.jsonl)
    if not p.exists(): raise FileNotFoundError(p)

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    if args.recreate:
        try: client.delete_collection(COLLECTION)
        except Exception: pass
        client.recreate_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=1536, distance=qm.Distance.COSINE),
        )
    else:
        names = [c.name for c in client.get_collections().collections]
        if COLLECTION not in names:
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=qm.VectorParams(size=1536, distance=qm.Distance.COSINE),
            )

    docs = read_docs(p)
    emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
    vs = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=emb)
    vs.add_documents(docs)

    cnt = client.count(collection_name=COLLECTION, exact=True).count
    print(f"Upserted {len(docs)} docs. Collection '{COLLECTION}' now has {cnt} points.")
    print("Sample payload:", docs[0].metadata)

if __name__ == "__main__":
    main()
