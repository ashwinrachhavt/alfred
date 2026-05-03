from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, func, or_
from sqlmodel import Session, select

from alfred.models.doc_storage import DocumentRow
from alfred.models.zettel import ZettelCard
from alfred.schemas.chat import ChatOmniboxResult


def _clean_query(query: str | None) -> str:
    return " ".join((query or "").strip().split())


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _contains(value: Any, query: str) -> bool:
    return query.lower() in _as_text(value).lower()


def _excerpt(value: Any, query: str, limit: int = 180) -> str | None:
    text = " ".join(_as_text(value).split())
    if not text:
        return None
    if not query:
        return text[:limit]

    lower_text = text.lower()
    lower_query = query.lower()
    index = lower_text.find(lower_query)
    if index < 0:
        return text[:limit]

    start = max(index - 45, 0)
    end = min(start + limit, len(text))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _topic_from_document(topics: dict[str, Any] | None) -> str | None:
    if not topics:
        return None
    for key in ("primary", "topic", "name", "label", "title"):
        value = topics.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in topics.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
                if isinstance(item, dict):
                    topic = _topic_from_document(item)
                    if topic:
                        return topic
        if isinstance(value, dict):
            topic = _topic_from_document(value)
            if topic:
                return topic
    return None


def _score_title(title: str | None, query: str, exact: float, prefix: float, substring: float) -> float:
    title_value = (title or "").strip().lower()
    query_value = query.lower()
    if title_value == query_value:
        return exact
    if title_value.startswith(query_value):
        return prefix
    if query_value in title_value:
        return substring
    return 0.0


def _score_zettel(card: ZettelCard, query: str) -> float:
    score = _score_title(card.title, query, exact=100.0, prefix=90.0, substring=80.0)
    if score:
        return score
    if _contains(card.topic, query) or _contains(card.tags, query):
        return 70.0
    if _contains(card.summary, query):
        return 60.0
    if _contains(card.content, query):
        return 50.0
    return 0.0


def _score_document(doc: DocumentRow, query: str) -> float:
    score = _score_title(doc.title, query, exact=95.0, prefix=85.0, substring=75.0)
    if score:
        return score
    if _contains(doc.topics, query) or _contains(doc.tags, query):
        return 70.0
    if _contains(doc.summary, query):
        return 60.0
    if _contains(doc.cleaned_text, query):
        return 50.0
    return 0.0


def _recency_score(value: Any) -> float:
    if value is None:
        return 0.0
    timestamp = getattr(value, "timestamp", None)
    if not callable(timestamp):
        return 0.0
    return float(timestamp()) / 1_000_000_000_000


def _lower_like(column: Any, query: str) -> Any:
    return func.lower(cast(column, String)).contains(query.lower())


@dataclass
class ChatOmniboxService:
    session: Session

    def search(self, query: str | None, limit: int = 8) -> list[ChatOmniboxResult]:
        clean_query = _clean_query(query)
        source_limit = max(limit - 2, 0)
        source_results = self._search_sources(clean_query, source_limit)
        action_results = self._actions(clean_query)
        return [*source_results, *action_results][:limit]

    def _search_sources(self, query: str, limit: int) -> list[ChatOmniboxResult]:
        if limit <= 0:
            return []

        zettels = self._query_zettels(query)
        documents = self._query_documents(query)
        results: list[ChatOmniboxResult] = []

        for card in zettels:
            score = _score_zettel(card, query) if query else 1.0 + _recency_score(card.updated_at)
            if query and score <= 0:
                continue
            results.append(
                ChatOmniboxResult(
                    kind="zettel",
                    id=card.id or "",
                    title=card.title,
                    topic=card.topic,
                    tags=list(card.tags or []),
                    source_url=card.source_url,
                    excerpt=_excerpt(card.summary or card.content, query),
                    score=score,
                    query=query,
                )
            )

        for doc in documents:
            score = (
                _score_document(doc, query)
                if query
                else 1.0 + _recency_score(doc.captured_at or doc.updated_at)
            )
            if query and score <= 0:
                continue
            results.append(
                ChatOmniboxResult(
                    kind="document",
                    id=str(doc.id),
                    title=doc.title or doc.source_url,
                    topic=_topic_from_document(doc.topics),
                    tags=list(doc.tags or []),
                    source_url=doc.source_url,
                    excerpt=_excerpt(doc.summary or doc.cleaned_text, query),
                    score=score,
                    query=query,
                )
            )

        return sorted(results, key=self._sort_key)[:limit]

    def _query_zettels(self, query: str) -> list[ZettelCard]:
        statement = select(ZettelCard).where(ZettelCard.status != "archived")
        if query:
            statement = statement.where(
                or_(
                    _lower_like(ZettelCard.title, query),
                    _lower_like(ZettelCard.topic, query),
                    _lower_like(ZettelCard.summary, query),
                    _lower_like(ZettelCard.content, query),
                    _lower_like(ZettelCard.tags, query),
                )
            )
        return list(
            self.session.exec(
                statement.order_by(ZettelCard.updated_at.desc().nullslast(), ZettelCard.id.desc())
            )
        )

    def _query_documents(self, query: str) -> list[DocumentRow]:
        statement = select(DocumentRow)
        if query:
            statement = statement.where(
                or_(
                    _lower_like(DocumentRow.title, query),
                    _lower_like(DocumentRow.cleaned_text, query),
                    _lower_like(DocumentRow.summary, query),
                    _lower_like(DocumentRow.topics, query),
                )
            )
        return list(
            self.session.exec(
                statement.order_by(
                    DocumentRow.captured_at.desc().nullslast(),
                    DocumentRow.updated_at.desc().nullslast(),
                    DocumentRow.id.desc(),
                )
            )
        )

    def _actions(self, query: str) -> list[ChatOmniboxResult]:
        search_score = 5.0 if query else 0.3
        create_score = 4.0 if query else 0.2
        return [
            ChatOmniboxResult(
                kind="action",
                id="search_all",
                title="Search all",
                score=search_score,
                action="search_all",
                description="Search across Alfred",
                query=query,
            ),
            ChatOmniboxResult(
                kind="action",
                id="create_card",
                title="Create card",
                score=create_score,
                action="create_card",
                description="Create a new knowledge card",
                query=query,
            ),
        ]

    @staticmethod
    def _sort_key(result: ChatOmniboxResult) -> tuple[float, str, int | str]:
        return (-result.score, result.kind, result.id)
