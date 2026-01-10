from __future__ import annotations

from alfred.services.planning_service import PlanningService


def test_planning_service_creates_heuristic_plan_when_llm_unavailable() -> None:
    svc = PlanningService(llm_service=None)
    plan = svc.create_plan(goal="Implement multilingual autocomplete", context=None, max_steps=4)

    assert plan.goal == "Implement multilingual autocomplete"
    assert 1 <= len(plan.steps) <= 4
    assert all(step.status == "pending" for step in plan.steps)
    assert all(step.step.strip() for step in plan.steps)
