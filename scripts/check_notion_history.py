"""Quick script to sanity check Notion history integration."""

from __future__ import annotations

import asyncio
from pprint import pprint

from alfred.core.config import settings
from alfred.services import notion


async def main() -> None:
    if not settings.notion_token:
        raise SystemExit("NOTION_TOKEN is not set in alfred/.env")

    pages = await notion.fetch_page_history(limit=5, include_content=False)
    print(f"Fetched {len(pages)} pages")
    if pages:
        pprint(pages[0])


if __name__ == "__main__":
    asyncio.run(main())
