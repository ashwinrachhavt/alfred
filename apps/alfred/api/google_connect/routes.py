from __future__ import annotations

import secrets
from typing import Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from alfred.services.google_oauth import (
    GOOGLE_SCOPES,
    exchange_code_for_tokens,
    generate_authorization_url,
    load_credentials_async,
    persist_credentials_async,
)

api_router = APIRouter(prefix="/api/google", tags=["google"])
ui_router = APIRouter(tags=["google"], include_in_schema=False)
legacy_router = APIRouter(prefix="/api/v1", tags=["google"], include_in_schema=False)

_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_SCOPE_CONFIG: Dict[str, Dict[str, object]] = {
    "gmail": {
        "label": "Gmail",
        "scopes": lambda: GOOGLE_SCOPES,
    },
    "calendar": {
        "label": "Google Calendar",
        "scopes": lambda: GOOGLE_SCOPES,
    },
}


def _resolve_scope(scope: str) -> dict[str, object]:
    normalized = scope.strip().lower()
    config = _SCOPE_CONFIG.get(normalized)
    if config is None:
        raise HTTPException(status_code=400, detail=f"Unsupported scope '{scope}'")
    return {
        "name": normalized,
        "label": config["label"],
        "scopes": list(config["scopes"]()),
    }


@api_router.get("/status")
async def google_status(scope: str = Query("gmail")) -> dict[str, object]:
    info = _resolve_scope(scope)
    creds = await load_credentials_async(is_calendar=info["name"] == "calendar")
    return {
        "scope": info["name"],
        "label": info["label"],
        "connected": creds is not None,
    }


@api_router.get("/auth-url")
async def google_auth_url(scope: str = Query("gmail"), state: str | None = None) -> dict[str, str | None]:
    info = _resolve_scope(scope)
    requested_state = state or f"{info['name']}:{secrets.token_urlsafe(12)}"
    url, returned_state = generate_authorization_url(state=requested_state, scopes=GOOGLE_SCOPES)
    return {"authorization_url": url, "state": returned_state}


async def _handle_callback(code: str, state: str | None) -> HTMLResponse:
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    scope_name = state.split(":", 1)[0]
    info = _resolve_scope(scope_name)

    creds = exchange_code_for_tokens(user_id=None, code=code, state=state)
    await persist_credentials_async(
        None,
        creds,
        scopes=list(creds.scopes or GOOGLE_SCOPES),
        is_calendar=info["name"] == "calendar",
    )

    html = f"""
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Google connection saved</title>
    <meta http-equiv=\"refresh\" content=\"2; url=/google/connect\" />
    <style>body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; text-align: center; padding-top: 80px; color: #1f2933; }}</style>
  </head>
  <body>
    <h1>{info['label']} connected</h1>
    <p>You can close this window, or wait while we take you back to the connection dashboard.</p>
  </body>
</html>
"""
    return HTMLResponse(html)


@api_router.get("/oauth/callback", response_class=HTMLResponse)
async def google_oauth_callback(code: str, state: str | None = None) -> HTMLResponse:
    return await _handle_callback(code, state)


@legacy_router.get("/gmail/callback", response_class=HTMLResponse)
async def legacy_gmail_callback(code: str, state: str | None = None) -> HTMLResponse:
    state = state or "gmail:legacy"
    return await _handle_callback(code, state)


@legacy_router.get("/calendar/callback", response_class=HTMLResponse)
async def legacy_calendar_callback(code: str, state: str | None = None) -> HTMLResponse:
    state = state or "calendar:legacy"
    return await _handle_callback(code, state)


@ui_router.get("/google/connect", response_class=HTMLResponse)
async def google_connect_page() -> str:
    page = """
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Connect Google Accounts</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 48px auto; max-width: 720px; line-height: 1.5; color: #1f2933; }
      h1 { font-size: 1.75rem; margin-bottom: 1rem; }
      section { border: 1px solid #cbd2d9; border-radius: 12px; padding: 24px; margin-bottom: 24px; background: #f8fafc; }
      button { background: #2563eb; border: none; color: white; padding: 10px 20px; border-radius: 999px; font-size: 1rem; cursor: pointer; }
      button[disabled] { background: #9aa5b1; cursor: not-allowed; }
      .status { margin-top: 8px; font-size: 0.95rem; }
      .results { margin-top: 16px; }
      .results ul { padding-left: 18px; }
      .results li { margin-bottom: 12px; }
      .muted { color: #64748b; font-size: 0.9rem; }
      #error { color: #b91c1c; margin-top: 16px; display: none; }
    </style>
  </head>
  <body>
    <h1>Connect Google Services</h1>
    <p>Link your Google accounts once so Alfred can access Gmail and Calendar securely via stored OAuth tokens.</p>

    <section id=\"gmail-section\">
      <h2>Gmail</h2>
      <p>Grant read access so Alfred can triage and draft replies from your inbox.</p>
      <button id=\"gmail-button\" type=\"button\" onclick=\"startConnect('gmail')\">Connect Gmail</button>
      <div class=\"status\" id=\"gmail-status\"></div>
      <div class=\"results\" id=\"gmail-results\"></div>
    </section>

    <section id=\"calendar-section\">
      <h2>Google Calendar</h2>
      <p>Allow Alfred to check availability and send calendar invites on your behalf.</p>
      <button id=\"calendar-button\" type=\"button\" onclick=\"startConnect('calendar')\">Connect Calendar</button>
      <div class=\"status\" id=\"calendar-status\"></div>
      <div class=\"results\" id=\"calendar-results\"></div>
    </section>

    <p id=\"error\"></p>

    <script>
      async function fetchStatus(scope) {
        const statusEl = document.getElementById(`${scope}-status`);
        const buttonEl = document.getElementById(`${scope}-button`);
        try {
          const res = await fetch(`/api/google/status?scope=${scope}`);
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          const connected = data.connected ? 'Connected' : 'Not connected';
          statusEl.textContent = `${data.label}: ${connected}`;
          buttonEl.textContent = data.connected ? 'Re-authenticate' : `Connect ${data.label}`;

          if (data.connected) {
            if (scope === 'gmail') {
              await fetchGmailPreview();
            } else if (scope === 'calendar') {
              await fetchCalendarPreview();
            }
          }
        } catch (err) {
          statusEl.textContent = 'Unable to determine status';
          showError(err);
        }
      }

      async function startConnect(scope) {
        try {
          const res = await fetch(`/api/google/auth-url?scope=${scope}`);
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (!data.authorization_url) throw new Error('Missing authorization URL');
          window.location.href = data.authorization_url;
        } catch (err) {
          showError(err);
        }
      }

      function showError(err) {
        const el = document.getElementById('error');
        el.textContent = `Something went wrong: ${err}`;
        el.style.display = 'block';
      }

      function renderList(containerId, title, items, formatter) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!items.length) {
          container.innerHTML = `<p class="muted">No ${title} found.</p>`;
          return;
        }
        const list = items.map(formatter).join('');
        container.innerHTML = `<h3>${title}</h3><ul>${list}</ul>`;
      }

      async function fetchGmailPreview() {
        try {
          const res = await fetch('/api/gmail/messages?q=is:inbox&max_results=10');
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          renderList(
            'gmail-results',
            'Latest Inbox Messages',
            data.items || [],
            (item) => {
              const subject = item.subject || '(no subject)';
              const from = item.from || 'Unknown sender';
              const when = item.date ? new Date(item.date).toLocaleString() : '';
              const snippet = item.snippet ? item.snippet.replace(/</g, '&lt;') : '';
              return `<li><strong>${subject}</strong><br/><span class="muted">${from} • ${when}</span><br/>${snippet}</li>`;
            }
          );
        } catch (err) {
          document.getElementById('gmail-results').innerHTML = '<p class="muted">Unable to load Gmail preview.</p>';
          console.error(err);
        }
      }

      async function fetchCalendarPreview() {
        try {
          const now = new Date();
          const inSeven = new Date(now);
          inSeven.setDate(now.getDate() + 7);
          const params = new URLSearchParams({
            start_date: now.toISOString(),
            end_date: inSeven.toISOString(),
            max_results: '10',
          });
          const res = await fetch(`/api/calendar/events?${params.toString()}`);
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          renderList(
            'calendar-results',
            'Upcoming Events (7 days)',
            data.items || [],
            (event) => {
              const summary = event.summary || '(untitled event)';
              const start = (event.start || {}).dateTime || (event.start || {}).date || '';
              const when = start ? new Date(start).toLocaleString() : '';
              const location = event.location ? ` • ${event.location}` : '';
              return `<li><strong>${summary}</strong><br/><span class="muted">${when}${location}</span></li>`;
            }
          );
        } catch (err) {
          document.getElementById('calendar-results').innerHTML = '<p class="muted">Unable to load calendar preview.</p>';
          console.error(err);
        }
      }

      fetchStatus('gmail');
      fetchStatus('calendar');
    </script>
  </body>
</html>
"""
    return page


@ui_router.get("/connect/gmail", include_in_schema=False)
async def legacy_connect_gmail() -> RedirectResponse:
    return RedirectResponse(url="/google/connect", status_code=307)


@ui_router.get("/gmail/connect", include_in_schema=False)
async def legacy_connect_gmail_alt() -> RedirectResponse:
    return RedirectResponse(url="/google/connect", status_code=307)
