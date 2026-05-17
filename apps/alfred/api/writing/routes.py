from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from starlette.responses import StreamingResponse

from alfred.core.settings import settings
from alfred.schemas.writing import WritingPreset, WritingRequest, WritingResponse
from alfred.services.writing_service import list_writing_presets, write, write_stream
from alfred.streaming.events import (
    AnyRunEvent,
    MessageDelta,
    MessageFinished,
    MessageStarted,
    RunErrored,
    RunFinished,
    RunStarted,
)
from alfred.streaming.projectors.wire_agui import AGUIProjector

router = APIRouter(prefix="/api/writing", tags=["writing"])

logger = logging.getLogger(__name__)


def _require_extension_token(x_alfred_token: str | None) -> None:
    """Optional shared-secret auth for local browser extensions.

    If ALFRED_EXTENSION_TOKEN is set, clients must send `X-Alfred-Token`.
    """

    token = settings.alfred_extension_token
    expected = token.get_secret_value().strip() if token else ""
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
    x_alfred_token: str | None = Header(default=None, alias="X-Alfred-Token"),
) -> WritingResponse:
    """Non-streaming writing response for simple clients."""

    _require_extension_token(x_alfred_token)
    result = write(req)
    return WritingResponse(preset_used=result.preset_used, output=result.output)


def _format_agui_sse(frame: dict, seq: int) -> str:
    """Format an AG-UI event object as an SSE data frame.

    Mirrors the format used by /api/agent/stream/v2: an `id:` line carrying
    the monotonic seq, followed by a JSON `data:` line whose payload's
    `type` field is the AG-UI event name.
    """
    payload = json.dumps(frame, separators=(",", ":"), default=str)
    return f"id: {seq}\ndata: {payload}\n\n"


@router.post("/compose/stream")
def compose_stream(
    req: WritingRequest,
    x_alfred_token: str | None = Header(default=None, alias="X-Alfred-Token"),
) -> StreamingResponse:
    """Stream a writing response as canonical AG-UI events over SSE.

    Wire frames emitted (in order):
      1. RUN_STARTED                     — once per request
      2. CUSTOM (alfred.writing.preset)  — preset metadata for compat
      3. TEXT_MESSAGE_START              — message boundary open
      4. TEXT_MESSAGE_CONTENT * N        — one per token chunk
      5. TEXT_MESSAGE_END                — message boundary close
      6. RUN_FINISHED                    — terminal success
      OR
      6'. RUN_ERROR                      — terminal failure (replaces 6)
    """

    _require_extension_token(x_alfred_token)

    preset, stream = write_stream(req)
    projector = AGUIProjector()
    run_id = uuid4()
    message_id = uuid4()

    def gen() -> Iterator[str]:
        seq = 0

        def emit(event: AnyRunEvent) -> Iterator[str]:
            """Project a domain event to AG-UI frames and format as SSE."""
            nonlocal seq
            for frame in projector.frames_for(event):
                yield _format_agui_sse(frame, seq)
                seq += 1

        # 1. Run lifecycle open.
        yield from emit(
            RunStarted(
                run_id=run_id,
                seq=seq,
                emitted_at=datetime.now(UTC),
                run_type="writing_compose",
                thread_id=None,
                input_summary=None,
                model_id=None,
            )
        )

        # 2. Preset metadata as a CUSTOM frame so non-message context still
        # rides the AG-UI bus (Smart Reader extension reads this).
        custom_frame = {
            "type": "CUSTOM",
            "name": "alfred.writing.preset",
            "value": {
                "preset": preset.model_dump(mode="json"),
                "intent": req.intent,
                "thread_id": req.thread_id,
            },
        }
        yield _format_agui_sse(custom_frame, seq)
        seq += 1

        # 3. Message open.
        yield from emit(
            MessageStarted(
                run_id=run_id,
                seq=seq,
                emitted_at=datetime.now(UTC),
                message_id=message_id,
            )
        )

        # 4. Stream tokens. Capture the full text so MessageFinished carries it.
        chunks: list[str] = []
        try:
            for chunk in stream:
                if not chunk:
                    continue
                chunks.append(chunk)
                yield from emit(
                    MessageDelta(
                        run_id=run_id,
                        seq=seq,
                        emitted_at=datetime.now(UTC),
                        message_id=message_id,
                        delta_text=chunk,
                    )
                )
        except Exception as exc:  # pragma: no cover - exercised by integration tests
            logger.exception("writing-stream generation failed")
            yield from emit(
                RunErrored(
                    run_id=run_id,
                    seq=seq,
                    emitted_at=datetime.now(UTC),
                    error_type=type(exc).__name__,
                    error_message=str(exc) or "Writing failed",
                )
            )
            return

        # 5. Message close.
        full_text = "".join(chunks)
        yield from emit(
            MessageFinished(
                run_id=run_id,
                seq=seq,
                emitted_at=datetime.now(UTC),
                message_id=message_id,
                final_text=full_text,
            )
        )

        # 6. Run lifecycle close.
        yield from emit(
            RunFinished(
                run_id=run_id,
                seq=seq,
                emitted_at=datetime.now(UTC),
            )
        )

    resp = StreamingResponse(gen(), media_type="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp
