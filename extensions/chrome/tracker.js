/**
 * Alfred Chrome Extension — Engagement Tracker (Gear 1)
 *
 * Runs on every page. Detects engagement signals (scroll depth, active reading
 * time, text selection, copy events) and sends them to the service worker.
 * Auto-captures page content when engagement score crosses threshold.
 */
(function () {
  "use strict";

  // Prevent double-injection
  if (window.__alfredTrackerLoaded) return;
  window.__alfredTrackerLoaded = true;

  // ── Blocklist — skip tracking on sensitive/local domains ──────────
  var BLOCKLIST = [
    "chase.com",
    "bankofamerica.com",
    "wellsfargo.com",
    "schwab.com",
    "mail.google.com",
    "outlook.live.com",
    "outlook.office.com",
    "messages.google.com",
    "web.whatsapp.com",
    "accounts.google.com",
    "localhost",
    "127.0.0.1",
  ];

  // Patterns that match auth/login/SSO domains (prefix matching)
  var BLOCK_PATTERNS = [
    "login.",
    "auth.",
    "sso.",
    "signin.",
    "accounts.",
    "id.",
  ];

  // Domains that contain these substrings anywhere
  var BLOCK_CONTAINS = [
    "duosecurity.com",
    "okta.com",
    "auth0.com",
    "onelogin.com",
    "microsoftonline.com",
  ];

  var domain = location.hostname;
  if (
    BLOCKLIST.some(function (b) {
      return domain === b || domain.endsWith("." + b);
    }) ||
    BLOCK_PATTERNS.some(function (p) {
      return domain.startsWith(p);
    }) ||
    BLOCK_CONTAINS.some(function (c) {
      return domain.includes(c);
    })
  )
    return;

  // ── State ─────────────────────────────────────────────────────────
  var startTime = Date.now();
  var activeTime = 0;
  var lastActiveTimestamp =
    document.visibilityState === "visible" ? Date.now() : null;
  var maxScrollDepth = 0;
  var hasSelected = false;
  var hasCopied = false;
  var score = 0;
  var captured = false;
  var progressBarVisible = false;
  var badgeVisible = false;

  // ── Scroll tracking (throttled to every 2 seconds) ────────────────
  var scrollThrottleTimer = null;
  window.addEventListener(
    "scroll",
    function () {
      if (scrollThrottleTimer) return;
      scrollThrottleTimer = setTimeout(function () {
        scrollThrottleTimer = null;
        var scrollTop = window.scrollY || document.documentElement.scrollTop;
        var docHeight = Math.max(
          document.documentElement.scrollHeight - window.innerHeight,
          1
        );
        var depth = Math.min(
          100,
          Math.round((scrollTop / docHeight) * 100)
        );
        if (depth > maxScrollDepth) {
          maxScrollDepth = depth;
          updateScore();
          sendUpdate();
        }
      }, 2000);
    },
    { passive: true }
  );

  // ── Active time tracking ──────────────────────────────────────────
  function updateActiveTime() {
    if (lastActiveTimestamp) {
      activeTime += Date.now() - lastActiveTimestamp;
    }
    lastActiveTimestamp =
      document.visibilityState === "visible" && document.hasFocus()
        ? Date.now()
        : null;
  }

  document.addEventListener("visibilitychange", function () {
    updateActiveTime();
    updateScore();
    sendUpdate();
  });

  window.addEventListener("focus", function () {
    updateActiveTime();
  });

  window.addEventListener("blur", function () {
    updateActiveTime();
    updateScore();
    sendUpdate();
  });

  // ── Selection tracking ────────────────────────────────────────────
  document.addEventListener("selectionchange", function () {
    var text = window.getSelection().toString().trim();
    if (text.length > 2 && !hasSelected) {
      hasSelected = true;
      updateScore();
      sendUpdate();
    }
  });

  // ── Copy tracking ────────────────────────────────────────────────
  document.addEventListener("copy", function () {
    if (!hasCopied) {
      hasCopied = true;
      updateScore();
      sendUpdate();
    }
  });

  // ── Score computation ─────────────────────────────────────────────
  function updateScore() {
    updateActiveTime();
    var activeMs = activeTime;
    var s = 0;

    // Time: 0-40 points
    if (activeMs >= 600000) s += 40; // 10min+
    else if (activeMs >= 300000) s += 30; // 5min+
    else if (activeMs >= 120000) s += 20; // 2min+

    // Scroll: 0-25 points
    if (maxScrollDepth >= 100) s += 25;
    else if (maxScrollDepth >= 75) s += 15;

    // Selection: 0 or 15
    if (hasSelected) s += 15;

    // Copy: 0 or 10
    if (hasCopied) s += 10;

    score = s;

    // Show progress bar and badge after 30 seconds of active reading
    if (activeMs >= 30000 && !progressBarVisible) {
      showProgressBar();
      progressBarVisible = true;
    }
    if (activeMs >= 30000 && !badgeVisible) {
      showBadge();
      badgeVisible = true;
    }

    updateProgressBar();
    updateBadge();

    // Auto-capture at threshold
    if (score >= 40 && !captured) {
      captured = true;
      triggerCapture();
    }
  }

  // ── Progress bar UI (thin orange bar at top of page) ──────────────
  var progressBar = null;
  var progressFill = null;

  function showProgressBar() {
    if (progressBar) return;

    progressBar = document.createElement("div");
    progressBar.className = "alfred-progress-bar";

    progressFill = document.createElement("div");
    progressFill.className = "alfred-progress-fill";
    progressFill.style.width = maxScrollDepth + "%";

    progressBar.appendChild(progressFill);
    document.body.appendChild(progressBar);
  }

  function updateProgressBar() {
    if (progressFill) {
      progressFill.style.width = maxScrollDepth + "%";
    }
  }

  // ── Tracking badge UI (bottom-left) ──────────────────────────────
  var badge = null;
  var badgeTimeEl = null;

  function showBadge() {
    if (badge) return;

    badge = document.createElement("div");
    badge.className = "alfred-tracking-badge";

    var dot = document.createElement("span");
    dot.className = "alfred-tracking-dot";

    badgeTimeEl = document.createElement("span");
    badgeTimeEl.className = "alfred-tracking-time";
    badgeTimeEl.textContent = formatActiveTime(activeTime);

    badge.appendChild(dot);
    badge.appendChild(badgeTimeEl);
    document.body.appendChild(badge);
  }

  function updateBadge() {
    if (badgeTimeEl) {
      badgeTimeEl.textContent = formatActiveTime(activeTime);
    }
  }

  function formatActiveTime(ms) {
    var totalSec = Math.floor(ms / 1000);
    var min = Math.floor(totalSec / 60);
    var sec = totalSec % 60;
    if (min > 0) {
      return min + "m " + (sec < 10 ? "0" : "") + sec + "s";
    }
    return sec + "s";
  }

  // ── Send update to service worker (throttled to every 5 seconds) ──
  var sendThrottleTimer = null;

  function sendUpdate() {
    if (sendThrottleTimer) return;
    sendThrottleTimer = setTimeout(function () {
      sendThrottleTimer = null;
      updateActiveTime();
      try {
        chrome.runtime.sendMessage({
          type: "ENGAGEMENT_UPDATE",
          data: {
            url: location.href,
            title: document.title,
            domain: location.hostname,
            score: score,
            activeTime: activeTime,
            scrollDepth: maxScrollDepth,
            hasSelected: hasSelected,
            hasCopied: hasCopied,
            timestamp: new Date().toISOString(),
          },
        }).catch(function () {
          // SW might be asleep — that's fine
        });
      } catch (e) {
        // Extension context invalidated — ignore
      }
    }, 5000);
  }

  // ── Trigger auto-capture when threshold crossed ───────────────────
  function triggerCapture() {
    // Use requestIdleCallback to avoid blocking the page
    var extractAndSend = function () {
      // Use shared extractor for consistent extraction
      var extracted = window.AlfredExtract
        ? window.AlfredExtract.extractPage()
        : { raw_text: document.body.innerText.slice(0, 50000), raw_markdown: null, quality: "basic", content_type_hint: "generic" };

      try {
        chrome.runtime.sendMessage({
          type: "AUTO_CAPTURE",
          data: {
            url: location.href,
            title: document.title,
            domain: location.hostname,
            text: extracted.raw_text,
            raw_markdown: extracted.raw_markdown,
            quality: extracted.quality,
            content_type_hint: extracted.content_type_hint,
            score: score,
            activeTime: activeTime,
            scrollDepth: maxScrollDepth,
          },
        }).catch(function () {
          // SW might be asleep
        });
      } catch (e) {
        // Extension context invalidated
      }
    };

    if (typeof requestIdleCallback !== "undefined") {
      requestIdleCallback(extractAndSend, { timeout: 5000 });
    } else {
      setTimeout(extractAndSend, 100);
    }
  }

  // ── Listen for side panel requesting article text ─────────────────
  // NOTE: content.js also handles GET_ARTICLE_TEXT with the shared extractor.
  // tracker.js handler is kept as fallback for when content.js hasn't loaded yet.
  try {
    chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
      if (msg.type === "GET_ARTICLE_TEXT") {
        var extracted = window.AlfredExtract
          ? window.AlfredExtract.extractPage()
          : { raw_text: document.body.innerText.slice(0, 50000), raw_markdown: null, quality: "basic", content_type_hint: "generic" };

        sendResponse({
          url: location.href,
          title: document.title,
          text: extracted.raw_text,
          raw_markdown: extracted.raw_markdown,
          quality: extracted.quality,
          content_type_hint: extracted.content_type_hint,
        });
        return true; // async response
      }
    });
  } catch (e) {
    // Extension context may be invalidated
  }

  // ── Periodic score update (every 10 seconds for time-based scoring)
  setInterval(function () {
    updateScore();
    sendUpdate();
  }, 10000);

  // ── Initial send after 5 seconds ─────────────────────────────────
  setTimeout(function () {
    updateScore();
    sendUpdate();
  }, 5000);
})();
