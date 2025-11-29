"""
Quick connectivity test for the Airtable connector.

Uses `AIRTABLE_API_KEY` from settings to call `/meta/bases`.
Prints a short summary and exits non-zero on failure.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from scripts._bootstrap import bootstrap


logger = logging.getLogger("scripts.test_airtable_connection")


def main() -> int:
    import argparse

    # Ensure `alfred` package is importable and env loaded
    bootstrap()

    from alfred.connectors.airtable_connector import AirtableConnector
    from alfred.core.config import settings
    from alfred.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase

    parser = argparse.ArgumentParser(description="Test Airtable Connector")
    parser.add_argument("--base-id", dest="base_id", help="Airtable Base ID", default=None)
    parser.add_argument("--table", dest="table_id", help="Airtable Table ID or name", default=None)
    args = parser.parse_args()

    api_key = settings.airtable_api_key
    if not api_key:
        logger.error("AIRTABLE_API_KEY is not set in environment or .env")
        return 2

    connector = AirtableConnector(AirtableAuthCredentialsBase(access_token=api_key))
    bases, err = connector.get_bases()
    if err:
        logger.error("Airtable connectivity test failed: %s", err)
        return 1

    count = len(bases)
    sample = ", ".join([b.get("name", b.get("id", "?")) for b in bases[:3]])
    logger.info("OK: Accessible bases: %d. Sample: %s", count, sample)

    # Optional: test listing a few records if base and table provided
    if args.base_id and args.table_id:
        rows, _, err = connector.get_records(args.base_id, args.table_id, max_records=5)
        if err:
            logger.error("Fetch records failed: %s", err)
            return 1
        logger.info("OK: Retrieved %d records from %s", len(rows), args.table_id)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
