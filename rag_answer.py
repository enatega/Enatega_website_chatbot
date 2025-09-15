# rag_answer.py
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_qdrant import QdrantVectorStore

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("COLLECTION_NAME")

def fmt_docs(docs, max_chars=6000, per_chunk_cap=2200):
    out, used = [], 0
    for d in docs:
        body = d.page_content
        if not body:
            continue
        # cap each chunk so one big chunk doesn't eat the whole budget
        body = body[:per_chunk_cap]
        chunk = f"{body}\nSource: {d.metadata.get('url')}\n"
        if used + len(chunk) > max_chars:
            # if nothing yet, still include a trimmed first chunk
            if not out:
                out.append(chunk[:max_chars])
            break
        out.append(chunk)
        used += len(chunk)
    return "\n\n".join(out)


def main():
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
    vs = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=emb)

    filt = qm.Filter(must=[
        qm.FieldCondition(key="domain", match=qm.MatchValue(value="enatega.com")),
        qm.FieldCondition(key="is_active", match=qm.MatchValue(value=True)),
    ])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    print("Ask about Enatega. Type 'q' to quit.")
    while True:
        q = input("\nQ: ").strip()
        if q.lower() in {"q","quit","exit"}: break

        # unfiltered first
        hits = vs.similarity_search_with_relevance_scores(q, k=6)
        if not hits:
            print("No hits (unfiltered)."); continue

        # then filtered
        hits_f = vs.similarity_search_with_relevance_scores(q, k=6, filter=filt)
        use_hits = [d for d, _ in hits]

        context = fmt_docs(use_hits)
        if not context.strip():
            print("Context empty."); continue

        system = ("You are Enatega’s website assistant. Answer ONLY from the context. "
                  "If not present, say you don’t know. Include source URLs.")
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {q}\nAnswer:"}
        ]
        resp = llm.invoke(messages).content
        cites = list({d.metadata.get('url') for d in use_hits if d.metadata.get('url')})

        print("\n--- Answer ---\n", resp)
        print("\nSources:", ", ".join(cites[:5]))

if __name__ == "__main__":
    main()
