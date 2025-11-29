"""
Quick connectivity test for the Slack connector.

Requires SLACK_API_KEY in alfred/.env or environment.

Checks:
- List channels the bot can access (names + IDs)
- Optionally fetch a short history for a given channel and date range
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    # Ensure `alfred` package is importable when run from repo root
    repo_root = Path(__file__).resolve().parents[1]
    apps_dir = repo_root / "apps"
    if str(apps_dir) not in sys.path:
        sys.path.append(str(apps_dir))
    try:  # Load env/disable pyc via sitecustomize
        import sitecustomize  # noqa: F401
    except Exception:
        pass

    # Local imports after sys.path adjustment (avoid E402)
    try:
        from alfred.core.config import settings  # type: ignore
    except Exception:
        settings = None  # type: ignore
    from alfred.connectors.slack_history import SlackHistory

    parser = argparse.ArgumentParser(description="Test Slack Connector")
    parser.add_argument("--channel", help="Channel ID to fetch messages from", default=None)
    parser.add_argument("--start", help="Start date YYYY-MM-DD", default=None)
    parser.add_argument("--end", help="End date YYYY-MM-DD", default=None)
    parser.add_argument("--limit", type=int, default=200, help="Max messages to fetch")
    parser.add_argument("--public-only", action="store_true", help="List only public channels")
    args = parser.parse_args()

    token = None
    if settings is not None:
        token = getattr(settings, "slack_api_key", None)
    token = token or os.getenv("SLACK_API_KEY")

    if not token:
        print("SLACK_API_KEY is not set in environment or settings")
        return 2

    client = SlackHistory(token)

    # Verify token type and workspace via auth.test for a clearer error message
    try:
        from slack_sdk import WebClient  # type: ignore

        wc = WebClient(token=token)
        info = wc.auth_test()
        team = info.get("team")
        user_id = info.get("user_id")
        token_prefix = token.split("-", 1)[0]
        print(f"OK: auth.test passed (team={team}, user={user_id}, token={token_prefix}-…)")
    except Exception as exc:  # pragma: no cover
        # Common cause: not_allowed_token_type (e.g., xapp-*). Provide guidance.
        pref = token.split("-", 1)[0]
        print(
            "Slack auth.test failed. If error shows 'not_allowed_token_type', use a Bot User OAuth token (xoxb-…) with conversations:read scopes.\n"
            f"Current token prefix: {pref}-… | Error: {exc}"
        )

    # List channels
    try:
        channels = client.get_all_channels(include_private=not args.public_only)
        count = len(channels)
        sample = ", ".join([f"#{c.get('name')}({c.get('id')})" for c in channels[:5]])
        print(f"OK: Slack reachable. Channels: {count}. Sample: {sample}")
    except Exception as exc:
        pref = token.split("-", 1)[0]
        msg = (
            "Slack connectivity test failed (channels). If you see 'not_allowed_token_type',\n"
            "switch to a Bot User OAuth Token (xoxb-…) with scopes: channels:read, groups:read.\n"
            "For DMs/MPIM, add im:read, mpim:read."
        )
        print(f"{msg}\nToken prefix: {pref}-…\nError: {exc}")
        return 1

    # Optional: fetch history for a channel
    if args.channel and args.start and args.end:
        try:
            msgs, err = client.get_history_by_date_range(
                channel_id=args.channel, start_date=args.start, end_date=args.end, limit=args.limit
            )
            if err:
                print(f"Slack history error: {err}")
                return 1
            print(f"OK: Retrieved {len(msgs)} messages from {args.channel}")
        except Exception as exc:
            print(f"Slack history test failed: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
