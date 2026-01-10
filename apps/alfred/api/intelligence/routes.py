from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from alfred.core.dependencies import (
    get_language_service,
    get_memory_service,
    get_planning_service,
    get_summarization_service,
    get_text_assist_service,
)
from alfred.schemas.intelligence import (
    AutocompleteRequest,
    AutocompleteResponse,
    ExecutionPlan,
    LanguageDetectRequest,
    LanguageDetectResponse,
    MemoryCreateRequest,
    MemoryExtractFromThreadRequest,
    MemoryItem,
    MemoryListResponse,
    PlanCreateRequest,
    QaRequest,
    QaResponse,
    SummarizeResponse,
    SummarizeTextRequest,
    SummarizeUrlRequest,
    TextEditRequest,
    TextEditResponse,
)
from alfred.services.language_service import LanguageService
from alfred.services.memory_service import MemoryService
from alfred.services.planning_service import PlanningService
from alfred.services.summarization_service import SummarizationService
from alfred.services.text_assist_service import TextAssistService

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.post(
    "/plan",
    response_model=ExecutionPlan,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(
    payload: PlanCreateRequest,
    svc: PlanningService = Depends(get_planning_service),
) -> ExecutionPlan:
    """Generate a compact execution plan for a goal."""

    try:
        return svc.create_plan(
            goal=payload.goal, context=payload.context, max_steps=payload.max_steps
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to create plan") from exc


@router.post(
    "/memory",
    response_model=MemoryItem,
    status_code=status.HTTP_201_CREATED,
)
def create_memory(
    payload: MemoryCreateRequest,
    svc: MemoryService = Depends(get_memory_service),
) -> MemoryItem:
    """Create a durable memory entry (stored as a note)."""

    try:
        return svc.create_memory(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to create memory") from exc


@router.get("/memory", response_model=MemoryListResponse)
def list_memories(
    q: str | None = Query(default=None, description="Optional text search"),
    user_id: int | None = Query(default=None),
    source: str | None = Query(default=None, description="Filter by source (thread/task/manual)"),
    thread_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    svc: MemoryService = Depends(get_memory_service),
) -> MemoryListResponse:
    """List stored memory entries with optional filtering."""

    try:
        return svc.list_memories(
            q=q,
            user_id=user_id,
            source=source,
            thread_id=thread_id,
            task_id=task_id,
            skip=skip,
            limit=limit,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to list memories") from exc


@router.get("/memory/context", response_model=list[MemoryItem])
def memory_context(
    q: str = Query(..., min_length=1, description="What you're working on right now"),
    user_id: int | None = Query(default=None),
    limit: int = Query(default=6, ge=1, le=25),
    svc: MemoryService = Depends(get_memory_service),
) -> list[MemoryItem]:
    """Return the most relevant memories for a query (to provide context)."""

    try:
        return svc.get_context_memories(query=q, user_id=user_id, limit=limit)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to fetch memory context") from exc


@router.post("/language/detect", response_model=LanguageDetectResponse)
def detect_language(
    payload: LanguageDetectRequest,
    svc: LanguageService = Depends(get_language_service),
) -> LanguageDetectResponse:
    """Detect the language of a text snippet (offline-first)."""

    try:
        return svc.detect(text=payload.text)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to detect language") from exc


@router.post("/autocomplete", response_model=AutocompleteResponse)
def autocomplete(
    payload: AutocompleteRequest,
    svc: TextAssistService = Depends(get_text_assist_service),
) -> AutocompleteResponse:
    """Suggest a continuation for the provided text."""

    try:
        return svc.autocomplete(text=payload.text, tone=payload.tone, max_chars=payload.max_chars)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Autocomplete failed") from exc


@router.post("/edit", response_model=TextEditResponse)
def edit_text(
    payload: TextEditRequest,
    svc: TextAssistService = Depends(get_text_assist_service),
) -> TextEditResponse:
    """Edit text with an instruction (tone-aware)."""

    try:
        return svc.edit(text=payload.text, instruction=payload.instruction, tone=payload.tone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Edit failed") from exc


@router.post(
    "/summarize/text",
    response_model=SummarizeResponse,
    status_code=status.HTTP_201_CREATED,
)
def summarize_text(
    payload: SummarizeTextRequest,
    svc: SummarizationService = Depends(get_summarization_service),
) -> SummarizeResponse:
    """Summarize raw text and optionally store it as a document for later Q&A."""

    try:
        summary, doc_id = svc.summarize_text(
            text=payload.text,
            title=payload.title,
            source_url=payload.source_url,
            content_type=payload.content_type,
            store=payload.store,
        )
        return SummarizeResponse(summary=summary, doc_id=doc_id, content_type=payload.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Summarization failed") from exc


@router.post(
    "/summarize/url",
    response_model=SummarizeResponse,
    status_code=status.HTTP_201_CREATED,
)
def summarize_url(
    payload: SummarizeUrlRequest,
    svc: SummarizationService = Depends(get_summarization_service),
) -> SummarizeResponse:
    """Fetch a URL, summarize it, and optionally store it as a document."""

    try:
        summary, doc_id = svc.summarize_url(
            url=payload.url,
            title=payload.title,
            render_js=payload.render_js,
            store=payload.store,
        )
        return SummarizeResponse(summary=summary, doc_id=doc_id, content_type="web")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Summarization failed") from exc


@router.post(
    "/summarize/pdf",
    response_model=SummarizeResponse,
    status_code=status.HTTP_201_CREATED,
)
def summarize_pdf(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    store: bool = Form(default=True),
    svc: SummarizationService = Depends(get_summarization_service),
) -> SummarizeResponse:
    """Summarize an uploaded PDF (best-effort text extraction)."""

    try:
        pdf_bytes = file.file.read()
        summary, doc_id = svc.summarize_pdf_bytes(
            pdf_bytes=pdf_bytes,
            title=title or (file.filename or None),
            source_url=source_url,
            store=store,
        )
        return SummarizeResponse(summary=summary, doc_id=doc_id, content_type="pdf")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Summarization failed") from exc


@router.post(
    "/summarize/audio",
    response_model=SummarizeResponse,
    status_code=status.HTTP_201_CREATED,
)
def summarize_audio(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    content_type: str = Form(default="audio"),
    store: bool = Form(default=True),
    svc: SummarizationService = Depends(get_summarization_service),
) -> SummarizeResponse:
    """Transcribe an uploaded audio file, summarize it, and optionally store it."""

    try:
        audio_bytes = file.file.read()
        summary, doc_id = svc.summarize_audio_bytes(
            audio_bytes=audio_bytes,
            filename=file.filename,
            title=title,
            source_url=source_url,
            content_type=content_type,
            store=store,
        )
        return SummarizeResponse(summary=summary, doc_id=doc_id, content_type=content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Summarization failed") from exc


@router.post("/qa", response_model=QaResponse)
def qa(
    payload: QaRequest,
    svc: SummarizationService = Depends(get_summarization_service),
) -> QaResponse:
    """Answer a question about either a stored document or an inline text blob."""

    try:
        if payload.doc_id:
            return svc.answer_question_for_doc(question=payload.question, doc_id=payload.doc_id)
        if payload.text:
            return svc.answer_question(question=payload.question, text=payload.text)
        raise HTTPException(status_code=422, detail="Provide either doc_id or text")
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Q&A failed") from exc


@router.post(
    "/memory/extract/thread",
    response_model=list[MemoryItem],
    status_code=status.HTTP_201_CREATED,
)
def extract_memories_from_thread(
    payload: MemoryExtractFromThreadRequest,
    svc: MemoryService = Depends(get_memory_service),
) -> list[MemoryItem]:
    """Extract durable memories from a thread transcript and persist them."""

    try:
        return svc.extract_memories_from_thread(
            thread_id=payload.thread_id,
            user_id=payload.user_id,
            max_memories=payload.max_memories,
            max_messages=payload.max_messages,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to extract memories") from exc
