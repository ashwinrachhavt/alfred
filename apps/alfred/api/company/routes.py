from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from alfred.services.company_outreach import generate_company_outreach
from alfred.services.company_researcher import research_company

router = APIRouter(prefix="/company", tags=["company"])


@router.get("/research")
async def company_research(name: str = Query(..., description="Company name")):
    try:
        report = research_company(name)
        return {"company": name, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/outreach")
async def company_outreach(
    name: str = Query(..., description="Company name"),
    role: str = Query("AI Engineer", description="Target role or angle for the outreach"),
):
    try:
        payload = generate_company_outreach(company=name, role=role)
        return {"company": name, "role": role, **payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OutreachRequest(BaseModel):
    name: str = Field(..., description="Company name")
    role: str | None = Field("AI Engineer", description="Target role or outreach angle")
    context: str | None = Field(
        None,
        description="Optional extra context or instructions to personalize the outreach output.",
    )
    k: int | None = Field(
        None, description="Optional top-k documents to retrieve from the personal knowledge base"
    )


@router.post("/outreach")
async def company_outreach_post(payload: OutreachRequest):
    try:
        data = generate_company_outreach(
            company=payload.name,
            role=payload.role or "AI Engineer",
            personal_context=payload.context or "",
            k=payload.k or 6,
        )
        return {"company": payload.name, "role": payload.role or "AI Engineer", **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
