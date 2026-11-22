import json
import logging
import tempfile
from typing import Literal

import pydantic
from fastapi import APIRouter, HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from geenii.agent.base_agent import BaseAgent
from geenii.agent.tasks import LLMTask
from geenii.chat_models import ContentPart, TextContent
from geenii.config import DEFAULT_COMPLETION_MODEL
from geenii.datamodels import ModelMessage
from geenii.hitl import NoHumanInTheLoopController
from geenii.memory import ShortTermChatMemory
from geenii.skills import SkillRegistry
from geenii.tool.registry import ToolRegistry
from geenii.tool.webtools import WebFetchTool

logger = logging.getLogger(__name__)

# Models offered in the sidebar's model selection, as (model id, label). The first one is preselected.
FF_CHATBOT_MODELS: list[tuple[str, str]] = [
    (DEFAULT_COMPLETION_MODEL, f"Default ({DEFAULT_COMPLETION_MODEL})"),
    ("ollama:gemma4:latest", "Gemma 4 (Ollama)"),
    ("ollama:qwen3:8b", "Qwen3 8B (Ollama)"),
    ("openai:gpt-4o-mini", "GPT-4o mini (OpenAI)"),
    ("anthropic:claude-haiku-4-5", "Claude Haiku 4.5 (Anthropic)"),
]


def _ff_models() -> list[dict[str, str]]:
    """FF_CHATBOT_MODELS without duplicate ids (e.g. when the default model is also listed)."""
    seen: set[str] = set()
    models = []
    for model_id, label in FF_CHATBOT_MODELS:
        if model_id not in seen:
            seen.add(model_id)
            models.append({"id": model_id, "label": label})
    return models

FF_CHATBOT_SYSTEM_PROMPT = (
    "You are Geenii, a helpful assistant running in the Firefox sidebar. "
    "Answer concisely and accurately. If the user shares selected text from a web page, "
    "use it as context for your answer. "
    "Use the web_fetch tool when you need the content of a web page, e.g. a URL the user mentions."
    "Extract URLs from <pageurl></pageurl> tags."
    "Always fetch the url contents"
)


class FirefoxChatbotAgent(BaseAgent):
    """
    Chat completion agent for the Firefox AI chatbot sidebar.
    Only tool is web_fetch; no skills, no slash commands / macros, no human-in-the-loop
    (tool calls are approved automatically).
    Stateless: the sidebar sends the whole conversation with every request,
    so the agent uses in-memory chat memory seeded with that history.
    """

    def __init__(self, history: list[ModelMessage] | None = None, model: str | None = None):
        tool_registry = ToolRegistry()
        tool_registry.register(WebFetchTool())
        memory = ShortTermChatMemory()
        for msg in history or []:
            memory.append(msg)
        super().__init__(
            name="firefox-chatbot",
            description="Firefox sidebar chatbot",
            model=model or DEFAULT_COMPLETION_MODEL,
            system_prompt=FF_CHATBOT_SYSTEM_PROMPT,
            memory=memory,
            cwd=tempfile.gettempdir(),  # web_fetch doesn't use the working dir, no need for a dedicated agent dir
            allowed_tools={WebFetchTool.NAME},
            mcp_servers=set(),
            tool_registry=tool_registry,
            skill_registry=SkillRegistry(),
            hitl=NoHumanInTheLoopController(),
        )

    def _initialize(self):
        self._initialized = True

    def _handle_message(self, message: str | list[ContentPart]):
        # no macro handling: every message goes straight to the model
        self.enqueue_task(LLMTask(self, message=message, allowed_tools=set(self.allowed_tools)))


router = APIRouter(prefix="/ff", tags=["firefox"])


class FFChatMessage(pydantic.BaseModel):
    role: Literal["user", "assistant"]
    content: str


class FFChatRequest(pydantic.BaseModel):
    messages: list[FFChatMessage]
    model: str | None = None  # one of FF_CHATBOT_MODELS; the first one if not given


@router.post("/chat", include_in_schema=False)
def ff_chat(body: FFChatRequest) -> dict:
    if not body.messages or body.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Last message must be a user message")
    models = [m["id"] for m in _ff_models()]
    model = body.model or models[0]
    if model not in models:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model}")

    print(body.messages)
    *previous, last = body.messages
    history = [ModelMessage(role=m.role, content=[TextContent(text=m.content)]) for m in previous]
    print(history)
    agent = FirefoxChatbotAgent(history=history, model=model)

    reply_parts = []
    for msg in agent.process(last.content):
        # only the model's text: tool calls are assistant messages too, tool results have role "tool"
        if isinstance(msg, ModelMessage) and msg.role == "assistant":
            text = "\n".join(p.text for p in msg.content if isinstance(p, TextContent)).strip()
            if text:
                reply_parts.append(text)

    return {"reply": "\n\n".join(reply_parts) or "(no response)"}

@router.get("", response_class=HTMLResponse)
def ff_chatbot_proxy(request: Request):
    print(request.query_params)
    print(request)
    # "<\\/" keeps a "</script>" in a label from ending the script element
    models_json = json.dumps(_ff_models()).replace("</", "<\\/")
    return FF_CHATBOT_HTML.replace("__FF_MODELS__", models_json)


FF_CHATBOT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Geenii 4 Firefox</title>

<style>
  :root {
    --bg: #f6f7fb;
    --surface: #ffffff;
    --surface-2: #eef0f6;
    --border: #e1e4ee;
    --text: #1d2030;
    --text-muted: #6b7088;
    --accent: #6d5cf6;
    --accent-2: #3d8bfd;
    --accent-text: #ffffff;
    --danger: #d64545;
    --danger-bg: #fdeeee;
    --shadow: 0 1px 2px rgba(20, 22, 40, 0.06), 0 4px 14px rgba(20, 22, 40, 0.06);
    --radius: 16px;
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14151b;
      --surface: #1d1f28;
      --surface-2: #262935;
      --border: #2f3241;
      --text: #eceef6;
      --text-muted: #9095ad;
      --accent: #8b7bff;
      --accent-2: #4f9bff;
      --danger: #ff7a7a;
      --danger-bg: #3a2024;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 4px 14px rgba(0, 0, 0, 0.25);
    }
  }

  * { box-sizing: border-box; }

  html { font-size: 16px; }
  html[data-font-size="sm"] { font-size: 14px; }
  html[data-font-size="lg"] { font-size: 18px; }

  body {
    margin: 0;
    font: 1rem/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    display: flex;
    flex-direction: column;
    height: 100dvh;
  }

  button, select, textarea { font: inherit; color: inherit; }
  button { cursor: pointer; }

  :focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* header */

  header {
    padding: 12px 14px 10px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .logo {
    width: 30px;
    height: 30px;
    flex: none;
    border-radius: 9px;
    display: grid;
    place-items: center;
    font-weight: 700;
    color: var(--accent-text);
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    box-shadow: 0 2px 8px color-mix(in srgb, var(--accent) 40%, transparent);
  }

  .title {
    flex: 1;
    min-width: 0;
    line-height: 1.2;
  }

  .title strong { display: block; font-size: 1.0625rem; }
  .title small { color: var(--text-muted); font-size: 0.8125rem; }

  .icon-button {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-2);
    font-size: 0.8125rem;
    transition: background 0.15s, border-color 0.15s;
  }

  .icon-button:hover { border-color: var(--accent); }
  .icon-button svg { width: 14px; height: 14px; }

  .model-picker {
    position: relative;
    display: flex;
    align-items: center;
  }

  .model-picker svg {
    position: absolute;
    right: 10px;
    width: 14px;
    height: 14px;
    pointer-events: none;
    color: var(--text-muted);
  }

  select {
    width: 100%;
    appearance: none;
    padding: 7px 30px 7px 12px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--surface-2);
    font-size: 0.875rem;
    cursor: pointer;
    text-overflow: ellipsis;
  }

  select:hover { border-color: var(--accent); }

  /* messages */

  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }

  .empty {
    margin: auto;
    max-width: 280px;
    text-align: center;
    color: var(--text-muted);
  }

  .empty .logo {
    width: 44px;
    height: 44px;
    margin: 0 auto 12px;
    border-radius: 14px;
    font-size: 1.375rem;
  }

  .empty h2 {
    margin: 0 0 4px;
    font-size: 1.1875rem;
    color: var(--text);
  }

  .empty p { margin: 0 0 16px; }

  .suggestions {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .suggestion {
    padding: 8px 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    text-align: left;
    box-shadow: var(--shadow);
    transition: border-color 0.15s, transform 0.15s;
  }

  .suggestion:hover {
    border-color: var(--accent);
    transform: translateY(-1px);
  }

  .message {
    padding: 10px 14px;
    border-radius: var(--radius);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    max-width: 92%;
    animation: pop-in 0.18s ease-out;
  }

  .user {
    align-self: flex-end;
    color: var(--accent-text);
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    border-bottom-right-radius: 4px;
  }

  .assistant {
    align-self: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    border-bottom-left-radius: 4px;
    box-shadow: var(--shadow);
  }

  .assistant.error {
    color: var(--danger);
    background: var(--danger-bg);
    border-color: color-mix(in srgb, var(--danger) 35%, transparent);
  }

  /* typing indicator while waiting for the reply */
  .assistant.pending {
    display: flex;
    gap: 4px;
    padding: 14px 16px;
  }

  .assistant.pending span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-muted);
    animation: blink 1.2s infinite ease-in-out;
  }

  .assistant.pending span:nth-child(2) { animation-delay: 0.15s; }
  .assistant.pending span:nth-child(3) { animation-delay: 0.3s; }

  @keyframes blink {
    0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
    40% { opacity: 1; transform: translateY(-3px); }
  }

  @keyframes pop-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: none; }
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }

  /* composer */

  form {
    padding: 10px 12px 12px;
    background: var(--bg);
  }

  .composer {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 6px 6px 6px 12px;
    border-radius: 18px;
    border: 1px solid var(--border);
    background: var(--surface);
    box-shadow: var(--shadow);
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .composer:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent);
  }

  .composer-actions {
    display: flex;
    justify-content: flex-end;
  }

  textarea {
    width: 100%;
    resize: none;
    max-height: 40dvh;  /* grows with the content (autoGrow), then scrolls */
    overflow-y: auto;
    padding: 6px 0;
    border: none;
    outline: none;
    background: transparent;
    scrollbar-width: thin;
  }

  textarea::placeholder { color: var(--text-muted); }

  #send {
    flex: none;
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    color: var(--accent-text);
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    transition: opacity 0.15s, transform 0.15s;
  }

  #send:hover:not(:disabled) { transform: scale(1.06); }
  #send:disabled { opacity: 0.45; cursor: default; }
  #send svg { width: 16px; height: 16px; }

  .footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 4px 8px;
    margin-top: 6px;
  }

  .hint {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .font-sizes { display: flex; align-items: baseline; gap: 2px; margin-left: auto; }

  .font-sizes button {
    padding: 0 5px;
    border: none;
    border-radius: 6px;
    background: none;
    color: var(--text-muted);
    font-weight: 600;
    line-height: 20px;
  }

  .font-sizes button:hover { color: var(--text); background: var(--surface-2); }
  .font-sizes button[aria-pressed="true"] { color: var(--accent); }

  kbd {
    font: inherit;
    padding: 0 4px;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: var(--surface-2);
  }
</style>
</head>

<body>
<header>
  <div class="brand">
    <div class="logo" aria-hidden="true">G</div>
    <div class="title">
      <strong>Geenii Fox</strong>
      <small>Your assistant in the sidebar</small>
    </div>
    <button id="clear" class="icon-button" type="button" title="Start a new chat">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
      New chat
    </button>
  </div>
  <div class="model-picker">
    <select id="model" aria-label="Model"></select>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
  </div>
</header>

<div id="messages" aria-live="polite"></div>

<template id="empty-state">
  <div class="empty">
    <div class="logo" aria-hidden="true">G</div>
    <h2>How can I help?</h2>
    <p>Ask a question, or paste a link to have me read the page.</p>
    <div class="suggestions">
      <button class="suggestion" type="button">Summarize this page: </button>
      <button class="suggestion" type="button">Explain this in simple terms: </button>
      <button class="suggestion" type="button">Draft a short, friendly reply to: </button>
    </div>
  </div>
</template>

<form id="form">
  <div class="composer">
    <textarea
      id="prompt"
      rows="1"
      placeholder="Ask anything..."
    ></textarea>
    <div class="composer-actions">
      <button id="send" type="submit" title="Send" aria-label="Send">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
      </button>
    </div>
  </div>
  <div class="footer">
    <div class="hint"><kbd>Enter</kbd> to send, <kbd>Shift</kbd> + <kbd>Enter</kbd> for a new line</div>
    <div class="font-sizes" role="group" aria-label="Font size">
      <button type="button" data-size="sm" title="Small text" aria-label="Small text" style="font-size: 11px">A</button>
      <button type="button" data-size="normal" title="Normal text" aria-label="Normal text" style="font-size: 13px">A</button>
      <button type="button" data-size="lg" title="Large text" aria-label="Large text" style="font-size: 15px">A</button>
    </div>
  </div>
</form>

<script>
const messages = [];
const container = document.getElementById("messages");
const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const modelSelect = document.getElementById("model");
const form = document.getElementById("form");

// models offered by the server (FF_CHATBOT_MODELS), the selection is kept across sidebar reloads
const MODELS = __FF_MODELS__;
for (const model of MODELS) {
  modelSelect.add(new Option(model.label, model.id));
}
const savedModel = localStorage.getItem("geenii-ff-model");
if (MODELS.some((m) => m.id === savedModel)) {
  modelSelect.value = savedModel;
}
modelSelect.onchange = () => localStorage.setItem("geenii-ff-model", modelSelect.value);

// grow the textarea with its content, from its rows="1" height up to the CSS max-height
function autoGrow() {
  promptBox.style.height = "auto";
  const border = promptBox.offsetHeight - promptBox.clientHeight;
  promptBox.style.height = promptBox.scrollHeight + border + "px";
}
promptBox.addEventListener("input", autoGrow);

// font size (sm / normal / lg), kept across sidebar reloads
const fontSizeButtons = document.querySelectorAll(".font-sizes button");
function setFontSize(size) {
  if (!["sm", "normal", "lg"].includes(size)) size = "normal";
  document.documentElement.dataset.fontSize = size;
  for (const button of fontSizeButtons) {
    button.setAttribute("aria-pressed", String(button.dataset.size === size));
  }
  localStorage.setItem("geenii-ff-font-size", size);
  autoGrow();
}
for (const button of fontSizeButtons) {
  button.addEventListener("click", () => setFontSize(button.dataset.size));
}
setFontSize(localStorage.getItem("geenii-ff-font-size"));

// Enter sends, Shift+Enter adds a new line (not while an input method is composing text)
promptBox.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

function showEmptyState() {
  const empty = document.getElementById("empty-state").content.cloneNode(true);
  for (const button of empty.querySelectorAll(".suggestion")) {
    button.onclick = () => {
      promptBox.value = button.textContent;
      autoGrow();
      promptBox.focus();
    };
  }
  container.replaceChildren(empty);
}

function addMessage(role, content) {
  container.querySelector(".empty")?.remove();
  const el = document.createElement("div");
  el.className = "message " + role;
  el.textContent = content;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
  return el;
}

function addPending() {
  const el = addMessage("assistant pending", "");
  el.setAttribute("aria-label", "Geenii is typing");
  el.append(document.createElement("span"), document.createElement("span"), document.createElement("span"));
  return el;
}

document.getElementById("clear").onclick = () => {
  messages.length = 0;
  showEmptyState();
  promptBox.value = "";
  autoGrow();
  promptBox.focus();
};

form.onsubmit = async (event) => {
  event.preventDefault();

  const text = promptBox.value.trim();
  if (!text || sendButton.disabled) return;

  messages.push({ role: "user", content: text });
  addMessage("user", text);
  promptBox.value = "";
  autoGrow();

  sendButton.disabled = true;
  const pending = addPending();

  try {
    const response = await fetch("http://localhost:33311/ff/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, model: modelSelect.value })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || data.error || "API error");
    }

    pending.className = "message assistant";
    pending.removeAttribute("aria-label");
    pending.textContent = data.reply;
    messages.push({
      role: "assistant",
      content: data.reply
    });
  } catch (error) {
    pending.className = "message assistant error";
    pending.removeAttribute("aria-label");
    pending.textContent = "Error: " + error.message;
  } finally {
    sendButton.disabled = false;
    container.scrollTop = container.scrollHeight;
    promptBox.focus();
  }
};

showEmptyState();

// Firefox passes selected text or suggested prompts
// through the q query parameter.
const params = new URLSearchParams(location.search);
const initialPrompt = params.get("q");

if (initialPrompt) {
  promptBox.value = initialPrompt;
  autoGrow();
  // Review before sending.
}
</script>
</body>
</html>
"""
