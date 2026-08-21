/**
 * FMCG AI Sales Assistant — Chat UI
 * fetch() calls to /api/chat, renders user/bot messages, collapsible SQL, error states.
 */

(function () {
  "use strict";

  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const messagesContainer = document.getElementById("chatMessages");

  const API_CHAT = "/api/chat";

  // ── Helpers ──────────────────────────────────────────────

  /** Append an HTML string to the messages container and scroll to bottom. */
  function appendMessage(html) {
    messagesContainer.insertAdjacentHTML("beforeend", html);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  /** Create a user bubble. */
  function addUserMessage(text) {
    const safe = escapeHtml(text);
    appendMessage(
      `<div class="message user-message">
         <div class="message-bubble">${safe}</div>
       </div>`
    );
  }

  /** Create a bot bubble. */
  function addBotMessage(text, options = {}) {
    const safe = escapeHtml(text);
    const errorClass = options.error ? " error" : "";
    const sqlBlock = options.sql
      ? `<details class="sql-toggle">
           <summary>Show SQL</summary>
           <pre>${escapeHtml(options.sql)}</pre>
         </details>`
      : "";
    appendMessage(
      `<div class="message bot-message${errorClass}">
         <div class="message-bubble">${safe}</div>
         ${sqlBlock}
       </div>`
    );
  }

  /** Show a typing indicator; returns a remove function. */
  function showTyping() {
    const id = "typing-" + Date.now();
    appendMessage(
      `<div class="message bot-message" id="${id}">
         <div class="typing-indicator">
           <span class="typing-dot"></span>
           <span class="typing-dot"></span>
           <span class="typing-dot"></span>
         </div>
       </div>`
    );
    return function remove() {
      const el = document.getElementById(id);
      if (el) el.remove();
    };
  }

  /** Minimal HTML escaping. */
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Send message ─────────────────────────────────────────

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed) return;

    if (trimmed.length > 2000) {
      addBotMessage("Your message is too long. Please keep it under 2000 characters.", {
        error: true,
      });
      return;
    }

    addUserMessage(trimmed);
    input.value = "";
    setDisabled(true);

    const removeTyping = showTyping();

    try {
      const res = await fetch(API_CHAT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!res.ok) {
        removeTyping();
        addBotMessage(
          "Sorry, something went wrong on the server. Please try again.",
          { error: true }
        );
        return;
      }

      const data = await res.json();
      removeTyping();

      if (data.error) {
        addBotMessage(data.answer || "I couldn't find data matching that question.", {
          error: true,
        });
      } else {
        addBotMessage(data.answer, { sql: data.sql });
      }
    } catch (err) {
      removeTyping();
      addBotMessage(
        "Network error — please check your connection and try again.",
        { error: true }
      );
      console.error("Chat fetch error:", err);
    } finally {
      setDisabled(false);
      input.focus();
    }
  }

  // ── UI state ─────────────────────────────────────────────

  function setDisabled(disabled) {
    sendBtn.disabled = disabled;
    input.disabled = disabled;
  }

  // ── Event listeners ──────────────────────────────────────

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    sendMessage(input.value);
  });

  // Enter sends (Shift+Enter for newline if we ever add textarea)
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input.value);
    }
  });

  // Focus on load
  input.focus();
})();
