from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.tasks import UserTaskRewardRow
from alfred.services.tasks.reward_service import TaskRewardService
from alfred.services.tasks.task_service import TaskService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _task(session: Session) -> int:
    task = TaskService(session).create_task(user_id="user_1", title="Ship task")
    assert task.id is not None
    return task.id


def test_reward_awarding_is_idempotent_for_same_threshold() -> None:
    session = _session()
    task_id = _task(session)
    service = TaskRewardService(session)

    _profile, first_rewards = service.record_task_completed(user_id="user_1", task_id=task_id)
    for _ in range(9):
        service.record_task_completed(user_id="user_1", task_id=task_id)
    _profile, second_rewards = service.record_task_completed(user_id="user_1", task_id=task_id)

    assert len(first_rewards) == 1
    assert second_rewards == []
    assert len(session.query(UserTaskRewardRow).all()) == 2


def test_invalid_reward_threshold_fails_without_award() -> None:
    session = _session()
    service = TaskRewardService(session)
    service.ensure_default_rewards()
    reward = service.ensure_default_rewards()[0]
    reward.metadata_ = {"trigger": "task_completed", "threshold": 0}
    session.add(reward)
    session.commit()
    task_id = _task(session)

    try:
        service.record_task_completed(user_id="user_1", task_id=task_id)
    except Exception as exc:
        assert "threshold" in str(exc)

    assert len(session.query(UserTaskRewardRow).all()) == 0
