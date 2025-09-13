from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import asyncio, json

router = APIRouter(prefix="/stream", tags=["stream"])

def sse_event(data: dict, event: str = "message"):
    return {"event": event, "data": json.dumps(data)}

@router.get("/crewai")
async def stream_crewai(request: Request, topic: str):
    """
    SSE stream of a single CrewAI run (Research -> Writer).
    Streams step logs + a simple token mock.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def push(msg: dict, ev="message"):
        await queue.put(sse_event(msg, ev))

    async def token_stream_mock():
        # Swap with real model streaming if you wire OpenAI stream=True yourself
        for ch in ["Thinking ", "… ", "done."]:
            await push({"type": "token", "text": ch})
            await asyncio.sleep(0.12)

    async def run():
        try:
            await push({"type": "start", "topic": topic}, "start")
            # Import lazily to avoid import-time errors if CrewAI optional
            from alfred_app.crew.runtime import kickoff_research_writer
            result = await kickoff_research_writer(topic, step_callback=lambda m: asyncio.create_task(push(m)))
            await push({"type": "result", "text": result}, "result")
            await push({"type": "end"}, "end")
        except Exception as e:
            await push({"type": "error", "error": str(e)}, "error")

    async def event_generator():
        runner = asyncio.create_task(run())
        streamer = asyncio.create_task(token_stream_mock())
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield ev
                except asyncio.TimeoutError:
                    continue
        finally:
            runner.cancel(); streamer.cancel()

    return EventSourceResponse(event_generator(), ping=20000)
