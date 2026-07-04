#!/usr/bin/env python3
"""ONE-TIME interactive script to obtain a YouTube OAuth2 refresh token for a
channel. Run this locally (needs a browser), once per channel you want the
factory to be able to upload to. The resulting refresh token never expires
(once the OAuth consent app is switched to "Production" in Google Cloud
Console) and gets stored as a GitHub Secret for the automated pipeline to use.

Usage:
    python scripts/setup_youtube_oauth.py

Prerequisites (one-time, per Google Cloud project — can be shared by all
channels since each channel just needs its OWN refresh token, not its own
OAuth app):
  1. Go to https://console.cloud.google.com/ -> create/select a project.
  2. Enable "YouTube Data API v3" (APIs & Services -> Library).
  3. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID.
     - Application type: Desktop app.
  4. Download the client secret; note the Client ID and Client Secret.
  5. OAuth consent screen -> Publishing status -> "In production" (so the
     refresh token doesn't expire after 7 days during testing).
"""

import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Missing dependency. Run: pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def main():
    client_id = input("Paste your OAuth Client ID: ").strip()
    client_secret = input("Paste your OAuth Client Secret: ").strip()
    channel_name = input("Channel nickname (e.g. ELINA, LUXE): ").strip().upper().replace(" ", "_")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    print("\nA browser window will open. Log in with the Google account that "
          "OWNS the target YouTube channel, then grant access.\n")
    creds = flow.run_local_server(port=0)

    env_name = f"YOUTUBE_REFRESH_TOKEN_{channel_name}"
    print("\n" + "=" * 70)
    print("✅ SUCCESS! Add these as GitHub repository secrets:")
    print("=" * 70)
    print(f"YOUTUBE_OAUTH_CLIENT_ID = {client_id}")
    print(f"YOUTUBE_OAUTH_CLIENT_SECRET = {client_secret}")
    print(f"{env_name} = {creds.refresh_token}")
    print("=" * 70)
    print(f"\nThen set channels/database.json -> this channel's "
          f"'refresh_token_env' field to: \"{env_name}\"")


if __name__ == "__main__":
    main()
