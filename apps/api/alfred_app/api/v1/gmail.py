import base64
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import io
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail"])


@router.get("/login")
def gmail_login(profile_id: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:  # missing deps
        raise HTTPException(
            status_code=503,
            detail="Gmail integration not installed. Run 'pip install -r apps/api/requirements.txt' and set GOOGLE_* env vars.",
        ) from e
    return RedirectResponse(GmailService.auth_url(profile_id))


@router.get("/callback")
def gmail_callback(code: str, state: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:  # missing deps
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    return GmailService.exchange_code(code, state)


@router.get("/messages")
def gmail_messages(profile_id: str, email: str, q: str = "newer_than:7d", max_results: int = 10):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    return {"messages": GmailService.list_messages(profile_id, email, q, max_results)}


@router.post("/watch")
def gmail_watch(profile_id: str, email: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    return GmailService.watch_mailbox(profile_id, email)


@router.post("/push")
async def gmail_push(request: Request):
    payload = await request.json()
    msg = payload.get("message", {})
    data_b64 = msg.get("data", "")
    # Optional OIDC verification for production
    from alfred_app.core.config import settings
    if settings.gmail_push_oidc_audience:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as grequests
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing bearer token")
            token = auth.split(" ", 1)[1]
            id_token.verify_oauth2_token(
                token,
                grequests.Request(),
                audience=settings.gmail_push_oidc_audience,
                clock_skew_in_seconds=60,
            )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid OIDC token")
    try:
        decoded = json.loads(base64.urlsafe_b64decode(data_b64 + "==").decode()) if data_b64 else {}
    except Exception:
        decoded = {}
    return {"status": "ok", "received": decoded}


@router.get("/message")
def gmail_message(
    profile_id: str,
    email: str,
    id: str,
    format: str = "metadata",  # metadata|full|raw
):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    if format not in {"metadata", "full", "raw"}:
        raise HTTPException(400, "format must be metadata, full, or raw")
    try:
        msg = GmailService.get_message(profile_id, email, id, fmt=format)
        return msg
    except Exception as e:
        m = str(e)
        if "Metadata scope" in m or "forbidden" in m:
            raise HTTPException(400, "Token missing gmail.readonly for this operation. Reconnect Gmail with consent.")
        raise


@router.get("/message/text")
def gmail_message_text(profile_id: str, email: str, id: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    try:
        msg = GmailService.get_message(profile_id, email, id, fmt="full")
        text = GmailService.extract_plaintext(msg) or ""
        return {"id": id, "text": text}
    except Exception as e:
        m = str(e)
        if "Metadata scope" in m or "forbidden" in m:
            raise HTTPException(400, "Token missing gmail.readonly; cannot fetch full body. Reconnect with consent.")
        raise


@router.get("/message/html")
def gmail_message_html(profile_id: str, email: str, id: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    try:
        msg = GmailService.get_message(profile_id, email, id, fmt="full")
        html = GmailService.extract_html(msg) or ""
        return {"id": id, "html": html}
    except Exception as e:
        m = str(e)
        if "Metadata scope" in m or "forbidden" in m:
            raise HTTPException(400, "Token missing gmail.readonly; cannot fetch HTML. Reconnect with consent.")
        raise


@router.get("/message/attachments")
def gmail_message_attachments(profile_id: str, email: str, id: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    msg = GmailService.get_message(profile_id, email, id, fmt="full")
    atts = GmailService.list_attachments_from_message(msg)
    return {"id": id, "attachments": atts}


@router.get("/message/attachment/download")
def gmail_attachment_download(profile_id: str, email: str, id: str, attachment_id: str, filename: str | None = None):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    content = GmailService.download_attachment(profile_id, email, id, attachment_id)
    fname = filename or "attachment"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=\"{fname}\""},
    )


@router.get("/search")
def gmail_search(profile_id: str, email: str, q: str, max_results: int = 10):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    items = GmailService.search_messages_enriched(profile_id, email, q=q, max_results=max_results)
    return {"results": items}


@router.get("/accounts")
def gmail_accounts(profile_id: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    return {"profile_id": profile_id, "emails": GmailService.list_accounts(profile_id)}


@router.get("/me")
def gmail_me(profile_id: str, email: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    return GmailService.get_profile(profile_id, email)


@router.get("/token/scopes")
def gmail_token_scopes(profile_id: str, email: str):
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gmail integration not installed") from e
    return {"profile_id": profile_id, "email": email, "scopes": GmailService.token_scopes(profile_id, email)}
@router.get("/login_url")
def gmail_login_url(profile_id: str):
    """Return the OAuth URL as JSON so you can open it manually from Swagger."""
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:  # missing deps
        raise HTTPException(
            status_code=503,
            detail="Gmail integration not installed. Run 'pip install -r apps/api/requirements.txt' and set GOOGLE_* env vars.",
        ) from e
    return {"auth_url": GmailService.auth_url(profile_id)}
