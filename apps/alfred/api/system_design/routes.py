from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from alfred.core.dependencies import get_system_design_service
from alfred.schemas.system_design import (
    AutosaveRequest,
    ComponentDefinition,
    DiagramAnalysis,
    DiagramEvaluation,
    DiagramQuestion,
    DiagramSuggestion,
    DiagramVersion,
    ScaleEstimateRequest,
    ScaleEstimateResponse,
    SystemDesignSession,
    SystemDesignSessionCreate,
    TemplateDefinition,
)
from alfred.services.system_design import SystemDesignService

router = APIRouter(prefix="/api/system-design", tags=["system-design"])


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


@router.post("/scale-estimate", response_model=ScaleEstimateResponse)
def scale_estimate(
    payload: ScaleEstimateRequest,
    svc: SystemDesignService = Depends(get_system_design_service),
) -> ScaleEstimateResponse:
    return svc.estimate_scale(payload)
