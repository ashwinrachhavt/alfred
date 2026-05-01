/**
 * Alfred Chrome Extension — Service Worker (MV3)
 *
 * Handles side panel open requests from content scripts and keyboard shortcuts.
 */

var LEGACY_STORAGE_KEYS = [
  "alfredPendingEvents",
  "alfredVisitedUrls",
  "alfredPendingCaptures",
];

chrome.runtime.onInstalled.addListener(function () {
  chrome.storage.local.remove(LEGACY_STORAGE_KEYS);
});

chrome.runtime.onStartup.addListener(function () {
  chrome.storage.local.remove(LEGACY_STORAGE_KEYS);
});

chrome.runtime.onMessage.addListener(function (msg, sender) {
  if (!msg || msg.type !== "OPEN_SIDE_PANEL") return;

  if (sender && sender.tab && sender.tab.id) {
    chrome.sidePanel.open({ tabId: sender.tab.id }).catch(function () {});
  }
});

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
