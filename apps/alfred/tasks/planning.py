from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.planning.generate_plan")
def generate_plan_task(*, goal: str, context: str | None = None, max_steps: int = 6) -> dict:
    """Generate an execution plan for a goal."""
    from alfred.services.planning_service import PlanningService

    logger.info("Generating plan for goal: %s", goal[:100])
    svc = PlanningService()
    plan = svc.create_plan(goal=goal, context=context, max_steps=max_steps)
    return plan.model_dump()
