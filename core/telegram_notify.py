"""TelegramNotify — one-way notifications from the factory pipeline (main.py)
to the user's chat, using the SAME bot as the interactive FactoryBot
(scripts/factory_bot.py). Kept separate from the bot's own request-handling
code so main.py doesn't need to import the whole bot module just to send a
"your video is ready" message.
"""

import os

import requests

_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_FACTORY", "")
_CHAT_FILE = "channels/notify_chat_id.txt"


def _chat_id() -> str:
    """The chat id is captured automatically the first time the user sends
    /start to the bot (see scripts/factory_bot.py) and persisted to a small
    tracked file — no manual "find my chat id" step needed."""
    env_val = os.environ.get("TELEGRAM_CHAT_ID_FACTORY", "")
    if env_val:
        return env_val
    if os.path.exists(_CHAT_FILE):
        try:
            with open(_CHAT_FILE) as f:
                return f.read().strip()
        except OSError:
            return ""
    return ""


def send(text: str) -> dict:
    chat_id = _chat_id()
    if not (_TOKEN and chat_id):
        print("[TelegramNotify] Not configured (missing bot token or chat id); skipping.")
        return {"ok": False, "error": "not_configured"}
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "Markdown"},
            timeout=15,
        )
        return r.json()
    except Exception as e:
        print(f"[TelegramNotify] send failed: {e}")
        return {"ok": False, "error": str(e)}
