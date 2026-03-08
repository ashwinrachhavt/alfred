from fastapi import FastAPI
from fastapi.routing import APIRoute

from alfred.api.google.routes import router as google_router


def test_google_oauth_callback_has_no_response_model() -> None:
    """Ensure callback route doesn't rely on return-type inference.

    FastAPI can error during app startup if it tries to build a Pydantic response
    model from a non-model/union return type annotation (e.g. Response | dict).
    """

    app = FastAPI()
    app.include_router(google_router)

    route = next(
        r for r in app.routes if isinstance(r, APIRoute) and r.path == "/api/google/oauth/callback"
    )
    assert route.response_model is None
