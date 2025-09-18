# 🤖 Enatega Website Chatbot

An AI-powered chatbot that answers questions about [Enatega](https://enatega.com/) using **RAG (Retrieval-Augmented Generation)**.  
It scrapes Enatega's website, rewrites text into structured paragraphs, chunks content, embeds it into **Qdrant**, and serves a chatbot API with **FastAPI + LangChain + OpenAI**.

---

## ✨ Features
- 🔍 **Automated Web Scraping** with Playwright & BeautifulSoup  
- 📝 **Text Rewriting** into headings & paragraphs for optimized chunking  
- 🧩 **Smart Chunking** (token-based with overlap for context retention)  
- 📦 **Vector Storage** in Qdrant (Cloud or Local)  
- 🧠 **RAG Chatbot API** powered by LangChain & OpenAI  
- 🌐 **Frontend Widget** easily embeddable into any website  
- 🔄 **Automated Refresh Workflow** (scrape → rewrite → chunk → ingest → deploy) every 2 months via GitHub Actions  
- ☁️ **Deployable** on Render / Railway / AWS / Docker  

---

## 📂 Project Structure

```
Enatega_website_chatbot/
├── api/                     # FastAPI app
│   └── main.py
├── data/
│   ├── raw/                 # Raw HTML
│   └── clean/               # Cleaned & rewritten text + chunks
├── frontend/                # Simple HTML/JS chatbot widget
├── web_scraping.py          # Scrapes website pages
├── rewrite_texts.py         # Rewrites text into structured form (headings/paragraphs)
├── chunking.py              # Splits text into chunks for embeddings
├── ingest_qdrant.py         # Ingests chunks into Qdrant
├── ensure_indexes.py        # Ensures indexes exist in Qdrant
├── run_pipeline.sh          # End-to-end pipeline runner
├── requirements.txt         # Python dependencies
├── Dockerfile               # For containerized deployment
└── .github/workflows/       # GitHub Actions automation
```

---

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/voiceofarsalan/Enatega_website_chatbot.git
cd Enatega_website_chatbot
```

### 2. Create virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment variables

Create a `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key
QDRANT_URL=https://your-qdrant-instance.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key
COLLECTION_NAME=enatega_home
```

---

## 🛠️ Usage

### Run the pipeline manually
```bash
./run_pipeline.sh
```

This will:
- Scrape Enatega website pages
- Rewrite text into structured format
- Chunk content
- Ingest into Qdrant
- Ensure indexes

### Run chatbot locally
```bash
uvicorn api.main:app --reload --port 8000
```

Test endpoint:
```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"What is Enatega?"}'
```

---

## 🌐 Deployment

### Docker
```bash
docker build -t enatega-bot .
docker run -p 8000:8000 enatega-bot
```

### Render (recommended)
1. Push repo to GitHub
2. Create a Web Service on Render
3. Point to this repo
4. Expose port 8000

Your bot will be live at `https://<your-app>.onrender.com`.

---

## 💬 Embedding Chat Widget

Add this snippet to your website:

```html
<div id="chatbot"></div>
<link rel="stylesheet" href="https://enatega-bot.onrender.com/style.css">
<script src="https://enatega-bot.onrender.com/app.js"></script>
<script>
  ChatbotWidget.init({
    endpoint: "https://enatega-bot.onrender.com/chat",
    title: "Enatega Assistant 🤖",
    subtitle: "Ask me anything about Enatega"
  });
</script>
```

---

## 🔄 Automated Workflow

GitHub Actions runs the full pipeline every 2 months.

The job:
- Scrapes & rewrites site content
- Updates chunks in Qdrant
- Auto-commits new data back to the repo

Trigger manually:
```bash
gh workflow run "RAG Refresh (bi-monthly)"
```

---

## 🧪 Example Queries

- What is Enatega and who is it for?
- How fast can I launch?
- Do you offer lifetime updates?
- What apps are included?
- Share some case studies.
- Does Enatega support non-food delivery?
- Who can deploy for me if I don't have a dev team?

---

## 🤝 Contributing

PRs are welcome! Open an issue for feature requests or bugs.

---

## 📜 License

MIT License © 2025 voiceofarsalan
