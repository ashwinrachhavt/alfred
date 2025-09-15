from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from alfred.services.company_researcher import research_company

router = APIRouter(prefix="/company", tags=["company"])


@router.get("/research")
async def company_research(name: str = Query(..., description="Company name")):
    try:
        report = research_company(name)
        return {"company": name, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
