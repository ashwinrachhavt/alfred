from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from starlette.responses import StreamingResponse

from alfred.schemas.writing import WritingPreset, WritingRequest, WritingResponse
from alfred.services.writing_service import list_writing_presets, write, write_stream

router = APIRouter(prefix="/api/writing", tags=["writing"])


def _require_extension_token(x_alfred_token: Optional[str]) -> None:
    """
    Optional shared-secret auth for local browser extensions.

    If ALFRED_EXTENSION_TOKEN is set, clients must send `X-Alfred-Token`.
    """

    expected = (os.getenv("ALFRED_EXTENSION_TOKEN") or "").strip()
    if not expected:
        return
    got = (x_alfred_token or "").strip()
    if got != expected:
        raise HTTPException(status_code=401, detail="Invalid extension token")


@router.get("/presets", response_model=list[WritingPreset])
def presets() -> list[WritingPreset]:
    """List available site writing presets."""

    return list_writing_presets()


@router.post("/compose", response_model=WritingResponse)
def compose(
    req: WritingRequest,
    x_alfred_token: Optional[str] = Header(default=None, alias="X-Alfred-Token"),
) -> WritingResponse:
    """Non-streaming writing response for simple clients."""

    _require_extension_token(x_alfred_token)
    result = write(req)
    return WritingResponse(preset_used=result.preset_used, output=result.output)


def _sse_encode(*, data: str, event: str = "token") -> str:
    # SSE frames require each line of `data` to be prefixed with "data:".
    lines = data.splitlines() or [""]
    payload = "".join([f"event: {event}\n"] + [f"data: {line}\n" for line in lines] + ["\n"])
    return payload


@router.post("/compose/stream")
def compose_stream(
    req: WritingRequest,
    x_alfred_token: Optional[str] = Header(default=None, alias="X-Alfred-Token"),
) -> StreamingResponse:
    """
    Stream a writing response using Server-Sent Events (SSE).

    Events:
    - meta: preset metadata (first)
    - token: incremental text chunks
    - done: stream finished
    """

    _require_extension_token(x_alfred_token)

    preset, stream = write_stream(req)

    def gen() -> Iterator[str]:
        yield _sse_encode(
            event="meta",
            data=json.dumps(
                {
                    "preset": preset.model_dump(mode="json"),
                    "intent": req.intent,
                    "thread_id": req.thread_id,
                },
                ensure_ascii=False,
            ),
        )
        try:
            for chunk in stream:
                if chunk:
                    yield _sse_encode(event="token", data=chunk)
        except Exception as exc:
            yield _sse_encode(event="error", data=str(exc))
            return
        yield _sse_encode(event="done", data="")

    resp = StreamingResponse(gen(), media_type="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp
