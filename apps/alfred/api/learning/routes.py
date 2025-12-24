from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.core.settings import settings
from alfred.models.learning import LearningQuiz, LearningReview, LearningTopic
from alfred.schemas.learning import (
    GraphResponse,
    QuizAttemptOut,
    QuizGenerateRequest,
    QuizOut,
    QuizSubmitRequest,
    ResourceCreate,
    ResourceOut,
    RetentionMetric,
    ReviewCompleteRequest,
    ReviewOut,
    StudyPlanRequest,
    StudyPlanResponse,
    TopicCreate,
    TopicOut,
    TopicUpdate,
)
from alfred.services.graph_service import GraphService
from alfred.services.learning_service import LearningService

router = APIRouter(prefix="/api/learning", tags=["learning"], include_in_schema=False)


def _topic_out(t: LearningTopic) -> TopicOut:
    return TopicOut(
        id=t.id or 0,
        name=t.name,
        description=t.description,
        tags=t.tags,
        status=t.status,
        progress=int(t.progress or 0),
        interview_at=t.interview_at,
        first_learned_at=t.first_learned_at,
        last_studied_at=t.last_studied_at,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _resource_out(r) -> ResourceOut:  # noqa: ANN001
    return ResourceOut(
        id=r.id or 0,
        topic_id=r.topic_id,
        title=r.title,
        source_url=r.source_url,
        document_id=r.document_id,
        notes=r.notes,
        added_at=r.added_at,
        extracted_at=r.extracted_at,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _quiz_out(q: LearningQuiz) -> QuizOut:
    items = []
    for raw in q.items or []:
        question = (raw or {}).get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        items.append({"question": question.strip(), "answer": (raw or {}).get("answer")})
    return QuizOut(
        id=q.id or 0,
        topic_id=q.topic_id,
        resource_id=q.resource_id,
        items=items,  # pydantic will coerce to QuizItem
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


def _attempt_out(a) -> QuizAttemptOut:  # noqa: ANN001
    return QuizAttemptOut(
        id=a.id or 0,
        quiz_id=a.quiz_id,
        known=a.known,
        responses=a.responses,
        score=float(a.score or 0.0),
        submitted_at=a.submitted_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _review_out(r: LearningReview) -> ReviewOut:
    return ReviewOut(
        id=r.id or 0,
        topic_id=r.topic_id,
        stage=int(r.stage),
        iteration=int(r.iteration),
        due_at=r.due_at,
        completed_at=r.completed_at,
        score=r.score,
        attempt_id=r.attempt_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post("/topics", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
def create_topic(
    payload: TopicCreate,
    session: Session = Depends(get_db_session),
) -> TopicOut:
    svc = LearningService(session)
    try:
        topic = svc.create_topic(
            name=payload.name,
            description=payload.description,
            tags=payload.tags,
            interview_at=payload.interview_at,
        )
        return _topic_out(topic)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Topic name already exists") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/topics", response_model=list[TopicOut])
def list_topics(session: Session = Depends(get_db_session)) -> list[TopicOut]:
    svc = LearningService(session)
    return [_topic_out(t) for t in svc.list_topics()]


@router.get("/topics/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: int, session: Session = Depends(get_db_session)) -> TopicOut:
    svc = LearningService(session)
    topic = svc.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return _topic_out(topic)


@router.patch("/topics/{topic_id}", response_model=TopicOut)
def update_topic(
    topic_id: int,
    payload: TopicUpdate,
    session: Session = Depends(get_db_session),
) -> TopicOut:
    svc = LearningService(session)
    topic = svc.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    try:
        updated = svc.update_topic(topic, **payload.model_dump(exclude_unset=True))
        return _topic_out(updated)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Topic name already exists") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_topic(topic_id: int, session: Session = Depends(get_db_session)) -> Response:
    svc = LearningService(session)
    topic = svc.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    svc.delete_topic(topic)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/topics/{topic_id}/resources", response_model=ResourceOut, status_code=status.HTTP_201_CREATED
)
def add_resource(
    topic_id: int,
    payload: ResourceCreate,
    session: Session = Depends(get_db_session),
) -> ResourceOut:
    svc = LearningService(session)
    topic = svc.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    try:
        res = svc.add_resource(
            topic=topic,
            title=payload.title,
            source_url=payload.source_url,
            document_id=payload.document_id,
            notes=payload.notes,
        )
        return _resource_out(res)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/topics/{topic_id}/resources", response_model=list[ResourceOut])
def list_resources(topic_id: int, session: Session = Depends(get_db_session)) -> list[ResourceOut]:
    svc = LearningService(session)
    topic = svc.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return [_resource_out(r) for r in svc.list_resources(topic_id=topic_id)]


@router.post("/topics/{topic_id}/quiz", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    topic_id: int,
    payload: QuizGenerateRequest,
    session: Session = Depends(get_db_session),
) -> QuizOut:
    svc = LearningService(session)
    topic = svc.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    try:
        quiz = svc.generate_quiz(
            topic=topic,
            question_count=payload.question_count,
            resource_id=payload.resource_id,
            source_text=payload.source_text,
        )
        return _quiz_out(quiz)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/quiz/{quiz_id}/submit", response_model=QuizAttemptOut)
def submit_quiz(
    quiz_id: int,
    payload: QuizSubmitRequest,
    session: Session = Depends(get_db_session),
) -> QuizAttemptOut:
    svc = LearningService(session)
    quiz = session.get(LearningQuiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    try:
        attempt = svc.submit_quiz(quiz=quiz, known=payload.known, responses=payload.responses)
        return _attempt_out(attempt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reviews/due", response_model=list[ReviewOut])
def due_reviews(
    session: Session = Depends(get_db_session),
) -> list[ReviewOut]:
    svc = LearningService(session)
    return [_review_out(r) for r in svc.list_due_reviews(now=datetime.utcnow(), limit=100)]


@router.post("/reviews/{review_id}/complete", response_model=ReviewOut)
def complete_review(
    review_id: int,
    payload: ReviewCompleteRequest,
    session: Session = Depends(get_db_session),
) -> ReviewOut:
    svc = LearningService(session)
    review = session.get(LearningReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    try:
        updated = svc.complete_review(
            review=review, score=payload.score, attempt_id=payload.attempt_id
        )
        return _review_out(updated)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plan", response_model=StudyPlanResponse)
def plan(
    payload: StudyPlanRequest,
    session: Session = Depends(get_db_session),
) -> StudyPlanResponse:
    svc = LearningService(session)
    items = svc.plan_session(
        minutes_available=payload.minutes_available,
        focus_topic_ids=payload.focus_topic_ids,
        include_new_material=payload.include_new_material,
    )
    return StudyPlanResponse(minutes_available=payload.minutes_available, items=items)


@router.get("/graph", response_model=GraphResponse)
def graph(
    session: Session = Depends(get_db_session),
    topic_id: int | None = None,
    backend: Literal["sql", "neo4j"] = "sql",
) -> GraphResponse:
    if backend == "neo4j":
        if topic_id is None:
            raise HTTPException(status_code=400, detail="topic_id is required for backend=neo4j")
        if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password):
            raise HTTPException(status_code=400, detail="Neo4j is not configured")
        gs = GraphService(
            uri=settings.neo4j_uri, user=settings.neo4j_user, password=settings.neo4j_password
        )
        try:
            data = gs.fetch_topic_subgraph(topic_id=str(topic_id), limit=400)
        finally:
            gs.close()
        topic = session.get(LearningTopic, topic_id)
        if topic and data.get("nodes"):
            for n in data["nodes"]:
                if n.get("id") == f"topic:{topic_id}":
                    n["label"] = topic.name
                    break
        return GraphResponse(**data)

    svc = LearningService(session)
    return GraphResponse(**svc.build_graph(topic_id=topic_id, max_entities=200))


@router.post("/resources/{resource_id}/extract")
def extract_resource(resource_id: int, session: Session = Depends(get_db_session)) -> dict:
    svc = LearningService(session)
    resource = svc.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    try:
        graph = svc.extract_resource_concepts(resource=resource)
        return {"ok": True, "graph": graph}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/metrics/retention", response_model=RetentionMetric)
def retention(session: Session = Depends(get_db_session)) -> RetentionMetric:
    svc = LearningService(session)
    metric = svc.retention_metric_30d()
    return RetentionMetric(**metric)


@router.get("/gaps")
def gaps(
    session: Session = Depends(get_db_session), limit: int = 20, min_mentions: int = 3
) -> dict:
    svc = LearningService(session)
    return {"items": svc.gap_suggestions(limit=limit, min_mentions=min_mentions)}
