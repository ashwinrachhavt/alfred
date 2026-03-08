"""Ingest GitHub repository content into Alfred's document store.

Imports READMEs and issues from configured (or all user) repositories.
Uses a stable hash per document to support idempotent upserts.
"""

from __future__ import annotations

import logging
from typing import Any

from alfred.connectors.github_connector import GitHubClient
from alfred.core.settings import settings
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _resolve_repos(client: GitHubClient, repos: list[str] | None = None) -> list[tuple[str, str]]:
    """Return (owner, repo) pairs from explicit list or auto-discovery."""
    if repos:
        pairs: list[tuple[str, str]] = []
        for slug in repos:
            parts = slug.strip().split("/")
            if len(parts) != 2:  # noqa: PLR2004
                logger.warning("Skipping invalid repo slug: %s", slug)
                continue
            pairs.append((parts[0], parts[1]))
        return pairs

    # Auto-discover from authenticated user repos
    raw = client.list_user_repos()
    return [(r["owner"]["login"], r["name"]) for r in raw if r.get("owner")]


def _render_issue_markdown(issue: dict[str, Any]) -> str:
    """Render an issue as a Markdown document."""
    lines: list[str] = []
    title = issue.get("title", "Untitled Issue")
    lines.append(f"# {title}")
    lines.append("")

    labels = issue.get("labels") or []
    if labels:
        label_names = [lb.get("name", "") for lb in labels if isinstance(lb, dict)]
        if label_names:
            lines.append(f"**Labels:** {', '.join(label_names)}")
            lines.append("")

    state = issue.get("state", "unknown")
    number = issue.get("number", "?")
    lines.append(f"**State:** {state} | **Number:** #{number}")
    lines.append("")

    body = (issue.get("body") or "").strip()
    if body:
        lines.append(body)
    else:
        lines.append("_No description provided._")

    return "\n".join(lines)


def import_readmes(
    *,
    doc_store: DocStorageService,
    client: GitHubClient | None = None,
    repos: list[str] | None = None,
) -> dict[str, Any]:
    """Import README files from GitHub repos into the document store."""
    client = client or GitHubClient()
    repos_cfg = repos if repos is not None else settings.github_repos
    repo_pairs = _resolve_repos(client, repos_cfg or None)

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []

    for owner, repo in repo_pairs:
        slug = f"{owner}/{repo}"
        try:
            readme = client.get_readme(owner, repo)
            if not readme:
                skipped += 1
                logger.debug("No README for %s", slug)
                continue

            metadata = client.get_repo_metadata(owner, repo)
            html_url = metadata.get("html_url", f"https://github.com/{slug}")
            stable_hash = f"github:readme:{slug}"

            repo_meta = {
                "owner": owner,
                "repo": repo,
                "description": metadata.get("description"),
                "stars": metadata.get("stargazers_count"),
                "language": metadata.get("language"),
                "topics": metadata.get("topics", []),
            }

            ingest = DocumentIngest(
                source_url=html_url,
                title=f"{slug} — README",
                content_type="github_readme",
                raw_markdown=readme,
                cleaned_text=readme,
                hash=stable_hash,
                metadata={"source": "github", "github": repo_meta},
            )

            res = doc_store.ingest_document_store_only(ingest)
            doc_id = str(res["id"])
            if res.get("duplicate"):
                updated += 1
                doc_store.update_document_text(
                    doc_id,
                    title=f"{slug} — README",
                    cleaned_text=readme,
                    raw_markdown=readme,
                    metadata_update={"source": "github", "github": repo_meta},
                )
            else:
                created += 1

            documents.append({"repo": slug, "document_id": doc_id})
        except Exception as exc:
            logger.exception("GitHub README import failed for %s", slug)
            errors.append({"repo": slug, "error": str(exc)})

    return {
        "ok": True,
        "type": "github_readme",
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "documents": documents,
    }


def import_issues(
    *,
    doc_store: DocStorageService,
    client: GitHubClient | None = None,
    repos: list[str] | None = None,
    state: str = "all",
    since: str | None = None,
) -> dict[str, Any]:
    """Import issues from GitHub repos into the document store."""
    client = client or GitHubClient()
    repos_cfg = repos if repos is not None else settings.github_repos
    repo_pairs = _resolve_repos(client, repos_cfg or None)

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []

    for owner, repo in repo_pairs:
        slug = f"{owner}/{repo}"
        try:
            issues = client.list_issues(owner, repo, state=state, since=since)
            for issue in issues:
                number = issue.get("number")
                if number is None:
                    skipped += 1
                    continue

                issue_url = issue.get("html_url", f"https://github.com/{slug}/issues/{number}")
                stable_hash = f"github:issue:{slug}/{number}"
                markdown = _render_issue_markdown(issue)

                issue_meta = {
                    "owner": owner,
                    "repo": repo,
                    "number": number,
                    "state": issue.get("state"),
                    "labels": [lb.get("name") for lb in (issue.get("labels") or []) if isinstance(lb, dict)],
                    "created_at": issue.get("created_at"),
                    "updated_at": issue.get("updated_at"),
                }

                ingest = DocumentIngest(
                    source_url=issue_url,
                    title=f"{slug}#{number}: {issue.get('title', 'Untitled')}",
                    content_type="github_issue",
                    raw_markdown=markdown,
                    cleaned_text=markdown,
                    hash=stable_hash,
                    metadata={"source": "github", "github_issue": issue_meta},
                )

                res = doc_store.ingest_document_store_only(ingest)
                doc_id = str(res["id"])
                if res.get("duplicate"):
                    updated += 1
                    doc_store.update_document_text(
                        doc_id,
                        title=f"{slug}#{number}: {issue.get('title', 'Untitled')}",
                        cleaned_text=markdown,
                        raw_markdown=markdown,
                        metadata_update={"source": "github", "github_issue": issue_meta},
                    )
                else:
                    created += 1

                documents.append({"repo": slug, "issue": number, "document_id": doc_id})
        except Exception as exc:
            logger.exception("GitHub issue import failed for %s", slug)
            errors.append({"repo": slug, "error": str(exc)})

    return {
        "ok": True,
        "type": "github_issue",
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "documents": documents,
    }


def import_github(
    *,
    doc_store: DocStorageService,
    repos: list[str] | None = None,
    state: str = "all",
    since: str | None = None,
) -> dict[str, Any]:
    """Import both READMEs and issues from GitHub into the document store."""
    client = GitHubClient()

    readme_result = import_readmes(doc_store=doc_store, client=client, repos=repos)
    issues_result = import_issues(
        doc_store=doc_store, client=client, repos=repos, state=state, since=since
    )

    return {
        "ok": True,
        "readmes": readme_result,
        "issues": issues_result,
    }


__all__ = [
    "import_github",
    "import_issues",
    "import_readmes",
]
