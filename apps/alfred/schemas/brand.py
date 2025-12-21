from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ExperienceKind = Literal["job", "project", "publication", "talk", "article", "other"]


class ExperienceItem(BaseModel):
    kind: ExperienceKind = Field(
        ...,
        description="Type of experience item: job, project, publication, talk, article, or other.",
    )
    title: str = Field(..., description="Role / project / publication title.")
    org: str = Field(..., description="Company, school, community, or venue.")
    timeframe: str = Field(..., description="When this happened (e.g., 2023–2024).")
    summary: str = Field(..., description="1–2 sentence summary in first person.")
    impact: list[str] = Field(
        ...,
        description="Concrete outcomes and metrics (bullets). Use numbers when possible.",
    )
    skills: list[str] = Field(..., description="Skills demonstrated.")
    technologies: list[str] = Field(..., description="Tools/tech used.")
    links: list[str] = Field(..., description="Relevant URLs (GitHub, demo, paper, talk).")


class ExperienceInventory(BaseModel):
    headline: str = Field(..., description="1-line positioning statement in first person.")
    highlights: list[str] = Field(..., description="3–7 high-signal highlights (bullets).")
    skills: list[str] = Field(..., description="Key skills (unique, concise).")
    technologies: list[str] = Field(..., description="Key technologies (unique, concise).")
    experiences: list[ExperienceItem] = Field(..., description="Jobs and other experiences.")


class InventoryRequest(BaseModel):
    resume_text: str = Field("", description="Optional raw resume text.")
    linkedin_text: str = Field("", description="Optional raw LinkedIn profile text.")
    github_text: str = Field("", description="Optional raw GitHub profile/projects text.")
    projects_text: str = Field("", description="Optional raw notes about saved projects.")
    extra_context: str = Field("", description="Optional extra background to include.")
    k: int = Field(10, ge=1, le=50, description="Top-k chunks to retrieve from the KB.")


class StarStory(BaseModel):
    title: str = Field(..., description="Short story title.")
    match_reason: str = Field(
        ...,
        description="Why this story best matches the job (1–2 sentences, first person).",
    )
    result_metric: str = Field(
        ...,
        description="First sentence: the result metric or outcome (e.g., 'Cut latency by 40%').",
    )
    situation: str = Field(..., description="Situation (1–2 tight sentences).")
    task: str = Field(..., description="Task (1–2 tight sentences).")
    action: list[str] = Field(..., description="Actions taken (3–6 bullets).")
    result: list[str] = Field(..., description="Results and impact (2–4 bullets).")
    skills: list[str] = Field(..., description="Skills signaled in this story.")
    technologies: list[str] = Field(..., description="Technologies used in this story.")


class StoriesRequest(BaseModel):
    job_description: str = Field(..., min_length=50, description="Full job description text.")
    resume_text: str = Field("", description="Optional resume text (overrides KB retrieval).")
    linkedin_text: str = Field("", description="Optional LinkedIn text.")
    github_text: str = Field("", description="Optional GitHub/projects text.")
    projects_text: str = Field("", description="Optional saved projects notes.")
    extra_context: str = Field("", description="Optional extra background/instructions.")
    k: int = Field(12, ge=1, le=50, description="Top-k chunks to retrieve from the KB.")


class StoriesResponse(BaseModel):
    stories: list[StarStory] = Field(..., description="Exactly 3 best-fit STAR stories.")


class OutreachRequest(BaseModel):
    company: str = Field(..., min_length=2, description="Target company name.")
    role: str = Field("AI Engineer", description="Target role or angle.")
    job_description: str = Field("", description="Optional job description text.")
    resume_text: str = Field("", description="Optional raw resume text.")
    linkedin_text: str = Field("", description="Optional raw LinkedIn profile text.")
    github_text: str = Field("", description="Optional raw GitHub profile/projects text.")
    projects_text: str = Field("", description="Optional raw notes about saved projects.")
    recipient_name: str = Field("", description="Optional recipient name (hiring manager).")
    recipient_title: str = Field("", description="Optional recipient title.")
    channel: Literal["linkedin", "email", "both"] = Field(
        "both", description="Which messages to generate."
    )
    extra_context: str = Field("", description="Optional extra instructions or constraints.")
    k: int = Field(10, ge=1, le=50, description="Top-k chunks to retrieve from the KB.")


class OutreachResponse(BaseModel):
    positioning: list[str] = Field(..., description="3–5 crisp positioning bullets.")
    talking_points: list[str] = Field(..., description="Conversation starters (bullets).")
    linkedin_message: str = Field(..., description="LinkedIn connection message (<= 300 chars).")
    linkedin_follow_up: str = Field(..., description="LinkedIn follow-up message.")
    cold_email_subject: str = Field(..., description="Cold email subject line.")
    cold_email_body: str = Field(..., description="Cold email body (polished, direct).")
    cold_email_follow_up: str = Field(..., description="Email follow-up message.")
    sources: list[str] = Field(..., description="Domains/note titles used.")


class PortfolioModel(BaseModel):
    title: str = Field(..., description="Page title.")
    tagline: str = Field(..., description="1-line tagline.")
    about: str = Field(..., description="Short about section in first person.")
    featured_projects: list[str] = Field(..., description="Featured projects (bullets).")
    publications: list[str] = Field(..., description="Publications (bullets).")
    talks: list[str] = Field(..., description="Talks (bullets).")
    articles: list[str] = Field(..., description="Articles (bullets).")
