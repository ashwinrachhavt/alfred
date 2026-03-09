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
from alfred.schemas.imports import (
    CONTENT_TYPE_GITHUB_DISCUSSION,
    CONTENT_TYPE_GITHUB_GIST,
    CONTENT_TYPE_GITHUB_ISSUE,
    CONTENT_TYPE_GITHUB_README,
    CONTENT_TYPE_GITHUB_STARRED,
    ImportStats,
)
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

    stats = ImportStats()

    for owner, repo in repo_pairs:
        slug = f"{owner}/{repo}"
        try:
            readme = client.get_readme(owner, repo)
            if not readme:
                stats.skipped += 1
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
                content_type=CONTENT_TYPE_GITHUB_README,
                raw_markdown=readme,
                cleaned_text=readme,
                hash=stable_hash,
                metadata={"source": "github", "github": repo_meta},
            )

            res = doc_store.ingest_document_store_only(ingest)
            doc_id = str(res["id"])
            if res.get("duplicate"):
                try:
                    doc_store.update_document_text(
                        doc_id,
                        title=f"{slug} — README",
                        cleaned_text=readme,
                        raw_markdown=readme,
                        metadata_update={"source": "github", "github": repo_meta},
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"repo": slug, "document_id": doc_id})
        except Exception as exc:
            logger.exception("GitHub README import failed for %s", slug)
            stats.errors.append({"repo": slug, "error": str(exc)})

    result = stats.to_dict()
    result["type"] = "github_readme"
    return result


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

    stats = ImportStats()

    for owner, repo in repo_pairs:
        slug = f"{owner}/{repo}"
        try:
            issues = client.list_issues(owner, repo, state=state, since=since)
            for issue in issues:
                number = issue.get("number")
                if number is None:
                    stats.skipped += 1
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
                    content_type=CONTENT_TYPE_GITHUB_ISSUE,
                    raw_markdown=markdown,
                    cleaned_text=markdown,
                    hash=stable_hash,
                    metadata={"source": "github", "github_issue": issue_meta},
                )

                res = doc_store.ingest_document_store_only(ingest)
                doc_id = str(res["id"])
                if res.get("duplicate"):
                    try:
                        doc_store.update_document_text(
                            doc_id,
                            title=f"{slug}#{number}: {issue.get('title', 'Untitled')}",
                            cleaned_text=markdown,
                            raw_markdown=markdown,
                            metadata_update={"source": "github", "github_issue": issue_meta},
                        )
                        stats.updated += 1
                    except Exception:
                        logger.debug("Skipping update for duplicate %s", doc_id)
                        stats.skipped += 1
                else:
                    stats.created += 1

                stats.documents.append({"repo": slug, "issue": number, "document_id": doc_id})
        except Exception as exc:
            logger.exception("GitHub issue import failed for %s", slug)
            stats.errors.append({"repo": slug, "error": str(exc)})

    result = stats.to_dict()
    result["type"] = "github_issue"
    return result


def _render_discussion_markdown(discussion: dict[str, Any], slug: str) -> str:
    """Render a discussion as a Markdown document."""
    lines: list[str] = []
    title = discussion.get("title", "Untitled Discussion")
    number = discussion.get("number", "?")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Repository:** {slug} | **Discussion:** #{number}")
    lines.append("")

    labels = discussion.get("labels", {}).get("nodes") or []
    if labels:
        label_names = [lb.get("name", "") for lb in labels]
        if label_names:
            lines.append(f"**Labels:** {', '.join(label_names)}")
            lines.append("")

    author = (discussion.get("author") or {}).get("login", "unknown")
    lines.append(f"**Author:** {author}")
    lines.append("")

    body = (discussion.get("body") or "").strip()
    if body:
        lines.append(body)
    else:
        lines.append("_No description provided._")
    lines.append("")

    # Accepted answer
    answer = discussion.get("answer")
    if answer:
        ans_author = (answer.get("author") or {}).get("login", "unknown")
        ans_body = (answer.get("body") or "").strip()
        lines.append("---")
        lines.append(f"## Accepted Answer (by {ans_author})")
        lines.append("")
        lines.append(ans_body)
        lines.append("")

    # Comments
    comments = (discussion.get("comments") or {}).get("nodes") or []
    if comments:
        lines.append("---")
        lines.append("## Comments")
        lines.append("")
        for comment in comments:
            c_author = (comment.get("author") or {}).get("login", "unknown")
            c_body = (comment.get("body") or "").strip()
            lines.append(f"### Comment by {c_author}")
            lines.append("")
            lines.append(c_body)
            lines.append("")

    return "\n".join(lines)


def _render_gist_markdown(gist: dict[str, Any]) -> str:
    """Render a gist as a Markdown document."""
    lines: list[str] = []
    description = gist.get("description") or "Untitled Gist"
    lines.append(f"# {description}")
    lines.append("")

    files = gist.get("files") or {}
    for filename, file_info in files.items():
        content = (file_info.get("content") or "").strip()
        language = file_info.get("language") or ""
        lines.append(f"## {filename}")
        lines.append("")
        lang_hint = language.lower() if language else ""
        lines.append(f"```{lang_hint}")
        lines.append(content)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def import_starred(
    *,
    doc_store: DocStorageService,
    client: GitHubClient | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Import README files from starred repos into the document store."""
    client = client or GitHubClient()

    stats = ImportStats()

    starred = client.list_starred()
    if limit:
        starred = starred[:limit]

    for repo_data in starred:
        owner = (repo_data.get("owner") or {}).get("login", "")
        repo = repo_data.get("name", "")
        slug = f"{owner}/{repo}"
        if not owner or not repo:
            stats.skipped += 1
            continue

        try:
            readme = client.get_readme(owner, repo)
            if not readme:
                stats.skipped += 1
                logger.debug("No README for starred repo %s", slug)
                continue

            html_url = repo_data.get("html_url", f"https://github.com/{slug}")
            stable_hash = f"github:starred:{slug}"

            repo_meta = {
                "owner": owner,
                "repo": repo,
                "description": repo_data.get("description"),
                "stars": repo_data.get("stargazers_count"),
                "language": repo_data.get("language"),
                "topics": repo_data.get("topics", []),
            }

            ingest = DocumentIngest(
                source_url=html_url,
                title=f"{slug} — Starred README",
                content_type=CONTENT_TYPE_GITHUB_STARRED,
                raw_markdown=readme,
                cleaned_text=readme,
                hash=stable_hash,
                metadata={"source": "github", "github_starred": repo_meta},
            )

            res = doc_store.ingest_document_store_only(ingest)
            doc_id = str(res["id"])
            if res.get("duplicate"):
                try:
                    doc_store.update_document_text(
                        doc_id,
                        title=f"{slug} — Starred README",
                        cleaned_text=readme,
                        raw_markdown=readme,
                        metadata_update={"source": "github", "github_starred": repo_meta},
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"repo": slug, "document_id": doc_id})
        except Exception as exc:
            logger.exception("GitHub starred import failed for %s", slug)
            stats.errors.append({"repo": slug, "error": str(exc)})

    result = stats.to_dict()
    result["type"] = "github_starred"
    return result


def import_gists(
    *,
    doc_store: DocStorageService,
    client: GitHubClient | None = None,
    since: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Import gists from GitHub into the document store."""
    client = client or GitHubClient()

    stats = ImportStats()

    gists = client.list_gists(since=since)
    if limit:
        gists = gists[:limit]

    for gist_summary in gists:
        gist_id = gist_summary.get("id", "")
        if not gist_id:
            stats.skipped += 1
            continue

        try:
            gist = client.get_gist(gist_id)
            description = gist.get("description") or "Untitled Gist"
            html_url = gist.get("html_url", f"https://gist.github.com/{gist_id}")
            stable_hash = f"github:gist:{gist_id}"

            markdown = _render_gist_markdown(gist)

            gist_meta = {
                "gist_id": gist_id,
                "description": description,
                "public": gist.get("public"),
                "created_at": gist.get("created_at"),
                "updated_at": gist.get("updated_at"),
                "files": list((gist.get("files") or {}).keys()),
            }

            ingest = DocumentIngest(
                source_url=html_url,
                title=f"Gist: {description}",
                content_type=CONTENT_TYPE_GITHUB_GIST,
                raw_markdown=markdown,
                cleaned_text=markdown,
                hash=stable_hash,
                metadata={"source": "github", "github_gist": gist_meta},
            )

            res = doc_store.ingest_document_store_only(ingest)
            doc_id = str(res["id"])
            if res.get("duplicate"):
                try:
                    doc_store.update_document_text(
                        doc_id,
                        title=f"Gist: {description}",
                        cleaned_text=markdown,
                        raw_markdown=markdown,
                        metadata_update={"source": "github", "github_gist": gist_meta},
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"gist_id": gist_id, "document_id": doc_id})
        except Exception as exc:
            logger.exception("GitHub gist import failed for %s", gist_id)
            stats.errors.append({"gist_id": gist_id, "error": str(exc)})

    result = stats.to_dict()
    result["type"] = "github_gist"
    return result


def import_discussions(
    *,
    doc_store: DocStorageService,
    client: GitHubClient | None = None,
    repos: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Import discussions from GitHub repos into the document store."""
    client = client or GitHubClient()
    repos_cfg = repos if repos is not None else settings.github_repos
    repo_pairs = _resolve_repos(client, repos_cfg or None)

    stats = ImportStats()

    for owner, repo in repo_pairs:
        slug = f"{owner}/{repo}"
        try:
            discussions = client.list_discussions(owner, repo)
            if limit:
                discussions = discussions[:limit]

            for discussion in discussions:
                number = discussion.get("number")
                if number is None:
                    stats.skipped += 1
                    continue

                discussion_url = f"https://github.com/{slug}/discussions/{number}"
                stable_hash = f"github:discussion:{slug}/{number}"
                markdown = _render_discussion_markdown(discussion, slug)

                disc_meta = {
                    "owner": owner,
                    "repo": repo,
                    "number": number,
                    "title": discussion.get("title"),
                    "author": (discussion.get("author") or {}).get("login"),
                    "labels": [
                        lb.get("name")
                        for lb in (discussion.get("labels", {}).get("nodes") or [])
                    ],
                    "created_at": discussion.get("createdAt"),
                    "updated_at": discussion.get("updatedAt"),
                    "has_answer": discussion.get("answer") is not None,
                }

                ingest = DocumentIngest(
                    source_url=discussion_url,
                    title=f"{slug} Discussion #{number}: {discussion.get('title', 'Untitled')}",
                    content_type=CONTENT_TYPE_GITHUB_DISCUSSION,
                    raw_markdown=markdown,
                    cleaned_text=markdown,
                    hash=stable_hash,
                    metadata={"source": "github", "github_discussion": disc_meta},
                )

                res = doc_store.ingest_document_store_only(ingest)
                doc_id = str(res["id"])
                if res.get("duplicate"):
                    try:
                        doc_store.update_document_text(
                            doc_id,
                            title=f"{slug} Discussion #{number}: {discussion.get('title', 'Untitled')}",
                            cleaned_text=markdown,
                            raw_markdown=markdown,
                            metadata_update={"source": "github", "github_discussion": disc_meta},
                        )
                        stats.updated += 1
                    except Exception:
                        logger.debug("Skipping update for duplicate %s", doc_id)
                        stats.skipped += 1
                else:
                    stats.created += 1

                stats.documents.append({"repo": slug, "discussion": number, "document_id": doc_id})
        except Exception as exc:
            logger.exception("GitHub discussion import failed for %s", slug)
            stats.errors.append({"repo": slug, "error": str(exc)})

    result = stats.to_dict()
    result["type"] = "github_discussion"
    return result


def import_github(
    *,
    doc_store: DocStorageService,
    repos: list[str] | None = None,
    state: str = "all",
    since: str | None = None,
    include_starred: bool = False,
    include_gists: bool = False,
    include_discussions: bool = False,
) -> dict[str, Any]:
    """Import READMEs, issues, and optionally starred/gists/discussions from GitHub."""
    client = GitHubClient()

    readme_result = import_readmes(doc_store=doc_store, client=client, repos=repos)
    issues_result = import_issues(
        doc_store=doc_store, client=client, repos=repos, state=state, since=since
    )

    result: dict[str, Any] = {
        "ok": True,
        "readmes": readme_result,
        "issues": issues_result,
    }

    if include_starred:
        result["starred"] = import_starred(doc_store=doc_store, client=client)

    if include_gists:
        result["gists"] = import_gists(doc_store=doc_store, client=client, since=since)

    if include_discussions:
        result["discussions"] = import_discussions(doc_store=doc_store, client=client, repos=repos)

    return result


__all__ = [
    "import_discussions",
    "import_gists",
    "import_github",
    "import_issues",
    "import_readmes",
    "import_starred",
]
