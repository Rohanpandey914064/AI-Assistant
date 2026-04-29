/**
 * Sentinel-Agent: Frontend Dashboard Controller
 * ================================================
 * Handles chat interaction, gate status updates, session/memory
 * management, and real-time UI feedback.
 */

const API_BASE = window.location.origin;
let sessionId = "session-" + Math.random().toString(36).substring(2, 10);
let isProcessing = false;

// --- DOM Elements ---
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const charCount = document.getElementById("char-count");
const thinkingBar = document.getElementById("thinking-bar");
const thinkingText = document.getElementById("thinking-text");
const sessionInput = document.getElementById("session-input");
const sessionDisplay = document.getElementById("session-display");
const toolsList = document.getElementById("tools-list");
const tracePanel = document.getElementById("trace-panel");
const traceLink = document.getElementById("trace-link");
const memoryList = document.getElementById("memory-list");

// Gate elements
const gates = {
  1: { card: document.getElementById("gate1-card"), status: document.getElementById("gate1-status"), detail: document.getElementById("gate1-detail"), time: document.getElementById("gate1-time") },
  2: { card: document.getElementById("gate2-card"), status: document.getElementById("gate2-status"), detail: document.getElementById("gate2-detail") },
  3: { card: document.getElementById("gate3-card"), status: document.getElementById("gate3-status"), detail: document.getElementById("gate3-detail") },
};

// --- Initialize ---
sessionInput.value = sessionId;
sessionDisplay.textContent = "Session: " + sessionId.substring(0, 12);

// --- Event Listeners ---
chatInput.addEventListener("input", () => {
  charCount.textContent = chatInput.value.length + " / 4096";
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

sendBtn.addEventListener("click", sendMessage);

document.getElementById("apply-session-btn").addEventListener("click", () => {
  const val = sessionInput.value.trim();
  if (val) { sessionId = val; sessionDisplay.textContent = "Session: " + val.substring(0, 12); }
});

document.getElementById("random-session-btn").addEventListener("click", () => {
  sessionId = "session-" + Math.random().toString(36).substring(2, 10);
  sessionInput.value = sessionId;
  sessionDisplay.textContent = "Session: " + sessionId.substring(0, 12);
});

document.getElementById("load-memory-btn").addEventListener("click", loadMemory);
document.getElementById("clear-memory-btn").addEventListener("click", clearMemory);

document.querySelectorAll(".quick-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    chatInput.value = btn.dataset.msg;
    chatInput.dispatchEvent(new Event("input"));
    sendMessage();
  });
});

// --- Core Functions ---
async function sendMessage() {
  const message = chatInput.value.trim();
  if (!message || isProcessing) return;

  isProcessing = true;
  sendBtn.disabled = true;
  chatInput.value = "";
  chatInput.style.height = "auto";
  charCount.textContent = "0 / 4096";

  addMessage(message, "user");
  resetGates();
  setGateActive(1);
  showThinking("Gate 1: Scanning for threats...");

  try {
    const response = await fetch(API_BASE + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const detail = errData.detail || {};

      if (response.status === 400 && detail.threat_type) {
        // Gate 1 blocked
        setGateFail(1, "BLOCKED — " + (detail.threat_type || "Threat detected"));
        addMessage("🚨 **Security Alert**: " + (detail.message || "Request blocked by Gate 1."), "system", true);
        hideThinking();
        return;
      }
      throw new Error(detail.message || "Server error: " + response.status);
    }

    const data = await response.json();

    // Update Gate 1
    setGatePass(1, "Passed in " + (data.security.gate1_scan_ms || 0).toFixed(1) + "ms");

    // Update Gate 2
    setGateActive(2);
    showThinking("Gate 2: ReAct reasoning (" + data.iterations + " iterations)...");
    await sleep(400);
    setGatePass(2, data.iterations + " iterations, " + data.tools_used.length + " tools");

    // Update Gate 3
    setGateActive(3);
    showThinking("Gate 3: Validating output...");
    await sleep(300);
    if (data.security.gate3_clean) {
      setGatePass(3, "Clean — no PII detected");
    } else {
      setGatePass(3, "Redacted " + data.security.gate3_violations.length + " items");
    }

    // Update tools panel
    updateToolsPanel(data.tools_used);

    // Update trace link
    if (data.trace_url) {
      tracePanel.style.display = "flex";
      traceLink.href = data.trace_url;
    }

    hideThinking();
    addMessage(data.response, "system");

  } catch (err) {
    hideThinking();
    addMessage("⚠️ Error: " + err.message, "system", true);
  } finally {
    isProcessing = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

function addMessage(content, type, isError = false) {
  const div = document.createElement("div");
  div.className = "message message--" + type + (isError ? " message--error" : "");

  const avatar = document.createElement("div");
  avatar.className = "message-avatar " + (type === "user" ? "user-avatar" : "system-avatar");
  avatar.textContent = type === "user" ? "You" : "SA";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  const contentEl = document.createElement("div");
  contentEl.className = "message-content";
  contentEl.innerHTML = formatContent(content);

  const timeEl = document.createElement("div");
  timeEl.className = "message-time";
  timeEl.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  bubble.appendChild(contentEl);
  bubble.appendChild(timeEl);
  div.appendChild(avatar);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatContent(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

// --- Gate Helpers ---
function resetGates() {
  for (const g of Object.values(gates)) {
    g.card.className = "gate-card";
    g.status.className = "gate-status";
    g.status.textContent = "—";
    g.detail.textContent = "Awaiting...";
    if (g.time) g.time.textContent = "";
  }
  toolsList.innerHTML = '<span class="tools-empty">No tools used yet</span>';
  tracePanel.style.display = "none";
}

function setGateActive(n) {
  gates[n].card.className = "gate-card active";
  gates[n].status.className = "gate-status active";
  gates[n].status.textContent = "ACTIVE";
  gates[n].detail.textContent = "Processing...";
}

function setGatePass(n, detail) {
  gates[n].card.className = "gate-card pass";
  gates[n].status.className = "gate-status pass";
  gates[n].status.textContent = "PASS";
  gates[n].detail.textContent = detail;
}

function setGateFail(n, detail) {
  gates[n].card.className = "gate-card fail";
  gates[n].status.className = "gate-status fail";
  gates[n].status.textContent = "FAIL";
  gates[n].detail.textContent = detail;
}

function updateToolsPanel(tools) {
  if (!tools.length) return;
  const icons = { get_weather: "🌤", get_news: "📰", calculate: "🧮", save_preference: "💾", get_preference: "📋", list_preferences: "📋", delete_preference: "🗑" };
  toolsList.innerHTML = tools.map((t) => '<span class="tool-chip">' + (icons[t] || "🔧") + " " + t + "</span>").join("");
}

function showThinking(text) {
  thinkingBar.style.display = "flex";
  thinkingText.textContent = text;
}
function hideThinking() { thinkingBar.style.display = "none"; }
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

// --- Memory ---
async function loadMemory() {
  try {
    const res = await fetch(API_BASE + "/memory/" + sessionId);
    const data = await res.json();
    if (!data.memories || !data.memories.length) {
      memoryList.innerHTML = '<span class="tools-empty">No memories found</span>';
      return;
    }
    memoryList.innerHTML = data.memories.map((m) =>
      '<div class="memory-item">' + m.content.substring(0, 120) + (m.content.length > 120 ? "..." : "") +
      '<div class="memory-item-time">' + m.created_at + "</div></div>"
    ).join("");
  } catch { memoryList.innerHTML = '<span class="tools-empty">Failed to load</span>'; }
}

async function clearMemory() {
  try {
    await fetch(API_BASE + "/memory/" + sessionId, { method: "DELETE" });
    memoryList.innerHTML = '<span class="tools-empty">Memory cleared</span>';
  } catch { /* ignore */ }
}
