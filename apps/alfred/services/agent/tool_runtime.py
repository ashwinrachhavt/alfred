"""Policy-aware tool execution for Alfred agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlmodel import Session

from alfred.services.agent.harness import (
    DEFAULT_AGENT_POLICY,
    AgentEventType,
    AgentPolicy,
    AgentRunTrace,
    ToolResultEnvelope,
    normalize_tool_result,
    stable_hash,
)


async def execute_tool_with_harness(
    tool_name: str,
    args: dict[str, Any],
    db: Session,
    *,
    policy: AgentPolicy | None = None,
    trace: AgentRunTrace | None = None,
    envelope: bool = False,
    executor: Callable[[str, dict[str, Any], Session], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Execute one tool behind policy, tracing, and result normalization.

    `envelope=False` preserves legacy return shape for existing callers while
    still enforcing policy and emitting trace events. New LangChain agents can
    opt into compact envelopes for context efficiency.
    """

    active_policy = policy or DEFAULT_AGENT_POLICY
    decision = active_policy.decide(tool_name, args)
    args_hash = stable_hash(args)

    if trace:
        trace.emit(
            AgentEventType.TOOL_STARTED,
            tool=tool_name,
            args_hash=args_hash,
            policy_tier=decision.tier,
            policy_action=decision.action,
        )

    if decision.action != "allow":
        result = {
            "error": decision.reason,
            "blocked": True,
            "tool": tool_name,
            "policy_tier": decision.tier,
            "policy_action": decision.action,
        }
        if trace:
            trace.emit(
                AgentEventType.TOOL_BLOCKED,
                tool=tool_name,
                result_hash=stable_hash(result),
                reason=decision.reason,
            )
        return _maybe_envelope(result, envelope=envelope)

    if executor is None:
        from alfred.services.agent.tools import execute_tool

        result = await execute_tool(tool_name, args, db)
    else:
        result = await executor(tool_name, args, db)
    normalized = normalize_tool_result(result)

    if trace:
        trace.emit(
            AgentEventType.TOOL_COMPLETED,
            tool=tool_name,
            result_hash=normalized.raw_hash,
            status=normalized.status,
            summary=normalized.summary,
        )

    return _maybe_envelope(result, envelope=envelope, normalized=normalized)


def _maybe_envelope(
    result: dict[str, Any],
    *,
    envelope: bool,
    normalized: ToolResultEnvelope | None = None,
) -> dict[str, Any]:
    if not envelope:
        return result
    return (normalized or normalize_tool_result(result)).to_dict()


__all__ = ["execute_tool_with_harness"]
