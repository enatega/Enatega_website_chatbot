const API_BASE = (localStorage.getItem("chat_api_base") || "http://127.0.0.1:8000").replace(/\/$/, "");
//const API_BASE = "https://enatega-bot.onrender.com";
//const API_BASE = "https://enategawebsitechatbot-production.up.railway.app"
const SESSION_ID = localStorage.getItem("chat_session_id") || crypto.randomUUID();
localStorage.setItem("chat_session_id", SESSION_ID);

const $ = s => document.querySelector(s);
const messagesEl = $("#messages");
const inputEl = $("#input");
const sendBtn = $("#sendBtn");
const latencyEl = $("#latency");
const widgetEl = $("#widget");
const launcherEl = $("#launcher");
const closeBtn = $("#closeBtn");

// Default quick questions shown on load
const DEFAULT_SUGGESTIONS = [
    "What is Enatega?",
    "Give me demos",
    "Features of Enatega",
    "Pricing options",
    "How do you deploy?"
  ];
  

launcherEl.addEventListener("click", () => {
  widgetEl.classList.toggle("hidden");
  launcherEl.classList.toggle("hidden");
  inputEl.focus();
});
closeBtn.addEventListener("click", () => {
  widgetEl.classList.add("hidden");
  launcherEl.classList.remove("hidden");
});

// Smooth streaming config (override at runtime via localStorage if you like)
const STREAM_SMOOTHING = {
    tickMs: parseInt(localStorage.getItem("chat_tick_ms") || "35", 15),   // render every N ms
    maxCharsPerTick: parseInt(localStorage.getItem("chat_chars_per_tick") || "60", 15), // add up to N chars per tick
    minMerge: 10, // merge tiny chunks to avoid stutter
  };
  


function addMessage(role, text, sources, latency) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + (role === "user" ? "me" : "bot");

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = normalizeHTML(sanitizeBasicHTML(text));

  wrap.appendChild(bubble);

  if (role !== "user" && sources && sources.length) {
    const srcWrap = document.createElement("div");
    srcWrap.className = "sources";
    for (const url of sources) {
      const a = document.createElement("a");
      a.className = "src-chip";
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = new URL(url).hostname.replace("www.","");
      srcWrap.appendChild(a);
    }
    wrap.appendChild(srcWrap);
  }

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = role === "user" ? "You" : "Assistant";
  wrap.appendChild(meta);

  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  if (typeof latency === "number") {
    latencyEl.textContent = `Latency: ${latency} ms`;
  }
}

function sanitizeBasicHTML(html) {
    // 1) Remove script/style/noscript/iframe objects entirely
    const blocked = /<\/?(script|style|noscript|iframe|object|embed|form|link|meta)[\s\S]*?>/gi;
    let safe = html.replace(blocked, "");
  
    // 2) Strip on* handlers and javascript: urls
    safe = safe
      .replace(/\son\w+="[^"]*"/gi, "")
      .replace(/\son\w+='[^']*'/gi, "")
      .replace(/javascript:/gi, "");
  
    // 3) Whitelist-only tags by removing everything else (optional—comment out if too strict)
    const allowed = /<(\/?(h1|h2|h3|h4|p|ul|ol|li|b|strong|i|em|br|hr|code|pre|a))(\s+[^>]*)?>/gi;
    safe = safe.replace(/<[^>]+>/g, m => m.match(allowed) ? m : "");
  
    return safe;
  }
  
  function normalizeHTML(html) {
    let out = html;
  
    // Collapse multiple blank lines
    out = out.replace(/(\n\s*){2,}/g, "\n");
  
    // Trim whitespace inside <p> and <li>
    out = out.replace(/<p>\s+/g, "<p>").replace(/\s+<\/p>/g, "</p>");
    out = out.replace(/<li>\s+/g, "<li>").replace(/\s+<\/li>/g, "</li>");
  
    // 🚨 Remove empty <p> tags
    out = out.replace(/<p>\s*<\/p>/g, "");
  
    return out;
  }

  async function askStreaming(question) {
    addMessage("user", question);
  
    // Prepare an empty assistant bubble
    const wrap = document.createElement("div");
    wrap.className = "msg bot";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  
    // spinner while first bytes arrive
    const thinking = document.createElement("span");
    thinking.className = "spinner";
    latencyEl.innerHTML = "";
    latencyEl.appendChild(thinking);
  
    // --- Smooth rendering queue ---
    const queue = [];
    let displayBuf = "";
    let streamDone = false;
    let intervalId = null;
  
    function startFlusher() {
      if (intervalId) return;
      const { tickMs, maxCharsPerTick, minMerge } = STREAM_SMOOTHING;
  
      intervalId = setInterval(() => {
        if (!queue.length && streamDone) {
          clearInterval(intervalId);
          intervalId = null;
          return;
        }
        if (!queue.length) return;
  
        // merge small pieces to reduce jitter
        let chunk = queue.shift();
        while (queue.length && (chunk.length < maxCharsPerTick || chunk.length < minMerge)) {
          chunk += queue.shift();
        }
  
        // limit how much we add per tick
        const piece = chunk.slice(0, maxCharsPerTick);
        const rest  = chunk.slice(maxCharsPerTick);
        if (rest) queue.unshift(rest);
  
        displayBuf += piece;
        bubble.innerHTML = normalizeHTML(sanitizeBasicHTML(displayBuf));
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }, tickMs);
    }
    // --- end smoothing ---
  
    try {
      const res = await fetch(`${API_BASE}/chat_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID, message: question }),
      });
      if (!res.ok || !res.body) {
        const t = await res.text();
        bubble.textContent = `Server error: ${res.status} ${t}`;
        return;
      }
  
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
  
      // read chunks fast, but reveal slowly via the flusher
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        queue.push(text);
        startFlusher();
      }
      streamDone = true;
    } catch (e) {
      bubble.textContent = `Network error: ${e.message}`;
    } finally {
      latencyEl.textContent = "";
    }
  }
  
  
  


    

async function ask(question) {
  addMessage("user", question);
  const thinking = document.createElement("span");
  thinking.className = "spinner";
  latencyEl.innerHTML = "";
  latencyEl.appendChild(thinking);

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, message: question }),
    });
    if (!res.ok) {
      const t = await res.text();
      addMessage("assistant", `Server error: ${res.status} ${t}`, [], 0);
      return;
    }
    const data = await res.json();
    addMessage("assistant", data.answer, data.sources || [], data.latency_ms);
  } catch (e) {
    addMessage("assistant", `Network error: ${e.message}`, [], 0);
  } finally {
    latencyEl.textContent = "";
  }
}
function renderSuggestions(items) {
    // Row that looks like a normal assistant message with chips inside
    const wrap = document.createElement("div");
    wrap.className = "msg bot";
    wrap.id = "sugg-row";
  
    const bubble = document.createElement("div");
    bubble.className = "bubble";
  
    const title = document.createElement("div");
    title.className = "sugg-title";
    title.textContent = "Quick questions";
  
    const list = document.createElement("div");
    list.className = "sugg";
  
    items.forEach(q => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sugg-chip";
      btn.setAttribute("data-suggest", q);
      btn.textContent = q;
      list.appendChild(btn);
    });
  
    bubble.appendChild(title);
    bubble.appendChild(list);
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
  
  // Welcome message + suggestions on load
  function showWelcome() {
    const html = `
      <h2><strong>Welcome to Enatega Assistant</strong></h2>
      <p>Ask me about features, demos, pricing, deployment, or integrations. You can also tap a quick question below to get started.</p>
    `;
    addMessage("assistant", html);
    renderSuggestions(DEFAULT_SUGGESTIONS);
  }
  
  // Click a suggestion → auto-send as user
  messagesEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".sugg-chip");
    if (!btn) return;
    const q = btn.getAttribute("data-suggest") || btn.textContent || "";
    // remove the suggestions row once a chip is used (optional)
    const row = document.getElementById("sugg-row");
    if (row) row.remove();
    // stream the selected question
    askStreaming(q);
  });
  
sendBtn.addEventListener("click", () => {
    const q = inputEl.value.trim();
    if (!q) return;
    inputEl.value = "";
    askStreaming(q);  // ⬅ stream instead of ask()
  });
  
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendBtn.click();
  });
  

// optional greeting
//addMessage("assistant", "Hi! I’m the Enatega assistant. Ask me about features, pricing, or deployment.");
showWelcome();
