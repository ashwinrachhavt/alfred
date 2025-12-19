import logging
import time

from fastapi import APIRouter, Query

from alfred.core.exceptions import ServiceUnavailableError
from alfred.services.agentic_rag import answer_agentic, get_context_chunks

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger(__name__)


@router.get("/answer")
async def rag_answer(
    q: str,
    k: int = 4,
    include_context: bool = False,
    mode: str = Query("minimal", description="Answer style: minimal | concise | formal | deep"),
):
    """
    Return a non-streaming RAG answer for Swagger/JSON clients.
    - q: question
    - k: top-k retrieval
    - include_context: return retrieved items metadata (slower)
    """
    try:
        t0 = time.perf_counter()
        answer = answer_agentic(q, k=k, mode=mode)
        latency_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as exc:
        logger.exception("RAG answer failed")
        raise ServiceUnavailableError("RAG answer failed") from exc

    resp = {"answer": answer, "latency_ms": latency_ms}
    if include_context:
        try:
            resp["context"] = get_context_chunks(q, k=k)
        except Exception as exc:
            logger.warning("RAG context fetch failed: %s", exc)
            resp["context_error"] = "Failed to retrieve context"
    return resp
