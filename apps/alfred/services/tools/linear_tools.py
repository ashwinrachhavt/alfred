from __future__ import annotations

import logging
from typing import Optional

from alfred.services.linear import LinearService

logger = logging.getLogger(__name__)


def linear_list_issues(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
    include_comments: bool = False,
) -> str:
    """Fetch issues from Linear and render them as markdown.

    If `start_date` and `end_date` are provided (YYYY-MM-DD), returns issues
    created/updated within that range.
    """

    try:
        svc = LinearService()
    except Exception as exc:
        return f"### Linear\n\n⚠️ Linear not configured. Error: {exc}"

    try:
        if (start_date and not end_date) or (end_date and not start_date):
            return "### Linear\n\n⚠️ Provide both start_date and end_date (YYYY-MM-DD)."

        if start_date and end_date:
            issues = svc.list_issues_by_date_range(
                start_date=start_date,
                end_date=end_date,
                include_comments=include_comments,
                limit=limit,
            )
            title = f"### Linear Issues ({start_date} → {end_date})"
        else:
            issues = svc.list_issues(include_comments=include_comments, limit=limit)
            title = "### Linear Issues"

        if not issues:
            return f"{title}\n\nNo issues found."

        rendered = "\n\n---\n\n".join(svc.issue_to_markdown(issue) for issue in issues)
        return f"{title}\n\n{rendered}"
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Linear list issues failed: %s", exc)
        return f"### Linear\n\n⚠️ Failed to fetch issues. Error: {exc}"
