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
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from sqlmodel import Session

from alfred.core.llm_factory import get_async_openai_client
from alfred.core.settings import settings
from alfred.services.agent.agent_types import AGENT_TYPES, AgentType
from alfred.services.agent.tools import (
    CORE_TOOL_SCHEMAS,
    _lc_tools_cache,
    _load_langchain_tools,
    execute_tool,
)

logger = logging.getLogger(__name__)

# HTML tag stripping for tool results
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Reasoning model prefixes
_REASONING_MODELS = {"o3", "o3-mini", "o4-mini"}
_MAX_COMPLETION_TOKEN_PREFIXES = ("gpt-5",)


def _get_tool_schemas_for_type(agent_type: AgentType) -> list[dict[str, Any]]:
    """Get OpenAI function-calling schemas for a specific agent type's tools."""
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

    def __init__(self, db: Session, *, model: str | None = None) -> None:
        self.db = db
        self.model = model or settings.llm_model or "gpt-5.4"
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

        for _round in range(agent_type.max_iterations):
            try:
                response = await self._call_model(messages, tool_schemas)
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

            # Execute tools and inject results
            for tc in tool_calls:
                try:
                    result = await asyncio.wait_for(
                        execute_tool(tc["name"], tc["args"], self.db),
                        timeout=60,
                    )
                except TimeoutError:
                    result = {"error": f"Tool {tc['name']} timed out"}
                except Exception as exc:
                    result = {"error": f"Tool {tc['name']} failed: {exc!s}"}

                result_str = json.dumps(result)
                result_str = _HTML_TAG_RE.sub("", result_str)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["call_id"],
                        "content": result_str,
                    }
                )

        logger.info(
            "Sub-agent [%s] completed in %d rounds, response: %d chars",
            agent_type.name,
            _round + 1,
            len(final_content),
        )

        return final_content or "Sub-agent completed but produced no response."

    async def _call_model(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Make a single (non-streaming) call to the model.

        Sub-agents don't stream to the client — they run to completion
        and return the full result. This is faster and simpler than
        streaming when the result goes back to a parent agent.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
        }

        if any(self.model.startswith(p) for p in _MAX_COMPLETION_TOKEN_PREFIXES) or any(
            self.model.startswith(p) for p in _REASONING_MODELS
        ):
            kwargs["max_completion_tokens"] = 4096
        else:
            kwargs["max_tokens"] = 4096

        if not any(self.model.startswith(p) for p in _REASONING_MODELS):
            kwargs["temperature"] = settings.llm_temperature

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
