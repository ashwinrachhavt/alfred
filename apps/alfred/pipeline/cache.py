"""PostgreSQL-backed stage result cache for LLM-calling pipeline nodes."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlmodel import Field, Session, SQLModel, select

logger = logging.getLogger(__name__)


class PipelineStageCacheRow(SQLModel, table=True):
    __tablename__ = "pipeline_stage_cache"
    __table_args__ = (
        sa.UniqueConstraint("stage", "content_hash", name="uq_stage_content_hash"),
    )

    id: int | None = Field(default=None, primary_key=True)
    stage: str = Field(index=True)
    content_hash: str = Field(index=True)
    result_json: str  # JSON-serialized result
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PipelineStageCache:
    """Simple cache: (stage, content_hash) -> result dict."""

    def __init__(self, *, session: Session) -> None:
        self._session = session

    def get(self, stage: str, content_hash: str) -> dict[str, Any] | None:
        stmt = select(PipelineStageCacheRow).where(
            PipelineStageCacheRow.stage == stage,
            PipelineStageCacheRow.content_hash == content_hash,
        )
        row = self._session.exec(stmt).first()
        if row is None:
            return None
        return json.loads(row.result_json)

    def set(self, stage: str, content_hash: str, result: dict[str, Any]) -> None:
        stmt = select(PipelineStageCacheRow).where(
            PipelineStageCacheRow.stage == stage,
            PipelineStageCacheRow.content_hash == content_hash,
        )
        row = self._session.exec(stmt).first()
        serialized = json.dumps(result, default=str)
        if row is not None:
            row.result_json = serialized
            row.created_at = datetime.now(UTC)
        else:
            row = PipelineStageCacheRow(
                stage=stage,
                content_hash=content_hash,
                result_json=serialized,
            )
            self._session.add(row)
        self._session.commit()
