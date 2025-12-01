"""Minimal demo showing Agno Agent using Alfred tools.

Run:
    uv run python scripts/demo_agno_tools.py

Requires OPENAI_API_KEY or a configured Ollama per settings.
"""

from __future__ import annotations

import logging
import os

from alfred.core import agno_tracing
from alfred.core.llm import make_chat_model
from alfred.core.logging import setup_logging
from alfred.services.tools import search_web, wiki_lookup
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    setup_logging()
    log = logging.getLogger("demo.agno")

    try:
        from agno.agent import Agent
    except Exception as exc:  # pragma: no cover - environment path
        log.error("Agno not installed or import failed: %s", exc)
        return

    # Prefer OpenAI when key is present; otherwise fall back to Ollama per settings
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY not set; using configured local model if available")

    model = make_chat_model()
    agent = Agent(model=model, tools=[search_web, wiki_lookup], markdown=True)

    prompt = "Find a short summary of LangGraph and latest mentions on the web."
    log.info("Running demo prompt: %s", prompt)

    # Initialize MLflow tracing if configured and record a single run
    agno_tracing.init()
    with agno_tracing.agent_run("DemoWebAgent", {"prompt": prompt}):
        result = agent.run(prompt)
        agno_tracing.log_output(getattr(result, "content", result))
        log.info("Agent response:\n%s", getattr(result, "content", result))


if __name__ == "__main__":
    main()
