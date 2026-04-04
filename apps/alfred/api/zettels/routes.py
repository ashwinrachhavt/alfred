from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.models.zettel import ZettelCard, ZettelReview
from alfred.schemas.zettel import (
    AIZettelGenerateRequest,
    BulkUpdateResult,
    CompleteReviewRequest,
    GraphSummary,
    LinkSuggestion,
    ZettelCardCreate,
    ZettelCardOut,
    ZettelCardPatch,
    ZettelCardUpdate,
    ZettelLinkCreate,
    ZettelLinkOut,
    ZettelReviewOut,
)
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
    return _card_out(card)


@router.get("/cards", response_model=list[ZettelCardOut])
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
) -> list[ZettelCardOut]:
    all_tags = list(tags or [])
    if tag and tag not in all_tags:
        all_tags.append(tag)
    svc = ZettelkastenService(session)
    cards = svc.list_cards(
        q=q, topic=topic, tags=all_tags or None,
        document_id=document_id, sort_by=sort_by, sort_dir=sort_dir,
        importance_min=importance_min, status=card_status,
        limit=limit, skip=skip,
    )
    return [_card_out(c) for c in cards]


@router.get("/topics", response_model=list[str])
def get_topics(session: Session = Depends(get_db_session)) -> list[str]:
    results = session.exec(
        select(ZettelCard.topic)
        .where(ZettelCard.topic.isnot(None))  # type: ignore[union-attr]
        .where(ZettelCard.status == "active")
        .distinct()
        .order_by(ZettelCard.topic)
    ).all()
    return [t for t in results if t]


@router.get("/tags", response_model=list[str])
def get_tags(session: Session = Depends(get_db_session)) -> list[str]:
    cards = session.exec(
        select(ZettelCard.tags)
        .where(ZettelCard.tags.isnot(None))  # type: ignore[union-attr]
        .where(ZettelCard.status == "active")
    ).all()
    all_tags: set[str] = set()
    for tags_list in cards:
        if isinstance(tags_list, list):
            all_tags.update(t for t in tags_list if t)
    return sorted(all_tags)


@router.post("/cards/bulk", response_model=list[ZettelCardOut], status_code=status.HTTP_201_CREATED)
def bulk_create_cards(
    payload: list[ZettelCardCreate],
    session: Session = Depends(get_db_session),
) -> list[ZettelCardOut]:
    """Create multiple cards in one call (batch insert, max 50)."""
    if len(payload) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 cards per batch")
    if len(payload) == 0:
        raise HTTPException(status_code=400, detail="At least one card required")
    svc = ZettelkastenService(session)
    cards_data = [p.model_dump() for p in payload]
    cards = svc.create_cards_batch(cards_data)
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
    rows = session.exec(
        select(ZettelCard).where(ZettelCard.id.in_(requested_ids))
    ).all()
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
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Failed to generate link suggestions") from exc
    return suggestions


@router.get("/graph", response_model=GraphSummary)
def graph(session: Session = Depends(get_db_session)) -> GraphSummary:
    svc = ZettelkastenService(session)
    return GraphSummary.model_validate(svc.graph_summary())


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
