from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.core.dependencies import get_system_design_service
from alfred.schemas.interview_prep import InterviewPrepRecord, InterviewPrepUpdate
from alfred.schemas.system_design import (
    AutosaveRequest,
    ComponentDefinition,
    DesignPrompt,
    DiagramAnalysis,
    DiagramEvaluation,
    DiagramExportRequest,
    DiagramQuestion,
    DiagramSuggestion,
    DiagramVersion,
    ScaleEstimateRequest,
    ScaleEstimateResponse,
    SystemDesignArtifacts,
    SystemDesignKnowledgeDraft,
    SystemDesignNotesUpdate,
    SystemDesignPublishRequest,
    SystemDesignPublishResponse,
    SystemDesignSession,
    SystemDesignSessionCreate,
    SystemDesignSessionUpdate,
    TemplateDefinition,
)
from alfred.services.interview_service import InterviewPrepService
from alfred.services.learning_service import LearningService
from alfred.services.system_design import SystemDesignService
from alfred.services.system_design_realtime import SystemDesignRealtimeHub
from alfred.services.zettelkasten_service import ZettelkastenService

router = APIRouter(prefix="/api/system-design", tags=["system-design"])
realtime_hub = SystemDesignRealtimeHub()


@router.post("/sessions", response_model=SystemDesignSession)
def create_session(
    payload: SystemDesignSessionCreate,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignSession:
    return svc.create_session(payload)


@router.get("/sessions/{session_id}", response_model=SystemDesignSession)
def get_session(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignSession:
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.get("/sessions/share/{share_id}", response_model=SystemDesignSession)
def get_shared_session(
    share_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignSession:
    session = svc.get_by_share_id(share_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.patch("/sessions/{session_id}", response_model=SystemDesignSession)
def update_session(
    session_id: str,
    payload: SystemDesignSessionUpdate,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignSession:
    session = svc.update_session(session_id, payload)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.patch("/sessions/{session_id}/diagram", response_model=SystemDesignSession)
def autosave_diagram(
    session_id: str,
    payload: AutosaveRequest,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignSession:
    session = svc.autosave(session_id, payload)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.patch("/sessions/{session_id}/notes", response_model=SystemDesignSession)
def update_notes(
    session_id: str,
    payload: SystemDesignNotesUpdate,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignSession:
    session = svc.update_notes(session_id, payload.notes_markdown)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.post("/sessions/{session_id}/exports", response_model=SystemDesignSession)
def add_export(
    session_id: str,
    payload: DiagramExportRequest,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignSession:
    session = svc.add_export(session_id, payload)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.get("/sessions/{session_id}/versions", response_model=list[DiagramVersion])
def list_versions(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
):
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session.versions


@router.get("/library/components", response_model=list[ComponentDefinition])
def get_components(svc: SystemDesignService = Depends(get_system_design_service)):
    return svc.component_library()


@router.get("/library/templates", response_model=list[TemplateDefinition])
def get_templates(svc: SystemDesignService = Depends(get_system_design_service)):
    return svc.template_library()


@router.post("/sessions/{session_id}/analyze", response_model=DiagramAnalysis)
def analyze_session(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> DiagramAnalysis:
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return svc.analyze(session.diagram)


@router.post("/sessions/{session_id}/questions", response_model=list[DiagramQuestion])
def probing_questions(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
):
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return svc.ask_probing_questions(session.diagram)


@router.post("/sessions/{session_id}/suggestions", response_model=list[DiagramSuggestion])
def suggestions(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
):
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return svc.suggest_improvements(session.diagram)


@router.post("/sessions/{session_id}/evaluate", response_model=DiagramEvaluation)
def evaluate(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
):
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return svc.evaluate_design(session.diagram)


@router.post("/sessions/{session_id}/prompt", response_model=DesignPrompt)
def prompt(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> DesignPrompt:
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return svc.present_design_problem(session.problem_statement)


@router.post("/sessions/{session_id}/knowledge", response_model=SystemDesignKnowledgeDraft)
def knowledge_draft(
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> SystemDesignKnowledgeDraft:
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return svc.knowledge_draft(session)


@router.post("/sessions/{session_id}/publish", response_model=SystemDesignPublishResponse)
def publish_session(
    session_id: str,
    payload: SystemDesignPublishRequest,
    svc: SystemDesignService = Depends(get_system_design_service),
    db_session: Session = Depends(get_db_session),
) -> SystemDesignPublishResponse:
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    draft = svc.knowledge_draft(session)
    artifacts = SystemDesignArtifacts()

    if payload.create_learning_topics:
        learning = LearningService(db_session)
        topic_id = payload.learning_topic_id
        if topic_id is None:
            title = payload.topic_title or session.title or session.problem_statement
            topic = learning.create_topic(
                name=title,
                description=session.problem_statement,
                tags=payload.topic_tags or ["system-design"],
            )
            topic_id = topic.id or 0
            artifacts.learning_topic_ids.append(topic_id)
        if topic_id:
            topic = learning.get_topic(topic_id)
            if not topic:
                raise HTTPException(status_code=404, detail="Learning topic not found.")
            resource = learning.add_resource(
                topic=topic,
                title=f"Whiteboard: {session.title or session.problem_statement}",
                source_url=f"system-design://share/{session.share_id}",
                notes="\n".join(draft.notes) if draft.notes else None,
            )
            artifacts.learning_resource_ids.append(resource.id or 0)

    if payload.create_zettels:
        zettels = ZettelkastenService(db_session)
        for draft_card in draft.zettels:
            card = zettels.create_card(
                title=draft_card.title,
                summary=draft_card.summary,
                content=draft_card.content,
                tags=list({*draft_card.tags, *payload.zettel_tags}),
                topic=draft_card.topic or session.problem_statement,
                source_url=f"system-design://share/{session.share_id}",
            )
            artifacts.zettel_card_ids.append(card.id or 0)

    if payload.create_interview_prep_items and payload.interview_prep_id:
        prep_service = InterviewPrepService()
        prep = prep_service.get(payload.interview_prep_id)
        if not prep:
            raise HTTPException(status_code=404, detail="Interview prep record not found.")
        record = InterviewPrepRecord.model_validate(prep)
        prep_doc = record.prep_doc
        prep_doc.likely_questions.extend(draft.interview_prep.likely_questions)
        prep_doc.technical_topics.extend(draft.interview_prep.technical_topics)
        update = InterviewPrepUpdate(prep_doc=prep_doc)
        prep_service.update(payload.interview_prep_id, update)
        artifacts.interview_prep_id = payload.interview_prep_id

    updated = svc.attach_artifacts(session_id, artifacts)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found.")
    return SystemDesignPublishResponse(session=updated, artifacts=artifacts, knowledge_draft=draft)


@router.post("/scale-estimate", response_model=ScaleEstimateResponse)
def scale_estimate(
    payload: ScaleEstimateRequest,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> ScaleEstimateResponse:
    return svc.estimate_scale(payload)


@router.websocket("/sessions/{session_id}/ws")
async def system_design_ws(
    websocket: WebSocket,
    session_id: str,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> None:
    session = svc.get_session(session_id)
    if not session:
        await websocket.close(code=1008)
        return
    await realtime_hub.connect(session_id, websocket)
    try:
        while True:
            payload = await websocket.receive_json()
            await realtime_hub.broadcast(session_id, payload)
            if payload.get("autosave") and payload.get("diagram"):
                autosave_payload = AutosaveRequest.model_validate(
                    {"diagram": payload.get("diagram"), "label": payload.get("label")}
                )
                svc.autosave(session_id, autosave_payload)
    except WebSocketDisconnect:
        return
    finally:
        await realtime_hub.disconnect(session_id, websocket)
