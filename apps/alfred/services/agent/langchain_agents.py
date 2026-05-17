"""Global LangChain/Deep Agents factories for Alfred.

All new LangChain 1.x agents should be created through this module, not by
calling `langchain.agents.create_agent` or `deepagents.create_deep_agent`
directly. This is the code-level enforcement point for Alfred's global harness
middleware.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from alfred.services.agent.langchain_middleware import (
    LangChainMiddlewareConfig,
    build_default_middlewares,
)

ResponseT = TypeVar("ResponseT")


ToolLike = BaseTool | Any


def create_alfred_agent(
    *,
    model: str | BaseChatModel,
    tools: Sequence[ToolLike] | None = None,
    system_prompt: str | None = None,
    middleware_config: LangChainMiddlewareConfig | None = None,
    **kwargs: Any,
) -> Any:
    """Create a LangChain 1.x agent with Alfred's global middleware stack."""

    from langchain.agents import create_agent

    middleware = [
        *build_default_middlewares(middleware_config),
        *list(kwargs.pop("middleware", ())),
    ]
    return create_agent(
        model=model,
        tools=cast(Sequence[BaseTool | Any] | None, tools),
        system_prompt=system_prompt,
        middleware=middleware,
        **kwargs,
    )


def create_alfred_deep_agent(
    *,
    model: str | BaseChatModel | None = None,
    tools: Sequence[ToolLike] | None = None,
    system_prompt: str | None = None,
    subagents: Sequence[Any] | None = None,
    middleware_config: LangChainMiddlewareConfig | None = None,
    **kwargs: Any,
) -> Any:
    """Create a Deep Agents graph with Alfred's global middleware stack."""

    from deepagents import create_deep_agent

    middleware = [
        *build_default_middlewares(middleware_config),
        *list(kwargs.pop("middleware", ())),
    ]
    return create_deep_agent(
        model=model,
        tools=cast(Sequence[BaseTool | Any] | None, tools),
        system_prompt=system_prompt,
        subagents=subagents,
        middleware=middleware,
        **kwargs,
    )


__all__ = ["create_alfred_agent", "create_alfred_deep_agent"]
