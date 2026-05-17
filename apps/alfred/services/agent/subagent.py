"""Sub-agent runner — isolated context window execution.

Each sub-agent gets its own message history, focused system prompt,
and tool subset. It runs a flat tool-calling loop to completion and
returns a summary string to the parent agent.

This is Claude Code's "Agent tool" pattern: the parent LLM decides
when to delegate, the sub-agent runs independently, and the result
flows back as a tool result.

┌─────────────────────────────────────────────────────────┐
│  SubAgentRunner.run(task, agent_type)                   │
│                                                          │
│  1. Create FRESH message history (isolated context)     │
│  2. Build system prompt for specialist type              │
│  3. Load ONLY the tools this specialist needs            │
│  4. Run flat tool-calling loop (same as main agent)     │
│  5. Return final response text                           │
│                                                          │
│  The parent agent NEVER sees:                            │
│  - The sub-agent's internal tool calls                   │
│  - The sub-agent's intermediate reasoning                │
│  - The sub-agent's full message history                  │
│                                                          │
│  The parent ONLY sees: the final summary string          │
└─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import Callable
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from sqlmodel import Session

from alfred.core.database import SessionLocal
from alfred.core.llm_factory import get_async_openai_client
from alfred.core.openai_compat import add_temperature_if_supported, uses_max_completion_tokens
from alfred.core.settings import DEFAULT_OPENAI_MODEL, settings
from alfred.services.agent.agent_types import AGENT_TYPES, AgentType
from alfred.services.agent.harness import AgentEventType, AgentRunContext, AgentRunTrace
from alfred.services.agent.tool_runtime import execute_tool_with_harness

logger = logging.getLogger(__name__)


async def execute_tool(tool_name: str, args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Lazy compatibility wrapper for tests and callers that patch this module."""

    from alfred.services.agent.tools import execute_tool as _execute_tool

    return await _execute_tool(tool_name, args, db)


# HTML tag stripping for tool results
_HTML_TAG_RE = re.compile(r"<[^>]+>")

def _get_tool_schemas_for_type(agent_type: AgentType) -> list[dict[str, Any]]:
    """Get OpenAI function-calling schemas for a specific agent type's tools."""
    from alfred.services.agent.tools import (
        CORE_TOOL_SCHEMAS,
        _lc_tools_cache,
        _load_langchain_tools,
    )

    _load_langchain_tools()

    schemas = []
    for tool_name in agent_type.tool_names:
        # Check core tools first
        for schema in CORE_TOOL_SCHEMAS:
            if schema["function"]["name"] == tool_name:
                schemas.append(schema)
                break
        else:
            # Check LangChain tools
            from alfred.services.agent.tools import _langchain_tool_to_openai_schema

            lc_tool = _lc_tools_cache.get(tool_name)
            if lc_tool:
                schemas.append(_langchain_tool_to_openai_schema(lc_tool))
            else:
                logger.warning(
                    "Tool %s not found for agent type %s",
                    tool_name,
                    agent_type.name,
                )
    return schemas


class SubAgentRunner:
    """Runs a sub-agent with its own isolated context window.

    Each sub-agent:
    - Has a fresh message history (no parent context)
    - Uses a focused system prompt for its specialist role
    - Only sees the tools relevant to its domain
    - Runs a flat tool-calling loop identical to the main agent
    - Returns a summary string when done
    """

    def __init__(
        self,
        db: Session,
        *,
        model: str | None = None,
        tool_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.db = db
        self.model = model or settings.llm_model or DEFAULT_OPENAI_MODEL
        self._tool_session_factory = tool_session_factory or SessionLocal
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = get_async_openai_client()
        return self._client

    async def run(
        self,
        *,
        task: str,
        agent_type_name: str,
        context: str | None = None,
    ) -> str:
        """Run a sub-agent to completion and return the result.

        Args:
            task: What the sub-agent should do (the objective).
            agent_type_name: Which specialist to use (knowledge, research, etc.).
            context: Optional additional context from the parent agent.

        Returns:
            The sub-agent's final response text.
        """
        agent_type = AGENT_TYPES.get(agent_type_name)
        if not agent_type:
            return f"Unknown agent type: {agent_type_name}. Available: {', '.join(AGENT_TYPES.keys())}"

        trace = AgentRunTrace(
            AgentRunContext(
                agent_name=agent_type.name,
                model=self.model,
                prompt_version=f"{agent_type.name}:v1",
            )
        )
        trace.emit(
            AgentEventType.AGENT_STARTED,
            delegated=True,
            max_iterations=agent_type.max_iterations,
        )

        tool_schemas = _get_tool_schemas_for_type(agent_type)
        if not tool_schemas:
            return f"No tools available for agent type: {agent_type_name}"

        # Build isolated context window — fresh message history
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": agent_type.system_prompt},
        ]

        # Add context from parent if provided
        user_content = task
        if context:
            user_content = f"{task}\n\nContext from parent agent:\n{context}"
        messages.append({"role": "user", "content": user_content})

        logger.info(
            "Sub-agent [%s] starting: %s (tools: %d, max_iter: %d)",
            agent_type.name,
            task[:100],
            len(tool_schemas),
            agent_type.max_iterations,
        )

        # Flat tool-calling loop — same pattern as main agent
        final_content = ""
        rounds_used = 0

        for _round in range(agent_type.max_iterations):
            rounds_used = _round + 1
            try:
                trace.emit(
                    AgentEventType.MODEL_STARTED,
                    round=_round + 1,
                    message_count=len(messages),
                )
                response = await self._call_model(messages, tool_schemas)
                trace.emit(
                    AgentEventType.MODEL_COMPLETED,
                    round=_round + 1,
                    tool_call_count=len(response.get("tool_calls", [])),
                )
            except (APITimeoutError, APIError, RateLimitError) as exc:
                logger.error("Sub-agent [%s] API error: %s", agent_type.name, exc)
                return f"Sub-agent error: {exc!s}"

            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            if content:
                final_content = content

            # No tool calls → done
            if not tool_calls:
                break

            # Add assistant message with tool calls
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {
                        "id": tc["call_id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"]),
                        },
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_msg)

            # Execute all tool calls from this model turn concurrently. Each
            # call gets an isolated DB session because SQLAlchemy sessions are
            # not safe to share across concurrent tasks.
            completed_results: dict[str, dict[str, Any]] = {}
            pending_tool_calls = [
                asyncio.create_task(self._run_tool_call(tc, trace=trace)) for tc in tool_calls
            ]
            for pending_tool_call in asyncio.as_completed(pending_tool_calls):
                tc, result = await pending_tool_call
                completed_results[tc["call_id"]] = result

            # Preserve model tool-call order in the transcript sent back to OpenAI.
            for tc in tool_calls:
                result = completed_results.get(
                    tc["call_id"],
                    {"error": f"Tool {tc['name']} did not return a result"},
                )
                result_str = json.dumps(result)
                result_str = _HTML_TAG_RE.sub("", result_str)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["call_id"],
                        "content": result_str,
                    }
                )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You have reached the tool-call budget. Stop calling tools. "
                        "Synthesize the evidence already gathered into the requested final answer. "
                        "If some searches failed, say which ones failed and use the successful "
                        "results instead of returning an empty response."
                    ),
                }
            )
            try:
                trace.emit(
                    AgentEventType.MODEL_STARTED,
                    round=rounds_used + 1,
                    message_count=len(messages),
                    finalization=True,
                )
                final_response = await self._call_model(messages, None)
                trace.emit(
                    AgentEventType.MODEL_COMPLETED,
                    round=rounds_used + 1,
                    tool_call_count=0,
                    finalization=True,
                )
            except (APITimeoutError, APIError, RateLimitError) as exc:
                logger.error("Sub-agent [%s] finalization API error: %s", agent_type.name, exc)
                if final_content:
                    return final_content
                return f"Sub-agent gathered tool results but failed to synthesize them: {exc!s}"
            final_text = final_response.get("content", "")
            if final_text:
                final_content = final_text

        trace.emit(
            AgentEventType.AGENT_COMPLETED,
            rounds_used=rounds_used,
            response_chars=len(final_content),
        )
        logger.info(
            "Sub-agent [%s] completed in %d rounds, response: %d chars, run_id=%s",
            agent_type.name,
            rounds_used,
            len(final_content),
            trace.context.run_id,
        )

        return final_content or "Sub-agent completed but produced no response."

    async def _run_tool_call(
        self,
        tc: dict[str, Any],
        *,
        trace: AgentRunTrace | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute one tool call with timeout, isolation, and event-loop protection."""
        tool_name = tc["name"]
        tool_args = tc["args"]

        def _execute_with_isolated_session() -> dict[str, Any]:
            tool_db = self._tool_session_factory()
            try:
                return asyncio.run(
                    execute_tool_with_harness(
                        tool_name,
                        tool_args,
                        tool_db,
                        trace=trace,
                        executor=execute_tool,
                    )
                )
            finally:
                close = getattr(tool_db, "close", None)
                if close:
                    close()

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_execute_with_isolated_session),
                timeout=60,
            )
        except TimeoutError:
            result = {"error": f"Tool {tool_name} timed out"}
        except Exception as exc:
            result = {"error": f"Tool {tool_name} failed: {exc!s}"}

        return tc, result

    async def _call_model(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Make a single (non-streaming) call to the model.

        Sub-agents don't stream to the client — they run to completion
        and return the full result. This is faster and simpler than
        streaming when the result goes back to a parent agent.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["parallel_tool_calls"] = True

        if uses_max_completion_tokens(self.model):
            kwargs["max_completion_tokens"] = 4096
        else:
            kwargs["max_tokens"] = 4096

        add_temperature_if_supported(
            kwargs,
            model=self.model,
            temperature=settings.llm_temperature,
        )

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        result: dict[str, Any] = {"content": message.content or ""}

        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    {
                        "call_id": tc.id or f"call_{uuid.uuid4().hex[:8]}",
                        "name": tc.function.name,
                        "args": args,
                    }
                )
            result["tool_calls"] = tool_calls

        return result
