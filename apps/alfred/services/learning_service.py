from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlmodel import Session, select

from alfred.core.settings import settings
from alfred.core.utils import STAGE_TO_DELTA, clamp_int
from alfred.core.utils import utcnow_naive as _utcnow
from alfred.models.learning import (
    LearningEntity,
    LearningEntityRelation,
    LearningQuiz,
    LearningQuizAttempt,
    LearningResource,
    LearningResourceEntity,
    LearningReview,
    LearningTopic,
)
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.extraction_service import ExtractionService
from alfred.services.graph_service import GraphService
from alfred.services.llm_service import LLMService


@dataclass
class LearningService:
    session: Session

    def _maybe_graph(self) -> GraphService | None:
        if settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password:
            return GraphService(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
            )
        return None

    # -----------------
    # Topics
    # -----------------
    def create_topic(
        self,
        *,
        name: str,
        description: str | None = None,
        tags: list[str] | None = None,
        interview_at: datetime | None = None,
    ) -> LearningTopic:
        topic = LearningTopic(
            name=name.strip(),
            description=(description.strip() if description else None),
            tags=tags,
            interview_at=interview_at,
            status="active",
            progress=0,
        )
        self.session.add(topic)
        self.session.commit()
        self.session.refresh(topic)

        gs = self._maybe_graph()
        if gs is not None:
            try:
                gs.upsert_topic_node(topic_id=str(topic.id), name=topic.name)
            finally:
                gs.close()
        return topic

    def list_topics(self) -> list[LearningTopic]:
        return list(
            self.session.exec(select(LearningTopic).order_by(LearningTopic.updated_at.desc()))
        )

    def get_topic(self, topic_id: int) -> LearningTopic | None:
        return self.session.get(LearningTopic, topic_id)

    def update_topic(self, topic: LearningTopic, **fields) -> LearningTopic:
        if "name" in fields and fields["name"] is not None:
            topic.name = str(fields["name"]).strip()
        if "description" in fields:
            topic.description = fields["description"]
        if "tags" in fields:
            topic.tags = fields["tags"]
        if "status" in fields and fields["status"] is not None:
            topic.status = str(fields["status"])
        if "progress" in fields and fields["progress"] is not None:
            topic.progress = clamp_int(int(fields["progress"]), lo=0, hi=100)
        if "interview_at" in fields:
            topic.interview_at = fields["interview_at"]
        topic.updated_at = _utcnow()
        self.session.add(topic)
        self.session.commit()
        self.session.refresh(topic)
        return topic

    def delete_topic(self, topic: LearningTopic) -> None:
        self.session.delete(topic)
        self.session.commit()

    # -----------------
    # Resources
    # -----------------
    def add_resource(
        self,
        *,
        topic: LearningTopic,
        title: str | None = None,
        source_url: str | None = None,
        document_id: str | None = None,
        notes: str | None = None,
    ) -> LearningResource:
        res = LearningResource(
            topic_id=topic.id or 0,
            title=(title.strip() if title else None),
            source_url=(source_url.strip() if source_url else None),
            document_id=(document_id.strip() if document_id else None),
            notes=notes,
            added_at=_utcnow(),
        )
        self.session.add(res)

        now = _utcnow()
        if topic.first_learned_at is None:
            topic.first_learned_at = now
        topic.last_studied_at = now
        topic.updated_at = now
        self.session.add(topic)

        self.session.commit()
        self.session.refresh(res)

        gs = self._maybe_graph()
        if gs is not None:
            try:
                gs.upsert_topic_node(topic_id=str(topic.id), name=topic.name)
                if res.document_id:
                    gs.upsert_document_node(
                        doc_id=str(res.document_id),
                        title=res.title,
                        source_url=res.source_url,
                    )
                    gs.link_topic_to_document(topic_id=str(topic.id), doc_id=str(res.document_id))
            finally:
                gs.close()

        # Ensure a first review exists (1-day after first learning)
        self._ensure_open_review(topic_id=topic.id or 0)
        return res

    def list_resources(self, *, topic_id: int) -> list[LearningResource]:
        stmt = (
            select(LearningResource)
            .where(LearningResource.topic_id == topic_id)
            .order_by(LearningResource.added_at.desc())
        )
        return list(self.session.exec(stmt))

    def get_resource(self, resource_id: int) -> LearningResource | None:
        return self.session.get(LearningResource, resource_id)

    # -----------------
    # Reviews (spaced repetition)
    # -----------------
    def list_due_reviews(
        self, *, now: datetime | None = None, limit: int = 50
    ) -> list[LearningReview]:
        now = now or _utcnow()
        stmt = (
            select(LearningReview)
            .where(LearningReview.completed_at.is_(None))
            .where(LearningReview.due_at <= now)
            .order_by(LearningReview.due_at.asc())
            .limit(int(limit))
        )
        return list(self.session.exec(stmt))

    def _ensure_open_review(self, *, topic_id: int) -> LearningReview:
        stmt = (
            select(LearningReview)
            .where(LearningReview.topic_id == topic_id)
            .where(LearningReview.completed_at.is_(None))
            .order_by(LearningReview.due_at.asc())
        )
        existing = self.session.exec(stmt).first()
        if existing:
            return existing

        # Start at stage 1, due in 1 day
        due_at = _utcnow() + STAGE_TO_DELTA[1]
        review = LearningReview(topic_id=topic_id, stage=1, iteration=1, due_at=due_at)
        self.session.add(review)
        self.session.commit()
        self.session.refresh(review)
        return review

    def complete_review(
        self,
        *,
        review: LearningReview,
        score: float | None,
        attempt_id: int | None = None,
        pass_threshold: float = 0.8,
    ) -> LearningReview:
        now = _utcnow()
        review.completed_at = now
        review.score = score
        review.attempt_id = attempt_id
        review.updated_at = now
        self.session.add(review)

        # Schedule next review
        effective_score = score if score is not None else 0.0
        if effective_score >= pass_threshold:
            next_stage = min(3, int(review.stage) + 1)
            next_iteration = int(review.iteration)
            if int(review.stage) >= 3:
                next_stage = 3
                next_iteration = int(review.iteration) + 1
            due_at = now + STAGE_TO_DELTA[next_stage]
        else:
            next_stage = int(review.stage)
            next_iteration = int(review.iteration)
            due_at = now + STAGE_TO_DELTA[1]

        self.session.add(
            LearningReview(
                topic_id=review.topic_id,
                stage=next_stage,
                iteration=next_iteration,
                due_at=due_at,
            )
        )
        self.session.commit()
        self.session.refresh(review)
        return review

    # -----------------
    # Quizzes
    # -----------------
    def generate_quiz(
        self,
        *,
        topic: LearningTopic,
        question_count: int = 8,
        resource_id: int | None = None,
        source_text: str | None = None,
    ) -> LearningQuiz:
        question_count = clamp_int(question_count, lo=1, hi=25)

        text = (source_text or "").strip()
        chosen_resource: LearningResource | None = None
        if not text:
            if resource_id is not None:
                chosen_resource = self.get_resource(resource_id)
                if not chosen_resource or chosen_resource.topic_id != (topic.id or -1):
                    raise ValueError("Resource not found for topic")
                text = self._load_resource_text(chosen_resource)
            else:
                resources = self.list_resources(topic_id=topic.id or 0)
                # Prefer documents with document_id; otherwise fall back to titles/notes.
                chunks: list[str] = []
                for res in resources:
                    try:
                        chunk = self._load_resource_text(res)
                    except Exception:
                        chunk = ""
                    if chunk.strip():
                        chunks.append(chunk)
                    if sum(len(c) for c in chunks) >= 8000:
                        break
                text = "\n\n".join(chunks).strip()

        if not text:
            raise ValueError("No source text available to generate quiz")

        items = self._generate_quiz_items(topic_name=topic.name, text=text, n=question_count)
        quiz = LearningQuiz(
            topic_id=topic.id or 0,
            resource_id=(chosen_resource.id if chosen_resource else resource_id),
            items=[i for i in items],
        )
        self.session.add(quiz)

        topic.last_studied_at = _utcnow()
        topic.updated_at = _utcnow()
        self.session.add(topic)

        self.session.commit()
        self.session.refresh(quiz)
        return quiz

    def submit_quiz(
        self, *, quiz: LearningQuiz, known: list[bool], responses: list[dict] | None
    ) -> LearningQuizAttempt:
        if not known:
            raise ValueError("known cannot be empty")
        expected = len(quiz.items or [])
        if expected and len(known) != expected:
            raise ValueError(f"known length must match quiz items ({expected})")
        score = float(sum(1 for k in known if k) / max(1, len(known)))
        attempt = LearningQuizAttempt(
            quiz_id=quiz.id or 0, known=known, responses=responses, score=score
        )
        self.session.add(attempt)
        now = _utcnow()
        topic = self.session.get(LearningTopic, quiz.topic_id)
        if topic:
            topic.last_studied_at = now
            topic.updated_at = now
            self.session.add(topic)
        self.session.commit()
        self.session.refresh(attempt)
        return attempt

    def _generate_quiz_items(self, *, topic_name: str, text: str, n: int) -> list[dict]:
        class _QuizItemOut:
            # Local schema to keep storage shape stable even if pydantic models evolve
            def __init__(self, question: str, answer: str | None) -> None:
                self.question = question
                self.answer = answer

            def to_dict(self) -> dict:
                out = {"question": self.question}
                if self.answer is not None:
                    out["answer"] = self.answer
                else:
                    out["answer"] = None
                return out

        # Best-effort: try LLM structured output; fall back to deterministic prompts.
        try:
            if not (
                getattr(settings, "openai_api_key", None)
                or getattr(settings, "openai_base_url", None)
            ):
                raise RuntimeError("OpenAI not configured")
            from pydantic import BaseModel, Field

            class QuizItemModel(BaseModel):
                question: str = Field(min_length=1)
                answer: str = Field(min_length=1)

            class QuizGen(BaseModel):
                items: list[QuizItemModel] = Field(min_length=1)

            prompt = (
                f"Generate {n} spaced-repetition quiz questions for the topic: {topic_name}.\n"
                "Use the provided study text as ground truth. "
                "Return short answers (1-3 sentences) suitable for self-check.\n\n" + text[:8000]
            )
            res = LLMService().structured(
                [
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                schema=QuizGen,
            )
            items = [
                _QuizItemOut(question=i.question.strip(), answer=i.answer.strip()).to_dict()
                for i in (res.items or [])[:n]
                if (i.question or "").strip()
            ]
            if items:
                return items
        except Exception:
            pass

        # Fallback: no LLM available
        fallback = [
            _QuizItemOut(
                question=f"Explain {topic_name} in 2-3 sentences.",
                answer=None,
            ),
            _QuizItemOut(
                question=f"What problem does {topic_name} solve, and why does it matter?",
                answer=None,
            ),
            _QuizItemOut(
                question=f"List 3 key ideas or components of {topic_name}.",
                answer=None,
            ),
            _QuizItemOut(
                question=f"Give one example where {topic_name} is a better choice than an alternative approach.",
                answer=None,
            ),
            _QuizItemOut(
                question=f"What are common failure modes or pitfalls when applying {topic_name}?",
                answer=None,
            ),
        ]
        while len(fallback) < n:
            idx = len(fallback) + 1
            fallback.append(
                _QuizItemOut(
                    question=f"{topic_name}: write a short flashcard-style Q&A ({idx}).",
                    answer=None,
                )
            )
        return [i.to_dict() for i in fallback[:n]]

    def _load_resource_text(self, resource: LearningResource) -> str:
        parts: list[str] = []
        if resource.document_id:
            svc = DocStorageService()
            text = svc.get_document_text(str(resource.document_id)) or ""
            if text:
                parts.append(text)

        parts.extend([(resource.title or "").strip(), (resource.notes or "").strip()])
        return "\n\n".join([p for p in parts if p]).strip()

    # -----------------
    # Concepts / knowledge graph (SQL-backed)
    # -----------------
    def extract_resource_concepts(self, *, resource: LearningResource) -> dict:
        if not resource.document_id:
            raise ValueError("resource.document_id is required for extraction")
        if not str(resource.document_id).strip():
            raise ValueError("resource.document_id is required for extraction")

        svc = DocStorageService()
        text = svc.get_document_text(str(resource.document_id)) or ""
        if not text:
            raise ValueError("Document has no cleaned_text")
        if not text:
            raise ValueError("Document has no cleaned_text")

        graph = ExtractionService().extract_graph(
            text=text, metadata={"doc_id": resource.document_id}
        )
        entities = graph.get("entities") or []
        relations = graph.get("relations") or []

        entity_ids = self._upsert_entities(entities)
        self._link_resource_entities(resource_id=resource.id or 0, entity_ids=entity_ids)
        self._upsert_relations(resource_id=resource.id or 0, relations=relations)

        resource.extracted_at = _utcnow()
        resource.updated_at = _utcnow()
        self.session.add(resource)
        self.session.commit()
        self.session.refresh(resource)

        gs = self._maybe_graph()
        if gs is not None:
            try:
                topic = self.session.get(LearningTopic, resource.topic_id)
                if topic:
                    gs.upsert_topic_node(topic_id=str(topic.id), name=topic.name)
                if resource.document_id:
                    gs.upsert_document_node(
                        doc_id=str(resource.document_id),
                        title=resource.title,
                        source_url=resource.source_url,
                    )
                    if topic:
                        gs.link_topic_to_document(
                            topic_id=str(topic.id), doc_id=str(resource.document_id)
                        )
                for ent in entities:
                    name = (ent.get("name") or "").strip()
                    if not name:
                        continue
                    gs.upsert_entity(name=name, type_=ent.get("type"))
                    if resource.document_id:
                        gs.link_doc_to_entity(doc_id=str(resource.document_id), name=name)
                    if topic:
                        gs.link_topic_to_entity(topic_id=str(topic.id), name=name)
                for rel in relations:
                    from_name = (rel.get("from") or "").strip()
                    to_name = (rel.get("to") or "").strip()
                    if from_name and to_name:
                        gs.link_entities(
                            from_name=from_name,
                            to_name=to_name,
                            rel_type=str(rel.get("type") or "RELATED_TO"),
                        )
            finally:
                gs.close()
        return graph

    def _upsert_entities(self, entities: Iterable[dict]) -> dict[str, int]:
        name_to_id: dict[str, int] = {}
        for ent in entities:
            name = (ent.get("name") or "").strip()
            if not name:
                continue
            type_ = ent.get("type") or None
            existing = self.session.exec(
                select(LearningEntity).where(LearningEntity.name == name)
            ).first()
            if existing:
                if type_ and not existing.type:
                    existing.type = str(type_)
                    existing.updated_at = _utcnow()
                    self.session.add(existing)
                    self.session.commit()
                    self.session.refresh(existing)
                name_to_id[name] = existing.id or 0
                continue
            created = LearningEntity(name=name, type=(str(type_) if type_ else None))
            self.session.add(created)
            self.session.commit()
            self.session.refresh(created)
            name_to_id[name] = created.id or 0
        return name_to_id

    def _link_resource_entities(self, *, resource_id: int, entity_ids: dict[str, int]) -> None:
        for entity_id in entity_ids.values():
            stmt = select(LearningResourceEntity).where(
                (LearningResourceEntity.resource_id == resource_id)
                & (LearningResourceEntity.entity_id == entity_id)
            )
            existing = self.session.exec(stmt).first()
            if existing:
                continue
            self.session.add(LearningResourceEntity(resource_id=resource_id, entity_id=entity_id))
        self.session.commit()

    def _upsert_relations(self, *, resource_id: int, relations: Iterable[dict]) -> None:
        # Relations are best-effort; skip if entities aren't present
        for rel in relations:
            from_name = (rel.get("from") or "").strip()
            to_name = (rel.get("to") or "").strip()
            if not from_name or not to_name:
                continue
            from_ent = self.session.exec(
                select(LearningEntity).where(LearningEntity.name == from_name)
            ).first()
            to_ent = self.session.exec(
                select(LearningEntity).where(LearningEntity.name == to_name)
            ).first()
            if not from_ent or not to_ent:
                continue
            self.session.add(
                LearningEntityRelation(
                    resource_id=resource_id,
                    from_entity_id=from_ent.id or 0,
                    to_entity_id=to_ent.id or 0,
                    type=str(rel.get("type") or "RELATED_TO"),
                )
            )
        self.session.commit()

    def build_graph(self, *, topic_id: int | None = None, max_entities: int = 200) -> dict:
        nodes: list[dict] = []
        edges: list[dict] = []

        topic_stmt = select(LearningTopic)
        if topic_id is not None:
            topic_stmt = topic_stmt.where(LearningTopic.id == topic_id)
        topics = list(self.session.exec(topic_stmt))

        topic_nodes = []
        for t in topics:
            topic_nodes.append(
                {
                    "id": f"topic:{t.id}",
                    "label": t.name,
                    "type": "topic",
                    "meta": {"progress": t.progress},
                }
            )
        nodes.extend(topic_nodes)

        # topic -> resource -> entity
        ent_stmt = (
            select(
                LearningTopic.id.label("topic_id"),
                LearningEntity.id.label("entity_id"),
                LearningEntity.name.label("entity_name"),
                LearningEntity.type.label("entity_type"),
            )
            .select_from(LearningTopic)
            .join(LearningResource, LearningResource.topic_id == LearningTopic.id)
            .join(LearningResourceEntity, LearningResourceEntity.resource_id == LearningResource.id)
            .join(LearningEntity, LearningEntity.id == LearningResourceEntity.entity_id)
        )
        if topic_id is not None:
            ent_stmt = ent_stmt.where(LearningTopic.id == topic_id)

        rows = list(self.session.exec(ent_stmt))

        # Count mentions and cap entities by frequency
        mention_counts: dict[str, int] = {}
        for r in rows:
            eid = f"entity:{r.entity_id}"
            mention_counts[eid] = mention_counts.get(eid, 0) + 1
        allowed = {
            eid
            for eid, _ in sorted(mention_counts.items(), key=lambda kv: kv[1], reverse=True)[
                :max_entities
            ]
        }

        # Aggregate topic->entity weights and compute topic-topic links via shared entities
        topic_entity_weight: dict[tuple[int, str], int] = {}
        entity_to_topics: dict[str, set[int]] = {}
        entity_meta: dict[str, dict] = {}
        for r in rows:
            eid = f"entity:{r.entity_id}"
            if eid not in allowed:
                continue
            tid = int(r.topic_id)
            topic_entity_weight[(tid, eid)] = topic_entity_weight.get((tid, eid), 0) + 1
            entity_to_topics.setdefault(eid, set()).add(tid)
            entity_meta[eid] = {
                "label": r.entity_name,
                "entity_type": r.entity_type,
            }

        for eid, meta in entity_meta.items():
            nodes.append(
                {
                    "id": eid,
                    "label": meta["label"],
                    "type": "entity",
                    "meta": {
                        "entity_type": meta.get("entity_type"),
                        "mention_count": mention_counts.get(eid, 0),
                        "topic_count": len(entity_to_topics.get(eid, set())),
                    },
                }
            )

        for (tid, eid), w in topic_entity_weight.items():
            edges.append({"source": f"topic:{tid}", "target": eid, "type": "MENTIONS", "weight": w})

        shared: dict[tuple[int, int], int] = {}
        for tids in entity_to_topics.values():
            tlist = sorted(tids)
            for i in range(len(tlist)):
                for j in range(i + 1, len(tlist)):
                    key = (tlist[i], tlist[j])
                    shared[key] = shared.get(key, 0) + 1
        for (a, b), w in sorted(shared.items(), key=lambda kv: kv[1], reverse=True)[:200]:
            edges.append(
                {
                    "source": f"topic:{a}",
                    "target": f"topic:{b}",
                    "type": "SHARED_CONCEPT",
                    "weight": w,
                }
            )

        return {"nodes": nodes, "edges": edges}

    # -----------------
    # Study planning / metrics
    # -----------------
    def plan_session(
        self,
        *,
        minutes_available: int,
        focus_topic_ids: list[int] | None = None,
        include_new_material: bool = True,
        now: datetime | None = None,
    ) -> list[dict]:
        now = now or _utcnow()
        remaining = clamp_int(minutes_available, lo=5, hi=24 * 60)
        items: list[dict] = []

        # 1) Due reviews first
        due = self.list_due_reviews(now=now, limit=20)
        if focus_topic_ids:
            due = [r for r in due if r.topic_id in set(focus_topic_ids)]

        for review in due:
            if remaining <= 0:
                break
            topic = self.session.get(LearningTopic, review.topic_id)
            if not topic:
                continue
            minutes = min(20, remaining)
            remaining -= minutes
            items.append(
                {
                    "topic_id": topic.id,
                    "topic_name": topic.name,
                    "action": f"Review (stage {review.stage})",
                    "minutes": minutes,
                    "reason": f"Due {review.due_at.isoformat()} (spaced repetition).",
                    "review_id": review.id,
                }
            )

        if not include_new_material or remaining <= 0:
            return items

        # 2) New material / catch-up
        t_stmt = select(LearningTopic).where(LearningTopic.status == "active")
        if focus_topic_ids:
            t_stmt = t_stmt.where(LearningTopic.id.in_(focus_topic_ids))
        topics = list(self.session.exec(t_stmt))

        def _priority(t: LearningTopic) -> float:
            base = 1.0 + (100 - int(t.progress or 0)) / 100.0
            if t.interview_at:
                days = max(0.0, (t.interview_at - now).total_seconds() / 86400.0)
                urgency = 1.0 / max(1.0, days)
                base += 2.0 * urgency
            if t.first_learned_at is None:
                base += 0.5  # not started yet
            return base

        topics.sort(key=_priority, reverse=True)
        for t in topics:
            if remaining <= 0:
                break
            if int(t.progress or 0) >= 100:
                continue
            minutes = min(30, remaining)
            remaining -= minutes
            items.append(
                {
                    "topic_id": t.id,
                    "topic_name": t.name,
                    "action": "Study / expand notes",
                    "minutes": minutes,
                    "reason": "High priority based on progress and interview date.",
                    "review_id": None,
                }
            )
        return items

    def retention_metric_30d(self, *, now: datetime | None = None) -> dict:
        now = now or _utcnow()
        # Stage 3 reviews approximate 30-day recall checks.
        stmt = (
            select(LearningReview)
            .where(LearningReview.stage == 3)
            .where(LearningReview.completed_at.is_not(None))
        )
        reviews = list(self.session.exec(stmt))
        scores = [float(r.score) for r in reviews if r.score is not None]
        if not scores:
            return {"retention_rate_30d": 0.0, "sample_size": 0, "as_of": now}
        return {
            "retention_rate_30d": float(sum(scores) / max(1, len(scores))),
            "sample_size": len(scores),
            "as_of": now,
        }

    def gap_suggestions(self, *, limit: int = 20, min_mentions: int = 3) -> list[dict]:
        """Suggest concepts worth turning into new topics.

        Heuristic: entities mentioned frequently but associated with only one topic.
        """
        stmt = (
            select(
                LearningEntity.id.label("entity_id"),
                LearningEntity.name.label("entity_name"),
                func.count().label("mentions"),
                func.count(func.distinct(LearningTopic.id)).label("topic_count"),
                func.min(LearningTopic.name).label("example_topic"),
            )
            .select_from(LearningEntity)
            .join(LearningResourceEntity, LearningResourceEntity.entity_id == LearningEntity.id)
            .join(LearningResource, LearningResource.id == LearningResourceEntity.resource_id)
            .join(LearningTopic, LearningTopic.id == LearningResource.topic_id)
            .group_by(LearningEntity.id, LearningEntity.name)
            .having(func.count() >= int(min_mentions))
            .having(func.count(func.distinct(LearningTopic.id)) == 1)
            .order_by(func.count().desc())
            .limit(int(limit))
        )
        out: list[dict] = []
        for r in self.session.exec(stmt):
            out.append(
                {
                    "entity": r.entity_name,
                    "mentions": int(r.mentions or 0),
                    "topic_count": int(r.topic_count or 0),
                    "example_topic": r.example_topic,
                }
            )
        return out
