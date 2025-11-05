#!/usr/bin/env python3
"""
End-to-end test script for Google OAuth integration.
Tests both Gmail and Calendar authentication and data fetching.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the apps directory to the path
sys.path.insert(0, str(Path(__file__).parent / "apps"))

from alfred.connectors.google_calendar_connector import GoogleCalendarConnector
from alfred.connectors.google_gmail_connector import GoogleGmailConnector
from alfred.core.database import get_session, init_db
from alfred.core.db_models import GoogleCredential
from alfred.services.gmail import GmailService
from alfred.services.google_oauth import (
    GOOGLE_SCOPES,
    load_credentials_async,
    persist_credentials_async,
)
from dotenv import load_dotenv
from sqlalchemy import delete

# Load environment variables
load_dotenv("apps/alfred/.env")


async def clear_credentials():
    """Clear all stored Google credentials."""
    print("\n🗑️  Clearing old credentials...")
    try:
        async with get_session() as session:
            await session.execute(delete(GoogleCredential))
            await session.commit()
        print("✅ Credentials cleared from database")
    except Exception as e:
        print(f"⚠️  Could not clear credentials: {e}")


async def check_credentials():
    """Check if credentials exist for Gmail and Calendar."""
    print("\n🔍 Checking for existing credentials...")

    gmail_creds = await load_credentials_async(is_calendar=False)
    calendar_creds = await load_credentials_async(is_calendar=True)

    print(f"  Gmail credentials: {'✅ Found' if gmail_creds else '❌ Not found'}")
    print(f"  Calendar credentials: {'✅ Found' if calendar_creds else '❌ Not found'}")

    return gmail_creds, calendar_creds


async def test_gmail(creds):
    """Test Gmail integration by fetching recent emails."""
    print("\n📧 Testing Gmail integration...")

    try:
        connector = GoogleGmailConnector(
            creds,
            user_id=None,
            on_credentials_refreshed=lambda c: persist_credentials_async(None, c, is_calendar=False)
        )

        # Get user profile
        profile, err = await connector.get_user_profile()
        if err:
            print(f"❌ Error getting profile: {err}")
            return False

        print(f"✅ Connected to Gmail: {profile.get('email_address')}")
        print(f"   Total messages: {profile.get('messages_total')}")
        print(f"   Total threads: {profile.get('threads_total')}")

        # Get recent inbox messages
        print("\n📬 Fetching recent inbox messages...")
        messages, err = await connector.get_messages_list(
            max_results=5,
            query="is:inbox"
        )

        if err:
            print(f"❌ Error fetching messages: {err}")
            return False

        print(f"✅ Found {len(messages)} messages")

        # Fetch and display message details
        for i, msg in enumerate(messages[:3], 1):
            detail, detail_err = await connector.get_message_details(msg.get("id", ""))
            if detail_err:
                continue

            headers = GmailService.parse_headers(detail)
            print(f"\n  Message {i}:")
            print(f"    Subject: {headers.get('Subject', 'No subject')}")
            print(f"    From: {headers.get('From', 'Unknown')}")
            print(f"    Date: {headers.get('Date', 'Unknown')}")
            print(f"    Snippet: {detail.get('snippet', '')[:100]}...")

        return True

    except Exception as e:
        print(f"❌ Gmail test failed: {e}")
        return False


async def test_calendar(creds):
    """Test Calendar integration by fetching upcoming events."""
    print("\n📅 Testing Calendar integration...")

    try:
        connector = GoogleCalendarConnector(
            creds,
            user_id=None,
            on_credentials_refreshed=lambda c: persist_credentials_async(
                None, c, scopes=creds.scopes, is_calendar=True
            )
        )

        # Get calendars list
        calendars, err = await connector.get_calendars()
        if err:
            print(f"❌ Error getting calendars: {err}")
            return False

        print(f"✅ Found {len(calendars)} calendar(s)")
        for cal in calendars:
            primary = " (PRIMARY)" if cal.get("primary") else ""
            print(f"   - {cal.get('summary')}{primary}")

        # Get events from primary calendar
        print("\n📆 Fetching upcoming events (next 7 days)...")
        now = datetime.now()
        end = now + timedelta(days=7)

        events, err = await connector.get_all_primary_calendar_events(
            start_date=now.isoformat(),
            end_date=end.isoformat(),
            max_results=10
        )

        if err:
            if "No events found" in err:
                print("ℹ️  No upcoming events in the next 7 days")
                return True
            print(f"❌ Error fetching events: {err}")
            return False

        print(f"✅ Found {len(events)} upcoming event(s)")

        for i, event in enumerate(events[:5], 1):
            summary = event.get("summary", "Untitled")
            start = event.get("start", {})
            start_time = start.get("dateTime") or start.get("date", "Unknown")
            location = event.get("location", "")

            print(f"\n  Event {i}:")
            print(f"    Summary: {summary}")
            print(f"    Start: {start_time}")
            if location:
                print(f"    Location: {location}")

        return True

    except Exception as e:
        print(f"❌ Calendar test failed: {e}")
        return False


async def main():
    """Main test function."""
    print("=" * 70)
    print("Google OAuth Integration Test")
    print("=" * 70)

    # Initialize database
    print("\n🔧 Initializing database...")
    await init_db()
    print("✅ Database initialized")

    # Check for existing credentials
    gmail_creds, calendar_creds = await check_credentials()

    # Offer to clear credentials if they exist
    if gmail_creds or calendar_creds:
        print("\n⚠️  Found existing credentials.")
        print("   If you're experiencing authentication issues, you should:")
        print("   1. Delete old credentials by calling clear_credentials()")
        print("   2. Update your Google Cloud Console redirect URI to:")
        print("      http://127.0.0.1:8080/api/google/oauth/callback")
        print("   3. Re-authenticate via the web UI")
        print()

        # For now, let's test with existing credentials
        if gmail_creds:
            await test_gmail(gmail_creds)

        if calendar_creds:
            await test_calendar(calendar_creds)
    else:
        print("\n❌ No credentials found!")
        print("\n📝 To authenticate:")
        print("   1. Make sure your server is running:")
        print("      cd apps/alfred && uvicorn alfred.main:app --reload --port 8080")
        print()
        print("   2. Update your Google Cloud Console OAuth redirect URI to:")
        print("      http://127.0.0.1:8080/api/google/oauth/callback")
        print()
        print("   3. Open http://127.0.0.1:8080/google/connect in your browser")
        print()
        print("   4. Click 'Connect Gmail' and 'Connect Calendar' to authenticate")
        print()
        print("   5. Run this script again to test the integration")
        print()
        print(f"   Required scopes: {GOOGLE_SCOPES}")

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
