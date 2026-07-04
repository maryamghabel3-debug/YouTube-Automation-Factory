"""Tiny JSON-file-backed state store for in-progress channel setups that
span MULTIPLE bot-runner ticks (device-code OAuth approval can take minutes
to hours, and the bot only wakes up every 5 minutes on a cron). Keeping this
as a small file (not in-memory) is what lets the flow survive across
separate, stateless GitHub Actions runs.
"""

import json
import os
import time

_PATH = "channels/pending_setups.json"


def _load() -> dict:
    if os.path.exists(_PATH):
        try:
            with open(_PATH) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def start(chat_id: str, channel_id: str, niche_key: str, language: str,
          name: str, voice_variant: str, device_code_info: dict) -> None:
    data = _load()
    data[channel_id] = {
        "chat_id": chat_id,
        "channel_id": channel_id,
        "niche_key": niche_key,
        "language": language,
        "name": name,
        "voice_variant": voice_variant,
        "device_code": device_code_info["device_code"],
        "user_code": device_code_info["user_code"],
        "verification_url": device_code_info["verification_url"],
        "interval": device_code_info.get("interval", 5),
        "created_at": time.time(),
        "expires_at": time.time() + device_code_info.get("expires_in", 1800),
        "status": "awaiting_google_approval",
    }
    _save(data)


def all_pending() -> list:
    return [v for v in _load().values() if v.get("status") == "awaiting_google_approval"]


def mark_done(channel_id: str) -> None:
    data = _load()
    if channel_id in data:
        del data[channel_id]
        _save(data)


def mark_status(channel_id: str, status: str) -> None:
    data = _load()
    if channel_id in data:
        data[channel_id]["status"] = status
        _save(data)
