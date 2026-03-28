/**
 * Alfred Chrome Extension — Service Worker (MV3)
 *
 * Handles:
 * 1. Engagement scoring updates from tracker.js
 * 2. Batch sync to backend via chrome.alarms (every 60s)
 * 3. Auto-capture forwarding to /api/documents/page/extract
 * 4. Side panel open/close
 * 5. Re-visit detection (URL hash lookup)
 */

// ── Constants ───────────────────────────────────────────────────────
var DEFAULT_API_URL = "http://localhost:8000";
var SYNC_ALARM_NAME = "alfred-sync";
var STORAGE_KEYS = {
  pendingEvents: "alfredPendingEvents",
  pendingCaptures: "alfredPendingCaptures",
  visitedUrls: "alfredVisitedUrls",
  baseUrl: "alfredBaseUrl",
};

// ── Install / Startup ───────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(function () {
  chrome.alarms.create(SYNC_ALARM_NAME, { periodInMinutes: 1 });

  // Initialize storage keys if missing
  chrome.storage.local.get(
    [
      STORAGE_KEYS.pendingEvents,
      STORAGE_KEYS.pendingCaptures,
      STORAGE_KEYS.visitedUrls,
    ],
    function (result) {
      var updates = {};
      if (!result[STORAGE_KEYS.pendingEvents]) {
        updates[STORAGE_KEYS.pendingEvents] = [];
      }
      if (!result[STORAGE_KEYS.pendingCaptures]) {
        updates[STORAGE_KEYS.pendingCaptures] = [];
      }
      if (!result[STORAGE_KEYS.visitedUrls]) {
        updates[STORAGE_KEYS.visitedUrls] = {};
      }
      if (Object.keys(updates).length > 0) {
        chrome.storage.local.set(updates);
      }
    }
  );
});

// Also ensure alarm exists on startup (in case it was cleared)
chrome.runtime.onStartup.addListener(function () {
  chrome.alarms.get(SYNC_ALARM_NAME, function (alarm) {
    if (!alarm) {
      chrome.alarms.create(SYNC_ALARM_NAME, { periodInMinutes: 1 });
    }
  });
});

// ── API helpers (duplicated from api.js since SW can't use content globals) ──
async function getBaseUrl() {
  return new Promise(function (resolve) {
    chrome.storage.local.get(STORAGE_KEYS.baseUrl, function (result) {
      var url = result[STORAGE_KEYS.baseUrl];
      resolve(url || DEFAULT_API_URL);
    });
  });
}

async function apiFetch(path, options) {
  var base = await getBaseUrl();
  var url = base + path;
  var defaults = {
    headers: { "Content-Type": "application/json" },
  };
  var merged = Object.assign({}, defaults, options || {});
  if (options && options.headers) {
    merged.headers = Object.assign({}, defaults.headers, options.headers);
  }

  var resp = await fetch(url, merged);
  if (!resp.ok) {
    var text = "";
    try {
      text = await resp.text();
    } catch (e) {
      // ignore
    }
    throw new Error("Alfred API " + resp.status + ": " + text);
  }
  var ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return resp.json();
  }
  return resp.text();
}

// ── URL hashing for re-visit detection ──────────────────────────────
function simpleHash(str) {
  var hash = 0;
  for (var i = 0; i < str.length; i++) {
    var ch = str.charCodeAt(i);
    hash = ((hash << 5) - hash + ch) | 0;
  }
  return hash.toString(36);
}

// ── Message handling ────────────────────────────────────────────────
chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (!msg || !msg.type) return;

  if (msg.type === "ENGAGEMENT_UPDATE") {
    handleEngagementUpdate(msg.data);
    return;
  }

  if (msg.type === "AUTO_CAPTURE") {
    handleAutoCapture(msg.data);
    return;
  }

  if (msg.type === "GET_PENDING_COUNT") {
    chrome.storage.local.get(STORAGE_KEYS.pendingEvents, function (result) {
      var events = result[STORAGE_KEYS.pendingEvents] || [];
      sendResponse({ count: events.length });
    });
    return true; // async response
  }

  if (msg.type === "OPEN_SIDE_PANEL") {
    if (sender && sender.tab && sender.tab.id) {
      chrome.sidePanel.open({ tabId: sender.tab.id }).catch(function () {});
    }
    return;
  }
});

// ── Handle engagement updates ───────────────────────────────────────
function handleEngagementUpdate(data) {
  if (!data || !data.url) return;

  var urlHash = simpleHash(data.url);

  chrome.storage.local.get(
    [STORAGE_KEYS.pendingEvents, STORAGE_KEYS.visitedUrls],
    function (result) {
      var events = result[STORAGE_KEYS.pendingEvents] || [];
      var visited = result[STORAGE_KEYS.visitedUrls] || {};

      // Check for re-visit
      var isRevisit = !!visited[urlHash];

      // Mark URL as visited
      visited[urlHash] = Date.now();

      // Find existing event for this URL or create new one
      var existingIdx = -1;
      for (var i = 0; i < events.length; i++) {
        if (events[i].url === data.url) {
          existingIdx = i;
          break;
        }
      }

      var event = {
        url: data.url,
        title: data.title,
        domain: data.domain,
        score: data.score,
        activeTime: data.activeTime,
        scrollDepth: data.scrollDepth,
        hasSelected: data.hasSelected,
        hasCopied: data.hasCopied,
        isRevisit: isRevisit,
        timestamp: data.timestamp,
        updatedAt: new Date().toISOString(),
      };

      if (existingIdx >= 0) {
        // Update existing — keep whichever has higher score/time
        var existing = events[existingIdx];
        event.score = Math.max(event.score, existing.score || 0);
        event.activeTime = Math.max(event.activeTime, existing.activeTime || 0);
        event.scrollDepth = Math.max(
          event.scrollDepth,
          existing.scrollDepth || 0
        );
        event.hasSelected = event.hasSelected || existing.hasSelected;
        event.hasCopied = event.hasCopied || existing.hasCopied;
        event.isRevisit = event.isRevisit || existing.isRevisit;
        events[existingIdx] = event;
      } else {
        events.push(event);
      }

      // Cap pending events at 500 to avoid storage bloat
      if (events.length > 500) {
        events = events.slice(-500);
      }

      // Clean up old visited URLs (keep last 10000)
      var visitedKeys = Object.keys(visited);
      if (visitedKeys.length > 10000) {
        // Sort by timestamp, remove oldest
        var sorted = visitedKeys.sort(function (a, b) {
          return (visited[a] || 0) - (visited[b] || 0);
        });
        var toRemove = sorted.slice(0, visitedKeys.length - 10000);
        for (var j = 0; j < toRemove.length; j++) {
          delete visited[toRemove[j]];
        }
      }

      var updates = {};
      updates[STORAGE_KEYS.pendingEvents] = events;
      updates[STORAGE_KEYS.visitedUrls] = visited;
      chrome.storage.local.set(updates);
    }
  );
}

// ── Handle auto-capture ─────────────────────────────────────────────
function handleAutoCapture(data) {
  if (!data || !data.url || !data.text) return;

  // Try to send immediately to backend
  var text = (data.text || "").trim();
  if (text.length < 50) return; // Too short for document extraction

  apiFetch("/api/documents/page/extract", {
    method: "POST",
    body: JSON.stringify({
      raw_text: text.slice(0, 50000),
      page_url: data.url,
      page_title: data.title || "",
      selection_type: "full_page",
      engagement_score: data.score,
      active_time: data.activeTime,
      scroll_depth: data.scrollDepth,
    }),
  }).catch(function (err) {
    // Backend unreachable — queue for later
    chrome.storage.local.get(STORAGE_KEYS.pendingCaptures, function (result) {
      var captures = result[STORAGE_KEYS.pendingCaptures] || [];
      captures.push({
        url: data.url,
        title: data.title,
        domain: data.domain,
        textLength: text.length,
        score: data.score,
        activeTime: data.activeTime,
        scrollDepth: data.scrollDepth,
        timestamp: new Date().toISOString(),
        // Don't store full text in chrome.storage — too large
        // Just store metadata; user can re-visit and capture
      });

      // Cap at 100
      if (captures.length > 100) {
        captures = captures.slice(-100);
      }

      var updates = {};
      updates[STORAGE_KEYS.pendingCaptures] = captures;
      chrome.storage.local.set(updates);
    });
  });
}

// ── Alarm handler — periodic batch sync ─────────────────────────────
chrome.alarms.onAlarm.addListener(function (alarm) {
  if (alarm.name !== SYNC_ALARM_NAME) return;
  syncPendingEvents();
});

async function syncPendingEvents() {
  var result = await chrome.storage.local.get(STORAGE_KEYS.pendingEvents);
  var events = result[STORAGE_KEYS.pendingEvents] || [];

  if (events.length === 0) return;

  try {
    await apiFetch("/api/reading/track", {
      method: "POST",
      body: JSON.stringify({ events: events }),
    });

    // Clear synced events on success
    var updates = {};
    updates[STORAGE_KEYS.pendingEvents] = [];
    await chrome.storage.local.set(updates);
  } catch (err) {
    // Backend unreachable — keep events for next sync
    // If the endpoint doesn't exist yet (404), still keep them queued
    // They'll be sent once the backend route is implemented
  }
}

// ── Command handler — toggle reading mode side panel ────────────────
chrome.commands.onCommand.addListener(function (command) {
  if (command === "toggle-reading-mode") {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (tabs && tabs[0]) {
        chrome.sidePanel.open({ tabId: tabs[0].id }).catch(function () {
          // Side panel may not be available
        });
      }
    });
  }
});
