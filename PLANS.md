# PLANS.md — Execution Framework (Multi‑Step Reasoning)

Alfred solves complex problems by turning an ambiguous request into a concrete, executable plan.
This document defines the **planning contract** used across services and UI so that:

- reasoning stays explicit and reviewable,
- execution is incremental (one step at a time),
- progress is persistable (threads/tasks), and
- failure modes are predictable (clear blockers, retries, and exits).

## When To Use A Plan

Use a plan when the work has any of the following:

- multiple dependencies (data sources, tools, state),
- meaningful sequencing (A must happen before B),
- unknowns that need discovery,
- non-trivial verification (tests, migrations, UI flows).

Skip a plan for single, atomic actions.

## Plan Format

A plan is a small list of steps (usually 3–7). Each step is:

- **specific** (one action),
- **verifiable** (clear “done” signal),
- **bounded** (doesn’t hide sub-projects).

Each step has a **status**:

- `pending`: not started
- `in_progress`: currently executing (at most one at a time)
- `completed`: finished successfully
- `blocked`: cannot proceed without input/dependency
- `canceled`: intentionally not executed

## Execution Loop

1. **Normalize the request**
   - Restate the goal in one sentence.
   - List constraints (time, dependencies, “do not touch” areas).
   - Identify unknowns; decide what must be discovered first.

2. **Draft the plan**
   - Prefer fewer steps.
   - Make the first step a discovery step if needed.
   - Avoid vague steps (“Improve the system”).

3. **Execute step-by-step**
   - Mark exactly one step `in_progress`.
   - Perform the action.
   - Persist outputs (e.g., to a thread) when useful.
   - Mark the step `completed`, then move to the next.

4. **Handle blockers**
   - If blocked, mark the step `blocked`, record what is needed, and stop.
   - Do not “fake complete” a step to move on.

5. **Verify**
   - Run the smallest possible checks first (unit tests, typecheck, targeted lint).
   - Expand to broader checks only if needed.

6. **Deliver**
   - Summarize what changed.
   - List how to use/validate the feature.
   - Call out follow-ups explicitly.

## Anti‑Patterns (Avoid)

- Plans with 10+ steps for a single feature (too granular).
- Steps that aren’t independently verifiable.
- Parallel “in_progress” steps (creates ambiguity).
- Skipping verification for stateful changes.

## Persistence (Optional)

Plans can be persisted in Alfred using:

- **Threads** (recommended for UI-visible progress): store the plan JSON as a message payload.
- **Notes** (recommended for “memory”): store the final outcome and learnings.

