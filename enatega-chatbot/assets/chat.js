(function () {
  const cfg = window.ENATEGA_CHAT_CFG || {};
  const JSON_ENDPOINT   = cfg.endpoint       || "https://enategawebsitechatbot-production.up.railway.app/chat";
  const STREAM_ENDPOINT = cfg.streamEndpoint || "https://enategawebsitechatbot-production.up.railway.app/chat_stream";
  const USE_STREAM      = cfg.useStream !== false; // default true

  // ===== NEW: CPT save endpoint + token =====
  const SAVE_ENDPOINT = cfg.saveEndpoint || "/wp-json/enatega/v1/save_chat";
  const LOG_TOKEN     = cfg.logToken || "change-me-please"; // set from PHP

  // --- derive API base for /clear (strip /chat or /chat_stream) ---
  const API_BASE = (JSON_ENDPOINT || "").replace(/\/chat(?:_stream)?\/?$/i, "");

  // ========= ONE-TIME CLEANUP: remove old localStorage artifacts (from an older build) =========
  (function migrateOldLocalStorage() {
    try {
      const LOG_PREFIX = "enatega_chat_log_v1_";
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (!k) continue;
        if (k === "enatega_sid" || k.startsWith(LOG_PREFIX)) {
          localStorage.removeItem(k);
          i--;
        }
      }
    } catch {}
  })();

  // ========== RELOAD DETECTION ==========
  function isReloadNav() {
    const entries = performance.getEntriesByType && performance.getEntriesByType("navigation");
    if (entries && entries[0] && typeof entries[0].type === "string") return entries[0].type === "reload";
    return performance && performance.navigation && performance.navigation.type === 1; // 1 = reload
  }

  // ========= SESSION (per tab, UI memory) =========
  const SID_KEY   = "enatega_sid";           // per-tab session id (so UI clears on reload)
  const LOG_PREFIX= "enatega_chat_log_v1_";  // per-tab chat log in sessionStorage

  // Stable session id (per tab)
  let sid = sessionStorage.getItem(SID_KEY);
  if (!sid) { sid = (self.crypto?.randomUUID?.() || String(Date.now()) + Math.random()); sessionStorage.setItem(SID_KEY, sid); }

  const LOG_KEY_FOR = (s) => `${LOG_PREFIX}${s}`;
  let LOG_KEY = LOG_KEY_FOR(sid);

  // On reload: wipe UI chat, clear server memory for this SID, rotate SID
  if (isReloadNav()) {
    try { sessionStorage.removeItem(LOG_KEY); } catch {}
    try { localStorage.removeItem("enatega_nudge_dismissed"); } catch {}
    if (sid && API_BASE) {
      fetch(`${API_BASE}/clear?session_id=${encodeURIComponent(sid)}`).catch(() => {});
    }
    sid = (self.crypto?.randomUUID?.() || String(Date.now()) + Math.random());
    sessionStorage.setItem(SID_KEY, sid);
    LOG_KEY = LOG_KEY_FOR(sid);
  }

  // ===== NEW: persistent visitor id (cross-tabs) for analytics =====
  const VISITOR_KEY = "enatega_visitor_id";
  let visitorId = localStorage.getItem(VISITOR_KEY);
  if (!visitorId) { visitorId = (self.crypto?.randomUUID?.() || String(Date.now())+Math.random()); localStorage.setItem(VISITOR_KEY, visitorId); }

  // ----- UI log (per-tab, sessionStorage) -----
  let chatLog = [];
  function loadLog() {
    try { chatLog = JSON.parse(sessionStorage.getItem(LOG_KEY) || "[]"); }
    catch { chatLog = []; }
  }
  let saveTimer = null;
  function saveLog() {
    try { sessionStorage.setItem(LOG_KEY, JSON.stringify(chatLog.slice(-200))); } catch {}
  }
  function saveLogSoon() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveLog, 150);
  }

  // ===== NEW: LocalStorage transcript (persisted) to push into WordPress CPT =====
  const LOCAL_CPT_KEY = `enatega_cpt_${sid}`;
  let cptLog = null;

  function loadCptLocal() {
    try {
      cptLog = JSON.parse(localStorage.getItem(LOCAL_CPT_KEY) || "null");
    } catch { cptLog = null; }
    if (!cptLog) {
      cptLog = {
        session_id: sid,
        visitor_id: visitorId,
        started_at: Date.now(),
        last_active: null,
        page_urls: [],
        messages: [],        // [{role:'user'|'assistant', html, ts}]
        _synced_len: 0       // how many messages have been sent to WP
      };
      saveCptLocal();
    }
  }
  function saveCptLocal() {
    try { localStorage.setItem(LOCAL_CPT_KEY, JSON.stringify(cptLog)); } catch {}
  }
  function appendCpt(role, html) {
    cptLog.messages.push({ role, html, ts: Date.now() });
    cptLog.last_active = Date.now();
    const here = location.href;
    if (!cptLog.page_urls.includes(here)) cptLog.page_urls.push(here);
    saveCptLocal();
    flushCptSoon();
  }

  // Send full transcript to CPT (upsert by session_id)
  let flushTimerCpt = null;
  function flushCptSoon() {
    if (flushTimerCpt) return;
    flushTimerCpt = setTimeout(flushCptToWP, 1200);
  }
  function postJSONWithBeacon(url, payload) {
    const body = JSON.stringify(payload);
    const withToken = `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(LOG_TOKEN)}`;
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(withToken, blob);
      return Promise.resolve({ ok: true });
    }
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  }
  async function flushCptToWP() {
    clearTimeout(flushTimerCpt);
    flushTimerCpt = null;
    if (!cptLog || !cptLog.messages || cptLog.messages.length === 0) return;

    // Only push if there’s something new since last sync
    if (cptLog._synced_len >= cptLog.messages.length) return;

    const payload = {
      token: LOG_TOKEN,
      session_id: cptLog.session_id,
      visitor_id: cptLog.visitor_id,
      started_at: cptLog.started_at,
      last_active: cptLog.last_active || Date.now(),
      page_urls: cptLog.page_urls,
      messages: cptLog.messages
    };

    try {
      const res = await postJSONWithBeacon(SAVE_ENDPOINT, payload);
      if (res && res.ok !== false) {
        // mark all synced
        cptLog._synced_len = cptLog.messages.length;
        saveCptLocal();
      }
    } catch (e) {
      // swallow; we’ll retry on next message / unload
      console.warn("CPT save failed (will retry):", e);
    }
  }

  // Flush when leaving the page
  window.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushCptToWP();
  });
  window.addEventListener("beforeunload", () => flushCptToWP());

  // ----- DOM helpers -----
  const $msgs = () => document.getElementById("enatega-chat-msgs");
  const $form = () => document.getElementById("enatega-chat-form");
  const $input= () => document.getElementById("enatega-chat-input");
  const $send = () => document.getElementById("enatega-chat-send");
  const $foot = () => document.getElementById("enatega-chat-footnote");

  // ===== Sticky-bottom + scroll-down arrow =====
  let autoStickBottom = false; // becomes true once a conversation exists
  const SCROLL_ARROW_THRESHOLD = 48; // px away from bottom to show arrow
  let downBtn = null;
  let downBtnObserver = null;

  function gapFromBottom(el) { return Math.max(0, el.scrollHeight - el.scrollTop - el.clientHeight); }
  function isNearBottom(el, thresholdPx = 8) { return gapFromBottom(el) <= thresholdPx; }
  function scrollToBottom(smooth = false) {
    const el = $msgs(); if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
  }
  function updateDownButtonVisibility() {
    const el = $msgs(); if (!el || !downBtn) return;
    const notNearBottom = gapFromBottom(el) > SCROLL_ARROW_THRESHOLD;
    if (notNearBottom) { downBtn.classList.add("show"); downBtn.style.display = "inline-flex"; }
    else               { downBtn.classList.remove("show"); downBtn.style.display = "none"; }
  }
  function maybeAutoScroll(force = false) {
    const el = $msgs(); if (!el) return;
    if (force || autoStickBottom || isNearBottom(el)) { scrollToBottom(false); }
    updateDownButtonVisibility();
  }
  function ensureDownButton() {
    const root = $msgs();
    if (!root) return;

    if (!downBtn) {
      downBtn = document.createElement("button");
      downBtn.id = "enatega-scroll-down";
      downBtn.type = "button";
      downBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
      downBtn.style.position = "absolute";
      downBtn.style.right = "10px";
      downBtn.style.bottom = "10px";
      downBtn.style.display = "none";
      downBtn.addEventListener("click", () => {
        autoStickBottom = true;
        scrollToBottom(true);
        updateDownButtonVisibility();
      });
      root.appendChild(downBtn);

      root.addEventListener("scroll", () => {
        autoStickBottom = isNearBottom(root);
        updateDownButtonVisibility();
      });

      window.addEventListener("resize", updateDownButtonVisibility);

      if ("MutationObserver" in window) {
        downBtnObserver = new MutationObserver(() => updateDownButtonVisibility());
        downBtnObserver.observe(root, { childList: true, subtree: true, characterData: true });
      }
    }
    updateDownButtonVisibility();
  }

  // ----- HTML safety & spacing -----
  function sanitizeBasicHTML(html) {
    // 1) Extract Calendly iframes before sanitization
    const calendlyIframeRegex = /<iframe\s+[^>]*src=["']https?:\/\/(www\.)?calendly\.com[^"']*["'][^>]*>[\s\S]*?<\/iframe>/gi;
    const calendlyIframes = [];
    let safe = String(html || "").replace(calendlyIframeRegex, (match) => {
      // Verify it's actually a Calendly iframe and sanitize it
      if (match.includes('calendly.com')) {
        calendlyIframes.push(match);
        return `__CALENDLY_IFRAME_${calendlyIframes.length - 1}__`;
      }
      return '';
    });

    // 2) Remove script/style/noscript/iframe/object/embed/form/link/meta
    const blocked = /<\/?(script|style|noscript|iframe|object|embed|form|link|meta)[\s\S]*?>/gi;
    safe = safe.replace(blocked, "");

    // 3) Strip on* handlers and javascript: urls
    safe = safe.replace(/\son\w+="[^"]*"/gi, "")
               .replace(/\son\w+='[^']*'/gi, "")
               .replace(/javascript:/gi, "");

    // 4) Whitelist-only tags by removing everything else
    const allowed = /<(\/?(h1|h2|h3|h4|p|ul|ol|li|b|strong|i|em|br|hr|code|pre|a|button))(\s+[^>]*)?>/gi;
    safe = safe.replace(/<[^>]+>/g, m => m.match(allowed) ? m : "");

    // 5) Restore Calendly iframes
    calendlyIframes.forEach((iframe, index) => {
      safe = safe.replace(`__CALENDLY_IFRAME_${index}__`, iframe);
    });

    return safe;
  }
  function normalizeHTML(html) {
    let out = String(html || "");
    out = out.replace(/(\n\s*){2,}/g, "\n");
    out = out.replace(/<p>\s+/g, "<p>").replace(/\s+<\/p>/g, "</p>");
    out = out.replace(/<li>\s+/g, "<li>").replace(/\s+<\/li>/g, "</li>");
    out = out.replace(/<p>\s*<\/p>/g, "");
    return out;
  }

  // ----- Make links open in new tab (scoped to chat) -----
  function makeLinksExternal(root) {
    root.querySelectorAll('a[href]').forEach(a => {
      a.setAttribute('target', '_blank');
      const rel = (a.getAttribute('rel') || '').split(/\s+/);
      if (!rel.includes('noopener')) rel.push('noopener');
      if (!rel.includes('noreferrer')) rel.push('noreferrer');
      a.setAttribute('rel', rel.join(' ').trim());
    });
  }

  // ----- Rendering -----
  function addMsg(role, html, { skipLog } = {}) {
    const row = document.createElement("div");
    row.className = `enatega-chat__row ${role === "user" ? "user" : "assistant"}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const safeHTML = normalizeHTML(sanitizeBasicHTML(html));
    bubble.innerHTML = safeHTML;
    makeLinksExternal(bubble);
    row.appendChild(bubble);
    $msgs().appendChild(row);

    maybeAutoScroll();

    if (!skipLog) {
      chatLog.push({ role, html: safeHTML });
      saveLogSoon();
    }
    return bubble;
  }

  function renderFromLog() {
    $msgs().innerHTML = "";
    for (const m of chatLog) {
      const bubble = addMsg(m.role, m.html, { skipLog: true });
      makeLinksExternal(bubble);
    }
  }

  function setBusy(b) {
    if ($send()) $send().disabled = b;
    if ($input()) $input().disabled = b;
    if ($foot())  $foot().textContent = b ? "Thinking…" : "";
  }

  // ----- Suggestions / welcome -----
  const DEFAULT_SUGGESTIONS = [
    "What is Enatega?",
    "Give me demos",
    "Products powered by Enatega",
    "Usecases of Enatega",
    "Get a Quote"
  ];

  function renderSuggestions(items) {
    const row = document.createElement("div");
    row.className = "enatega-chat__row assistant";
    row.id = "enatega-sugg-row";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = `<div class="sugg-title">Quick questions</div><div class="sugg"></div>`;
    const box = bubble.querySelector(".sugg");
    items.forEach(q => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sugg-chip";
      btn.setAttribute("data-suggest", q);
      btn.textContent = q;
      box.appendChild(btn);
    });
    row.appendChild(bubble);
    $msgs().appendChild(row);
    maybeAutoScroll();
  }

  function showWelcomeIfEmpty() {
    if (!chatLog.length) {
      addMsg("assistant", `
        <h2>Welcome to Enatega Assistant</h2>
        <p>Ask me about features, demos, pricing, deployment, or integrations. You can also tap a quick question below to get started.</p>
      `);
      renderSuggestions(DEFAULT_SUGGESTIONS);
    } else {
      renderFromLog();
    }
  }

  // Suggestion click → auto send
  $msgs().addEventListener("click", (e) => {
    const btn = e.target.closest(".sugg-chip");
    if (!btn) return;
    const q = btn.getAttribute("data-suggest") || btn.textContent || "";
    const row = document.getElementById("enatega-sugg-row");
    if (row) row.remove();
    autoStickBottom = true;
    if (USE_STREAM) askStreaming(q); else askJSON(q);
  });

  // ----- Typing indicator -----
  function startTypingIndicator(bubble) {
    const holder = document.createElement("div");
    holder.className = "typing";
    holder.setAttribute("aria-live", "polite");
    holder.innerHTML = `<span class="dot"></span><span class="dot"></span><span class="dot"></span>`;
    bubble.appendChild(holder);
    let i = 0;
    const frames = ["typing", "typing.", "typing..", "typing..."];
    const timer = setInterval(() => { holder.setAttribute("aria-label", frames[i++ % frames.length]); }, 500);
    return function stop() { clearInterval(timer); holder.remove(); };
  }

  // ----- Streaming (with smoothing) -----
  const STREAM_SMOOTHING = {
    tickMs: parseInt(localStorage.getItem("chat_tick_ms") || "35", 10),
    maxCharsPerTick: parseInt(localStorage.getItem("chat_chars_per_tick") || "60", 10),
    minMerge: 16,
  };

  async function askStreaming(message) {
    setBusy(true);
    if ($foot()) $foot().textContent = "Thinking…";

    addMsg("user", message);         // UI log
    appendCpt("user", sanitizeBasicHTML(message)); // LocalStorage + schedule save to CPT

    const botBubble = addMsg("assistant", "", { skipLog: true });
    const stopTyping = startTypingIndicator(botBubble);
    let typingCleared = false;

    const botIndex = chatLog.push({ role: "assistant", html: botBubble.innerHTML }) - 1;
    saveLogSoon();

    try {
      const res = await fetch(STREAM_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, message })
      });
      if (!res.ok || !res.body) {
        const t = await res.text();
        if (!typingCleared) { stopTyping(); typingCleared = true; }
        const err = `Server error: ${res.status} ${t}`;
        botBubble.textContent = err;
        chatLog[botIndex].html = botBubble.textContent;
        saveLogSoon();
        appendCpt("assistant", sanitizeBasicHTML(err));
        flushCptSoon();
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      const queue = [];
      let displayBuf = "";
      let streamDone = false;
      let intervalId = null;

      function startFlusher() {
        if (intervalId) return;
        const { tickMs, maxCharsPerTick, minMerge } = STREAM_SMOOTHING;
        intervalId = setInterval(() => {
          if (!queue.length && streamDone) { clearInterval(intervalId); intervalId = null; return; }
          if (!queue.length) return;

          let chunk = queue.shift();
          while (queue.length && (chunk.length < maxCharsPerTick || chunk.length < minMerge)) {
            chunk += queue.shift();
          }

          const piece = chunk.slice(0, maxCharsPerTick);
          const rest  = chunk.slice(maxCharsPerTick);
          if (rest) queue.unshift(rest);

          if (!typingCleared) { stopTyping(); typingCleared = true; }

          displayBuf += piece;
          const safe = normalizeHTML(sanitizeBasicHTML(displayBuf));
          botBubble.innerHTML = safe;
          makeLinksExternal(botBubble);

          chatLog[botIndex].html = safe;
          saveLogSoon();

          maybeAutoScroll();
        }, tickMs);
      }

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        queue.push(text);
        startFlusher();
      }
      streamDone = true;
      if ($foot()) $foot().textContent = "";

      // FINAL assistant HTML → store once
      const finalSafe = botBubble.innerHTML;
      appendCpt("assistant", finalSafe);
      flushCptSoon();
    } catch (e) {
      if (!typingCleared) { stopTyping(); typingCleared = true; }
      const err = `Network error: ${e.message}`;
      botBubble.textContent = err;
      chatLog[botIndex].html = err;
      saveLogSoon();
      appendCpt("assistant", sanitizeBasicHTML(err));
      flushCptSoon();
      console.error(e);
    } finally {
      setBusy(false);
      saveLogSoon();
    }
  }

  // ----- Non-stream fallback (JSON) -----
  async function askJSON(message) {
    setBusy(true);
    if ($foot()) $foot().textContent = "Thinking…";

    addMsg("user", message);
    appendCpt("user", sanitizeBasicHTML(message));

    const botBubble = addMsg("assistant", "", { skipLog: true });
    const botIndex = chatLog.push({ role: "assistant", html: "" }) - 1;

    try {
      const res = await fetch(JSON_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, message })
      });
      const data = await res.json();
      const safe = normalizeHTML(sanitizeBasicHTML(data.answer || "(no answer)"));
      botBubble.innerHTML = safe;
      makeLinksExternal(botBubble);
      chatLog[botIndex].html = safe;
      saveLogSoon();

      appendCpt("assistant", safe);
      flushCptSoon();

      if ($foot()) {
        if (data.sources?.length) {
          const links = data.sources.map(s => `<a href="${s}" target="_blank" rel="noopener noreferrer">source</a>`).join(" · ");
          $foot().innerHTML = `Sources: ${links}`;
        } else {
          $foot().textContent = "";
        }
      }
      maybeAutoScroll();
    } catch (err) {
      const errorMsg = "Sorry, something went wrong. Please try again.";
      botBubble.textContent = errorMsg;
      chatLog[botIndex].html = errorMsg;
      saveLogSoon();
      appendCpt("assistant", sanitizeBasicHTML(errorMsg));
      flushCptSoon();
      console.error(err);
    } finally {
      setBusy(false);
    }
  }

  // ===== NUDGE BADGE (keeps blinking until chat opens) =====
   (function () {
     const NUDGE_TEXT = "Talk to Enatega AI";

     function showNudge() {
       const chatBox = document.getElementById("enatega-chat-box");
       const isOpen = chatBox && getComputedStyle(chatBox).display !== "none" && !chatBox.classList.contains("hidden");
       if (isOpen) return;

       let nudge = document.getElementById("enatega-nudge");
       if (!nudge) {
         nudge = document.createElement("div");
         nudge.id = "enatega-nudge";
         nudge.className = "enatega-nudge";
         nudge.textContent = NUDGE_TEXT;
         document.body.appendChild(nudge);
       }

       const toggle = document.getElementById("enatega-chat-toggle");
       if (toggle) toggle.classList.add("nudge");
       let observer = null;
       function hideNudge() {
         if (toggle) toggle.classList.remove("nudge");
         if (nudge)  nudge.remove();
         if (toggle) toggle.removeEventListener("click", onOpen);
         if (form)   form.removeEventListener("submit", onSubmit);
         if (observer) observer.disconnect();
       }
       function onOpen()   { hideNudge(); }
       function onSubmit() { hideNudge(); }

       const form = document.getElementById("enatega-chat-form");
       if (toggle) toggle.addEventListener("click", onOpen, { once: true });
       if (form)   form.addEventListener("submit", onSubmit, { once: true });

       if (chatBox && "MutationObserver" in window) {
         observer = new MutationObserver(() => {
           const nowOpen = getComputedStyle(chatBox).display !== "none" && !chatBox.classList.contains("hidden");
           if (nowOpen) hideNudge();
         });
         observer.observe(chatBox, { attributes: true, attributeFilter: ["class", "style"] });
       }
     }

     window.addEventListener("DOMContentLoaded", showNudge);
     window.enategaShowNudge = showNudge;
   })();

  // ----- Init -----
  window.addEventListener("DOMContentLoaded", () => {
    // init persistent transcript store
    loadCptLocal();

    if (!$form()) return;

    loadLog();
    showWelcomeIfEmpty();

    // Initial scroll position:
    if (chatLog.length > 0) { autoStickBottom = true; scrollToBottom(false); }
    else { autoStickBottom = false; const el = $msgs(); if (el) el.scrollTop = 0; }

    // Create down-arrow, observers & wire scroll detector
    ensureDownButton();

    $form().addEventListener("submit", (e) => {
      e.preventDefault();
      const msg = $input().value.trim();
      if (!msg) return;
      $input().value = "";
      autoStickBottom = true;
      if (USE_STREAM) askStreaming(msg); else askJSON(msg);
    });

    // Optional: toggle open/close if you wired these IDs
    const toggleBtn = document.getElementById("enatega-chat-toggle");
    const chatBox   = document.getElementById("enatega-chat-box");
    const closeBtn  = document.getElementById("enatega-chat-close");
    if (toggleBtn && chatBox) {
      toggleBtn.addEventListener("click", () => {
        chatBox.style.display = "flex";
        toggleBtn.style.display = "none";
        if (chatLog.length > 0) { autoStickBottom = true; scrollToBottom(false); }
        else { autoStickBottom = false; const el = $msgs(); if (el) el.scrollTop = 0; }
        // re-evaluate arrow on open
        const el = $msgs(); if (el) setTimeout(() => { el.dispatchEvent(new Event('scroll')); }, 0);
      });
    }
    if (closeBtn && chatBox && toggleBtn) {
      closeBtn.addEventListener("click", () => {
        chatBox.style.display = "none";
        toggleBtn.style.display = "block";
      });
    }
  });
})();
