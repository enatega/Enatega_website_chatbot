# query_qdrant.py
import os, textwrap
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
# For filtered search (later):
from qdrant_client.http import models as qmodels

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("COLLECTION_NAME")

def preview(txt: str, n=180) -> str:
    return textwrap.shorten(" ".join((txt or "").split()), width=n, placeholder="…")

def main():
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Sanity: how many points?
    cnt = client.count(collection_name=COLLECTION, exact=True).count
    print(f"Collection '{COLLECTION}' has {cnt} points.")

    emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
    vs = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=emb)

    print("Ask something about Enatega’s homepage. Type 'q' to quit.")
    while True:
        q = input("\nQuery: ").strip()
        if q.lower() in {"q", "quit", "exit"}:
            break

        # 1) Unfiltered search (should return hits)
        results = vs.similarity_search_with_relevance_scores(q, k=4)
        if not results:
            print("No hits (unfiltered).")
            continue

        print("\nTop matches (unfiltered):")
        for i, (doc, score) in enumerate(results, 1):
            print(f"{i}) score={score:.4f} | url={doc.metadata.get('url')}")
            print("   ", preview(doc.page_content))

        # 2) Filtered search (proper Qdrant filter object)
        filt = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="domain", match=qmodels.MatchValue(value="enatega.com")
                ),
                qmodels.FieldCondition(
                    key="is_active", match=qmodels.MatchValue(value=True)
                ),
            ]
        )
        results_filt = vs.similarity_search_with_relevance_scores(q, k=4, filter=filt)
        print("\nTop matches (filtered):")
        for i, (doc, score) in enumerate(results_filt, 1):
            print(f"{i}) score={score:.4f} | url={doc.metadata.get('url')}")
            print("   ", preview(doc.page_content))

if __name__ == "__main__":
    main()
