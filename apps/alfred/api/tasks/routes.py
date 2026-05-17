from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlmodel import Session

from alfred.api.dependencies import AuthUser, get_current_user, get_db_session
from alfred.core.celery_client import get_celery_client
from alfred.models.tasks import TaskPriority, TaskStatus
from alfred.schemas.tasks import (
    TaskBoardResponse,
    TaskCalendarEventCreate,
    TaskCalendarEventResponse,
    TaskColumnResponse,
    TaskCreate,
    TaskDoneRequest,
    TaskDoneResponse,
    TaskFocusSessionComplete,
    TaskFocusSessionCreate,
    TaskFocusSessionResponse,
    TaskListResponse,
    TaskMoveRequest,
    TaskPlanRequest,
    TaskPlanResponse,
    TaskPomodoroCreate,
    TaskPomodoroResponse,
    TaskResponse,
    TaskUpdate,
    UserTaskGamificationProfileResponse,
    UserTaskRewardResponse,
)
from alfred.services.tasks import (
    TaskBoardService,
    TaskFocusService,
    TaskLearningService,
    TaskRewardService,
    TaskService,
)
from alfred.services.tasks.exceptions import (
    InvalidTimezoneError,
    RewardComputationError,
    TaskAuthorizationError,
    TaskBoardNotFoundError,
    TaskCalendarEventNotFoundError,
    TaskColumnInvariantError,
    TaskFocusSessionNotFoundError,
    TaskMigrationConflictError,
    TaskNotFoundError,
    TaskPlanningParseError,
    TaskPlanningUnavailableError,
    TaskProjectNotFoundError,
    TaskRewardNotFoundError,
    TaskScheduleConflictError,
    TaskValidationError,
)
from alfred.services.tasks.metrics import increment_task_metric

logger = logging.getLogger(__name__)

router = APIRouter()
legacy_router = APIRouter(prefix="/tasks", tags=["tasks"])
task_system_router = APIRouter(prefix="/api/task-system", tags=["task-system"])


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    ready: bool
    successful: bool
    failed: bool
    result: Any | None = None
    error: str | None = None


TASK_NOT_FOUND_ERRORS = (
    TaskBoardNotFoundError,
    TaskCalendarEventNotFoundError,
    TaskFocusSessionNotFoundError,
    TaskNotFoundError,
    TaskProjectNotFoundError,
    TaskRewardNotFoundError,
)


def task_system_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TaskAuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, TASK_NOT_FOUND_ERRORS):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, TaskColumnInvariantError | TaskMigrationConflictError | RewardComputationError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, TaskPlanningUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, InvalidTimezoneError | TaskPlanningParseError | TaskScheduleConflictError | TaskValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Task system error")


def _task_response(task: Any) -> TaskResponse:
    return TaskResponse.model_validate(task)


def _board_response(board: Any) -> TaskBoardResponse:
    return TaskBoardResponse.model_validate(board)


def _column_response(column: Any) -> TaskColumnResponse:
    return TaskColumnResponse.model_validate(column)


def _calendar_event_response(event: Any) -> TaskCalendarEventResponse:
    return TaskCalendarEventResponse.model_validate(event)


def _focus_session_response(session: Any) -> TaskFocusSessionResponse:
    return TaskFocusSessionResponse.model_validate(session)


def _pomodoro_response(pomodoro: Any) -> TaskPomodoroResponse:
    return TaskPomodoroResponse.model_validate(pomodoro)


def _reward_response(reward: Any) -> UserTaskRewardResponse:
    return UserTaskRewardResponse.model_validate(reward)


def _profile_response(profile: Any) -> UserTaskGamificationProfileResponse:
    return UserTaskGamificationProfileResponse.model_validate(profile)


def _task_create_payload(payload: TaskCreate) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    allowed = {
        "title",
        "description_md",
        "board_id",
        "column_id",
        "priority",
        "status",
        "type",
        "estimate_minutes",
        "estimated_pomodoros",
        "tags",
        "due_at",
        "source_kind",
        "source_id",
        "source_url",
        "project_id",
        "auto_generated",
        "ai_planned",
        "from_brain_dump",
        "legacy_today_entry_id",
        "meta",
    }
    return {key: value for key, value in data.items() if key in allowed}


@legacy_router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str, *, include_result: bool = True) -> TaskStatusResponse:
    celery_client = get_celery_client()
    async_result = celery_client.AsyncResult(task_id)

    result: Any | None = None
    error: str | None = None
    try:
        is_ready = async_result.ready()
        is_successful = async_result.successful()
        is_failed = async_result.failed()
        status_value = async_result.status

        if is_ready and include_result:
            if is_successful:
                try:
                    result = jsonable_encoder(async_result.result)
                except TypeError:
                    result = str(async_result.result)
            elif is_failed:
                error = str(async_result.result)
    except Exception as exc:  # pragma: no cover - depends on external broker/result backend
        # If Redis (or another result backend) is unavailable, avoid returning 500s for
        # status polling. Let the UI degrade gracefully.
        return TaskStatusResponse(
            task_id=task_id,
            status="unavailable",
            ready=False,
            successful=False,
            failed=False,
            result=None,
            error=str(exc),
        )

    return TaskStatusResponse(
        task_id=task_id,
        status=status_value,
        ready=is_ready,
        successful=is_successful,
        failed=is_failed,
        result=result,
        error=error,
    )


@task_system_router.get("/tasks", response_model=TaskListResponse)
def list_task_system_tasks(
    status_filter: list[TaskStatus] | None = Query(default=None, alias="status"),
    priority: list[TaskPriority] | None = Query(default=None),
    board_id: int | None = None,
    project_id: int | None = None,
    source_kind: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskListResponse:
    service = TaskService(session)
    try:
        tasks = service.list_tasks(
            user_id=current_user.user_id,
            board_id=board_id,
            status=[value.value for value in status_filter] if status_filter else None,
            priority=[value.value for value in priority] if priority else None,
            project_id=project_id,
            source_kind=source_kind,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return TaskListResponse(
        tasks=[_task_response(task) for task in tasks],
        total=len(tasks),
        next_cursor=str(offset + limit) if len(tasks) == limit else None,
    )


@task_system_router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task_system_task(
    payload: TaskCreate,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskResponse:
    try:
        task = TaskService(session).create_task(user_id=current_user.user_id, **_task_create_payload(payload))
        increment_task_metric("tasks_created")
        logger.info("task_system.task_created", extra={"operation": "create", "task_id": task.id, "board_id": task.board_id, "user_id": current_user.user_id, "duration_ms": None, "error_class": None})
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _task_response(task)


@task_system_router.post("/tasks/plan", response_model=TaskPlanResponse)
def plan_task_system_tasks(
    payload: TaskPlanRequest,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskPlanResponse:
    try:
        from alfred.services.tasks.planning_service import TaskPlanningService

        result = TaskPlanningService(session).plan(
            user_id=current_user.user_id,
            input_text=payload.input,
            create_tasks=payload.create_tasks,
            board_id=payload.board_id,
            project_id=payload.project_id,
        )
    except ModuleNotFoundError as exc:
        increment_task_metric("planner_attempts")
        increment_task_metric("planner_failures")
        raise task_system_http_error(TaskPlanningUnavailableError("planner service is not implemented")) from exc
    except Exception as exc:
        increment_task_metric("planner_failures")
        raise task_system_http_error(exc) from exc
    increment_task_metric("planner_attempts")
    return TaskPlanResponse.model_validate(result)


@task_system_router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task_system_task(
    task_id: int,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskResponse:
    try:
        task = TaskService(session).get_task(task_id, user_id=current_user.user_id)
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _task_response(task)


@task_system_router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task_system_task(
    task_id: int,
    payload: TaskUpdate,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskResponse:
    try:
        task = TaskService(session).update_task(
            task_id,
            user_id=current_user.user_id,
            patch=payload.model_dump(exclude_unset=True),
        )
        logger.info("task_system.task_updated", extra={"operation": "update", "task_id": task.id, "board_id": task.board_id, "user_id": current_user.user_id, "duration_ms": None, "error_class": None})
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _task_response(task)


@task_system_router.get("/boards", response_model=list[TaskBoardResponse])
def list_task_system_boards(
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> list[TaskBoardResponse]:
    try:
        boards = TaskBoardService(session).list_boards(current_user.user_id)
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return [_board_response(board) for board in boards]


@task_system_router.post("/boards/default", response_model=TaskBoardResponse)
def ensure_task_system_default_board(
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskBoardResponse:
    try:
        board = TaskBoardService(session).get_or_create_default_board(current_user.user_id)
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _board_response(board)


@task_system_router.get("/boards/{board_id}/columns", response_model=list[TaskColumnResponse])
def list_task_system_columns(
    board_id: int,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> list[TaskColumnResponse]:
    try:
        columns = TaskBoardService(session).list_columns(board_id, current_user.user_id)
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return [_column_response(column) for column in columns]


@task_system_router.patch("/tasks/{task_id}/move", response_model=TaskResponse)
def move_task_system_task(
    task_id: int,
    payload: TaskMoveRequest,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskResponse:
    try:
        task = TaskService(session).move_task(task_id, column_id=payload.column_id, user_id=current_user.user_id)
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _task_response(task)


@task_system_router.post("/calendar/events", response_model=TaskCalendarEventResponse, status_code=status.HTTP_201_CREATED)
def schedule_task_system_focus_block(
    payload: TaskCalendarEventCreate,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskCalendarEventResponse:
    try:
        event = TaskFocusService(session).schedule_focus_block(
            user_id=current_user.user_id,
            title=payload.title,
            start_at=payload.start_at,
            end_at=payload.end_at,
            task_id=payload.task_id,
            tz_name=payload.tz_name,
            description_md=payload.description_md,
            location=payload.location,
            tags=payload.tags,
        )
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _calendar_event_response(event)


@task_system_router.post("/focus-sessions", response_model=TaskFocusSessionResponse, status_code=status.HTTP_201_CREATED)
def start_task_system_focus_session(
    payload: TaskFocusSessionCreate,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskFocusSessionResponse:
    try:
        focus_session = TaskFocusService(session).start_focus_session(
            user_id=current_user.user_id,
            task_id=payload.task_id,
            event_id=payload.event_id,
            started_at=payload.started_at,
        )
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _focus_session_response(focus_session)


@task_system_router.patch("/focus-sessions/{session_id}/complete", response_model=TaskFocusSessionResponse)
def complete_task_system_focus_session(
    session_id: int,
    payload: TaskFocusSessionComplete,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskFocusSessionResponse:
    try:
        focus_session = TaskFocusService(session).complete_focus_session(
            session_id,
            user_id=current_user.user_id,
            ended_at=payload.ended_at,
            interruptions=payload.interruptions,
        )
        TaskRewardService(session).record_focus_completed(user_id=current_user.user_id)
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _focus_session_response(focus_session)


@task_system_router.post("/pomodoros/start", response_model=TaskFocusSessionResponse, status_code=status.HTTP_201_CREATED)
def start_task_system_pomodoro(
    payload: TaskFocusSessionCreate,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskFocusSessionResponse:
    try:
        focus_session = TaskFocusService(session).start_focus_session(
            user_id=current_user.user_id,
            task_id=payload.task_id,
            event_id=payload.event_id,
            started_at=payload.started_at,
        )
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _focus_session_response(focus_session)


@task_system_router.post("/pomodoros/complete", response_model=TaskPomodoroResponse, status_code=status.HTTP_201_CREATED)
def complete_task_system_pomodoro(
    payload: TaskPomodoroCreate,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskPomodoroResponse:
    try:
        pomodoro = TaskFocusService(session).record_pomodoro(
            user_id=current_user.user_id,
            task_id=payload.task_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            duration_minutes=payload.duration_minutes,
            reflection_md=payload.reflection_md,
            status=payload.status,
        )
        TaskLearningService(session).record_pomodoro_reflection(
            user_id=current_user.user_id,
            task_id=payload.task_id,
            reflection_md=payload.reflection_md,
            duration_minutes=payload.duration_minutes,
        )
        TaskRewardService(session).record_pomodoro_completed(user_id=current_user.user_id, task_id=payload.task_id)
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return _pomodoro_response(pomodoro)


@task_system_router.patch("/tasks/{task_id}/done", response_model=TaskDoneResponse)
def mark_task_system_task_done(
    task_id: int,
    payload: TaskDoneRequest | None = None,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> TaskDoneResponse:
    try:
        task = TaskService(session).mark_done(task_id, user_id=current_user.user_id)
        increment_task_metric("tasks_completed")
        logger.info("task_system.task_done", extra={"operation": "done", "task_id": task.id, "board_id": task.board_id, "user_id": current_user.user_id, "duration_ms": None, "error_class": None})
        TaskLearningService(session).record_completion_reflection(
            user_id=current_user.user_id,
            task_id=task_id,
            reflection_md=payload.reflection_md if payload else None,
        )
        profile = None
        rewards = []
        if payload is None or payload.award_rewards:
            try:
                profile, rewards = TaskRewardService(session).record_task_completed(user_id=current_user.user_id, task_id=task_id)
                task = TaskService(session).get_task(task_id, user_id=current_user.user_id)
            except RewardComputationError:
                increment_task_metric("reward_failures")
                profile = None
                rewards = []
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return TaskDoneResponse(
        task=_task_response(task),
        profile=_profile_response(profile) if profile else None,
        rewards=[_reward_response(reward) for reward in rewards],
    )


@task_system_router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_system_task(
    task_id: int,
    session: Session = Depends(get_db_session),
    current_user: AuthUser = Depends(get_current_user),
) -> Response:
    try:
        TaskService(session).delete_task(task_id, user_id=current_user.user_id)
        logger.info("task_system.task_deleted", extra={"operation": "delete", "task_id": task_id, "board_id": None, "user_id": current_user.user_id, "duration_ms": None, "error_class": None})
    except Exception as exc:
        raise task_system_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(legacy_router)
router.include_router(task_system_router)

__all__ = ["router", "task_system_http_error", "task_system_router"]
