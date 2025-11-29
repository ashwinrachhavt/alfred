"""
Quick connectivity test for the Airtable connector.

Uses `AIRTABLE_API_KEY` from settings to call `/meta/bases`.
Prints a short summary and exits non-zero on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure `alfred` package is importable when run from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "apps"))

from alfred.core.config import settings
from alfred.connectors.airtable_connector import AirtableConnector
from alfred.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Test Airtable Connector")
    parser.add_argument("--base-id", dest="base_id", help="Airtable Base ID", default=None)
    parser.add_argument("--table", dest="table_id", help="Airtable Table ID or name", default=None)
    args = parser.parse_args()

    api_key = settings.airtable_api_key
    if not api_key:
        print("AIRTABLE_API_KEY is not set in environment or .env")
        return 2

    connector = AirtableConnector(AirtableAuthCredentialsBase(access_token=api_key))
    bases, err = connector.get_bases()
    if err:
        print(f"Airtable connectivity test failed: {err}")
        return 1

    count = len(bases)
    sample = ", ".join([b.get("name", b.get("id", "?")) for b in bases[:3]])
    print(f"OK: Accessible bases: {count}. Sample: {sample}")

    # Optional: test listing a few records if base and table provided
    if args.base_id and args.table_id:
        rows, _, err = connector.get_records(args.base_id, args.table_id, max_records=5)
        if err:
            print(f"Fetch records failed: {err}")
            return 1
        print(f"OK: Retrieved {len(rows)} records from {args.table_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
