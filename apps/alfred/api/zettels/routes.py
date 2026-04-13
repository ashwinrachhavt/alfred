from __future__ import annotations

import json as _json
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.core.redis_client import get_redis_client
from alfred.models.zettel import ZettelCard, ZettelReview

_log = logging.getLogger(__name__)
_TOPICS_CACHE_KEY = "zettel:topics"
_TAGS_CACHE_KEY = "zettel:tags"
_GRAPH_EXT_CACHE_KEY = "zettel:graph:extended"
_CACHE_TTL_SECONDS = 300  # 5 minutes
_GRAPH_EXT_CACHE_TTL = 3600  # 1 hour
from alfred.schemas.zettel import (
    AIZettelGenerateRequest,
    BacklinkResponse,
    BulkUpdateResult,
    CardSearchResponse,
    CompleteReviewRequest,
    LinkSuggestion,
    PaginatedZettelResponse,
    SyncWikiLinksRequest,
    ZettelCardCreate,
    ZettelCardOut,
    ZettelCardPatch,
    ZettelCardUpdate,
    ZettelLinkCreate,
    ZettelLinkOut,
    ZettelReviewOut,
)
from alfred.services.zettel_creation_stream import ZettelCreationStream
from alfred.services.zettelkasten_service import ZettelkastenService

router = APIRouter(prefix="/api/zettels", tags=["zettels"])


def _card_out(card) -> ZettelCardOut:
    return ZettelCardOut.model_validate(card)


def _link_out(link) -> ZettelLinkOut:
    return ZettelLinkOut.model_validate(link)


def _review_out(review) -> ZettelReviewOut:
    return ZettelReviewOut.model_validate(review)


@router.post("/cards", response_model=ZettelCardOut, status_code=status.HTTP_201_CREATED)
def create_card(
    payload: ZettelCardCreate,
    session: Session = Depends(get_db_session),
) -> ZettelCardOut:
    svc = ZettelkastenService(session)
    card = svc.create_card(**payload.model_dump())
    _invalidate_topic_tag_cache()
    _invalidate_graph_cache()
    return _card_out(card)


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/cards/create-stream")
async def create_card_stream(payload: ZettelCardCreate) -> StreamingResponse:
    """Create a zettel with streaming enrichment via SSE."""
    stream = ZettelCreationStream(payload)
    return StreamingResponse(
        stream.run(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/cards/stub", status_code=status.HTTP_201_CREATED)
def create_stub_card(
    title: str = Body(..., embed=True),
    session: Session = Depends(get_db_session),
):
    """Create a stub card for an unresolved wiki-link target."""
    svc = ZettelkastenService(session)
    card = svc.create_stub_card(title)
    _invalidate_graph_cache()
    return {"id": card.id, "title": card.title, "status": card.status}


@router.get("/cards", response_model=PaginatedZettelResponse)
def list_cards(
    q: str | None = None,
    topic: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = Query(None),
    document_id: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    importance_min: int | None = None,
    card_status: str | None = Query(None, alias="status"),
    limit: int = 50,
    skip: int = 0,
    session: Session = Depends(get_db_session),
) -> PaginatedZettelResponse:
    all_tags = list(tags or [])
    if tag and tag not in all_tags:
        all_tags.append(tag)
    svc = ZettelkastenService(session)
    cards = svc.list_cards(
        q=q,
        topic=topic,
        tags=all_tags or None,
        document_id=document_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
        importance_min=importance_min,
        status=card_status,
        limit=limit,
        skip=skip,
    )
    total_count = svc.count_cards(
        q=q,
        topic=topic,
        tags=all_tags or None,
        document_id=document_id,
        importance_min=importance_min,
        status=card_status,
    )
    return PaginatedZettelResponse(
        items=[_card_out(c) for c in cards],
        total_count=total_count,
        limit=limit,
        skip=skip,
    )


@router.get("/cards/count")
def count_cards(
    q: str | None = None,
    topic: str | None = None,
    tags: list[str] | None = Query(None),
    importance_min: int | None = None,
    card_status: str | None = Query(None, alias="status"),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = ZettelkastenService(session)
    total = svc.count_cards(
        q=q,
        topic=topic,
        tags=tags or None,
        importance_min=importance_min,
        status=card_status,
    )
    return {"total": total}


def _cache_get(key: str) -> list[str] | None:
    """Try to read a cached JSON list from Redis; return None on miss."""
    redis = get_redis_client()
    if not redis:
        return None
    try:
        raw = redis.get(key)
        return _json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value: list[str]) -> None:
    """Best-effort write to Redis cache."""
    redis = get_redis_client()
    if not redis:
        return
    try:
        redis.set(key, _json.dumps(value), ex=_CACHE_TTL_SECONDS)
    except Exception:
        pass


def _invalidate_topic_tag_cache() -> None:
    """Bust topics/tags cache on card mutations."""
    redis = get_redis_client()
    if not redis:
        return
    try:
        redis.delete(_TOPICS_CACHE_KEY, _TAGS_CACHE_KEY)
    except Exception:
        pass


def _cache_delete_prefix(prefix: str) -> None:
    """Best-effort delete all Redis keys matching a prefix."""
    redis = get_redis_client()
    if not redis:
        return
    try:
        for key in redis.scan_iter(f"{prefix}*"):
            redis.delete(key)
    except Exception:
        pass


def _invalidate_graph_cache() -> None:
    """Bust extended graph cache + clustering cache on card mutations."""
    from alfred.services.clustering_service import ClusteringService

    _cache_delete_prefix(_GRAPH_EXT_CACHE_KEY)
    ClusteringService.invalidate_cache()


@router.get("/topics", response_model=list[str])
def get_topics(session: Session = Depends(get_db_session)) -> list[str]:
    cached = _cache_get(_TOPICS_CACHE_KEY)
    if cached is not None:
        return cached
    results = session.exec(
        select(ZettelCard.topic)
        .where(ZettelCard.topic.isnot(None))  # type: ignore[union-attr]
        .where(ZettelCard.status == "active")
        .distinct()
        .order_by(ZettelCard.topic)
    ).all()
    topics = [t for t in results if t]
    _cache_set(_TOPICS_CACHE_KEY, topics)
    return topics


@router.get("/tags", response_model=list[str])
def get_tags(session: Session = Depends(get_db_session)) -> list[str]:
    cached = _cache_get(_TAGS_CACHE_KEY)
    if cached is not None:
        return cached
    cards = session.exec(
        select(ZettelCard.tags)
        .where(ZettelCard.tags.isnot(None))  # type: ignore[union-attr]
        .where(ZettelCard.status == "active")
    ).all()
    all_tags: set[str] = set()
    for tags_list in cards:
        if isinstance(tags_list, list):
            all_tags.update(t for t in tags_list if t)
    result = sorted(all_tags)
    _cache_set(_TAGS_CACHE_KEY, result)
    return result


@router.post("/cards/bulk", response_model=list[ZettelCardOut], status_code=status.HTTP_201_CREATED)
def bulk_create_cards(
    payload: list[ZettelCardCreate],
    session: Session = Depends(get_db_session),
) -> list[ZettelCardOut]:
    """Create multiple cards in one call (batch insert, max 50)."""
    _MAX_BATCH = 50
    if len(payload) > _MAX_BATCH:
        raise HTTPException(status_code=400, detail="Maximum 50 cards per batch")
    if len(payload) == 0:
        raise HTTPException(status_code=400, detail="At least one card required")
    svc = ZettelkastenService(session)
    cards_data = [p.model_dump() for p in payload]
    cards = svc.create_cards_batch(cards_data)
    _invalidate_topic_tag_cache()
    return [_card_out(c) for c in cards]


@router.patch("/cards/bulk", response_model=BulkUpdateResult)
def bulk_update_cards(
    payload: list[ZettelCardPatch],
    session: Session = Depends(get_db_session),
) -> BulkUpdateResult:
    svc = ZettelkastenService(session)
    updated: list[int] = []
    missing: list[int] = []

    # Batch-fetch all cards in one query
    requested_ids = [patch.id for patch in payload]
    rows = session.exec(select(ZettelCard).where(ZettelCard.id.in_(requested_ids))).all()
    cards_by_id = {card.id: card for card in rows}

    for patch in payload:
        card = cards_by_id.get(patch.id)
        if not card:
            missing.append(patch.id)
            continue
        data = patch.model_dump(exclude_unset=True)
        data.pop("id", None)
        svc.update_card(card, **data)
        updated.append(card.id)  # type: ignore[arg-type]

    return BulkUpdateResult(updated_ids=updated, missing_ids=missing)


@router.get("/cards/search", response_model=CardSearchResponse)
def search_cards(
    q: str | None = None,
    context_card_id: int | None = None,
    text_limit: int = 10,
    ai_limit: int = 5,
    session: Session = Depends(get_db_session),
) -> CardSearchResponse:
    """Unified search for wiki-link autocomplete.

    Returns text matches (instant ILIKE) and optional AI suggestions
    (from suggest_links engine, requires context_card_id).
    """
    svc = ZettelkastenService(session)
    result = svc.search_cards_unified(
        q,
        context_card_id=context_card_id,
        text_limit=min(text_limit, 20),
        ai_limit=min(ai_limit, 10),
    )
    return CardSearchResponse.model_validate(result)


@router.get("/cards/{card_id}", response_model=ZettelCardOut)
def get_card(card_id: int, session: Session = Depends(get_db_session)) -> ZettelCardOut:
    svc = ZettelkastenService(session)
    card = svc.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return _card_out(card)


@router.patch("/cards/{card_id}", response_model=ZettelCardOut)
def update_card(
    card_id: int,
    payload: ZettelCardUpdate,
    session: Session = Depends(get_db_session),
) -> ZettelCardOut:
    svc = ZettelkastenService(session)
    card = svc.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    data = payload.model_dump(exclude_unset=True)
    updated = svc.update_card(card, **data)
    _invalidate_topic_tag_cache()
    _invalidate_graph_cache()
    return _card_out(updated)


@router.delete("/cards/{card_id}", status_code=status.HTTP_200_OK)
def delete_card(
    card_id: int,
    session: Session = Depends(get_db_session),
) -> dict:
    svc = ZettelkastenService(session)
    card = svc.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    svc.archive_card(card, remove_links=True)
    _invalidate_topic_tag_cache()
    _invalidate_graph_cache()
    return {"status": "archived", "id": card_id}


@router.post("/cards/generate", response_model=ZettelCardOut, status_code=status.HTTP_201_CREATED)
def generate_card(
    payload: AIZettelGenerateRequest,
    session: Session = Depends(get_db_session),
) -> ZettelCardOut:
    if not payload.prompt and not payload.content:
        raise HTTPException(status_code=400, detail="Either prompt or content is required")
    svc = ZettelkastenService(session)
    try:
        card = svc.generate_card_from_ai(
            prompt=payload.prompt,
            content=payload.content,
            topic=payload.topic,
            tags=payload.tags,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI generation failed: {exc}") from exc
    return _card_out(card)


@router.post(
    "/cards/{card_id}/links",
    response_model=list[ZettelLinkOut],
    status_code=status.HTTP_201_CREATED,
)
def link_card(
    card_id: int,
    payload: ZettelLinkCreate,
    session: Session = Depends(get_db_session),
) -> list[ZettelLinkOut]:
    svc = ZettelkastenService(session)
    if not svc.get_card(card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    if not svc.get_card(payload.to_card_id):
        raise HTTPException(status_code=404, detail="Target card not found")
    links = svc.create_link(
        from_card_id=card_id,
        to_card_id=payload.to_card_id,
        type=payload.type,
        context=payload.context,
        bidirectional=payload.bidirectional,
    )
    return [_link_out(link) for link in links]


@router.get("/cards/{card_id}/links", response_model=list[ZettelLinkOut])
def list_links(card_id: int, session: Session = Depends(get_db_session)) -> list[ZettelLinkOut]:
    svc = ZettelkastenService(session)
    if not svc.get_card(card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    links = svc.list_links(card_id=card_id)
    return [_link_out(link) for link in links]


@router.delete("/links/{link_id}", status_code=status.HTTP_200_OK)
def delete_link(
    link_id: int,
    session: Session = Depends(get_db_session),
) -> dict:
    svc = ZettelkastenService(session)
    deleted = svc.delete_link(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"status": "deleted", "id": link_id}


@router.post(
    "/cards/{card_id}/suggest-links",
    response_model=list[LinkSuggestion],
    status_code=status.HTTP_200_OK,
)
def suggest_links(
    card_id: int,
    min_confidence: float = 0.6,
    limit: float | int = 10,
    session: Session = Depends(get_db_session),
) -> list[LinkSuggestion]:
    if not (0.0 <= min_confidence <= 1.0):
        raise HTTPException(status_code=400, detail="min_confidence must be between 0 and 1")
    try:
        limit_int = int(float(limit))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="limit must be a number") from None
    limit_int = max(1, min(50, limit_int))
    svc = ZettelkastenService(session)
    try:
        suggestions = svc.suggest_links(
            card_id=card_id, min_confidence=min_confidence, limit=limit_int
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        _log.warning(
            "Link suggestions unavailable for card %s; returning empty result set",
            card_id,
            exc_info=True,
        )
        return []
    return suggestions


@router.post("/batch-link", status_code=status.HTTP_202_ACCEPTED)
def batch_link(
    limit: int = 50,
    max_existing_links: int = 3,
    auto_link: bool = True,
) -> dict:
    """Queue batch link generation for cards with few connections."""
    from alfred.tasks.batch_linking import batch_link_task

    result = batch_link_task.delay(
        limit=limit,
        max_existing_links=max_existing_links,
        auto_link=auto_link,
    )
    return {"task_id": result.id}


@router.post("/cards/{card_id}/generate-links", status_code=status.HTTP_202_ACCEPTED)
def generate_links_for_card(card_id: int) -> dict:
    """Queue link generation for a single card via Celery."""
    from alfred.tasks.batch_linking import link_card_task

    result = link_card_task.delay(card_id=card_id, auto_link=True)
    return {"task_id": result.id, "card_id": card_id}


@router.get("/cards/{card_id}/backlinks", response_model=BacklinkResponse)
def get_backlinks(
    card_id: int,
    session: Session = Depends(get_db_session),
) -> BacklinkResponse:
    """Get all wiki-links and graph links pointing to this card."""
    svc = ZettelkastenService(session)
    card = svc.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    backlinks = svc.list_backlinks(card_id)

    # AI connections: similar cards not yet linked
    ai_connections: list[dict] = []
    try:
        suggestions = svc.suggest_links(card_id=card_id, min_confidence=0.6, limit=5)
        for s in suggestions:
            ai_connections.append(
                {
                    "id": s.to_card_id,
                    "title": s.to_title,
                    "topic": s.to_topic,
                    "tags": s.to_tags or [],
                    "score": round(s.scores.composite_score, 2),
                    "reason": s.reason,
                }
            )
    except Exception:
        pass  # Degraded mode: AI connections unavailable

    return BacklinkResponse.model_validate(
        {"backlinks": backlinks, "ai_connections": ai_connections}
    )


@router.post("/wiki-links/sync", status_code=status.HTTP_200_OK)
def sync_wiki_links(
    payload: SyncWikiLinksRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    """Sync wiki-links for a source note or zettel.

    Called on save to keep wiki_links table in sync with editor content.
    """
    if payload.source_type not in ("note", "zettel"):
        raise HTTPException(status_code=400, detail="source_type must be 'note' or 'zettel'")
    svc = ZettelkastenService(session)
    svc.sync_wiki_links(
        source_type=payload.source_type,
        source_id=payload.source_id,
        target_card_ids=payload.target_card_ids,
    )
    return {"status": "synced", "count": len(payload.target_card_ids)}


@router.get("/graph")
def graph(
    include: str | None = None,
    session: Session = Depends(get_db_session),
):
    svc = ZettelkastenService(session)
    if include:
        includes = set(include.split(","))
        cache_key = f"{_GRAPH_EXT_CACHE_KEY}:{','.join(sorted(includes))}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        result = svc.extended_graph_summary(
            include_clusters="clusters" in includes,
            include_gaps="gaps" in includes,
        )
        # Cache the extended graph result with a longer TTL
        redis = get_redis_client()
        if redis:
            try:
                redis.set(cache_key, _json.dumps(result), ex=_GRAPH_EXT_CACHE_TTL)
            except Exception:
                pass
        return result
    return svc.graph_summary()


@router.get("/reviews/due", response_model=list[ZettelReviewOut])
def list_due_reviews(
    limit: int = 50,
    session: Session = Depends(get_db_session),
) -> list[ZettelReviewOut]:
    svc = ZettelkastenService(session)
    reviews = svc.list_due_reviews(limit=limit)
    return [_review_out(r) for r in reviews]


@router.post("/reviews/{review_id}/complete", response_model=ZettelReviewOut)
def complete_review(
    review_id: int,
    payload: CompleteReviewRequest,
    session: Session = Depends(get_db_session),
) -> ZettelReviewOut:
    svc = ZettelkastenService(session)
    review = session.get(ZettelReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    updated = svc.complete_review(review=review, score=payload.score)
    return _review_out(updated)
