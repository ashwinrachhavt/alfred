/**
 * Alfred Chrome Extension — Dashboard Script
 */
(async function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ── Panel navigation ───────────────────────────────────────────────

  $$(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".nav-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      $$(".panel").forEach((p) => p.classList.remove("active"));
      $(`#panel-${btn.dataset.panel}`).classList.add("active");
    });
  });

  // ── Connection status ──────────────────────────────────────────────

  async function checkStatus() {
    const online = await AlfredAPI.health();
    const dot = $("#sidebar-status");
    dot.classList.toggle("online", online);
    dot.title = online ? "Connected to Alfred" : "Alfred backend offline";
    return online;
  }
  const isOnline = await checkStatus();

  // ── Load settings ──────────────────────────────────────────────────

  const res = await chrome.storage.local.get("alfredBaseUrl");
  if (res.alfredBaseUrl) {
    $("#setting-api-url").value = res.alfredBaseUrl;
  }

  // ── Helpers ────────────────────────────────────────────────────────

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

  function truncate(str, len) {
    if (!str) return "";
    return str.length > len ? str.slice(0, len) + "..." : str;
  }

  function makeCard({ title, preview, meta, tags, onClick }) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-title">${escHtml(title || "Untitled")}</div>
      ${preview ? `<div class="card-preview">${escHtml(preview)}</div>` : ""}
      ${tags ? `<div class="card-meta">${tags.map((t) => `<span class="card-tag">${escHtml(t)}</span>`).join("")}</div>` : ""}
      ${meta ? `<div class="card-meta">${escHtml(meta)}</div>` : ""}
    `;
    if (onClick) card.addEventListener("click", onClick);
    return card;
  }

  function escHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  // ── Notes panel ────────────────────────────────────────────────────

  let allNotes = [];
  let editingNoteId = null;

  async function loadNotes() {
    const container = $("#notes-list");
    container.innerHTML = '<p class="empty-state">Loading notes...</p>';
    try {
      const data = await AlfredAPI.listNotes();
      // The tree endpoint may return nested structure; flatten notes
      allNotes = flattenNotes(data);
      renderNotes(allNotes);
    } catch (err) {
      container.innerHTML = `<p class="empty-state">Could not load notes. Is Alfred running?</p>`;
    }
  }

  function flattenNotes(data) {
    // Handle various response shapes
    if (Array.isArray(data)) {
      const flat = [];
      for (const item of data) {
        flat.push(item);
        if (item.children) flat.push(...flattenNotes(item.children));
        if (item.notes) flat.push(...flattenNotes(item.notes));
      }
      return flat;
    }
    if (data && data.notes) return flattenNotes(data.notes);
    if (data && data.items) return flattenNotes(data.items);
    return [];
  }

  function renderNotes(notes) {
    const container = $("#notes-list");
    container.innerHTML = "";
    if (notes.length === 0) {
      container.innerHTML = '<p class="empty-state">No notes yet. Create one!</p>';
      return;
    }
    for (const note of notes) {
      container.appendChild(
        makeCard({
          title: note.title || "Untitled",
          preview: truncate(note.content || "", 200),
          meta: note.updated_at
            ? `Updated ${new Date(note.updated_at).toLocaleDateString()}`
            : "",
          onClick: () => openNoteModal(note),
        })
      );
    }
  }

  // Search notes
  $("#notes-search").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    if (!q) {
      renderNotes(allNotes);
      return;
    }
    const filtered = allNotes.filter(
      (n) =>
        (n.title || "").toLowerCase().includes(q) ||
        (n.content || "").toLowerCase().includes(q)
    );
    renderNotes(filtered);
  });

  // Refresh notes
  $("#btn-refresh-notes").addEventListener("click", loadNotes);

  // New note
  $("#btn-new-note").addEventListener("click", () => {
    editingNoteId = null;
    $("#modal-note-title").value = "";
    $("#modal-note-content").value = "";
    $("#modal-delete").style.display = "none";
    $("#note-modal").classList.remove("hidden");
  });

  // ── Note modal ─────────────────────────────────────────────────────

  function openNoteModal(note) {
    editingNoteId = note.id || null;
    $("#modal-note-title").value = note.title || "";
    $("#modal-note-content").value = note.content || "";
    $("#modal-delete").style.display = editingNoteId ? "inline-flex" : "none";
    $("#note-modal").classList.remove("hidden");
  }

  $("#modal-close").addEventListener("click", () => {
    $("#note-modal").classList.add("hidden");
  });

  $(".modal-backdrop").addEventListener("click", () => {
    $("#note-modal").classList.add("hidden");
  });

  // Save note
  $("#modal-save").addEventListener("click", async () => {
    const title = $("#modal-note-title").value.trim() || "Untitled";
    const content = $("#modal-note-content").value;
    const btn = $("#modal-save");
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
      if (editingNoteId) {
        await AlfredAPI.updateNote(editingNoteId, { title, content });
      } else {
        await AlfredAPI.createNote({ title, content });
      }
      $("#note-modal").classList.add("hidden");
      await loadNotes();
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = "Save";
    }
  });

  // Delete note
  $("#modal-delete").addEventListener("click", async () => {
    if (!editingNoteId) return;
    if (!confirm("Delete this note?")) return;
    try {
      await AlfredAPI.deleteNote(editingNoteId);
      $("#note-modal").classList.add("hidden");
      await loadNotes();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  });

  // ── Library panel ──────────────────────────────────────────────────

  let allDocs = [];

  async function loadLibrary() {
    const container = $("#library-list");
    container.innerHTML = '<p class="empty-state">Loading documents...</p>';
    try {
      const data = await AlfredAPI.listDocuments();
      allDocs = Array.isArray(data) ? data : data.documents || data.items || [];
      renderLibrary(allDocs);
    } catch {
      container.innerHTML = '<p class="empty-state">Could not load library. Is Alfred running?</p>';
    }
  }

  function renderLibrary(docs) {
    const container = $("#library-list");
    container.innerHTML = "";
    if (docs.length === 0) {
      container.innerHTML = '<p class="empty-state">No documents in library.</p>';
      return;
    }
    for (const doc of docs) {
      container.appendChild(
        makeCard({
          title: doc.title || doc.name || doc.filename || "Untitled",
          preview: truncate(doc.summary || doc.description || "", 200),
          tags: doc.tags || [],
          meta: doc.created_at
            ? `Added ${new Date(doc.created_at).toLocaleDateString()}`
            : "",
        })
      );
    }
  }

  // Search library
  $("#library-search").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    if (!q) {
      renderLibrary(allDocs);
      return;
    }
    const filtered = allDocs.filter(
      (d) =>
        (d.title || d.name || "").toLowerCase().includes(q) ||
        (d.summary || d.description || "").toLowerCase().includes(q)
    );
    renderLibrary(filtered);
  });

  $("#btn-refresh-library").addEventListener("click", loadLibrary);

  // ── Capture History panel ──────────────────────────────────────────

  async function loadHistory() {
    const container = $("#history-list");
    container.innerHTML = '<p class="empty-state">Loading history...</p>';
    const history = await AlfredAPI.getCaptureHistory();
    container.innerHTML = "";
    if (history.length === 0) {
      container.innerHTML = '<p class="empty-state">No captures yet. Use Alt+S or Alt+P on any page.</p>';
      return;
    }
    for (const item of history) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="card-title">${escHtml(item.title || "Untitled")}</div>
        <div class="card-meta">
          <span class="card-tag">${escHtml(item.type || "capture")}</span>
          ${timeAgo(item.timestamp)}
        </div>
        ${item.url ? `<div class="card-meta" style="margin-top:4px;font-size:11px;word-break:break-all;color:var(--text-dim)">${escHtml(truncate(item.url, 80))}</div>` : ""}
      `;
      container.appendChild(card);
    }
  }

  $("#btn-clear-history").addEventListener("click", async () => {
    if (!confirm("Clear all capture history?")) return;
    await AlfredAPI.clearCaptureHistory();
    loadHistory();
  });

  // ── Settings ───────────────────────────────────────────────────────

  $("#btn-save-settings").addEventListener("click", async () => {
    const url = $("#setting-api-url").value.trim();
    const status = $("#settings-status");
    if (url) {
      await AlfredAPI.setBase(url);
    } else {
      await AlfredAPI.setBase("http://localhost:3001");
    }
    status.textContent = "Settings saved!";
    status.className = "success";
    setTimeout(() => (status.textContent = ""), 3000);
    checkStatus();
  });

  // ── Initial load ───────────────────────────────────────────────────

  if (isOnline) {
    loadNotes();
    loadLibrary();
  } else {
    $("#notes-list").innerHTML = '<p class="empty-state">Alfred backend is offline. Start Alfred and refresh.</p>';
    $("#library-list").innerHTML = '<p class="empty-state">Alfred backend is offline. Start Alfred and refresh.</p>';
  }
  loadHistory();
})();
