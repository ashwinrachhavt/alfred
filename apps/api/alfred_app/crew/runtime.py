import asyncio
from typing import Callable, Awaitable, Any, Optional

from alfred_app.crew.tools import web_search_tool, style_writer_tool

StepCallback = Optional[Callable[[dict], Awaitable[Any]]]


async def kickoff_research_writer(topic: str, step_callback: StepCallback = None) -> str:
    """
    Minimal, dependency-light implementation that mimics a research->writer pipeline.
    Avoids importing heavy CrewAI at module import time. Emits simple step events.
    """
    async def emit(msg: dict):
        if step_callback:
            await step_callback(msg)

    await emit({"type": "step", "phase": "research", "status": "start", "topic": topic})
    # Very light mock "research" using the web_search_tool util
    urls = web_search_tool(topic)
    await asyncio.sleep(0.05)
    await emit({"type": "step", "phase": "research", "status": "done", "results": urls})

    await emit({"type": "step", "phase": "synthesis", "status": "start"})
    bullets = [f"Key source: {u}" for u in urls[:3]] or ["No sources found"]
    await asyncio.sleep(0.05)
    await emit({"type": "step", "phase": "synthesis", "status": "done", "bullets": bullets})

    await emit({"type": "step", "phase": "writing", "status": "start"})
    output = style_writer_tool(topic, bullets)
    await asyncio.sleep(0.02)
    await emit({"type": "step", "phase": "writing", "status": "done"})
    return output
