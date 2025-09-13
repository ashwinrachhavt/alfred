import importlib.util
from pathlib import Path
from fastapi import APIRouter
from alfred_app.core.config import settings

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail-status"])


def _dep_present(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def gmail_readiness():
    deps_installed = all(
        [
            _dep_present("itsdangerous"),
            _dep_present("googleapiclient"),
            _dep_present("google_auth_oauthlib"),
            _dep_present("google.oauth2"),
        ]
    )

    required = {
        "GOOGLE_CLIENT_ID": bool(settings.google_client_id),
        "GOOGLE_CLIENT_SECRET": bool(settings.google_client_secret),
        "GOOGLE_REDIRECT_URI": bool(settings.google_redirect_uri),
        "GOOGLE_PROJECT_ID": bool(settings.google_project_id),
    }
    configured = all(required.values())
    missing = [k for k, ok in required.items() if not ok]

    token_dir = Path(settings.token_store_dir)
    try:
        token_dir.mkdir(parents=True, exist_ok=True)
        token_dir_ready = True
    except Exception:
        token_dir_ready = False

    enabled = bool(settings.enable_gmail)
    ready = enabled and deps_installed and configured and token_dir_ready

    return {
        "enabled": enabled,
        "deps_installed": deps_installed,
        "configured": configured,
        "missing": missing,
        "token_dir_ready": token_dir_ready,
        "ready": ready,
    }


@router.get("/status")
def gmail_status():
    return gmail_readiness()
