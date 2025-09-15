# api/main.py
import os, time
from typing import List, Dict
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_qdrant import QdrantVectorStore

from langchain.memory import ConversationBufferMemory  # or ConversationSummaryMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
# ---------- env ----------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("COLLECTION_NAME")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")

# ---------- app ----------
app = FastAPI(title="Enatega RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ---------- models / vector store ----------
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
vs = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=emb)


retriever = vs.as_retriever(search_kwargs={"k": 6})

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=OPENAI_API_KEY)

# ---------- memory (per session) ----------
SESSION_MEM: Dict[str, ConversationBufferMemory] = {}
MAX_TURNS = 8  # keep recent context lean

def get_memory(session_id: str) -> ConversationBufferMemory:
    mem = SESSION_MEM.get(session_id)
    if not mem:
        # ConversationSummaryMemory(llm=llm, ...) for chat summarization
        mem = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            input_key="question",
            output_key="answer",
        )
        SESSION_MEM[session_id] = mem
    return mem

# ---------- prompt ----------
RAG_PROMPT = PromptTemplate.from_template(
    "You are Enatega’s website assistant.\n"
    "Answer ONLY using the provided context. If the answer is not in the context, say you don’t know.\n"
    "Greet user and be polite. If user introduces themselves, greet them back and introduce yourself.\n"
    "Always include source URLs.\n\n"
    "Reply in English Only\n"
    "Context:\n{context}\n\n"
    "{chat_history}\nUser: {question}\nAssistant:"
)

# ---------- request/response ----------
class ChatReq(BaseModel):
    session_id: str
    message: str

class ChatResp(BaseModel):
    answer: str
    sources: List[str]
    used_chunks: int
    latency_ms: int

# ---------- endpoints ----------
@app.get("/healthz")
def healthz():
    try:
        cnt = client.count(collection_name=COLLECTION, exact=True).count
    except Exception:
        cnt = -1
    return {"ok": True, "collection": COLLECTION, "points": cnt}

@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    t0 = time.time()

    memory = get_memory(req.session_id)
    if hasattr(memory, "buffer") and isinstance(memory.buffer, list):
        memory.buffer[:] = memory.buffer[-(2 * MAX_TURNS):]

    # 2) PRE-CHECK: pull docs directly from retriever
    seed_docs = retriever.get_relevant_documents(req.message)
    if not seed_docs:
        return ChatResp(
            answer="I don’t have that in my current knowledge yet. Please rephrase or check the site.",
            sources=[],
            used_chunks=0,
            latency_ms=int((time.time() - t0) * 1000),
        )

    # 3) Build the chain and run (now that we know there is context)
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt": RAG_PROMPT},
    )

    result = chain({"question": req.message})
    answer = result["answer"]
    docs = result.get("source_documents", []) or []
    sources = list({d.metadata.get("url") for d in docs if d.metadata.get("url")})[:5]

    return ChatResp(
        answer=answer,
        sources=sources,
        used_chunks=len(docs),
        latency_ms=int((time.time() - t0) * 1000),
    )


# --- mount static folder ---
# serves /index.html, /style.css, /app.js, images, etc.
app.mount("/static", StaticFiles(directory="frontend/public"), name="static")

# --- root route -> index.html ---
@app.get("/", include_in_schema=False)
def root():
    return FileResponse("frontend/public/index.html")

# --- optional: avoid favicon 404 noise ---
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # put a real favicon at frontend/public/favicon.ico if you want
    return Response(status_code=204)


@app.post("/clear")
def clear(session_id: str):
    SESSION_MEM.pop(session_id, None)
    return {"ok": True}
