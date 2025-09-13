from fastapi import APIRouter

router = APIRouter(prefix="/crewai", tags=["crewai"])

@router.post("/run")
async def crew_run(topic: str):
    # Lazy import to prevent import-time failures
    from alfred_app.crew.runtime import kickoff_research_writer
    result = await kickoff_research_writer(topic)
    return {"topic": topic, "result": result}
