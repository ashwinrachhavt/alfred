from __future__ import annotations


def render_oauth_callback_page(*, ok: bool, message: str) -> str:
    """Render a minimal HTML page for OAuth callback windows.

    Intended for popup-based OAuth flows where the backend receives the callback
    and should notify the opener before closing itself.
    """

    status = "success" if ok else "error"
    heading = "Google connected" if ok else "Google connection failed"
    body = (message or "").replace("<", "&lt;").replace(">", "&gt;")

    # Inline CSS/JS to keep this endpoint dependency-free.
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{heading}</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; padding: 32px; }}
      .card {{ max-width: 520px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px 20px; }}
      .badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; }}
      .badge.success {{ background: #dcfce7; color: #166534; }}
      .badge.error {{ background: #fee2e2; color: #991b1b; }}
      h1 {{ font-size: 18px; margin: 12px 0 8px; }}
      p {{ color: #374151; margin: 0; line-height: 1.5; }}
      .hint {{ margin-top: 10px; color: #6b7280; font-size: 13px; }}
    </style>
  </head>
  <body>
    <div class="card">
      <span class="badge {status}">{status}</span>
      <h1>{heading}</h1>
      <p>{body}</p>
      <p class="hint">This window should close automatically. If it doesn't, you can close it and return to Alfred.</p>
    </div>
    <script>
      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage({{ type: "alfred:google_oauth", ok: {str(ok).lower()} }}, "*");
        }}
      }} catch (e) {{}}
      setTimeout(() => {{
        try {{ window.close(); }} catch (e) {{}}
      }}, 250);
    </script>
  </body>
</html>"""


__all__ = ["render_oauth_callback_page"]
