#!/usr/bin/env python3
"""
Helper script to clear stored Google OAuth credentials.
Use this when you need to re-authenticate with new scopes.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps"))

from alfred.core.database import get_session, init_db
from alfred.core.db_models import GoogleCredential
from dotenv import load_dotenv
from sqlalchemy import delete

load_dotenv("apps/alfred/.env")


async def clear_all_credentials():
    """Clear all stored Google credentials from the database."""
    print("🗑️  Clearing Google OAuth credentials...")

    try:
        await init_db()

        async with get_session() as session:
            result = await session.execute(delete(GoogleCredential))
            await session.commit()
            count = result.rowcount

        print(f"✅ Cleared {count} credential record(s) from database")
        print("\n📝 Next steps:")
        print("   1. Start your server: cd apps/alfred && uvicorn alfred.main:app --reload --port 8080")
        print("   2. Visit: http://127.0.0.1:8080/google/connect")
        print("   3. Click 'Connect Gmail' and/or 'Connect Calendar'")
        print("   4. Complete the OAuth flow in your browser")
        print()
        print("✅ You'll be ready to use the new scopes!")

    except Exception as e:
        print(f"❌ Error clearing credentials: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(clear_all_credentials())
