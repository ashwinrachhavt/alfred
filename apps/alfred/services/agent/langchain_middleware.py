"""LangChain 1.x middleware defaults for Alfred agents.

Use this when building agents with `langchain.agents.create_agent` or libraries
that pass middleware through to LangGraph-backed agents. The defaults are chosen
for Alfred's harness goals: retry transient failures, cap runaway loops, preserve
context with summarization/editing, provide todo state for complex work, and
redact common PII in model-facing traces.

Filesystem/shell execution middlewares are available but remain opt-in because
turning them on globally would expose every agent to host-side effects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alfred.core.settings import DEFAULT_OPENAI_MODEL, settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LangChainMiddlewareConfig:
    """Configurable defaults for LangChain 1.x agent middleware."""

    model_name: str | None = None
    summary_model_name: str | None = None
    selector_model_name: str | None = None
    enable_summarization: bool = True
    enable_context_editing: bool = True
    enable_todos: bool = True
    enable_pii_redaction: bool = True
    enable_tool_selection: bool = True
    enable_human_in_loop: bool = True
    run_model_call_limit: int = 12
    run_tool_call_limit: int = 30
    max_selected_tools: int = 12
    fallback_models: tuple[str, ...] = ()
    filesystem_root: str | Path | None = None
    enable_filesystem_search: bool = False
    enable_shell: bool = False


def build_default_middlewares(
    config: LangChainMiddlewareConfig | None = None,
) -> list[Any]:
    """Build Alfred's standard LangChain 1.x middleware stack.

    The returned objects are intentionally typed as `Any` because LangChain's
    middleware generics vary between minor versions. Import failures degrade to
    a smaller safe stack instead of breaking non-LangChain agents.
    """

    cfg = config or LangChainMiddlewareConfig()
    model_name = cfg.model_name or settings.llm_model or DEFAULT_OPENAI_MODEL
    summary_model = cfg.summary_model_name or model_name
    selector_model = cfg.selector_model_name or model_name

    try:
        from langchain.agents.middleware import (  # type: ignore[import-not-found]
            ClearToolUsesEdit,
            ContextEditingMiddleware,
            FilesystemFileSearchMiddleware,
            HumanInTheLoopMiddleware,
            LLMToolSelectorMiddleware,
            ModelCallLimitMiddleware,
            ModelFallbackMiddleware,
            ModelRetryMiddleware,
            PIIMiddleware,
            SummarizationMiddleware,
            TodoListMiddleware,
            ToolCallLimitMiddleware,
            ToolRetryMiddleware,
        )
    except Exception:
        logger.exception("Failed to import LangChain 1.x middleware")
        return []

    middleware: list[Any] = [
        ModelRetryMiddleware(max_retries=2),
        ToolRetryMiddleware(max_retries=2),
        ModelCallLimitMiddleware(run_limit=cfg.run_model_call_limit, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=cfg.run_tool_call_limit, exit_behavior="continue"),
    ]

    if cfg.fallback_models:
        middleware.append(ModelFallbackMiddleware(*cfg.fallback_models))

    if cfg.enable_pii_redaction:
        for pii_type in ("email", "credit_card", "ip", "mac_address"):
            middleware.append(
                PIIMiddleware(
                    pii_type,
                    strategy="redact",
                    apply_to_input=True,
                    apply_to_output=False,
                    apply_to_tool_results=True,
                )
            )

    if cfg.enable_context_editing:
        try:
            middleware.append(
                ContextEditingMiddleware(
                    edits=[ClearToolUsesEdit(trigger=60000, clear_at_least=4000, keep=20)]
                )
            )
        except TypeError:
            # LangChain minor versions have changed ClearToolUsesEdit's constructor.
            middleware.append(ContextEditingMiddleware())

    if cfg.enable_summarization:
        middleware.append(
            SummarizationMiddleware(
                model=summary_model,
                trigger=("tokens", 80000),
                keep=("messages", 24),
                trim_tokens_to_summarize=4000,
            )
        )

    if cfg.enable_todos:
        middleware.append(TodoListMiddleware())

    if cfg.enable_tool_selection:
        middleware.append(
            LLMToolSelectorMiddleware(
                model=selector_model,
                max_tools=cfg.max_selected_tools,
                always_include=["delegate_task"],
            )
        )

    if cfg.enable_human_in_loop:
        middleware.append(
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "create_zettel": True,
                    "update_zettel": True,
                    "create_link": True,
                    "batch_link": True,
                    "run_import": True,
                    "import_notes_from_filesystem": True,
                    "delete_zettel": True,
                    "delete_document": True,
                }
            )
        )

    if cfg.enable_filesystem_search:
        if cfg.filesystem_root is None:
            raise ValueError("filesystem_root is required when filesystem search is enabled")
        middleware.append(FilesystemFileSearchMiddleware(root_path=str(cfg.filesystem_root)))

    if cfg.enable_shell:
        # Import lazily so normal application startup does not expose shell execution.
        from langchain.agents.middleware import (
            ShellToolMiddleware,  # type: ignore[import-not-found]
        )

        middleware.append(ShellToolMiddleware(workspace_root=cfg.filesystem_root))

    return middleware


__all__ = ["LangChainMiddlewareConfig", "build_default_middlewares"]
