"""Quick script to sanity check Notion history integration."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure `apps/` on sys.path and env loaded via sitecustomize
from scripts._bootstrap import bootstrap
bootstrap()

from alfred.core.config import settings
from alfred.services import notion


async def main() -> None:
    if not settings.notion_token:
        raise SystemExit("NOTION_TOKEN is not set in alfred/.env")

    pages = await notion.fetch_page_history(limit=5, include_content=False)
    logger = logging.getLogger("scripts.check_notion_history")
    logger.info("Fetched %d pages", len(pages))
    if pages:
        logger.info("First page: %s", pages[0])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
