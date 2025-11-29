"""
Quick connectivity test for the Linear connector.

Uses LINEAR_API_KEY from environment (or settings if present) to call GraphQL
and list a few issues. Exits non-zero on failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    # Ensure `alfred` package is importable when run from repo root
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.append(str(repo_root / "apps"))

    # Local imports after sys.path adjustment (avoid E402)
    from alfred.connectors.linear_connector import LinearConnector
    try:
        from alfred.core.config import settings  # type: ignore
    except Exception:  # pragma: no cover
        settings = None  # type: ignore

    # Also load .env explicitly to catch local runs in subdirs
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(repo_root / "apps" / "alfred" / ".env")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Test Linear Connector")
    parser.add_argument("--start", dest="start_date", help="Start date YYYY-MM-DD", default=None)
    parser.add_argument("--end", dest="end_date", help="End date YYYY-MM-DD", default=None)
    parser.add_argument(
        "--no-comments", dest="include_comments", action="store_false", help="Exclude comments"
    )
    parser.set_defaults(include_comments=True)
    args = parser.parse_args()

    token = None
    if settings is not None:
        token = getattr(settings, "linear_api_key", None)
    token = token or os.getenv("LINEAR_API_KEY")

    if not token:
        print("LINEAR_API_KEY is not set in environment or settings")
        return 2

    client = LinearConnector(token)

    try:
        if args.start_date and args.end_date:
            issues, err = client.get_issues_by_date_range(
                args.start_date, args.end_date, include_comments=args.include_comments
            )
            if err:
                print(f"Linear connectivity test failed: {err}")
                return 1
        else:
            issues = client.get_all_issues(include_comments=args.include_comments)

        count = len(issues)
        sample_ids = []
        for it in issues[:3]:
            ident = it.get("identifier") or it.get("id")
            title = (it.get("title") or "").strip()
            if ident:
                sample_ids.append(f"{ident}: {title[:40]}")
        sample = ", ".join(sample_ids)
        print(f"OK: Retrieved {count} issues. Sample: {sample}")
        return 0
    except Exception as exc:
        print(f"Linear connectivity test failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
