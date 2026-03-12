/**
 * Alfred Chrome Extension — Content Script
 *
 * Injects a floating dock and selection toolbar on every page.
 * Keyboard shortcuts: Alt+N toggle dock, Alt+S save selection, Alt+P capture page.
 */
(function () {
  "use strict";

  // Prevent double-injection
  if (window.__alfredContentLoaded) return;
  window.__alfredContentLoaded = true;

  const DOMAIN_KEY = `alfred_draft_${location.hostname}`;

  // ── Helpers ──────────────────────────────────────────────────────────

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "class") e.className = v;
        else if (k === "style" && typeof v === "object")
          Object.assign(e.style, v);
        else if (k.startsWith("on") && typeof v === "function")
          e.addEventListener(k.slice(2).toLowerCase(), v);
        else e.setAttribute(k, v);
      }
    }
    if (children) {
      for (const c of Array.isArray(children) ? children : [children]) {
        if (typeof c === "string") e.appendChild(document.createTextNode(c));
        else if (c) e.appendChild(c);
      }
    }
    return e;
  }

  // ── Toast system ────────────────────────────────────────────────────

  let toastContainer = null;

  function ensureToastContainer() {
    if (toastContainer && document.body.contains(toastContainer)) return;
    toastContainer = el("div", { id: "alfred-toast-container" });
    document.body.appendChild(toastContainer);
  }

  function showToast(message, type = "info") {
    ensureToastContainer();
    const t = el("div", { class: `alfred-toast alfred-toast-${type}` }, message);
    toastContainer.appendChild(t);
    setTimeout(() => {
      if (t.parentNode) t.remove();
    }, 3000);
  }

  // ── Connection status ───────────────────────────────────────────────

  let isOnline = false;

  async function checkConnection() {
    try {
      isOnline = await AlfredAPI.health();
    } catch {
      isOnline = false;
    }
    const dot = qs("#alfred-dock-status");
    if (dot) {
      dot.classList.toggle("alfred-status-online", isOnline);
      dot.title = isOnline ? "Alfred backend connected" : "Alfred backend offline";
    }
  }

  // ── Build the dock ──────────────────────────────────────────────────

  let dock = null;
  let dockBuilt = false;

  function buildDock() {
    if (dockBuilt) return;
    dockBuilt = true;

    dock = el("div", { id: "alfred-dock" }, [
      // Header
      el("div", { id: "alfred-dock-header" }, [
        el("div", { class: "alfred-logo" }, [
          el("span", { class: "alfred-logo-icon" }, "A"),
          "Alfred",
          el("div", { id: "alfred-dock-status", title: "Checking..." }),
        ]),
        el("div", { class: "alfred-dock-actions" }, [
          el("button", {
            class: "alfred-dock-btn-icon",
            title: "Move to other side",
            onClick: toggleDockSide,
          }, "\u21C4"),
          el("button", {
            class: "alfred-dock-btn-icon",
            title: "Open Dashboard",
            onClick: () => {
              const url = chrome.runtime.getURL("dashboard.html");
              window.open(url, "_blank");
            },
          }, "\u2630"),
          el("button", {
            class: "alfred-dock-btn-icon",
            title: "Close (Alt+N)",
            onClick: toggleDock,
          }, "\u2715"),
        ]),
      ]),

      // Body
      el("div", { id: "alfred-dock-body" }, [
        el("textarea", {
          id: "alfred-note-textarea",
          placeholder: "Quick note... (Alt+S to save)",
          rows: "6",
        }),
        el("div", { class: "alfred-btn-row" }, [
          el("button", {
            class: "alfred-btn alfred-btn-primary",
            onClick: saveQuickNote,
          }, "Save Note"),
          el("button", {
            class: "alfred-btn alfred-btn-secondary",
            onClick: captureFullPage,
          }, "Capture Page"),
        ]),
        el("div", { class: "alfred-shortcuts-hint" }, [
          el("span", { class: "alfred-kbd" }, "Alt+N"),
          " Toggle dock  ",
          el("span", { class: "alfred-kbd" }, "Alt+S"),
          " Save  ",
          el("span", { class: "alfred-kbd" }, "Alt+P"),
          " Capture page",
        ]),
        el("p", { class: "alfred-section-label" }, "Recent Captures"),
        el("ul", { id: "alfred-recent-captures", class: "alfred-capture-list" }),
      ]),
    ]);

    document.body.appendChild(dock);

    // Restore draft
    try {
      const saved = localStorage.getItem(DOMAIN_KEY);
      if (saved) qs("#alfred-note-textarea").value = saved;
    } catch {}

    // Auto-save draft on input
    qs("#alfred-note-textarea").addEventListener("input", (e) => {
      try {
        localStorage.setItem(DOMAIN_KEY, e.target.value);
      } catch {}
    });

    // Restore dock side
    try {
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get("alfredDockSide", (res) => {
          if (res && res.alfredDockSide === "left") dock.classList.add("alfred-dock-left");
        });
      }
    } catch {}

    // Initial connection check
    checkConnection();
    setInterval(checkConnection, 30000);

    // Load recent captures
    refreshRecentCaptures();
  }

  async function refreshRecentCaptures() {
    const list = qs("#alfred-recent-captures");
    if (!list) return;
    const history = await AlfredAPI.getCaptureHistory();
    list.innerHTML = "";
    const recent = history.slice(0, 5);
    if (recent.length === 0) {
      list.appendChild(
        el("li", { class: "alfred-capture-item" }, "No captures yet.")
      );
      return;
    }
    for (const item of recent) {
      const ago = timeAgo(item.timestamp);
      list.appendChild(
        el("li", { class: "alfred-capture-item" }, [
          el("span", { class: "alfred-capture-item-title" }, item.title || "Untitled"),
          el("span", { class: "alfred-capture-item-meta" }, `${ago} — ${item.type || "note"}`),
        ])
      );
    }
  }

  function timeAgo(ts) {
    const diff = Date.now() - ts;
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return "just now";
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const days = Math.floor(hr / 24);
    return `${days}d ago`;
  }

  // ── Dock actions ────────────────────────────────────────────────────

  function toggleDock() {
    buildDock();
    dock.classList.toggle("alfred-dock-visible");
  }

  function toggleDockSide() {
    if (!dock) return;
    dock.classList.toggle("alfred-dock-left");
    const isLeft = dock.classList.contains("alfred-dock-left");
    try {
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ alfredDockSide: isLeft ? "left" : "right" });
      }
    } catch {}
  }

  async function saveQuickNote() {
    const textarea = qs("#alfred-note-textarea");
    let text = textarea ? textarea.value.trim() : "";

    // If textarea is empty, try clipboard, then selected text, then full page
    if (!text) {
      const selected = getSelectedText();
      if (selected) {
        text = selected;
      } else {
        try {
          const clip = await navigator.clipboard.readText();
          if (clip && clip.trim()) {
            text = clip.trim();
          }
        } catch {
          // Clipboard access denied or unavailable — fall through
        }
      }
    }

    // Last resort: capture full page text
    if (!text) {
      text = document.body.innerText.slice(0, 50000).trim();
    }

    if (!text) {
      showToast("Nothing to save.", "warning");
      return;
    }

    const isFullPage = text.length > 500;
    const captureType = isFullPage ? "page-capture" : "quick-note";

    try {
      if (isFullPage) {
        await AlfredAPI.capturePage({
          url: location.href,
          title: document.title,
          content: text,
        });
      } else {
        await AlfredAPI.captureSelection({
          url: location.href,
          title: document.title,
          selectedText: text,
        });
      }
      if (textarea) {
        textarea.value = "";
        try { localStorage.removeItem(DOMAIN_KEY); } catch {}
      }
      showToast(isFullPage ? "Page captured to Alfred!" : "Note saved to Alfred!", "success");
      AlfredAPI.addCaptureHistory({
        title: isFullPage ? `[Page] ${document.title}` : text.slice(0, 80),
        url: location.href,
        type: captureType,
      }).then(() => refreshRecentCaptures()).catch(() => {});
    } catch (err) {
      showToast(`Save failed: ${err.message}`, "error");
    }
  }

  async function captureFullPage() {
    try {
      const content = document.body.innerText.slice(0, 50000);
      await AlfredAPI.capturePage({
        url: location.href,
        title: document.title,
        content,
      });
      showToast("Page captured to Alfred!", "success");
      AlfredAPI.addCaptureHistory({
        title: `[Page] ${document.title}`,
        url: location.href,
        type: "page-capture",
      }).then(() => refreshRecentCaptures()).catch(() => {});
    } catch (err) {
      showToast(`Capture failed: ${err.message}`, "error");
    }
  }

  async function saveSelectionToNotes(text) {
    try {
      await AlfredAPI.captureSelection({
        url: location.href,
        title: document.title,
        selectedText: text,
      });
      showToast("Selection saved to Alfred!", "success");
      AlfredAPI.addCaptureHistory({
        title: text.slice(0, 80),
        url: location.href,
        type: "selection",
      }).then(() => refreshRecentCaptures()).catch(() => {});
    } catch (err) {
      showToast(`Save failed: ${err.message}`, "error");
    }
  }

  async function summarizeSelection(text) {
    try {
      showToast("Summarizing...", "info");
      const result = await AlfredAPI.summarize(text);
      const summary = typeof result === "string" ? result : result.text || result.content || JSON.stringify(result);
      // Put summary in dock textarea
      buildDock();
      if (!dock.classList.contains("alfred-dock-visible")) {
        dock.classList.add("alfred-dock-visible");
      }
      qs("#alfred-note-textarea").value = summary;
      showToast("Summary ready in dock.", "success");
    } catch (err) {
      showToast(`Summarize failed: ${err.message}`, "error");
    }
  }

  // ── Selection toolbar ───────────────────────────────────────────────

  let toolbar = null;

  function buildToolbar() {
    if (toolbar) return;
    toolbar = el("div", { id: "alfred-selection-toolbar" }, [
      el("button", {
        class: "alfred-toolbar-btn",
        onClick: () => {
          const text = getSelectedText();
          if (text) saveSelectionToNotes(text);
          hideToolbar();
        },
      }, "Save to Notes"),
      el("button", {
        class: "alfred-toolbar-btn",
        onClick: () => {
          const text = getSelectedText();
          if (text) saveSelectionToNotes(text);
          hideToolbar();
        },
      }, "Save to Library"),
      el("button", {
        class: "alfred-toolbar-btn",
        onClick: () => {
          const text = getSelectedText();
          if (text) summarizeSelection(text);
          hideToolbar();
        },
      }, "Summarize"),
    ]);
    document.body.appendChild(toolbar);
  }

  function getSelectedText() {
    return window.getSelection().toString().trim();
  }

  function showToolbar(x, y) {
    buildToolbar();
    toolbar.style.left = `${Math.min(x, window.innerWidth - 320)}px`;
    toolbar.style.top = `${y + window.scrollY - 44}px`;
    toolbar.classList.add("alfred-toolbar-visible");
  }

  function hideToolbar() {
    if (toolbar) toolbar.classList.remove("alfred-toolbar-visible");
  }

  // Show toolbar on text selection
  document.addEventListener("mouseup", (e) => {
    // Ignore clicks inside our own UI
    if (e.target.closest("#alfred-dock") || e.target.closest("#alfred-selection-toolbar")) return;

    setTimeout(() => {
      const text = getSelectedText();
      if (text.length > 2) {
        const sel = window.getSelection();
        const range = sel.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        showToolbar(rect.left + rect.width / 2 - 120, rect.top);
      } else {
        hideToolbar();
      }
    }, 10);
  });

  // Hide toolbar on click elsewhere
  document.addEventListener("mousedown", (e) => {
    if (!e.target.closest("#alfred-selection-toolbar")) {
      hideToolbar();
    }
  });

  // ── Floating Action Button (always visible) ────────────────────────

  function buildFab() {
    const fab = el("div", { id: "alfred-fab", onClick: toggleDock }, [
      el("span", { class: "alfred-fab-letter" }, "A"),
    ]);
    document.body.appendChild(fab);
  }

  // Build FAB immediately so user sees something on page load
  if (document.body) {
    buildFab();
  } else {
    document.addEventListener("DOMContentLoaded", buildFab);
  }

  // ── Keyboard shortcuts ──────────────────────────────────────────────

  document.addEventListener("keydown", (e) => {
    // Alt+N — toggle dock
    if (e.altKey && e.key.toLowerCase() === "n") {
      e.preventDefault();
      toggleDock();
    }

    // Alt+S — save selection or quick note
    if (e.altKey && e.key.toLowerCase() === "s") {
      e.preventDefault();
      const selected = getSelectedText();
      if (selected) {
        saveSelectionToNotes(selected);
      } else {
        saveQuickNote();
      }
    }

    // Alt+P — capture full page
    if (e.altKey && e.key.toLowerCase() === "p") {
      e.preventDefault();
      captureFullPage();
    }
  });
})();
