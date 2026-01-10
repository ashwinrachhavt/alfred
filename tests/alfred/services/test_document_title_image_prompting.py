from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alfred.models.doc_storage import DocumentRow
from alfred.services.doc_storage_pg import DocStorageService
from sqlalchemy import create_engine, select
from sqlmodel import Session, SQLModel


class _StubLLM:
    def __init__(self) -> None:
        self.last_visual_brief_args: dict[str, object] | None = None
        self.last_image_prompt: str | None = None

    def build_cover_visual_brief(  # type: ignore[no-untyped-def]
        self, *, title, primary_topic, domain, excerpt, summary, model=None
    ):
        self.last_visual_brief_args = {
            "title": title,
            "primary_topic": primary_topic,
            "domain": domain,
            "excerpt": excerpt,
            "summary": summary,
            "model": model,
        }
        return "A calm, minimalist scene with symbolic objects representing the key idea."

    def generate_image_png(  # type: ignore[no-untyped-def]
        self, *, prompt, model, size, quality
    ):
        self.last_image_prompt = prompt
        return b"\x89PNG\r\n\x1a\nstub", None


def test_generate_document_title_image_uses_content_excerpt_and_visual_brief() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    long_text = " ".join(["alpha"] * 2000)  # long enough to force truncation
    doc = DocumentRow(
        id=uuid.uuid4(),
        source_url="https://example.com",
        canonical_url="https://example.com",
        domain="example.com",
        title="Example",
        content_type="web",
        cleaned_text=long_text,
        tokens=2,
        hash=str(uuid.uuid4()),
        day_bucket=now.date(),
        captured_at=now,
        captured_hour=now.astimezone(timezone.utc).hour,
        processed_at=now,
        created_at=now,
        updated_at=now,
        meta={},
        topics={"primary": "testing"},
        summary={"short": "Short summary", "long": None},
        image=None,
    )

    stub = _StubLLM()

    with Session(engine) as session:
        session.add(doc)
        session.commit()

        svc = DocStorageService(session=session, llm_service=stub)
        svc.generate_document_title_image(str(doc.id), force=True, model="dall-e-2")

        assert stub.last_visual_brief_args is not None
        excerpt = str(stub.last_visual_brief_args["excerpt"])
        assert len(excerpt) <= 900
        assert "alpha" in excerpt

        assert stub.last_image_prompt is not None
        assert "Excerpt (for visual grounding):" in stub.last_image_prompt
        assert "Visual brief:" in stub.last_image_prompt

        row = session.exec(select(DocumentRow.meta).where(DocumentRow.id == doc.id)).one()
        meta = row[0] if hasattr(row, "__len__") else row
        generated = (meta or {}).get("generated_cover_image") or {}
        assert generated.get("prompt_strategy") == "content_excerpt"
        assert generated.get("content_hash")
