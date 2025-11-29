"""Persistence helpers for research runs."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from alfred.core.database import SessionLocal

logger = logging.getLogger(__name__)


def persist_research_run(
    *,
    query: str,
    target_length_words: int,
    tone: str,
    article: str,
    state: dict[str, Any],
) -> None:
    """Persist a completed research run to the database."""

    session = SessionLocal()
    try:
        clean_state = json.loads(json.dumps(state, default=str))
        from alfred.models.research import ResearchRun  # type: ignore
        record = ResearchRun(
            query=query,
            target_length_words=target_length_words,
            tone=tone,
            article=article,
            state=clean_state,
        )
        session.add(record)
        session.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - DB failure logging only
        session.rollback()
        logger.exception("Failed to persist research run: %s", exc)
    finally:
        session.close()
