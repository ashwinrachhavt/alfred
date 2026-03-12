/**
 * Alfred Chrome Extension — Popup Script
 */
(async function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // ── Populate current page URL ──────────────────────────────────────

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      $("#page-url").textContent = tab.url;
    } else {
      $("#page-url").textContent = "N/A";
    }
  } catch {
    $("#page-url").textContent = "N/A";
  }

  // ── Connection check ───────────────────────────────────────────────

  async function checkStatus() {
    const online = await AlfredAPI.health();
    const dot = $("#status-dot");
    dot.classList.toggle("online", online);
    dot.title = online ? "Alfred backend connected" : "Alfred backend offline";
  }
  checkStatus();

  // ── Load saved settings ────────────────────────────────────────────

  const res = await chrome.storage.local.get("alfredBaseUrl");
  if (res.alfredBaseUrl) {
    $("#api-url-input").value = res.alfredBaseUrl;
  }

  // ── Status message helper ──────────────────────────────────────────

  function flashStatus(container, message, type = "success") {
    // Remove previous
    const prev = container.querySelector(".status-msg");
    if (prev) prev.remove();
    const msg = document.createElement("p");
    msg.className = `status-msg ${type}`;
    msg.textContent = message;
    container.appendChild(msg);
    setTimeout(() => msg.remove(), 3000);
  }

  // ── Capture page ───────────────────────────────────────────────────

  $("#btn-capture").addEventListener("click", async () => {
    const btn = $("#btn-capture");
    btn.disabled = true;
    btn.textContent = "Capturing...";
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      // Execute script in the active tab to get page content
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => ({
          text: document.body.innerText.slice(0, 50000),
          title: document.title,
          url: location.href,
        }),
      });
      const page = results[0].result;
      await AlfredAPI.capturePage({
        url: page.url,
        title: page.title,
        content: page.text,
      });
      await AlfredAPI.addCaptureHistory({
        title: `[Page] ${page.title}`,
        url: page.url,
        type: "page-capture",
      });
      flashStatus($("#quick-actions"), "Page captured!", "success");
    } catch (err) {
      flashStatus($("#quick-actions"), `Error: ${err.message}`, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Capture Page";
    }
  });

  // ── Open Alfred ────────────────────────────────────────────────────

  $("#btn-open-alfred").addEventListener("click", async () => {
    const base = await AlfredAPI.base();
    chrome.tabs.create({ url: base });
  });

  // ── Open Dashboard ─────────────────────────────────────────────────

  $("#btn-dashboard").addEventListener("click", () => {
    chrome.tabs.create({ url: chrome.runtime.getURL("dashboard.html") });
  });

  // ── Save quick note ────────────────────────────────────────────────

  $("#btn-save-note").addEventListener("click", async () => {
    let text = $("#note-input").value.trim();
    const btn = $("#btn-save-note");
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // If textarea is empty, try clipboard
    if (!text) {
      try {
        const clip = await navigator.clipboard.readText();
        if (clip && clip.trim()) text = clip.trim();
      } catch {}
    }

    // Still empty? Capture the full page
    if (!text) {
      btn.disabled = true;
      btn.textContent = "Capturing page...";
      try {
        const results = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => ({
            text: document.body.innerText.slice(0, 50000),
            title: document.title,
            url: location.href,
          }),
        });
        const page = results[0].result;
        await AlfredAPI.capturePage({
          url: page.url,
          title: page.title,
          content: page.text,
        });
        AlfredAPI.addCaptureHistory({
          title: `[Page] ${page.title}`,
          url: page.url,
          type: "page-capture",
        }).catch(() => {});
        flashStatus($("#quick-note"), "Page captured!", "success");
      } catch (err) {
        flashStatus($("#quick-note"), `Error: ${err.message}`, "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "Save Note";
      }
      return;
    }

    // Save the text (from textarea or clipboard)
    btn.disabled = true;
    try {
      await AlfredAPI.captureSelection({
        url: tab?.url || "",
        title: tab?.title || "",
        selectedText: text,
      });
      AlfredAPI.addCaptureHistory({
        title: text.slice(0, 80),
        url: tab?.url || "",
        type: "quick-note",
      }).catch(() => {});
      $("#note-input").value = "";
      flashStatus($("#quick-note"), "Note saved!", "success");
    } catch (err) {
      flashStatus($("#quick-note"), `Error: ${err.message}`, "error");
    } finally {
      btn.disabled = false;
    }
  });

  // ── Save settings ──────────────────────────────────────────────────

  $("#btn-save-settings").addEventListener("click", async () => {
    const url = $("#api-url-input").value.trim();
    if (url) {
      await AlfredAPI.setBase(url);
    } else {
      await AlfredAPI.setBase("http://localhost:3001");
      $("#api-url-input").value = "";
    }
    flashStatus($("#settings-section"), "Settings saved!", "success");
    checkStatus();
  });
})();
