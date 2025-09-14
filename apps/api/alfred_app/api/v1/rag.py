from fastapi import APIRouter, HTTPException
import time
from alfred_app.services.rag_bot import build_chain, get_context_chunks

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/answer")
async def rag_answer(q: str, k: int = 4, include_context: bool = False):
    """
    Return a non-streaming RAG answer for Swagger/JSON clients.
    - q: question
    - k: top-k retrieval
    - include_context: return retrieved items metadata (slower)
    """
    try:

        chain = build_chain(k=k, streaming=False)
        t0 = time.perf_counter()
        answer = chain.invoke(q)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        resp = {"answer": answer, "latency_ms": latency_ms}
        if include_context:
            try:
                resp["context"] = get_context_chunks(q, k=k)
            except Exception as e:
                resp["context_error"] = str(e)
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
