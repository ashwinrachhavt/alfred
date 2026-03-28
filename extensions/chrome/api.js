/**
 * Alfred API client for Chrome extension.
 * Wraps all Alfred backend calls with error handling and base URL management.
 */
const AlfredAPI = {
  _baseUrl: null,
  _workspaceId: null,
  _defaultUrl: "http://localhost:8000",

  /** Resolve the API base URL from storage or fall back to default. */
  async base() {
    if (this._baseUrl) return this._baseUrl;
    try {
      // One-time migration: clear stale localhost:8080 URL from when that was the default.
      // SearXNG runs on 8080 and its /healthz returns 200, tricking the old health check.
      const migrated = await this._getStorage("alfredUrlMigrated_v2");
      if (!migrated) {
        const old = await this._getStorage("alfredBaseUrl");
        if (old && old.includes(":8080")) {
          await this._setStorage("alfredBaseUrl", null);
        }
        await this._setStorage("alfredUrlMigrated_v2", true);
      }
      const stored = await this._getStorage("alfredBaseUrl");
      // Only use stored URL if it was explicitly set and is reachable.
      // Otherwise fall back to default to avoid stale cached URLs.
      if (stored && stored !== this._defaultUrl) {
        try {
          // Verify the stored URL is actually Alfred (not another service on that port)
          // by checking /api/v1/workspaces which only Alfred serves.
          const resp = await fetch(`${stored}/api/v1/workspaces`, {
            signal: AbortSignal.timeout(1500),
            headers: { "Content-Type": "application/json" },
          });
          if (resp.ok) {
            this._baseUrl = stored;
            return this._baseUrl;
          }
        } catch {
          // Stored URL unreachable or not Alfred — fall through to default
        }
      }
      this._baseUrl = this._defaultUrl;
    } catch {
      this._baseUrl = this._defaultUrl;
    }
    return this._baseUrl;
  },

  /** Update the stored base URL and clear cache. */
  async setBase(url) {
    const clean = url.replace(/\/+$/, "");
    try {
      await this._setStorage("alfredBaseUrl", clean);
    } catch {}
    this._baseUrl = clean;
  },

  /** Generic fetch wrapper with JSON parsing and error handling. */
  async _fetch(path, options = {}) {
    const base = await this.base();
    const url = `${base}${path}`;
    const defaults = {
      headers: { "Content-Type": "application/json" },
    };
    const merged = { ...defaults, ...options };
    if (options.headers) {
      merged.headers = { ...defaults.headers, ...options.headers };
    }
    const resp = await fetch(url, merged);
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`Alfred API ${resp.status}: ${text}`);
    }
    const ct = resp.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      return resp.json();
    }
    return resp.text();
  },

  // ── Notes ──────────────────────────────────────────────────────────

  /** Get or create the default workspace id. */
  async _ensureWorkspaceId() {
    if (this._workspaceId) return this._workspaceId;
    try {
      const workspaces = await this._fetch("/api/v1/workspaces");
      if (workspaces && workspaces.length > 0) {
        this._workspaceId = workspaces[0].id;
        return this._workspaceId;
      }
      // No workspace — create one
      const ws = await this._fetch("/api/v1/workspaces", {
        method: "POST",
        body: JSON.stringify({ name: "Personal" }),
      });
      this._workspaceId = ws.id;
      return this._workspaceId;
    } catch {
      return null;
    }
  },

  /** List notes tree. */
  async listNotes() {
    const wsId = await this._ensureWorkspaceId();
    if (!wsId) return { workspace_id: null, items: [] };
    return this._fetch(`/api/v1/notes/tree?workspace_id=${wsId}`);
  },

  /** Create a note. */
  async createNote({ title, content, workspace_id }) {
    const wsId = workspace_id || (await this._ensureWorkspaceId());
    return this._fetch("/api/v1/notes", {
      method: "POST",
      body: JSON.stringify({
        title,
        content_markdown: content,
        workspace_id: wsId,
      }),
    });
  },

  /** Get a single note by ID. */
  async getNote(noteId) {
    return this._fetch(`/api/v1/notes/${noteId}`);
  },

  /** Update a note. */
  async updateNote(noteId, { title, content }) {
    const payload = {};
    if (title !== undefined) payload.title = title;
    if (content !== undefined) payload.content_markdown = content;
    return this._fetch(`/api/v1/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  /** Delete a note. */
  async deleteNote(noteId) {
    return this._fetch(`/api/v1/notes/${noteId}`, { method: "DELETE" });
  },

  // ── Workspaces ─────────────────────────────────────────────────────

  /** List workspaces. */
  async listWorkspaces() {
    return this._fetch("/api/v1/workspaces");
  },

  /** Create workspace. */
  async createWorkspace(name) {
    return this._fetch("/api/v1/workspaces", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },

  // ── Documents ──────────────────────────────────────────────────────

  /** List documents. */
  async listDocuments() {
    return this._fetch("/api/documents/explorer");
  },

  /** Get document text. */
  async getDocumentText(id) {
    return this._fetch(`/api/documents/${id}/text`);
  },

  /** Get document details. */
  async getDocumentDetails(id) {
    return this._fetch(`/api/documents/${id}/details`);
  },

  // ── Intelligence ───────────────────────────────────────────────────

  /** AI autocomplete. */
  async autocomplete(text) {
    return this._fetch("/api/intelligence/autocomplete", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },

  /** AI text editing. */
  async editText(text, instruction) {
    return this._fetch("/api/intelligence/edit", {
      method: "POST",
      body: JSON.stringify({ text, instruction }),
    });
  },

  // ── Capture helpers ────────────────────────────────────────────────

  /**
   * Ingest a page into the document store (Knowledge Inbox).
   * Uses /api/documents/page/extract which requires raw_text (min 50 chars).
   * Falls back to creating a note if the text is too short.
   */
  async capturePage({ url, title, content }) {
    const text = (content || "").trim();
    if (text.length >= 50) {
      return this._fetch("/api/documents/page/extract", {
        method: "POST",
        body: JSON.stringify({
          raw_text: text,
          page_url: url,
          page_title: title,
          selection_type: "full_page",
        }),
      });
    }
    // Fallback for very short content — save as a note
    return this.createNote({ title: `[Capture] ${title || url}`, content: `**Source:** ${url}\n\n---\n\n${text}` });
  },

  /** Capture a text selection into the document store. */
  async captureSelection({ url, title, selectedText }) {
    const text = (selectedText || "").trim();
    if (text.length >= 50) {
      return this._fetch("/api/documents/page/extract", {
        method: "POST",
        body: JSON.stringify({
          raw_text: text,
          page_url: url,
          page_title: `[Selection] ${title || url}`,
          selection_type: "selection",
        }),
      });
    }
    // Fallback for very short selections — save as a note
    return this.createNote({ title: `[Selection] ${title || url}`, content: `**Source:** ${url}\n\n> ${text.replace(/\n/g, "\n> ")}` });
  },

  /** Summarize selected text using AI edit. */
  async summarize(text) {
    return this.editText(text, "Summarize the following text concisely.");
  },

  // ── Health ─────────────────────────────────────────────────────────

  /** Check if Alfred backend is reachable. */
  async health() {
    try {
      const base = await this.base();
      const resp = await fetch(`${base}/api/v1/workspaces`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(3000),
      });
      return resp.ok;
    } catch {
      return false;
    }
  },

  // ── Capture history (local) ────────────────────────────────────────

  /** Storage helper — chrome.storage when available, else localStorage fallback. */
  _storageAvailable() {
    return typeof chrome !== "undefined" && chrome.storage && chrome.storage.local;
  },

  async _getStorage(key) {
    if (this._storageAvailable()) {
      const result = await chrome.storage.local.get(key);
      return result[key];
    }
    try {
      const raw = localStorage.getItem(`alfred_${key}`);
      return raw ? JSON.parse(raw) : undefined;
    } catch {
      return undefined;
    }
  },

  async _setStorage(key, value) {
    if (this._storageAvailable()) {
      await chrome.storage.local.set({ [key]: value });
      return;
    }
    try {
      localStorage.setItem(`alfred_${key}`, JSON.stringify(value));
    } catch {}
  },

  /** Add a capture to local history (last 100). */
  async addCaptureHistory(entry) {
    try {
      const history = (await this._getStorage("captureHistory")) || [];
      history.unshift({
        ...entry,
        timestamp: Date.now(),
      });
      if (history.length > 100) history.length = 100;
      await this._setStorage("captureHistory", history);
    } catch {
      // Silently ignore storage errors — don't break the main save flow
    }
  },

  /** Get capture history. */
  async getCaptureHistory() {
    try {
      return (await this._getStorage("captureHistory")) || [];
    } catch {
      return [];
    }
  },

  /** Clear capture history. */
  async clearCaptureHistory() {
    try {
      await this._setStorage("captureHistory", []);
    } catch {}
  },
};

// Make available globally (content scripts share the same scope per injection)
if (typeof window !== "undefined") {
  window.AlfredAPI = AlfredAPI;
}
