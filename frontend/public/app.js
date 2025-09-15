// const API_BASE = (localStorage.getItem("chat_api_base") || "http://127.0.0.1:8000").replace(/\/$/, "");
const API_BASE = "";
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

launcherEl.addEventListener("click", () => {
  widgetEl.classList.toggle("hidden");
  launcherEl.classList.toggle("hidden");
  inputEl.focus();
});
closeBtn.addEventListener("click", () => {
  widgetEl.classList.add("hidden");
  launcherEl.classList.remove("hidden");
});

function addMessage(role, text, sources, latency) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + (role === "user" ? "me" : "bot");

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
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

sendBtn.addEventListener("click", () => {
  const q = inputEl.value.trim();
  if (!q) return;
  inputEl.value = "";
  ask(q);
});
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBtn.click();
});

// optional greeting
addMessage("assistant", "Hi! I’m the Enatega assistant. Ask me about features, pricing, or deployment.");
