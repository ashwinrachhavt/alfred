"""Adapters for building LangChain tools from Alfred services.

Goal: keep business logic in services (DI-friendly), and expose a thin tool layer
that agents/graphs can compose.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

TInput = TypeVar("TInput", bound=BaseModel)


def structured_tool(
    *,
    name: str,
    description: str,
    args_schema: type[TInput],
    func: Callable[..., Any],
) -> BaseTool:
    """Create a structured LangChain tool with an explicit Pydantic schema."""

    return StructuredTool.from_function(
        func,
        name=name,
        description=description,
        args_schema=args_schema,
    )
