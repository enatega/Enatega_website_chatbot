# api/main.py
import os, time, re, json
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


# --- streaming helpers ---
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Optional, Dict
from difflib import get_close_matches
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableMap, RunnablePassthrough



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


retriever = vs.as_retriever(search_kwargs={"k": 4})

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

#---------- prompt ----------
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
    "• CRUCIAL:- Anything related to Enatega, technical or non-technical that is not in your context\n"
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

# RAG_PROMPT = PromptTemplate.from_template(
#     "You are Enatega's enthusiastic assistant helping businesses discover the perfect delivery solution. Create engaging conversations that showcase Enatega's value while maintaining strict accuracy.\n\n"
    
#     "🚨 CRITICAL REQUIREMENTS:\n"
#     "• Answer EXCLUSIVELY from provided context - ZERO assumptions or external knowledge\n"
#     "• Respond STRICTLY in English - never switch languages under any circumstances\n"
#     "• Use HTML formatting ONLY: <h2> for headings, <p> for paragraphs, <ul><li> for lists\n"
#     "• NEVER fabricate technical specs, pricing, or features not explicitly in context\n\n"
    
#     "📋 ACCURACY CONTROLS:\n"
#     "• If information missing: 'I don't have specific details on that, but here's what I can share about [related topic]...'\n"
#     "• When correcting misconceptions: 'Actually, here's how it works...' then provide context facts\n"
#     "• No technical claims without explicit source evidence\n"
#     "• No pricing details unless stated in context\n\n"
    
#     "💬 RESPONSE STRUCTURE:\n"
#     "<h2>Engaging Heading</h2>\n"
#     "<p>Acknowledge their situation with empathy</p>\n"
#     "<p>Provide relevant information from context</p>\n"
#     "<p>Connect to business value (cost savings, efficiency, growth)</p>\n"
#     "<p>End with discovery question or meeting referral</p>\n\n"
    
#     "🎯 CONVERSATION EXCELLENCE:\n"
#     "• Show genuine curiosity about their business challenges\n"
#     "• Ask discovery questions: 'What's your biggest delivery challenge?' 'How many orders do you handle?'\n"
#     "• Share relevant success stories from context when applicable\n"
#     "• Position Enatega as the optimal solution while staying truthful\n"
#     "• Professional but energetic tone - like an excited consultant\n\n"
    
#     "📞 MEETING REFERRALS:\n"
#     f"Suggest strategy calls at {calendly_link} when users:\n"
#     "• Ask complex technical questions beyond context scope\n"
#     "• Show buying intent (pricing, timelines, implementation)\n"
#     "• Have enterprise needs requiring detailed discussion\n"
#     "• Need validation beyond available context\n\n"
    
#     "Meeting invitation template:\n"
#     f"'This is exactly what our team specializes in! They can provide specific guidance for your needs and show you how similar businesses have succeeded. Ready for a free strategy call? {calendly_link}'\n\n"
    
#     "🎨 TONE GUIDELINES:\n"
#     "• Enthusiastic but professional\n"
#     "• Empathetic to pain points before presenting solutions\n"
#     "• Natural conversation flow, not robotic\n"
#     "• Focus on their business success\n\n"
    
#     "Context: {context}\n"
#     "Chat History: {chat_history}\n"
#     "User: {question}\n"
#     "Assistant:"
# )

# ---------- request/response ----------
class ChatReq(BaseModel):
    session_id: str
    message: str

class ChatResp(BaseModel):
    answer: str
    sources: List[str]
    used_chunks: int
    latency_ms: int


# ---- Demo catalog (canonical keys are lowercase) ----
DEMO_LINKS = {
    "customer app": {
        "ios": "https://apps.apple.com/us/app/enatega-multivendor/id1526488093",
        "android": "https://play.google.com/store/apps/details?id=com.enatega.multivendor",
        "prototype": "https://embed.figma.com/proto/LSolukFLwl0bAzMUd6Pmg4/Customer-Mobile-App?page-id=275%E2%80%A6esponsive&starting-point-node-id=5502%3A4571&embed-host=share",
    },
    "rider app": {
        "ios": "https://apps.apple.com/pk/app/enatega-mulitvendor-rider/id1526674511",
        "android": "https://play.google.com/store/apps/details?id=com.enatega.multirider",
        "prototype": "https://www.figma.com/proto/YSwFI6jvKEfppvumDfZ5GT/Rider-App?content-scaling=respon%E2%80%A6age-id=0%3A1&scaling=scale-down&starting-point-node-id=1%3A587",
    },
    "restaurant app": {
        "ios": "https://apps.apple.com/pk/app/enatega-store/id1526672537",
        "android": "https://play.google.com/store/apps/details?id=multivendor.enatega.restaurant",
        "prototype": "https://www.figma.com/proto/KnBNgwoio8zujFKSEzXTZ4/Restaurant-App?content-scaling=r%E2%80%A6age-id=0%3A1&scaling=scale-down&starting-point-node-id=0%3A731",
    },
    "customer web": {
        "web": "https://multivendor.enatega.com/?_gl=1*13cpnd2*_gcl_au*MTIwMzg0NDY0NS4xNzU3NDg0OTA2",
        "prototype": "https://embed.figma.com/proto/bdA2QOM79DtIGJAQMa4LEv/Customer-Web-App?page-id=0%3A1&%E2%80%A6caling=fixed&starting-point-node-id=1%3A6328&embed-host=share",
    },
    "admin dashboard": {
        "web": "https://multivendor-admin.enatega.com/?_gl=1*3lj6s*_gcl_au*MTIwMzg0NDY0NS4xNzU3NDg0OTA2",
        "prototype": "https://www.figma.com/proto/D7HeChxKZo45MWEEVGQ1mK/Admin-Web-App?content-scaling=fi%E2%80%A6page-id=0%3A1&scaling=contain&starting-point-node-id=1%3A13258",
    },
    "server": {
        "web": "https://v1-api-enatega-multivendor-stage.up.railway.app/graphql",
    },
}

# Aliases (no regex). You can add more colloquialisms here.
APP_ALIASES = {
    "customer": "customer app",
    "customer app": "customer app",
    "rider": "rider app",
    "rider app": "rider app",
    "restaurant": "restaurant app",
    "restaurant app": "restaurant app",
    "web": "customer web",
    "customer web": "customer web",
    "admin": "admin dashboard",
    "admin dashboard": "admin dashboard",
    "dashboard": "admin dashboard",
    "server": "server",
}

TYPE_ALIASES = {
    "ios": "ios", "iphone": "ios", "ipad": "ios",
    "android": "android", "apk": "android",
    "web": "web", "website": "web",
    "prototype": "prototype", "figma": "prototype", "proto": "prototype",
    "docs": "docs", "documentation": "docs",
}

def _norm_app(s: Optional[str]) -> Optional[str]:
    if not s: return None
    key = s.strip().lower()
    if key in APP_ALIASES:
        return APP_ALIASES[key]
    # fuzzy match to canonical keys
    canon = list(DEMO_LINKS.keys())
    match = get_close_matches(key, canon, n=1, cutoff=0.75)
    return match[0] if match else key

def _norm_type(s: Optional[str]) -> Optional[str]:
    if not s: return None
    key = s.strip().lower()
    return TYPE_ALIASES.get(key, key)

def _render_demo_html(app: Optional[str] = None, demo_type: Optional[str] = None) -> str:
    app = _norm_app(app)
    demo_type = _norm_type(demo_type)

    def pill(label, url):
        # Frontend already forces target=_blank safely
        return f'<a href="{url}">{label}</a>'

    blocks = []
    items = DEMO_LINKS.items()
    if app and app in DEMO_LINKS:
        items = [(app, DEMO_LINKS[app])]
    for app_name, targets in items:
        pills = []
        for tlabel, url in targets.items():
            if demo_type and tlabel != demo_type:
                continue
            pills.append(pill(tlabel.capitalize(), url))
        if not pills:  # if filter removed all, show all for that app
            pills = [pill(t.capitalize(), u) for t, u in targets.items()]
        title = app_name.title() if app_name != "admin dashboard" else "Admin Dashboard"
        blocks.append(f"<h3><strong>{title}</strong></h3><p>Demo Links: {' '.join(pills)}</p>")

    if not blocks:
        return "<p>No demo links configured yet.</p>"
    return "<h2><strong>Explore Our Live Demos</strong></h2>" + "".join(blocks)

@tool("get_demo_links", return_direct=False)
def get_demo_links(app: Optional[str] = None, demo_type: Optional[str] = None) -> str:
    """Return HTML with demo links. app ∈ {customer app, rider app, restaurant app, customer web, admin dashboard, server}. demo_type ∈ {ios, android, web, prototype, docs}. Omit args to show all."""
    return _render_demo_html(app, demo_type)


# Small, deterministic router that only decides whether to call the tool
router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=OPENAI_API_KEY).bind_tools([get_demo_links])

ROUTER_SYS = (
    "You can call get_demo_links when the user asks for a demo or demo links. "
    "If they specify an app (customer app, rider app, restaurant app, customer web, admin dashboard, server) "
    "and/or a demo type (ios, android, web, prototype, docs), pass them. "
    "If unspecified, omit the arg to show all. "
    "If the request is not about demos, do not call any tool."
)

def maybe_answer_with_demos(user_msg: str) -> Optional[str]:
    ai = router_llm.invoke([SystemMessage(content=ROUTER_SYS), HumanMessage(content=user_msg)])
    calls = ai.additional_kwargs.get("tool_calls") or []
    for c in calls:
        fn = (c.get("function") or {}).get("name")
        if fn == "get_demo_links":
            raw = (c.get("function") or {}).get("arguments") or "{}"
            args = json.loads(raw)
            # Execute tool
            return get_demo_links.invoke(args)
    return None


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

    demo_html = maybe_answer_with_demos(req.message)
    if demo_html:
        return ChatResp(
            answer=demo_html,
            sources=[],
            used_chunks=0,
            latency_ms=int((time.time() - t0) * 1000),
        )
    
    # NEW: invoke instead of get_relevant_documents
    seed_docs = retriever.invoke(req.message)
    if not seed_docs:
        return ChatResp(
            answer="I don’t have that in my current knowledge yet. Please rephrase or check the site.",
            sources=[],
            used_chunks=0,
            latency_ms=int((time.time() - t0) * 1000),
        )

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,   # turn on so sources work
        combine_docs_chain_kwargs={"prompt": RAG_PROMPT},
    )

    # NEW: invoke instead of __call__
    result = chain.invoke({"question": req.message})
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


def format_docs(docs):
    # You can keep it short; top 3-4 chunks is usually enough for snappy answers
    return "\n\n".join(d.page_content.strip() for d in docs)

def format_history(chat_messages) -> str:
    # memory returns a list[BaseMessage]; serialize to plain text for your prompt
    if not chat_messages:
        return ""
    lines = []
    for m in chat_messages:
        role = "User" if m.type == "human" else "Assistant"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


@app.post("/chat_stream")
async def chat_stream(req: ChatReq):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    demo_html = maybe_answer_with_demos(req.message)
    if demo_html:
        return StreamingResponse(iter([demo_html.encode("utf-8")]), media_type="text/plain")

    memory = get_memory(req.session_id)
    if hasattr(memory, "buffer") and isinstance(memory.buffer, list):
        memory.buffer[:] = memory.buffer[-(2 * MAX_TURNS):]

    # Use the new retriever API (no deprecation)
    docs = retriever.invoke(req.message)
    if not docs:
        async def _empty() -> AsyncGenerator[bytes, None]:
            # ✅ encode to utf-8 so curly quotes are fine
            yield "I don’t have that in my current knowledge yet. Please rephrase or check the site.".encode("utf-8")
        return StreamingResponse(_empty(), media_type="text/plain; charset=utf-8")

    context = "\n\n".join(d.page_content.strip() for d in docs[:4])
    hist = memory.load_memory_variables({}).get("chat_history") or []
    # flatten history to text
    if hist:
        try:
            hist_text = "\n".join(
                (("User: " if m.type == "human" else "Assistant: ") + (m.content or ""))
                for m in hist
            )
        except Exception:
            hist_text = ""
    else:
        hist_text = ""

    prompt_text = RAG_PROMPT.format(context=context, chat_history=hist_text, question=req.message)

    async def token_gen() -> AsyncGenerator[bytes, None]:
        pieces = []
        async for chunk in llm.astream([SystemMessage(content=prompt_text)]):
            text = getattr(chunk, "content", "") or ""
            if not text:
                continue
            pieces.append(text)
            # ✅ Always send bytes, explicitly UTF-8
            yield text.encode("utf-8")
        # Save to memory after stream completes
        try:
            final = "".join(pieces)
            memory.save_context({"question": req.message}, {"answer": final})
        except Exception:
            pass

    return StreamingResponse(token_gen(), media_type="text/plain; charset=utf-8")



