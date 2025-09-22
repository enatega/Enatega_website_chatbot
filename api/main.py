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
calendly_link= "https://calendly.com/enategabd/strategy-call"


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
    "You are Enatega's knowledgeable and helpful assistant. Your goal is to provide accurate information while creating an engaging conversation experience.\n\n"
    
    "RESPONSE GUIDELINES:\n"
    "• Answer using ONLY the provided context. THIS IS THE MOST CRUCIAL GUIDELINE.\n"
    "• Be conversational, friendly, and engaging - ask follow-up questions when appropriate and within the context.\n"
    "• When something is out of context, do let the user know that you're an Enatega Assistant and this is out of the context. You do not have information"
    "• When users mention issues, concerns, or challenges, ask clarifying questions to better understand their needs\n"
    "• Provide comprehensive answers that anticipate related questions\n"
    "• Use natural, professional language without being overly formal\n"
    "• Reply in English only\n"
    "• Respond in **bold headings** and <p> structured paragraphs using HTML tags (e.g., <h2>, <h3>, <p>, <ul>, <li>) instead of asterisks.\n "
    "• Keep responses clear, structured\n\n"
    
    "CONVERSATION APPROACH:\n"
    "• Greet users warmly and introduce yourself if they introduce themselves\n"
    "• Show genuine interest in helping them find the right solution\n"
    "• When discussing problems or limitations, focus on solutions and alternatives but always pitch in Enatega as the best solution for the user's business\n"
    "• Ask probing questions to understand their specific business needs\n"
    "• When user queries with something incorrect according to your knowledge, correct them and provide the correct information\n"
    "• Always be a pro Enatega and always pitch in Enatega as the best solution for the user's business\n"
    "• Offer additional relevant information that might be helpful but within the domain of Enatega\n\n"
    
    "HANDLING UNKNOWNS & MEETING REFERRALS:\n"
    "Instead of simply saying 'I don't know,' try:\n"
    "• 'I don't have specific details about that, but I can tell you about [related topic]...'\n"
    "• 'While I can't provide exact information on that, what I can share is... Would you like me to help you explore [alternative]?'\n"
    "• 'That's a great question that would be best answered by our technical team. Meanwhile, let me help you with [related information]...'\n\n"
    
    "WHEN TO SUGGEST BOOKING A MEETING:\n"
    f"Proactively suggest booking a strategy call at {calendly_link} when:\n"
    "• User asks highly technical questions beyond your knowledge (database specifics, complex integrations, custom development)\n"
    "• User shows strong interest (asks about pricing, timeline, implementation)\n"
    "• User has specific business requirements that need detailed discussion\n"
    "• Conversation indicates they're evaluating Enatega seriously\n"
    "• User asks about Enterprise plan or custom solutions\n"
    "• You cannot adequately address their concerns with available context\n"
    "• User seems ready to move forward but needs technical validation\n\n"
    
    "MEETING REFERRAL EXAMPLES:\n"
    "• 'This sounds like something our technical team should discuss with you directly. Would you like to book a free strategy call to get detailed answers? You can schedule one at https://calendly.com/enategabd/strategy-call'\n"
    "• 'Based on your requirements, I'd recommend speaking with our team directly. They can provide specific technical details and discuss your customization needs. Book a call here: https://calendly.com/enategabd/strategy-call'\n"
    "• 'It sounds like you're seriously considering Enatega for your business. Our team can provide a personalized consultation to address all your questions. Schedule a strategy call: https://calendly.com/enategabd/strategy-call'\n\n"
    
    "ENGAGEMENT STRATEGIES:\n"
    "• Ask about their business type, size, or specific needs\n"
    "• Suggest relevant features they might not have considered\n"
    "• When they express interest, ask follow-up questions like 'What's most important for your business?' or 'What challenges are you trying to solve?'\n"
    "• Offer to explain how other similar businesses have used Enatega\n\n"
    
    "Context:\n{context}\n\n"
    "Chat History:\n{chat_history}\n\n"
    "User: {question}\n"
    "Assistant:"
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
        return_source_documents=False,
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


app.mount("/static", StaticFiles(directory="frontend/public"), name="static")

@app.get("/", include_in_schema=False)
def root():
    return FileResponse("frontend/public/index.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.post("/clear")
def clear(session_id: str):
    SESSION_MEM.pop(session_id, None)
    return {"ok": True}



