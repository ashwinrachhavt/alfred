#!/usr/bin/env python3
"""
Check current OAuth configuration and generate authorization URL to see redirect_uri.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps"))

from alfred.services.google_oauth import generate_authorization_url, GOOGLE_SCOPES
from alfred.core.config import settings
from dotenv import load_dotenv

load_dotenv("apps/alfred/.env")

print("=" * 70)
print("Google OAuth Configuration Check")
print("=" * 70)

print("\n📋 Current Settings:")
print(f"  Client ID: {settings.google_client_id}")
print(f"  Redirect URI: {settings.google_redirect_uri}")
print(f"  Scopes: {GOOGLE_SCOPES}")

print("\n🔗 Generating test authorization URL...")
try:
    auth_url, state = generate_authorization_url(state="test:config_check")

    print("\n✅ Authorization URL generated successfully!")
    print(f"\n  State: {state}")
    print(f"\n  Full URL:\n  {auth_url}")

    # Extract redirect_uri from the URL
    if "redirect_uri=" in auth_url:
        parts = auth_url.split("redirect_uri=")
        if len(parts) > 1:
            redirect_part = parts[1].split("&")[0]
            from urllib.parse import unquote
            redirect_uri = unquote(redirect_part)
            print(f"\n📍 Redirect URI being sent to Google:")
            print(f"  {redirect_uri}")
            print("\n⚠️  This EXACT URI must be added to Google Cloud Console:")
            print(f"  → https://console.cloud.google.com/apis/credentials?project={settings.google_project_id}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("Next Steps:")
print("=" * 70)
print("1. Copy the redirect URI shown above")
print("2. Go to Google Cloud Console")
print("3. Edit your OAuth 2.0 Client ID")
print("4. Add the redirect URI under 'Authorized redirect URIs'")
print("5. Save and wait 1-2 minutes")
print("6. Try authenticating again")
print("=" * 70)
