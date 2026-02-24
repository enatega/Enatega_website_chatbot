# # api/main.py
# import os, time, re, json
# from typing import List, Dict
# from pydantic import BaseModel
# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv

# from qdrant_client import QdrantClient
# from qdrant_client.http import models as qm

# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
# from langchain_qdrant import QdrantVectorStore

# from langchain.memory import ConversationBufferMemory  # or ConversationSummaryMemory
# from langchain.chains import ConversationalRetrievalChain
# from langchain.prompts import PromptTemplate

# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse, Response


# # --- streaming helpers ---
# from fastapi.responses import StreamingResponse
# from typing import AsyncGenerator, Optional, Dict
# from difflib import get_close_matches
# from langchain_core.tools import tool
# from langchain_core.messages import SystemMessage, HumanMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langchain_core.runnables import RunnableLambda, RunnableMap, RunnablePassthrough



# # ---------- env ----------
# load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# QDRANT_URL = os.getenv("QDRANT_URL")
# QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
# COLLECTION = os.getenv("COLLECTION_NAME")

# if not OPENAI_API_KEY:
#     raise RuntimeError("OPENAI_API_KEY missing")

# # ---------- app ----------
# app = FastAPI(title="Enatega RAG API")
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],           
#     allow_methods=["POST", "GET"],
#     allow_headers=["*"],
# )

# # ---------- models / vector store ----------
# client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
# emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
# vs = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=emb)
# form_link= "https://enatega.com/contact/?utm_source=AI&utm_medium=Chatbot&utm_campaign=leads"


# retriever = vs.as_retriever(search_kwargs={"k": 6})

# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=OPENAI_API_KEY)

# # ---------- memory (per session) ----------
# SESSION_MEM: Dict[str, ConversationBufferMemory] = {}
# MAX_TURNS = 8  # keep recent context lean

# def get_memory(session_id: str) -> ConversationBufferMemory:
#     mem = SESSION_MEM.get(session_id)
#     if not mem:
#         # ConversationSummaryMemory(llm=llm, ...) for chat summarization
#         mem = ConversationBufferMemory(
#             memory_key="chat_history",
#             return_messages=True,
#             input_key="question",
#             output_key="answer",
#         )
#         SESSION_MEM[session_id] = mem
#     return mem

# #---------- prompt ----------
# RAG_PROMPT = PromptTemplate.from_template(
#     "You are Enatega's knowledgeable and helpful assistant. Your goal is to provide accurate information while creating an engaging conversation experience.\n\n"
    
#     "RESPONSE GUIDELINES:\n"
#     "• Answer using ONLY the provided context. THIS IS THE MOST CRUCIAL GUIDELINE.\n"
#     "• Be conversational, friendly, and engaging - ask follow-up questions when appropriate and within the context.\n"
#     "• When something is out of context, do let the user know that you're an Enatega Assistant and this is out of the context. You do not have information"
#     "• When users mention issues, concerns, or challenges, ask clarifying questions to better understand their needs\n"
#     "• Provide comprehensive answers that anticipate related questions\n"
#     "• Use natural, professional language without being overly formal\n"
#     "• Reply in the language of the user's query or English only\n"
#     "• Respond in **bold headings** and <p> structured paragraphs using HTML tags (e.g., <h2>, <h3>, <p>, <ul>, <li>) instead of asterisks.\n "
#     "• The placeholder/text for the form link should be dynamic e.g schedule a call, get a quote etc based on user query\n"
#     "• The link for user form submission should be structured at the end of the response to make UX better.\n"
#     "• When asked for use cases, provide complete use cases rather than explaining, provide precise list of use cases. - Food Delivery - Flower Delivery - Grocery Delivery - Milk Delivery - Document Delivery - Liquor Delivery - Medicine Delivery - Courier Service - Beauty Services - Roadside Assistance - Gift Delivery - Laundry On-Demand Services \n"
#     "• Keep responses clear, complete and structured\n\n"
    
#     "CONVERSATION APPROACH:\n"
#     "• Greet users warmly and introduce yourself if they introduce themselves\n"
#     "• Show genuine interest in helping them find the right solution\n"
#     "• When discussing problems or limitations, focus on solutions and alternatives but always pitch in Enatega as the best solution for the user's business\n"
#     "• Ask probing questions to understand their specific business needs\n"
#     "• When user queries with something incorrect according to your knowledge, correct them and provide the correct information\n"
#     "• Always be a pro Enatega and always pitch in Enatega as the best solution for the user's business\n"
#     "• Offer additional relevant information that might be helpful but within the domain of Enatega\n\n"
    
#     "HANDLING UNKNOWNS & MEETING REFERRALS:\n"
#     "Instead of simply saying 'I don't know,' try:\n"
#     "• 'I don't have specific details about that, but I can tell you about [related topic]...'\n"
#     "• 'While I can't provide exact information on that, what I can share is... Would you like me to help you explore [alternative]?'\n"
#     "• 'That's a great question that would be best answered by our technical team. Meanwhile, let me help you with [related information]...'\n\n"
    
#     "WHEN TO SUGGEST BOOKING A MEETING OR GET A QUOTE THROUGH FORM SUBMISSION:\n"
#     f"Proactively suggest booking a strategy call by having the user fill out the form at {form_link} when:\n"
#     "• CRUCIAL: Anything related to Enatega, technical or non-technical that is not in your context\n"
#     "• User asks highly technical questions beyond your knowledge (database specifics, complex integrations, custom development)\n"
#     "• User shows strong interest (asks about pricing, timeline, implementation)\n"
#     "• User has specific business requirements that need detailed discussion\n"
#     "• Conversation indicates they're evaluating Enatega seriously\n"
#     "• User asks about Enterprise plan or custom solutions\n"
#     "• You cannot adequately address their concerns with available context\n"
#     "• User seems ready to move forward but needs technical validation\n\n"

#     "MEETING REFERRAL EXAMPLES BY DIRECTING USERS TO FILL OUT THE FORM:\n"
#     f"• 'This sounds like something our technical team should discuss with you directly. To get started with a free strategy call where you'll receive detailed answers, please fill out our form at {form_link}'\n"
#     f"• 'Based on your requirements, I'd recommend speaking with our team directly. They can provide specific technical details and discuss your customization needs. Please complete the form here to schedule your consultation: {form_link}'\n"
#     f"• 'It sounds like you're seriously considering Enatega for your business. Our team can provide a personalized consultation to address all your questions. Please fill out the form to get started: {form_link}'\n\n"
    
#     "ENGAGEMENT STRATEGIES:\n"
#     "• Ask about their business type, size, or specific needs\n"
#     "• Suggest relevant features they might not have considered\n"
#     "• When they express interest, ask follow-up questions like 'What's most important for your business?' or 'What challenges are you trying to solve?'\n"
#     "• Offer to explain how other similar businesses have used Enatega\n\n"
    
#     "Context:\n{context}\n\n"
#     "Chat History:\n{chat_history}\n\n"
#     "User: {question}\n"
#     "Assistant:"
# )

# # RAG_PROMPT = PromptTemplate.from_template(
# #     "You are Enatega's enthusiastic assistant helping businesses discover the perfect delivery solution. Create engaging conversations that showcase Enatega's value while maintaining strict accuracy.\n\n"
    
# #     "🚨 CRITICAL REQUIREMENTS:\n"
# #     "• Answer EXCLUSIVELY from provided context - ZERO assumptions or external knowledge\n"
# #     "• Respond STRICTLY in English - never switch languages under any circumstances\n"
# #     "• Use HTML formatting ONLY: <h2> for headings, <p> for paragraphs, <ul><li> for lists\n"
# #     "• NEVER fabricate technical specs, pricing, or features not explicitly in context\n\n"
    
# #     "📋 ACCURACY CONTROLS:\n"
# #     "• If information missing: 'I don't have specific details on that, but here's what I can share about [related topic]...'\n"
# #     "• When correcting misconceptions: 'Actually, here's how it works...' then provide context facts\n"
# #     "• No technical claims without explicit source evidence\n"
# #     "• No pricing details unless stated in context\n\n"
    
# #     "💬 RESPONSE STRUCTURE:\n"
# #     "<h2>Engaging Heading</h2>\n"
# #     "<p>Acknowledge their situation with empathy</p>\n"
# #     "<p>Provide relevant information from context</p>\n"
# #     "<p>Connect to business value (cost savings, efficiency, growth)</p>\n"
# #     "<p>End with discovery question or meeting referral</p>\n\n"
    
# #     "🎯 CONVERSATION EXCELLENCE:\n"
# #     "• Show genuine curiosity about their business challenges\n"
# #     "• Ask discovery questions: 'What's your biggest delivery challenge?' 'How many orders do you handle?'\n"
# #     "• Share relevant success stories from context when applicable\n"
# #     "• Position Enatega as the optimal solution while staying truthful\n"
# #     "• Professional but energetic tone - like an excited consultant\n\n"
    
# #     "📞 MEETING REFERRALS:\n"
# #     f"Suggest strategy calls at {calendly_link} when users:\n"
# #     "• Ask complex technical questions beyond context scope\n"
# #     "• Show buying intent (pricing, timelines, implementation)\n"
# #     "• Have enterprise needs requiring detailed discussion\n"
# #     "• Need validation beyond available context\n\n"
    
# #     "Meeting invitation template:\n"
# #     f"'This is exactly what our team specializes in! They can provide specific guidance for your needs and show you how similar businesses have succeeded. Ready for a free strategy call? {calendly_link}'\n\n"
    
# #     "🎨 TONE GUIDELINES:\n"
# #     "• Enthusiastic but professional\n"
# #     "• Empathetic to pain points before presenting solutions\n"
# #     "• Natural conversation flow, not robotic\n"
# #     "• Focus on their business success\n\n"
    
# #     "Context: {context}\n"
# #     "Chat History: {chat_history}\n"
# #     "User: {question}\n"
# #     "Assistant:"
# # )

# # ---------- request/response ----------
# class ChatReq(BaseModel):
#     session_id: str
#     message: str

# class ChatResp(BaseModel):
#     answer: str
#     sources: List[str]
#     used_chunks: int
#     latency_ms: int


# # ---- Demo catalog (canonical keys are lowercase) ----
# DEMO_LINKS = {
#     "customer app": {
#         "ios": "https://apps.apple.com/us/app/enatega-multivendor/id1526488093",
#         "android": "https://play.google.com/store/apps/details?id=com.enatega.multivendor",
#         "prototype": "https://embed.figma.com/proto/LSolukFLwl0bAzMUd6Pmg4/Customer-Mobile-App?page-id=2751%3A10941&node-id=5502-4571&p=f&viewport=537%2C341%2C0.02&scaling=scale-down&content-scaling=responsive&starting-point-node-id=5502%3A4571&embed-host=share",
#     },
#     "rider app": {
#         "ios": "https://apps.apple.com/pk/app/enatega-mulitvendor-rider/id1526674511",
#         "android": "https://play.google.com/store/apps/details?id=com.enatega.multirider",
#         "prototype": "https://www.figma.com/proto/YSwFI6jvKEfppvumDfZ5GT/Rider-App?content-scaling=responsive&kind=proto&node-id=1-507&page-id=0%3A1&scaling=scale-down&starting-point-node-id=1%3A587",
#     },
#     "restaurant app": {
#         "ios": "https://apps.apple.com/pk/app/enatega-store/id1526672537",
#         "android": "https://play.google.com/store/apps/details?id=multivendor.enatega.restaurant",
#         "prototype": "https://www.figma.com/proto/KnBNgwoio8zujFKSEzXTZ4/Restaurant-App?content-scaling=responsive&kind=proto&node-id=0-651&page-id=0%3A1&scaling=scale-down&starting-point-node-id=0%3A731",
#     },
#     "customer web": {
#         "web": "https://multivendor.enatega.com/?_gl=1*13cpnd2*_gcl_au*MTIwMzg0NDY0NS4xNzU3NDg0OTA2",
#         "prototype": "https://embed.figma.com/proto/bdA2QOM79DtIGJAQMa4LEv/Customer-Web-App?page-id=0%3A1&node-id=1-6328&p=f&viewport=560%2C25%2C0.02&scaling=scale-down-width&content-scaling=fixed&starting-point-node-id=1%3A6328&embed-host=share",
#     },
#     "admin dashboard": {
#         "web": "https://multivendor-admin.enatega.com/?_gl=1*3lj6s*_gcl_au*MTIwMzg0NDY0NS4xNzU3NDg0OTA2",
#         "prototype": "https://www.figma.com/proto/D7HeChxKZo45MWEEVGQ1mK/Admin-Web-App?content-scaling=fixed&kind=proto&node-id=1-3496&page-id=0%3A1&scaling=contain&starting-point-node-id=1%3A13258",
#     },
#     "server": {
#         "web": "https://v1-api-enatega-multivendor-stage.up.railway.app/graphql",
#     },
# }

# # Aliases (no regex). You can add more colloquialisms here.
# APP_ALIASES = {
#     "customer": "customer app",
#     "customer app": "customer app",
#     "rider": "rider app",
#     "rider app": "rider app",
#     "restaurant": "restaurant app",
#     "restaurant app": "restaurant app",
#     "web": "customer web",
#     "customer web": "customer web",
#     "admin": "admin dashboard",
#     "admin dashboard": "admin dashboard",
#     "dashboard": "admin dashboard",
#     "server": "server",
# }

# TYPE_ALIASES = {
#     "ios": "ios", "iphone": "ios", "ipad": "ios",
#     "android": "android", "apk": "android",
#     "web": "web", "website": "web",
#     "prototype": "prototype", "figma": "prototype", "proto": "prototype",
#     "docs": "docs", "documentation": "docs",
# }

# def _norm_app(s: Optional[str]) -> Optional[str]:
#     if not s: return None
#     key = s.strip().lower()
#     if key in APP_ALIASES:
#         return APP_ALIASES[key]
#     # fuzzy match to canonical keys
#     canon = list(DEMO_LINKS.keys())
#     match = get_close_matches(key, canon, n=1, cutoff=0.75)
#     return match[0] if match else key

# def _norm_type(s: Optional[str]) -> Optional[str]:
#     if not s: return None
#     key = s.strip().lower()
#     return TYPE_ALIASES.get(key, key)

# def _render_demo_html(app: Optional[str] = None, demo_type: Optional[str] = None) -> str:
#     app = _norm_app(app)
#     demo_type = _norm_type(demo_type)

#     def pill(label, url):
#         # Frontend already forces target=_blank safely
#         return f'<a href="{url}">{label}</a>'

#     blocks = []
#     items = DEMO_LINKS.items()
#     if app and app in DEMO_LINKS:
#         items = [(app, DEMO_LINKS[app])]
#     for app_name, targets in items:
#         pills = []
#         for tlabel, url in targets.items():
#             if demo_type and tlabel != demo_type:
#                 continue
#             pills.append(pill(tlabel.capitalize(), url))
#         if not pills:  # if filter removed all, show all for that app
#             pills = [pill(t.capitalize(), u) for t, u in targets.items()]
#         title = app_name.title() if app_name != "admin dashboard" else "Admin Dashboard"
#         blocks.append(f"<h3>{title}</h3><p>{' '.join(pills)}</p>")

#     if not blocks:
#         return "<p>No demo links configured yet.</p>"
#     return "<h2>Explore Our Live Demos<br></h2>" + "".join(blocks)

# @tool("get_demo_links", return_direct=False)
# def get_demo_links(app: Optional[str] = None, demo_type: Optional[str] = None) -> str:
#     """Return HTML with demo links. app ∈ {customer app, rider app, restaurant app, customer web, admin dashboard, server}. demo_type ∈ {ios, android, web, prototype, docs}. Omit args to show all."""
#     return _render_demo_html(app, demo_type)


# # Small, deterministic router that only decides whether to call the tool
# router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=OPENAI_API_KEY).bind_tools([get_demo_links])

# ROUTER_SYS = (
#     "You can call get_demo_links when the user asks for a demo or demo links. "
#     "If they specify an app (customer app, rider app, restaurant app, customer web, admin dashboard, server) "
#     "and/or a demo type (ios, android, web, prototype, docs), pass them. "
#     "If unspecified, omit the arg to show all. "
#     "If the request is not about demos, do not call any tool."
# )

# def maybe_answer_with_demos(user_msg: str) -> Optional[str]:
#     ai = router_llm.invoke([SystemMessage(content=ROUTER_SYS), HumanMessage(content=user_msg)])
#     calls = ai.additional_kwargs.get("tool_calls") or []
#     for c in calls:
#         fn = (c.get("function") or {}).get("name")
#         if fn == "get_demo_links":
#             raw = (c.get("function") or {}).get("arguments") or "{}"
#             args = json.loads(raw)
#             # Execute tool
#             return get_demo_links.invoke(args)
#     return None


# # ---------- endpoints ----------
# @app.get("/healthz")
# def healthz():
#     try:
#         cnt = client.count(collection_name=COLLECTION, exact=True).count
#     except Exception:
#         cnt = -1
#     return {"ok": True, "collection": COLLECTION, "points": cnt}

# @app.post("/chat", response_model=ChatResp)
# def chat(req: ChatReq):
#     if not req.message.strip():
#         raise HTTPException(status_code=400, detail="Empty message")
#     t0 = time.time()

#     memory = get_memory(req.session_id)
#     if hasattr(memory, "buffer") and isinstance(memory.buffer, list):
#         memory.buffer[:] = memory.buffer[-(2 * MAX_TURNS):]

#     demo_html = maybe_answer_with_demos(req.message)
#     if demo_html:
#         return ChatResp(
#             answer=demo_html,
#             sources=[],
#             used_chunks=0,
#             latency_ms=int((time.time() - t0) * 1000),
#         )
    
#     # NEW: invoke instead of get_relevant_documents
#     seed_docs = retriever.invoke(req.message)
#     if not seed_docs:
#         return ChatResp(
#             answer="I don’t have that in my current knowledge yet. Please rephrase or check the site.",
#             sources=[],
#             used_chunks=0,
#             latency_ms=int((time.time() - t0) * 1000),
#         )

#     chain = ConversationalRetrievalChain.from_llm(
#         llm=llm,
#         retriever=retriever,
#         memory=memory,
#         return_source_documents=True,   # turn on so sources work
#         combine_docs_chain_kwargs={"prompt": RAG_PROMPT},
#     )

#     # NEW: invoke instead of __call__
#     result = chain.invoke({"question": req.message})
#     answer = result["answer"]
#     docs = result.get("source_documents", []) or []
#     sources = list({d.metadata.get("url") for d in docs if d.metadata.get("url")})[:5]

#     return ChatResp(
#         answer=answer,
#         sources=sources,
#         used_chunks=len(docs),
#         latency_ms=int((time.time() - t0) * 1000),
#     )



# app.mount("/static", StaticFiles(directory="frontend/public"), name="static")

# @app.get("/", include_in_schema=False)
# def root():
#     return FileResponse("frontend/public/index.html")

# @app.get("/favicon.ico", include_in_schema=False)
# def favicon():
#     return Response(status_code=204)


# @app.post("/clear")
# def clear(session_id: str):
#     SESSION_MEM.pop(session_id, None)
#     return {"ok": True}


# def format_docs(docs):
#     # You can keep it short; top 3-4 chunks is usually enough for snappy answers
#     return "\n\n".join(d.page_content.strip() for d in docs)

# def format_history(chat_messages) -> str:
#     # memory returns a list[BaseMessage]; serialize to plain text for your prompt
#     if not chat_messages:
#         return ""
#     lines = []
#     for m in chat_messages:
#         role = "User" if m.type == "human" else "Assistant"
#         lines.append(f"{role}: {m.content}")
#     return "\n".join(lines)


# @app.post("/chat_stream")
# async def chat_stream(req: ChatReq):
#     if not req.message.strip():
#         raise HTTPException(status_code=400, detail="Empty message")

#     demo_html = maybe_answer_with_demos(req.message)
#     if demo_html:
#         return StreamingResponse(iter([demo_html.encode("utf-8")]), media_type="text/plain")

#     memory = get_memory(req.session_id)
#     if hasattr(memory, "buffer") and isinstance(memory.buffer, list):
#         memory.buffer[:] = memory.buffer[-(2 * MAX_TURNS):]

#     # Use the new retriever API (no deprecation)
#     docs = retriever.invoke(req.message)
#     if not docs:
#         async def _empty() -> AsyncGenerator[bytes, None]:
#             # ✅ encode to utf-8 so curly quotes are fine
#             yield "I don’t have that in my current knowledge yet. Please rephrase or check the site.".encode("utf-8")
#         return StreamingResponse(_empty(), media_type="text/plain; charset=utf-8")

#     context = "\n\n".join(d.page_content.strip() for d in docs[:4])
#     hist = memory.load_memory_variables({}).get("chat_history") or []
#     # flatten history to text
#     if hist:
#         try:
#             hist_text = "\n".join(
#                 (("User: " if m.type == "human" else "Assistant: ") + (m.content or ""))
#                 for m in hist
#             )
#         except Exception:
#             hist_text = ""
#     else:
#         hist_text = ""

#     prompt_text = RAG_PROMPT.format(context=context, chat_history=hist_text, question=req.message)

#     async def token_gen() -> AsyncGenerator[bytes, None]:
#         pieces = []
#         async for chunk in llm.astream([SystemMessage(content=prompt_text)]):
#             text = getattr(chunk, "content", "") or ""
#             if not text:
#                 continue
#             pieces.append(text)
#             # ✅ Always send bytes, explicitly UTF-8
#             yield text.encode("utf-8")
#         # Save to memory after stream completes
#         try:
#             final = "".join(pieces)
#             memory.save_context({"question": req.message}, {"answer": final})
#         except Exception:
#             pass

#     return StreamingResponse(token_gen(), media_type="text/plain; charset=utf-8")



# from pydantic import BaseModel

# import os, re, json, time
# # ... your other imports ...

# CHAT_DEBUG = os.getenv("CHAT_DEBUG", "0") == "1"

# _ctrl_re = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
# def clean_text(s: str) -> str:
#     if not isinstance(s, str):
#         try:
#             s = s.decode("utf-8", "replace")  # if bytes sneaked in
#         except Exception:
#             s = str(s)
#     s = s.replace("\u0000", " ").replace("\uffff", " ")
#     s = _ctrl_re.sub(" ", s)                  # strip control chars
#     return s

# class DiagReq(BaseModel):
#     message: str
#     k: int | None = None  # override k if you want


# @app.post("/diag/retrieval")
# def diag_retrieval(req: DiagReq):
#     r = vs.as_retriever(search_kwargs={"k": req.k or 6})
#     docs = r.invoke(req.message)
#     payload = []
#     for i, d in enumerate(docs):
#         txt = d.page_content or ""
#         payload.append({
#             "idx": i,
#             "chars": len(txt),
#             "has_null": "\x00" in txt,
#             "url": d.metadata.get("url"),
#             "id": d.metadata.get("id") or d.metadata.get("point_id"),
#             "sample": clean_text(txt[:220]).replace("\n", " "),
#         })
#     return {"k": len(docs), "chunks": payload}


# api/main.py
import os, time, re, json
from typing import List, Dict, Optional, AsyncGenerator
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
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
from fastapi.responses import FileResponse, Response, StreamingResponse

from difflib import get_close_matches
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableMap, RunnablePassthrough

# ----- NEW: Mongo for chat persistence -----
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
import html
import jwt
import base64
import hmac
import hashlib

# ----- Admin KB Router -----
from api.admin_kb import router as admin_router

# ---------- env ----------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("COLLECTION_NAME")

# Mongo env
MONGO_URI = os.getenv("MONGO_URI")  # e.g. mongodb+srv://user:pass@cluster/enatega?retryWrites=true&w=majority
MONGO_DB  = os.getenv("MONGO_DB", "enatega")
MONGO_COL = os.getenv("MONGO_COL", "chat_sessions")
TTL_DAYS  = int(os.getenv("CHAT_TTL_DAYS", "7"))

# User token signing secret
ENATEGA_USER_SIGNING_SECRET = os.getenv("ENATEGA_USER_SIGNING_SECRET", "Hyvsyftwo2398cvvvGG8cw5")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")

# ---------- app ----------
app = FastAPI(title="Enatega RAG API")

# Include admin router
app.include_router(admin_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for chat endpoints (WordPress sites)
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Explicit CORS preflight handler for chat endpoints (backup)
@app.options("/chat")
@app.options("/chat_stream")
@app.options("/clear")
def cors_preflight():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400",
        }
    )

app.include_router(admin_router)

# ---------- models / vector store ----------
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
vs = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=emb)
# calendly_link = "https://calendly.com/enategabd/strategy-call?hide_landing_page_details=1&hide_gdpr_banner=0&hide_event_type_details=1&primary_color=624de3&month=2026-01&utm_source=chatbot&utm_medium=AI"
# calendly_iframe = f'<iframe src="{calendly_link}" style="width: 80%; min-width: 320px; height: 400px;" frameborder="0"></iframe>'
onboarding_link = "https://onboarding.enatega.com/home/"
# Button template with link already included - only placeholder text needs to be replaced
onboarding_button_template = f'<a href="{onboarding_link}" target="_blank" rel="noopener noreferrer" style="display: inline-block; padding: 12px 24px; background: linear-gradient(135deg, #7C6CE4 0, #624DE3 100%); color: #fff; text-decoration: none; border-radius: 8px; font-weight: 600; margin-top: 12px;">PLACEHOLDER_TEXT</a>'
github_repo_link = "https://github.com/enatega/food-delivery-multivendor"
github_repo_html = f'<a href="{github_repo_link}" target="_blank" rel="noopener noreferrer">Get Source Code</a>'

retriever = vs.as_retriever(search_kwargs={"k": 6})
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=OPENAI_API_KEY)

# ---------- memory (per session) ----------
SESSION_MEM: Dict[str, ConversationBufferMemory] = {}
MAX_TURNS = 8  # keep recent context lean

def get_memory(session_id: str) -> ConversationBufferMemory:
    mem = SESSION_MEM.get(session_id)
    if not mem:
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
    "• Reply in the language of the user's query or English only\n"
    "• Respond in **bold headings** and <p> structured paragraphs using HTML tags (e.g., <h2>, <h3>, <p>, <ul>, <li>) instead of asterisks. Do not use asterisks.\n "
    f"• When suggesting to register or get a quote, add a dynamic button/link at the end of the response. Use the onboarding link ({onboarding_link}) with a dynamic placeholder text based on user query (e.g., 'Get a Quote', 'Schedule a Call', 'Register Now', 'Get Started').\n"
    "• The button should be formatted as an HTML anchor tag with styling and should link to the onboarding page.\n"
    f"• When users ask about downloading, viewing, or accessing FRONTEND code/software/repository, provide the GitHub repository link as an HTML anchor tag: {github_repo_html}. IMPORTANT: The GitHub repository contains only FRONTEND source code.\n"
    "• When users ask about BACKEND source code, server code, or API code: inform them that backend source code is paid and proprietary. Immediately suggest registering on the onboarding page to discuss backend access options.\n"
    "• CRUCIAL PITCH ALL INCLUDING TAXI BOOKING: When asked for use cases, provide complete use cases rather than explaining, provide precise list of use cases. - Food Delivery - Flower Delivery - Grocery Delivery - Milk Delivery - Document Delivery - Liquor Delivery - Medicine Delivery - Courier Service - Beauty Services - Roadside Assistance - Gift Delivery - Laundry On-Demand Services - Taxi Booking - Pet Marketplace \n"
    "• Keep responses clear, complete and structured\n\n"
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
    "WHEN TO SUGGEST REGISTRATION/ONBOARDING:\n"
    "Proactively suggest registering on the onboarding page by adding a dynamic button/link in your response when:\n"
    "• CRUCIAL: User asks for a quote, pricing, or 'Get a Quote' - ALWAYS respond with onboarding registration button, never mention forms\n"
    "• CRUCIAL: User expresses buying intent or readiness to launch (e.g., 'Launch Now', 'I want to launch', 'Let's get started', 'I'm ready to start', 'How do I launch', 'I want to get started') - IMMEDIATELY respond with onboarding registration button\n"
    "• CRUCIAL: Anything related to Enatega, technical or non-technical that is not in your context\n"
    "• User asks highly technical questions beyond your knowledge (database specifics, complex integrations, custom development)\n"
    "• User shows strong interest (asks about pricing, timeline, implementation, costs, plans)\n"
    "• User has specific business requirements that need detailed discussion\n"
    "• Conversation indicates they're evaluating Enatega seriously\n"
    "• User asks about Enterprise plan or custom solutions\n"
    "• You cannot adequately address their concerns with available context\n"
    "• User seems ready to move forward but needs technical validation\n"
    "• User expresses interest in purchasing, signing up, or getting started\n"
    "• User asks about downloading, viewing, accessing, or getting FRONTEND code/software/repository - provide the GitHub link\n"
    "• User asks about BACKEND source code, server code, API code, or backend repository - inform that backend is paid/proprietary and IMMEDIATELY suggest registering on onboarding page\n\n"
    "REGISTRATION/ONBOARDING REFERRAL EXAMPLES:\n"
    f"When suggesting registration, end your response with appropriate text and then add a dynamic button. The button HTML template is: {onboarding_button_template}\n"
    f"Replace PLACEHOLDER_TEXT with dynamic text based on user query (e.g., 'Get a Quote', 'Schedule a Call', 'Register Now', 'Get Started', 'Book a Meeting', 'Request a Demo'). The link is already set to {onboarding_link}.\n\n"
    "FEW-SHOT EXAMPLE FOR PRICING/ONBOARDING:\n"
    "User: How to get pricing from client onboarding platform\n"
    "Chatbot:\n"
    "<p>To get pricing, please register on our onboarding platform. The onboarding platform includes complete information about our pricing plans, deployment options, what will be delivered, and the expected delivery timeline.</p>\n"
    "<p>Our pricing model is transparent and flexible, with no hidden fees or recurring subscriptions. You pay once for the complete solution, which includes full source code and all essential applications.</p>\n"
    "<p>Please register below to get started:</p>\n"
    f"{onboarding_button_template.replace('PLACEHOLDER_TEXT', 'Register Now')}\n\n"
    "OTHER EXAMPLES:\n"
    f"Example for 'Get a Quote': 'Great! I'd love to help you get a personalized quote for Enatega. Our team can discuss your specific needs, pricing options, and provide you with a tailored solution. Please register below to get started:'\n"
    f"Then add the button with placeholder 'Get a Quote'. Example for 'Launch Now' or buying intent: 'Excellent! I'm excited to help you launch your delivery service with Enatega. Our team can guide you through the setup process, discuss your specific requirements, and get you started on the right foot. Please register below to begin:'\n"
    f"Then add the button with placeholder 'Get Started'. Example for general interest: 'This sounds like something our technical team should discuss with you directly. To get started and receive detailed answers, please register below:'\n"
    f"Then add the button with placeholder 'Register Now'. NEVER mention forms or form submissions when user asks for quotes or pricing.\n"
    f"Example for FRONTEND code/repository requests: 'You can access our GitHub Multivendor Repository here: {github_repo_html}. This contains the frontend source code for Enatega's multi-vendor delivery platform.'\n"
    f"Example for BACKEND code requests: 'The backend source code is paid and proprietary. To discuss backend access options and licensing, please register below:' Then add the button with placeholder 'Register to Discuss Backend Access'.\n\n"
    "ENGAGEMENT STRATEGIES:\n"
    "• Ask about their business type, size, or specific needs\n"
    "• Suggest relevant features they might not have considered\n"
    "• When they express interest, ask follow-up questions like 'What's most important for your business?' or 'What challenges are you trying to solve?'\n"
    "• Offer to explain how other similar businesses have used Enatega\n"
    "• Proactively suggest booking a meeting when users show buying intent or ask about pricing/quotes\n"
    "• Always prioritize booking a strategy call over providing generic information when users are ready to move forward\n\n"
    "Context:\n{context}\n\n"
    "Chat History:\n{chat_history}\n\n"
    "User: {question}\n"
    "Assistant:"
)

# ---------- request/response ----------
class ChatReq(BaseModel):
    session_id: str
    message: str
    user_token: Optional[str] = None

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
        "prototype": "https://embed.figma.com/proto/LSolukFLwl0bAzMUd6Pmg4/Customer-Mobile-App?page-id=2751%3A10941&node-id=5502-4571&p=f&viewport=537%2C341%2C0.02&scaling=scale-down&content-scaling=responsive&starting-point-node-id=5502%3A4571&embed-host=share",
    },
    "rider app": {
        "ios": "https://apps.apple.com/pk/app/enatega-mulitvendor-rider/id1526674511",
        "android": "https://play.google.com/store/apps/details?id=com.enatega.multirider",
        "prototype": "https://www.figma.com/proto/YSwFI6jvKEfppvumDfZ5GT/Rider-App?content-scaling=responsive&kind=proto&node-id=1-507&page-id=0%3A1&scaling=scale-down&starting-point-node-id=1%3A587",
    },
    "restaurant app": {
        "ios": "https://apps.apple.com/pk/app/enatega-store/id1526672537",
        "android": "https://play.google.com/store/apps/details?id=multivendor.enatega.restaurant",
        "prototype": "https://www.figma.com/proto/KnBNgwoio8zujFKSEzXTZ4/Restaurant-App?content-scaling=responsive&kind=proto&node-id=0-651&page-id=0%3A1&scaling=scale-down&starting-point-node-id=0%3A731",
    },
    "customer web": {
        "web": "https://multivendor.enatega.com/?_gl=1*13cpnd2*_gcl_au*MTIwMzg0NDY0NS4xNzU3NDg0OTA2",
        "prototype": "https://embed.figma.com/proto/bdA2QOM79DtIGJAQMa4LEv/Customer-Web-App?page-id=0%3A1&node-id=1-6328&p=f&viewport=560%2C25%2C0.02&scaling=scale-down-width&content-scaling=fixed&starting-point-node-id=1%3A6328&embed-host=share",
    },
    "admin dashboard": {
        "web": "https://multivendor-admin.enatega.com/?_gl=1*3lj6s*_gcl_au*MTIwMzg0NDY0NS4xNzU3NDg0OTA2",
        "prototype": "https://www.figma.com/proto/D7HeChxKZo45MWEEVGQ1mK/Admin-Web-App?content-scaling=fixed&kind=proto&node-id=1-3496&page-id=0%3A1&scaling=contain&starting-point-node-id=1%3A13258",
    },
    "server": {
        "web": "https://v1-api-enatega-multivendor-stage.up.railway.app/graphql",
    },
}

# ---- Use Case Prototypes Catalog ----
# Structure: Each use case has multivendor and single_vendor sections
USE_CASE_PROTOTYPES = {
    "food_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/LSolukFLwl0bAzMUd6Pmg4/Customer-Mobile-App?page-id=2751%3A10941&node-id=5502-4571&p=f&viewport=537%2C341%2C0.02&scaling=scale-down&content-scaling=responsive&starting-point-node-id=5502%3A4571&embed-host=share",
            "ios": "https://apps.apple.com/us/app/enatega-multivendor/id1526488093",
            "android": "https://play.google.com/store/apps/details?id=com.enatega.multivendor"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/Hi8fAXM0NwEGZhJUQW56yD/Food-Delivery-Single-vendor?page-id=10845%3A3557&node-id=35506-6490&viewport=-1318%2C1716%2C0.13&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "taxi_booking": {
        "admin_dashboard": {
            "prototype": "https://embed.figma.com/proto/yJR49T3sXgBclT2zlY3CYO/Enatega-Rider-Admin?page-id=2692%3A7064&node-id=2692-7065&viewport=-967%2C601%2C0.05&scaling=contain&content-scaling=fixed&embed-host=share"
        },
        "rider_side": {
            "prototype": "https://embed.figma.com/proto/7t5xmP8Q8phBVlxvM3SRja/Online-Taxi-Booking--Single-Vendor--?page-id=2%3A23700&node-id=139-26828&viewport=-388%2C135%2C0.19&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "customer_side": {
            "prototype": "https://embed.figma.com/proto/7t5xmP8Q8phBVlxvM3SRja/Online-Taxi-Booking--Single-Vendor--?page-id=56%3A10356&node-id=79-26206&viewport=243%2C-66%2C0.11&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "flower_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/3IsFQ4y0dngt3gDBj9O4Ki/Flower-App--Multi-vendor-?page-id=2751%3A10941&node-id=33278-18295&viewport=-7076%2C5028%2C0.25&scaling=scale-down&content-scaling=fixed&starting-point-node-id=33278%3A18295&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/hzLj7ulZRk6E52m3VvX07e/Flower-App--Single-vendor-?page-id=10845%3A3557&node-id=37587-4082&viewport=-17895%2C4473%2C0.39&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "grocery_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/RFmA1PUoAWMwUihmUOhjTR/Grocery-Delivery-App--Single-vendor-?page-id=10845%3A3557&node-id=35506-6490&viewport=-24500%2C5980%2C0.53&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/RFmA1PUoAWMwUihmUOhjTR/Grocery-Delivery-App--Single-vendor-?page-id=10845%3A3557&node-id=35506-6490&viewport=-24500%2C5980%2C0.53&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "document_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/IpDkGbRRBUKh0qqf6vXC5W/Courier-Service-App--Multi-vendor-?page-id=2751%3A10941&node-id=38746-8779&viewport=-2361%2C7836%2C0.17&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/fGYqxGYxzJBWC96KmMKXIb/Document-Delivery---Single-vendor-?page-id=10845%3A3557&node-id=35506-6490&viewport=-15595%2C3940%2C0.34&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "liquor_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/Lks3Hj5zOFdWpINtzmvd4U/Liquor-Delivery--Multi-vendor-?page-id=2751%3A10941&node-id=34524-14390&viewport=-139%2C708%2C0.02&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/lEwKVXJlaJV9qRhsye2kJb/Liquor-App--Single-vendor-?page-id=10845%3A3557&node-id=39572-4195&viewport=-10279%2C2531%2C0.22&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "gift_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/JH8QQTpeu8QAw4SFubuzLy/Gift-Delivery-App--Multi-vendor-?page-id=2751%3A10941&node-id=34591-19335&viewport=-1895%2C2183%2C0.1&scaling=scale-down&content-scaling=fixed&starting-point-node-id=34591%3A19335&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/7PGECsllcOjAGYmZa8Dd8W/Gift-Delivery--Single-vendor-?page-id=10845%3A3557&node-id=45572-4074&viewport=-4693%2C1207%2C0.1&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "laundry_on_demand": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/5VAgHel7XWwuVyHDc9H6O4/Laundary--Service-App--Multi-vendor-?page-id=2751%3A10941&node-id=36736-11260&viewport=-3849%2C6876%2C0.17&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/DNEB3NWlL0yldIyPMCLQvd/Laundry-on-Demand---Single-vendor-?page-id=10845%3A3557&node-id=43529-3008&viewport=-7624%2C1974%2C0.17&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "milk_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/zUBXz6MSKzzAaQq36giAim/Milk-Delivery-App--Multi-vendor-?page-id=2751%3A10941&node-id=34628-11817&viewport=-14772%2C10052%2C0.39&scaling=scale-down&content-scaling=fixed&starting-point-node-id=34628%3A11817&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/HpXD8czrCbuQzfTJsTBYXF/Milk-Delivery--Single-vendor-?page-id=10845%3A3557&node-id=39504-2958&viewport=-11132%2C2845%2C0.24&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "courier_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/IpDkGbRRBUKh0qqf6vXC5W/Courier-Service-App--Multi-vendor-?page-id=2751%3A10941&node-id=38746-8779&viewport=-2361%2C7836%2C0.17&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/KRlPG2L8SB5Wnp9lKiC56K/Courier-Service--Single-vendor-?page-id=10845%3A3557&node-id=47585-3168&viewport=-7963%2C2340%2C0.18&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "roadside_assistance": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/WDjMsjD0yoUKEOS8gGbV76/Road-Side-Service-App--Multi-vendor-?page-id=2751%3A10941&node-id=36624-12771&viewport=-652%2C829%2C0.03&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/1E4WCaAhV2erFp3iGzb7AL/Roadside-App--Single-vendor-?page-id=10845%3A3557&node-id=41635-3341&viewport=-12489%2C1527%2C0.28&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "medicine_delivery": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/PuDZkoNsK8WhIwzwBZTZfF/Medicine-Delivery--Multi-vendor-?page-id=2751%3A10941&node-id=34604-39731&viewport=-1058%2C1852%2C0.09&scaling=scale-down&content-scaling=fixed&starting-point-node-id=34604%3A39731&show-proto-sidebar=1&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/13iHkXMQg6TvgIBv4GHD7I/Medicine-Delivery--Single-vendor-?page-id=10845%3A3557&node-id=35506-6490&viewport=-7456%2C2014%2C0.17&scaling=scale-down&content-scaling=fixed&embed-host=share"
        }
    },
    "beauty_services": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/prjfwqZ5XqOei1VYtv3FUJ/Beauty-Service-App--Multi-vendor-?page-id=2751%3A10941&node-id=34636-12649&viewport=-4370%2C2884%2C0.16&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/PrDHCJJhrFYqAAfrCQ9w8e/Beauty-Services--Single-vendor-?page-id=10845%3A3557&node-id=35506-6490&p=f&viewport=-10721%2C2722%2C0.23&scaling=scale-down&content-scaling=fixed&starting-point-node-id=47510%3A3796&embed-host=share"
        }
    },
    "pet_marketplace": {
        "multivendor": {
            "prototype": "https://embed.figma.com/proto/IpMAzFzp228HS2BXONl1s9/Pet-Market-Place-App-Multivendor?page-id=2751%3A10941&node-id=36617-7202&viewport=-2874%2C2268%2C0.07&scaling=scale-down&content-scaling=fixed&embed-host=share"
        },
        "single_vendor": {
            "prototype": "https://embed.figma.com/proto/pFlFHRXiOGLHXRmbM0z8ix/Pet-Market-Place-App--Single-vendor-?page-id=10845%3A3557&node-id=41505-11214&viewport=-5209%2C1372%2C0.09&scaling=scale-down&content-scaling=fixed&starting-point-node-id=41505%3A11064&embed-host=share"
        }
    }
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

# Use case aliases (mapping common names to canonical keys)
USE_CASE_ALIASES = {
    "food and beverage": "food_delivery",
    "food and beverage solution": "food_delivery",
    "food delivery": "food_delivery",
    "food": "food_delivery",
    "grocery delivery": "grocery_delivery",
    "grocery delivery solution": "grocery_delivery",
    "grocery": "grocery_delivery",
    "milk delivery": "milk_delivery",
    "milk delivery solution": "milk_delivery",
    "milk": "milk_delivery",
    "courier delivery": "courier_delivery",
    "courier delivery solution": "courier_delivery",
    "courier": "courier_delivery",
    "courier service": "courier_delivery",
    "beauty services": "beauty_services",
    "beauty services scheduling": "beauty_services",
    "beauty services scheduling solution": "beauty_services",
    "beauty": "beauty_services",
    "laundry on demand": "laundry_on_demand",
    "laundry on demand services": "laundry_on_demand",
    "laundry on demand services solution": "laundry_on_demand",
    "laundry": "laundry_on_demand",
    "document delivery": "document_delivery",
    "document delivery solution": "document_delivery",
    "document": "document_delivery",
    "flower delivery": "flower_delivery",
    "flower delivery solution": "flower_delivery",
    "flower": "flower_delivery",
    "medicine delivery": "medicine_delivery",
    "medicine delivery solution": "medicine_delivery",
    "medicine": "medicine_delivery",
    "liquor delivery": "liquor_delivery",
    "liquor delivery solution": "liquor_delivery",
    "liquor": "liquor_delivery",
    "gift delivery": "gift_delivery",
    "gift delivery solution": "gift_delivery",
    "gift": "gift_delivery",
    "roadside assistance": "roadside_assistance",
    "roadside assistance services": "roadside_assistance",
    "roadside assistance services solution": "roadside_assistance",
    "roadside": "roadside_assistance",
    "taxi booking": "taxi_booking",
    "taxi": "taxi_booking",
    "pet marketplace": "pet_marketplace",
    "pet market": "pet_marketplace",
    "pet": "pet_marketplace",
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

def _norm_use_case(s: Optional[str]) -> Optional[str]:
    if not s: return None
    key = s.strip().lower()
    if key in USE_CASE_ALIASES:
        return USE_CASE_ALIASES[key]
    # fuzzy match to canonical keys
    canon = list(USE_CASE_PROTOTYPES.keys())
    match = get_close_matches(key, canon, n=1, cutoff=0.75)
    return match[0] if match else key

def _render_demo_html(app: Optional[str] = None, demo_type: Optional[str] = None) -> str:
    app = _norm_app(app)
    demo_type = _norm_type(demo_type)

    def pill(label, url):
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
        blocks.append(f"<h3>{title}</h3><p>{' '.join(pills)}</p>")

    if not blocks:
        return "<p>No demo links configured yet.</p>"
    return "<h2>Explore Our Live Demos<br></h2>" + "".join(blocks)

def _render_use_case_prototypes_html(use_case: Optional[str] = None) -> str:
    use_case = _norm_use_case(use_case)
    
    def pill(label, url):
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
    
    def format_use_case_name(name: str) -> str:
        """Convert snake_case to Title Case"""
        return name.replace("_", " ").title()
    
    def format_section_name(section: str) -> str:
        """Format section names for display"""
        return section.replace("_", " ").title()
    
    blocks = []
    items = USE_CASE_PROTOTYPES.items()
    if use_case and use_case in USE_CASE_PROTOTYPES:
        items = [(use_case, USE_CASE_PROTOTYPES[use_case])]
    
    for use_case_name, data in items:
        use_case_title = format_use_case_name(use_case_name)
        use_case_block = []
        
        # Iterate through sections (multivendor, single_vendor, admin_dashboard, etc.)
        for section_name, section_data in data.items():
            if not isinstance(section_data, dict):
                continue
            
            section_pills = []
            section_title = format_section_name(section_name)
            
            # Add prototype link
            if "prototype" in section_data:
                section_pills.append(pill("Prototype", section_data["prototype"]))
            
            # Add iOS link if available
            if "ios" in section_data:
                section_pills.append(pill("iOS", section_data["ios"]))
            
            # Add Android link if available
            if "android" in section_data:
                section_pills.append(pill("Android", section_data["android"]))
            
            # Add web link if available
            if "web" in section_data:
                section_pills.append(pill("Web", section_data["web"]))
            
            if section_pills:
                use_case_block.append(f"<h4>{section_title}</h4><p>{' '.join(section_pills)}</p>")
        
        if use_case_block:
            blocks.append(f"<h3>{use_case_title}</h3>{''.join(use_case_block)}")
    
    if not blocks:
        return "<p>No prototype links found for this use case.</p>"
    return "<h2>Use Case Prototypes & Demos<br></h2>" + "".join(blocks)

@tool("get_demo_links", return_direct=False)
def get_demo_links(app: Optional[str] = None, demo_type: Optional[str] = None) -> str:
    """Return HTML with demo links. app ∈ {customer app, rider app, restaurant app, customer web, admin dashboard, server}. demo_type ∈ {ios, android, web, prototype, docs}. Omit args to show all."""
    return _render_demo_html(app, demo_type)

@tool("get_use_case_prototypes", return_direct=False)
def get_use_case_prototypes(use_case: Optional[str] = None) -> str:
    """Return HTML with prototype links for use cases. use_case can be any use case name (e.g., 'food delivery', 'grocery delivery', 'courier delivery', etc.). Omit arg to show all."""
    return _render_use_case_prototypes_html(use_case)

# Small, deterministic router that only decides whether to call the tool
router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=OPENAI_API_KEY).bind_tools([get_demo_links, get_use_case_prototypes])

ROUTER_SYS = (
    "You can call get_demo_links when the user asks for a demo or demo links for applications. "
    "If they specify an app (customer app, rider app, restaurant app, customer web, admin dashboard, server) "
    "and/or a demo type (ios, android, web, prototype, docs), pass them. "
    "If unspecified, omit the arg to show all. "
    "You can call get_use_case_prototypes when the user asks for prototypes, demos, or demo links related to use cases "
    "(e.g., food delivery, grocery delivery, courier delivery, beauty services, laundry, document delivery, flower delivery, "
    "medicine delivery, liquor delivery, gift delivery, roadside assistance, single vendor web demo). "
    "If they specify a use case name, pass it. If unspecified, omit the arg to show all. "
    "If the request is not about demos or prototypes, do not call any tool."
)

def maybe_answer_with_demos(user_msg: str) -> Optional[str]:
    ai = router_llm.invoke([SystemMessage(content=ROUTER_SYS), HumanMessage(content=user_msg)])
    calls = ai.additional_kwargs.get("tool_calls") or []
    for c in calls:
        fn = (c.get("function") or {}).get("name")
        if fn == "get_demo_links":
            raw = (c.get("function") or {}).get("arguments") or "{}"
            args = json.loads(raw)
            return get_demo_links.invoke(args)
        elif fn == "get_use_case_prototypes":
            raw = (c.get("function") or {}).get("arguments") or "{}"
            args = json.loads(raw)
            return get_use_case_prototypes.invoke(args)
    return None

# ---------- Mongo helpers ----------
try:
    mongo_client = MongoClient(MONGO_URI) if MONGO_URI else None
except Exception as e:
    mongo_client = None
    print("Mongo init failed:", e)

chat_col = mongo_client[MONGO_DB][MONGO_COL] if mongo_client else None

def _now_utc():
    return datetime.now(timezone.utc)

def _expire_at():
    return _now_utc() + timedelta(days=TTL_DAYS)

def _ensure_indexes():
    if chat_col is None:
        return
    # One document per session id
    chat_col.create_index([("session_id", ASCENDING)], unique=True)
    # TTL based on expireAt
    chat_col.create_index([("expireAt", ASCENDING)], expireAfterSeconds=0)

_ensure_indexes()

def decode_user_token(user_token: Optional[str]) -> Optional[Dict]:
    """
    Decode and verify custom WordPress user token.
    Format: {base64url_encoded_json}.{hmac_signature}
    The token contains: iss, iat, exp, uid, uname, email
    """
    if not user_token:
        return None
    
    try:
        # Split token into payload and signature
        parts = user_token.split('.')
        if len(parts) != 2:
            print(f"Invalid token format: expected 'payload.signature', got {len(parts)} parts")
            return None
        
        b64_payload, sig = parts
        
        # Verify signature using HMAC SHA256
        expected_sig = hmac.new(
            ENATEGA_USER_SIGNING_SECRET.encode('utf-8'),
            b64_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(sig, expected_sig):
            print("Token signature verification failed")
            return None
        
        # Decode base64url payload
        # Base64URL uses -_ instead of +/ and no padding
        b64_payload_normalized = b64_payload.replace('-', '+').replace('_', '/')
        # Add padding if needed
        padding = len(b64_payload_normalized) % 4
        if padding:
            b64_payload_normalized += '=' * (4 - padding)
        
        decoded_bytes = base64.b64decode(b64_payload_normalized)
        decoded = json.loads(decoded_bytes.decode('utf-8'))
        
        # Check expiration
        exp = decoded.get('exp')
        if exp and exp < time.time():
            print("User token expired")
            return None
        
        # Map token fields to database schema format
        # Token contains: uid, uname, email, iss, iat, exp
        user_info = {
            "id": decoded.get("uid"),  # WordPress user ID
            "user_login": decoded.get("uname"),  # WordPress username
            "user_email": decoded.get("email"),  # User email
        }
        
        # Remove None values
        user_info = {k: v for k, v in user_info.items() if v is not None}
        
        # Include other token fields for reference
        if decoded.get("iss"):
            user_info["iss"] = decoded.get("iss")  # Issuer (home_url)
        if decoded.get("iat"):
            user_info["iat"] = decoded.get("iat")  # Issued at
        if decoded.get("exp"):
            user_info["exp"] = decoded.get("exp")  # Expiration
        
        if user_info:
            print(f"Debug: Decoded user token - ID: {user_info.get('id')}, Login: {user_info.get('user_login')}, Email: {user_info.get('user_email')}")
        return user_info if user_info else None
        
    except json.JSONDecodeError as e:
        print(f"Error decoding token JSON: {e}")
        return None
    except Exception as e:
        print(f"Error decoding user token: {e}")
        import traceback
        traceback.print_exc()
        return None

def ensure_session_doc(session_id: str, page_url: Optional[str] = None, user_details: Optional[Dict] = None):
    """Create or touch a session document with user details."""
    if chat_col is None or not session_id:
        return
    try:
        update = {
            "$setOnInsert": {
                "session_id": session_id,
                "started_at": _now_utc(),
                "messages": [],
            },
            "$set": {
                "last_active": _now_utc(),
                "expireAt": _expire_at(),
            },
        }
        if page_url:
            update["$addToSet"] = {"page_urls": page_url}
        if user_details:
            # Store user details (e.g., user_id, email, etc. from token)
            update["$set"]["user_details"] = user_details
        chat_col.update_one({"session_id": session_id}, update, upsert=True)
    except DuplicateKeyError:
        pass

def append_message(session_id: str, role: str, html_text: str, user_details: Optional[Dict] = None):
    """Append a message into the session transcript with user details."""
    if chat_col is None or not session_id:
        return
    safe = (html_text or "").strip()
    message_doc = {
        "role": "assistant" if role == "assistant" else "user",
        "html": safe,
        "ts": _now_utc(),
    }
    # Add user details to user messages
    if role == "user" and user_details:
        message_doc["user_details"] = user_details
    
    chat_col.update_one(
        {"session_id": session_id},
        {
            "$push": {"messages": message_doc},
            "$set": {"last_active": _now_utc(), "expireAt": _expire_at()},
        },
        upsert=True,
    )

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

    # Decode user token to get user details
    user_details = decode_user_token(req.user_token)

    # NEW: persist user turn with user details
    try:
        ensure_session_doc(req.session_id, user_details=user_details)
        append_message(req.session_id, "user", html.escape(req.message), user_details=user_details)
    except Exception as e:
        print("Mongo log (user) failed:", e)

    memory = get_memory(req.session_id)
    if hasattr(memory, "buffer") and isinstance(memory.buffer, list):
        memory.buffer[:] = memory.buffer[-(2 * MAX_TURNS):]

    demo_html = maybe_answer_with_demos(req.message)
    if demo_html:
        # NEW: persist assistant turn
        try: append_message(req.session_id, "assistant", demo_html)
        except Exception as e: print("Mongo log (assistant demo) failed:", e)
        return ChatResp(
            answer=demo_html,
            sources=[],
            used_chunks=0,
            latency_ms=int((time.time() - t0) * 1000),
        )

    # Use new retriever API
    seed_docs = retriever.invoke(req.message)
    if not seed_docs:
        answer = "I don’t have that in my current knowledge yet. Please rephrase or check the site."
        try: append_message(req.session_id, "assistant", answer)
        except Exception as e: print("Mongo log (assistant fallback) failed:", e)
        return ChatResp(
            answer=answer,
            sources=[],
            used_chunks=0,
            latency_ms=int((time.time() - t0) * 1000),
        )

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt": RAG_PROMPT},
    )

    result = chain.invoke({"question": req.message})
    answer = result["answer"]
    docs = result.get("source_documents", []) or []
    sources = list({d.metadata.get("url") for d in docs if d.metadata.get("url")})[:5]

    # NEW: persist assistant turn
    try:
        append_message(req.session_id, "assistant", answer)
    except Exception as e:
        print("Mongo log (assistant) failed:", e)

    return ChatResp(
        answer=answer,
        sources=sources,
        used_chunks=len(docs),
        latency_ms=int((time.time() - t0) * 1000),
    )

app.mount("/static", StaticFiles(directory="frontend/public"), name="static")

# Serve admin panel
@app.get("/admin/{file_path:path}", include_in_schema=False)
def serve_admin(file_path: str):
    from pathlib import Path
    admin_dir = Path("admin")
    if not file_path:
        file_path = "index.html"
    file = admin_dir / file_path
    if file.exists() and file.is_file():
        return FileResponse(file)
    return FileResponse(admin_dir / "index.html")

@app.get("/", include_in_schema=False)
def root():
    return FileResponse("frontend/public/index.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.post("/clear")
def clear(session_id: str):
    # Clear in-memory context
    SESSION_MEM.pop(session_id, None)
    # Optional: also clear Mongo transcript for this session
    try:
        if chat_col is not None:
            chat_col.delete_one({"session_id": session_id})
    except Exception as e:
        print("Mongo clear failed:", e)
    return {"ok": True}

def format_docs(docs):
    return "\n\n".join(d.page_content.strip() for d in docs)

def format_history(chat_messages) -> str:
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

    # Decode user token to get user details
    user_details = decode_user_token(req.user_token)
    
    # Debug: Log if user token was provided but decoding failed
    if req.user_token and not user_details:
        print(f"Warning: User token provided but decoding returned None for session {req.session_id}")
    elif user_details:
        print(f"Debug: User details decoded successfully for session {req.session_id}: {list(user_details.keys())}")

    # NEW: persist user turn with user details
    try:
        ensure_session_doc(req.session_id, user_details=user_details)
        append_message(req.session_id, "user", html.escape(req.message), user_details=user_details)
    except Exception as e:
        print("Mongo log (user stream) failed:", e)

    demo_html = maybe_answer_with_demos(req.message)
    if demo_html:
        async def _demo() -> AsyncGenerator[bytes, None]:
            yield demo_html.encode("utf-8")
        # NEW: log assistant (demo)
        try: append_message(req.session_id, "assistant", demo_html)
        except Exception as e: print("Mongo log (assistant demo stream) failed:", e)
        return StreamingResponse(
            _demo(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Expose-Headers": "*",
            },
        )

    memory = get_memory(req.session_id)
    if hasattr(memory, "buffer") and isinstance(memory.buffer, list):
        memory.buffer[:] = memory.buffer[-(2 * MAX_TURNS):]

    docs = retriever.invoke(req.message)
    if not docs:
        async def _empty() -> AsyncGenerator[bytes, None]:
            msg = "I don’t have that in my current knowledge yet. Please rephrase or check the site."
            yield msg.encode("utf-8")
            # NEW: log fallback assistant
            try: append_message(req.session_id, "assistant", msg)
            except Exception as e: print("Mongo log (assistant empty) failed:", e)
        return StreamingResponse(
            _empty(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Expose-Headers": "*",
            },
        )

    context = "\n\n".join(d.page_content.strip() for d in docs[:4])
    hist = memory.load_memory_variables({}).get("chat_history") or []
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
            yield text.encode("utf-8")
        # Save to memory and Mongo after stream completes
        try:
            final = "".join(pieces)
            memory.save_context({"question": req.message}, {"answer": final})
            append_message(req.session_id, "assistant", final)
        except Exception as e:
            print("Finalize stream save failed:", e)

    return StreamingResponse(
        token_gen(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "*",
        },
    )

# ---------- Diagnostics ----------
CHAT_DEBUG = os.getenv("CHAT_DEBUG", "0") == "1"
_ctrl_re = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
def clean_text(s: str) -> str:
    if not isinstance(s, str):
        try:
            s = s.decode("utf-8", "replace")
        except Exception:
            s = str(s)
    s = s.replace("\u0000", " ").replace("\uffff", " ")
    s = _ctrl_re.sub(" ", s)
    return s

class DiagReq(BaseModel):
    message: str
    k: int | None = None

@app.post("/diag/retrieval")
def diag_retrieval(req: DiagReq):
    r = vs.as_retriever(search_kwargs={"k": req.k or 6})
    docs = r.invoke(req.message)
    payload = []
    for i, d in enumerate(docs):
        txt = d.page_content or ""
        payload.append({
            "idx": i,
            "chars": len(txt),
            "has_null": "\x00" in txt,
            "url": d.metadata.get("url"),
            "id": d.metadata.get("id") or d.metadata.get("point_id"),
            "sample": clean_text(txt[:220]).replace("\n", " "),
        })
    return {"k": len(docs), "chunks": payload}

# ---------- OPTIONAL: simple session browsers ----------
@app.get("/sessions")
def list_sessions(limit: int = 50):
    if chat_col is None:
        return []
    cur = chat_col.find(
        {}, {"_id": 0, "session_id": 1, "started_at": 1, "last_active": 1, "page_urls": 1}
    ).sort("last_active", -1).limit(min(200, max(1, limit)))
    return list(cur)

@app.get("/session/{session_id}")
def get_session(session_id: str):
    if chat_col is None:
        return {}
    doc = chat_col.find_one({"session_id": session_id}, {"_id": 0})
    return doc or {}
