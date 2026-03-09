"""Shared schemas and constants for knowledge import integrations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Content type constants
# ---------------------------------------------------------------------------

CONTENT_TYPE_ARXIV_PAPER = "arxiv_paper"
CONTENT_TYPE_GITHUB_README = "github_readme"
CONTENT_TYPE_GITHUB_ISSUE = "github_issue"
CONTENT_TYPE_GITHUB_STARRED = "github_starred"
CONTENT_TYPE_GITHUB_GIST = "github_gist"
CONTENT_TYPE_GITHUB_DISCUSSION = "github_discussion"
CONTENT_TYPE_GOOGLE_DOC = "google_doc"
CONTENT_TYPE_GOOGLE_TASKS = "google_tasks"
CONTENT_TYPE_HYPOTHESIS_ANNOTATION = "hypothesis_annotation"
CONTENT_TYPE_LINEAR_ISSUE = "linear_issue"
CONTENT_TYPE_NOTION = "notion"
CONTENT_TYPE_POCKET_ARTICLE = "pocket_article"
CONTENT_TYPE_READWISE = "readwise"
CONTENT_TYPE_RSS_ENTRY = "rss_entry"
CONTENT_TYPE_ACADEMIC_PAPER = "academic_paper"
CONTENT_TYPE_SLACK_CHANNEL = "slack_channel"
CONTENT_TYPE_SLACK_BOOKMARK = "slack_bookmark"
CONTENT_TYPE_TODOIST_PROJECT = "todoist_project"


# ---------------------------------------------------------------------------
# Shared API response model
# ---------------------------------------------------------------------------


class ImportResponse(BaseModel):
    """Standard response for all import endpoints."""

    status: str
    result: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Import stats helper
# ---------------------------------------------------------------------------


class ImportStats:
    """Accumulates created/updated/skipped counts and errors during an import run."""

    __slots__ = ("created", "updated", "skipped", "errors", "documents")

    def __init__(self) -> None:
        self.created: int = 0
        self.updated: int = 0
        self.skipped: int = 0
        self.errors: list[dict[str, str]] = []
        self.documents: list[dict[str, str]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "documents": self.documents,
        }
