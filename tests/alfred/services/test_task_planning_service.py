import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.services.tasks.exceptions import TaskPlanningParseError, TaskPlanningUnavailableError
from alfred.services.tasks.planning_service import TaskPlanningService


class Response:
    def __init__(self, content: str):
        self.content = content


class Model:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, _prompt: str):
        return Response(self.content)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_planner_valid_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "alfred.services.tasks.planning_service.get_chat_model",
        lambda: Model('{"tasks":[{"title":"Ship","estimatePomodoros":2,"priority":"HIGH"}],"rationale":"ok"}'),
    )
    result = TaskPlanningService(_session()).plan(user_id="user_1", input_text="ship it")
    assert result.tasks[0].title == "Ship"
    assert result.tasks[0].estimate_minutes == 50


def test_planner_fenced_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "alfred.services.tasks.planning_service.get_chat_model",
        lambda: Model('```json\n{"tasks":[{"title":"Ship"}]}\n```'),
    )
    result = TaskPlanningService(_session()).plan(user_id="user_1", input_text="ship it")
    assert result.tasks[0].title == "Ship"


def test_planner_empty_output_raises(monkeypatch) -> None:
    monkeypatch.setattr("alfred.services.tasks.planning_service.get_chat_model", lambda: Model(""))
    with pytest.raises(TaskPlanningParseError):
        TaskPlanningService(_session()).plan(user_id="user_1", input_text="ship it")


def test_planner_malformed_output_raises(monkeypatch) -> None:
    monkeypatch.setattr("alfred.services.tasks.planning_service.get_chat_model", lambda: Model("not json"))
    with pytest.raises(TaskPlanningParseError):
        TaskPlanningService(_session()).plan(user_id="user_1", input_text="ship it")


def test_planner_unavailable_model_raises(monkeypatch) -> None:
    def fail():
        raise RuntimeError("missing")

    monkeypatch.setattr("alfred.services.tasks.planning_service.get_chat_model", fail)
    with pytest.raises(TaskPlanningUnavailableError):
        TaskPlanningService(_session()).plan(user_id="user_1", input_text="ship it")
