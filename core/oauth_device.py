"""Google OAuth2 Device Authorization Grant (RFC 8628) — lets a channel be
authorized WITHOUT a local browser/computer. This is what makes "chat with
the bot to add a channel" actually work end-to-end from a phone:

  1. Bot asks Google for a device_code + a short user_code.
  2. Bot sends the user a link + code via Telegram.
  3. User opens the link on ANY device (even the same phone), types the code,
     logs into the Google account that owns the YouTube channel, and clicks
     Allow.
  4. Bot (running in GitHub Actions, polling in the background across
     multiple cron ticks) detects approval and receives a refresh token.
  5. Bot calls GitHubSecrets.set_secret() to store it — zero manual GitHub
     Secrets editing required.

IMPORTANT: this flow requires an OAuth Client ID of type "TVs and Limited
Input devices" in Google Cloud Console (APIs & Services -> Credentials ->
Create Credentials -> OAuth client ID -> TVs and Limited Input devices).
The existing "Desktop app" client (used by scripts/setup_youtube_oauth.py,
still kept as a manual fallback) does NOT work here — Google rejects device
flow requests from Desktop-type clients with 'invalid_client'.
"""

import time

import requests

_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"


def request_device_code(client_id: str) -> dict:
    """Step 1: returns {'device_code', 'user_code', 'verification_url',
    'expires_in', 'interval'} or {'error': ...}."""
    try:
        r = requests.post(
            _DEVICE_CODE_URL,
            data={"client_id": client_id, "scope": SCOPES},
            timeout=20,
        )
        data = r.json()
        if r.status_code != 200:
            return {"error": data.get("error_description") or data.get("error") or f"http_{r.status_code}"}
        return data
    except Exception as e:
        return {"error": str(e)}


def poll_once(client_id: str, client_secret: str, device_code: str) -> dict:
    """Step 2 (call repeatedly, e.g. once per bot-runner tick ~5 min apart):
    returns one of:
      {'status': 'pending'}                — user hasn't approved yet
      {'status': 'slow_down'}               — poll less often
      {'status': 'expired'}                 — device_code expired, restart
      {'status': 'denied'}                  — user clicked Deny
      {'status': 'approved', 'refresh_token': ..., 'access_token': ...}
      {'status': 'error', 'error': ...}
    """
    try:
        r = requests.post(
            _TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=20,
        )
        data = r.json()
        if r.status_code == 200 and "refresh_token" in data:
            return {"status": "approved", "refresh_token": data["refresh_token"],
                     "access_token": data.get("access_token")}
        err = data.get("error", "")
        if err == "authorization_pending":
            return {"status": "pending"}
        if err == "slow_down":
            return {"status": "slow_down"}
        if err == "expired_token":
            return {"status": "expired"}
        if err == "access_denied":
            return {"status": "denied"}
        return {"status": "error", "error": data.get("error_description") or err or f"http_{r.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # Manual CLI test (can still be run locally if useful, but not required).
    cid = input("Client ID (TVs and Limited Input devices type): ").strip()
    csec = input("Client Secret: ").strip()
    dc = request_device_code(cid)
    if "error" in dc:
        print("Error:", dc["error"])
    else:
        print(f"Go to {dc['verification_url']} and enter code: {dc['user_code']}")
        interval = dc.get("interval", 5)
        deadline = time.time() + dc.get("expires_in", 1800)
        while time.time() < deadline:
            time.sleep(interval)
            result = poll_once(cid, csec, dc["device_code"])
            print(result["status"])
            if result["status"] == "approved":
                print("Refresh token:", result["refresh_token"])
                break
            if result["status"] in ("denied", "expired", "error"):
                break
