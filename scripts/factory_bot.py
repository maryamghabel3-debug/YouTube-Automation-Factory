#!/usr/bin/env python3
"""FactoryBot — Telegram control panel for YouTube-Automation-Factory.

Runs on a GitHub Actions cron (every 5 minutes, see
.github/workflows/factory-bot.yml) — same pattern as elina-radman's
scripts/elina_bot.py, but this is a SEPARATE bot/token so the two projects
stay cleanly independent (as requested).

What it lets you do, entirely from Telegram, with zero manual GitHub
website clicking:
  /start            — register this chat to receive results/notifications
  /newchannel       — step-by-step wizard: pick niche -> pick language ->
                       name the channel -> registers it in
                       channels/database.json
  /channels         — list every registered channel + its status
  /oauth <id>       — connect a channel's real YouTube account (device-code
                       flow: bot gives you a link+code, you approve on your
                       phone/laptop, bot detects approval automatically and
                       stores the refresh token as a GitHub Secret AND wires
                       it into the run-factory.yml workflow — no manual
                       secrets-page editing)
  /pause <id> /resume <id> /remove <id>
  /testvideo <id>   — build ONE video for this channel right now (no
                       upload) and send it back to you to review
  /makevideo <id>   — build + really upload to YouTube right now
  /runall           — trigger the full daily run immediately
  /status           — which API keys/secrets are configured
  /cancel           — abort whatever wizard step you're in
  /help
"""

import os
import sys
import json
import glob as g

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import content_config as cfg
from core.channel_spawner import ChannelSpawner
from core import pending_setups
from core import oauth_device
from core.gh_secrets import GitHubSecrets
from core.workflow_editor import ensure_secret_in_workflow
from core.gh_actions import trigger_run_factory

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_FACTORY", "")
GEMINI = os.environ.get("GEMINI_API_KEY", "")

if not TOKEN:
    print("❌ Missing TELEGRAM_BOT_TOKEN_FACTORY secret. Skipping bot run.")
    sys.exit(0)

BASE = f"https://api.telegram.org/bot{TOKEN}"

_STATE_PATH = "channels/bot_state.json"
_OFFSET_PATH = "channels/factory_bot_offset.txt"
_CHAT_FILE = "channels/notify_chat_id.txt"
_WORKFLOW_PATH = ".github/workflows/run-factory.yml"


# --------------------------------------------------------------------------- #
# Telegram helpers
# --------------------------------------------------------------------------- #
def tg(method, data=None):
    return requests.post(f"{BASE}/{method}", json=data or {}, timeout=15).json()


def send(chat, text, reply_to=None):
    d = {"chat_id": chat, "text": text[:4000], "parse_mode": "Markdown"}
    if reply_to:
        d["reply_to_message_id"] = reply_to
    result = tg("sendMessage", d)
    if not result.get("ok"):
        # Markdown parse errors (unescaped _ * [ ] ( ) etc in dynamic content
        # like niche labels) are a common silent-failure cause -- retry once
        # as plain text so the user still gets SOME response instead of
        # nothing, and always log the real reason to the Actions log.
        print(f"[send] sendMessage failed for chat {chat}: {result}")
        if d.get("parse_mode"):
            d2 = {k: v for k, v in d.items() if k != "parse_mode"}
            result2 = tg("sendMessage", d2)
            if not result2.get("ok"):
                print(f"[send] plain-text retry also failed for chat {chat}: {result2}")
            return result2
    return result


def send_video(chat, video_path, caption=""):
    try:
        with open(video_path, "rb") as f:
            return requests.post(
                f"{BASE}/sendVideo",
                data={"chat_id": chat, "caption": caption[:1000]},
                files={"video": f},
                timeout=180,
            ).json()
    except Exception as e:
        print("send_video error:", e)
        return {"ok": False}


def setup_bot_commands():
    commands = [
        {"command": "start", "description": "🚀 شروع و ثبت این چت برای دریافت ویدیوها"},
        {"command": "newchannel", "description": "🆕 اضافه کردن کانال جدید (نیچ، زبان، نام)"},
        {"command": "channels", "description": "📋 لیست کانال‌ها و وضعیت هرکدوم"},
        {"command": "oauth", "description": "🔐 وصل کردن اکانت یوتیوب یک کانال"},
        {"command": "testvideo", "description": "🎬 ساخت یک ویدیوی تستی (بدون آپلود)"},
        {"command": "makevideo", "description": "📤 ساخت و آپلود واقعی ویدیو"},
        {"command": "runall", "description": "🏭 اجرای کامل فکتوری برای همه کانال‌ها"},
        {"command": "pause", "description": "⏸ متوقف کردن موقت یک کانال"},
        {"command": "resume", "description": "▶️ فعال کردن دوباره یک کانال"},
        {"command": "remove", "description": "🗑 حذف یک کانال"},
        {"command": "status", "description": "📊 وضعیت کلیدها و اتصال‌ها"},
        {"command": "cancel", "description": "❌ لغو مرحله فعلی"},
        {"command": "help", "description": "🕊️ راهنما"},
    ]
    res = tg("setMyCommands", {"commands": commands})
    if not res.get("ok"):
        print("⚠️ Could not update bot menu commands:", res)


setup_bot_commands()


# --------------------------------------------------------------------------- #
# Small state helpers
# --------------------------------------------------------------------------- #
def _load_state() -> dict:
    if os.path.exists(_STATE_PATH):
        try:
            with open(_STATE_PATH) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_state(state: dict):
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _remember_chat_id(chat: str):
    os.makedirs(os.path.dirname(_CHAT_FILE), exist_ok=True)
    with open(_CHAT_FILE, "w") as f:
        f.write(str(chat))


def _niche_menu() -> str:
    lines = ["کدوم نیچ؟ عدد رو بفرست:\n"]
    for i, k in enumerate(cfg.list_niches(), 1):
        n = cfg.NICHES[k]
        lines.append(f"{i}. {n['label_fa']} / {n['label_en']}  — RPM: {n['rpm_estimate']}")
    return "\n".join(lines)


def _language_menu() -> str:
    lines = ["زبان کانال؟ عدد رو بفرست:\n"]
    for i, k in enumerate(cfg.list_languages(), 1):
        lines.append(f"{i}. {cfg.LANGUAGES[k]['label']} ({k})")
    return "\n".join(lines)


def _channel_status_line(ch: dict) -> str:
    token_env = ch.get("refresh_token_env", "")
    has_token = token_env and os.environ.get(token_env, "")
    oauth_icon = "✅" if has_token else "❌ (نیاز به /oauth)"
    active_icon = "🟢" if ch.get("active", True) else "⏸"
    return (f"{active_icon} `{ch['id']}` — {ch['name']}\n"
            f"   نیچ: {ch.get('niche_label','')} | زبان: {ch.get('language','')}\n"
            f"   یوتیوب متصل: {oauth_icon}")


# --------------------------------------------------------------------------- #
# Pending OAuth polling — checked on EVERY tick, independent of new messages,
# since Google approval can happen between bot runs (cron is every 5 min).
# --------------------------------------------------------------------------- #
def _poll_pending_oauth():
    client_id = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        return

    for entry in pending_setups.all_pending():
        result = oauth_device.poll_once(client_id, client_secret, entry["device_code"])
        status = result["status"]
        chat = entry["chat_id"]
        channel_id = entry["channel_id"]

        if status == "pending":
            continue  # nothing to do yet, check again next tick

        if status in ("denied", "expired", "error"):
            pending_setups.mark_done(channel_id)
            send(chat, f"⚠️ اتصال یوتیوب برای `{channel_id}` ناموفق بود ({status}). "
                       f"دوباره با `/oauth {channel_id}` امتحان کن.")
            continue

        if status == "approved":
            refresh_token = result["refresh_token"]
            secret_name = f"YOUTUBE_REFRESH_TOKEN_{channel_id.upper()}"

            gh = GitHubSecrets()
            set_result = gh.set_secret(secret_name, refresh_token)
            if not set_result.get("ok"):
                send(chat, f"⚠️ توکن گرفته شد ولی ذخیره‌اش توی GitHub Secrets شکست خورد: "
                           f"{set_result.get('error')}\nبه صورت دستی به Settings → Secrets اضافه کن: "
                           f"`{secret_name}`")
                pending_setups.mark_done(channel_id)
                continue

            ensure_secret_in_workflow(_WORKFLOW_PATH, secret_name)
            ChannelSpawner().set_refresh_token_env(channel_id, secret_name)
            pending_setups.mark_done(channel_id)

            send(chat, f"✅ کانال `{channel_id}` به یوتیوب وصل شد!\n"
                       f"از این به بعد آپلود واقعی روش کار می‌کنه.\n"
                       f"می‌تونی با `/testvideo {channel_id}` یه تست بگیری.")


# --------------------------------------------------------------------------- #
# Command handlers
# --------------------------------------------------------------------------- #
def handle_start(chat, mid):
    _remember_chat_id(chat)
    send(chat, "🏭 *به کنترل‌پنل فکتوری یوتیوب خوش اومدی!*\n\n"
               "🆕 `/newchannel` — اضافه کردن کانال جدید\n"
               "📋 `/channels` — لیست کانال‌ها\n"
               "🔐 `/oauth شناسه_کانال` — وصل کردن یوتیوب\n"
               "🎬 `/testvideo شناسه_کانال` — یک ویدیوی تستی بساز\n"
               "📤 `/makevideo شناسه_کانال` — بساز و واقعی آپلود کن\n"
               "🏭 `/runall` — اجرای کامل برای همه کانال‌ها\n"
               "📊 `/status` — وضعیت کلیدها\n"
               "🕊️ `/help` — راهنمای کامل", reply_to=mid)


def handle_help(chat, mid):
    send(chat, __doc__.split("What it lets you do")[1] if "What it lets you do" in __doc__ else __doc__,
         reply_to=mid)


def handle_newchannel(chat, mid, state):
    state[chat] = {"flow": "new_channel", "step": "niche", "data": {}}
    _save_state(state)
    send(chat, _niche_menu(), reply_to=mid)


def handle_channels(chat, mid):
    channels = ChannelSpawner().list_channels()
    if not channels:
        send(chat, "📭 هنوز هیچ کانالی ثبت نشده. با `/newchannel` شروع کن.", reply_to=mid)
        return
    lines = ["📋 *کانال‌های ثبت‌شده*\n"]
    for ch in channels:
        lines.append(_channel_status_line(ch))
    send(chat, "\n\n".join(lines), reply_to=mid)


def handle_oauth(chat, mid, arg):
    if not arg:
        send(chat, "فرمت درست: `/oauth شناسه_کانال` (شناسه رو از `/channels` ببین)", reply_to=mid)
        return
    ch = ChannelSpawner().get_channel(arg)
    if not ch:
        send(chat, f"❌ کانالی با شناسه `{arg}` پیدا نشد.", reply_to=mid)
        return

    client_id = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        send(chat, "❌ هنوز `YOUTUBE_OAUTH_CLIENT_ID`/`YOUTUBE_OAUTH_CLIENT_SECRET` تنظیم نشده.\n"
                   "توی Google Cloud Console یک OAuth Client از نوع "
                   "*TVs and Limited Input devices* بساز و مقادیرش رو به GitHub Secrets اضافه کن.\n"
                   "راهنمای کامل: docs/YOUTUBE-OAUTH-SETUP.md", reply_to=mid)
        return

    dc = oauth_device.request_device_code(client_id)
    if "error" in dc:
        send(chat, f"❌ خطا در شروع اتصال: {dc['error']}", reply_to=mid)
        return

    pending_setups.start(chat, arg, ch.get("niche_key", ""), ch.get("language", ""),
                          ch.get("name", ""), "default", dc)

    send(chat, f"🔐 *اتصال یوتیوب برای کانال «{ch['name']}»*\n\n"
               f"۱. برو به: {dc['verification_url']}\n"
               f"۲. این کد رو وارد کن: `{dc['user_code']}`\n"
               f"۳. با اکانت گوگلی که *مالک همین کانال یوتیوب* هست وارد شو و اجازه بده\n\n"
               f"⏳ من هر چند دقیقه یه بار چک می‌کنم و وقتی تأیید کردی خودم بهت خبر می‌دم "
               f"(نیازی نیست دوباره پیام بدی).", reply_to=mid)


def handle_pause_resume(chat, mid, arg, active: bool):
    if not arg:
        send(chat, "فرمت درست: `/pause شناسه_کانال` یا `/resume شناسه_کانال`", reply_to=mid)
        return
    ok = ChannelSpawner().set_active(arg, active)
    verb = "فعال" if active else "متوقف"
    send(chat, f"{'✅' if ok else '❌'} کانال `{arg}` {'پیدا نشد' if not ok else verb + ' شد'}.", reply_to=mid)


def handle_remove(chat, mid, arg):
    if not arg:
        send(chat, "فرمت درست: `/remove شناسه_کانال`", reply_to=mid)
        return
    ok = ChannelSpawner().remove_channel(arg)
    send(chat, f"{'✅ حذف شد.' if ok else '❌ پیدا نشد.'}", reply_to=mid)


def handle_test_or_make_video(chat, mid, arg, skip_upload: bool):
    if not arg:
        send(chat, f"فرمت درست: `/{'testvideo' if skip_upload else 'makevideo'} شناسه_کانال`", reply_to=mid)
        return
    ch = ChannelSpawner().get_channel(arg)
    if not ch:
        send(chat, f"❌ کانالی با شناسه `{arg}` پیدا نشد.", reply_to=mid)
        return

    result = trigger_run_factory({
        "skip_upload": "1" if skip_upload else "0",
        "target_minutes": "3" if skip_upload else "8",
        "only_channel": arg,
        "deliver_mode": "both",
    })
    if result.get("ok"):
        mode = "تستی (بدون آپلود)" if skip_upload else "واقعی (با آپلود روی یوتیوب)"
        send(chat, f"🚀 ساخت ویدیوی {mode} برای «{ch['name']}» شروع شد.\n"
                   f"این معمولاً چند دقیقه طول می‌کشه — همین که آماده شد، ویدیو یا لینکش رو برات می‌فرستم.",
             reply_to=mid)
    else:
        send(chat, f"❌ شروع اجرا ناموفق بود: {result.get('error')}", reply_to=mid)


def handle_runall(chat, mid):
    result = trigger_run_factory({"skip_upload": "0", "target_minutes": "8", "only_channel": "", "deliver_mode": "both"})
    if result.get("ok"):
        send(chat, "🏭 اجرای کامل فکتوری برای همه کانال‌های فعال شروع شد. نتیجه هر کانال جدا برات می‌آد.",
             reply_to=mid)
    else:
        send(chat, f"❌ شروع اجرا ناموفق بود: {result.get('error')}", reply_to=mid)


def handle_status(chat, mid):
    def icon(v):
        return "✅" if v else "❌"

    channels = ChannelSpawner().list_channels()
    lines = [
        "📊 *وضعیت فکتوری*\n",
        f"🎬 Pexels: {icon(os.environ.get('PEXELS_API_KEY'))}",
        f"🎬 Pixabay: {icon(os.environ.get('PIXABAY_API_KEY'))}",
        f"✍️ Gemini (اسکریپت اصیل): {icon(GEMINI)}",
        f"🔐 YouTube OAuth Client: {icon(os.environ.get('YOUTUBE_OAUTH_CLIENT_ID'))}",
        f"📈 YouTube API (آمار): {icon(os.environ.get('YOUTUBE_API_KEY'))}",
        f"📺 تعداد کانال‌های ثبت‌شده: {len(channels)}",
    ]
    send(chat, "\n".join(lines), reply_to=mid)


def handle_cancel(chat, mid, state):
    if chat in state:
        del state[chat]
        _save_state(state)
        send(chat, "❌ لغو شد.", reply_to=mid)
    else:
        send(chat, "چیزی برای لغو کردن نیست.", reply_to=mid)


# --------------------------------------------------------------------------- #
# Wizard step machine (multi-tick, since bot only wakes up every 5 minutes)
# --------------------------------------------------------------------------- #
def handle_wizard_reply(chat, mid, text, state):
    flow_state = state[chat]
    step = flow_state["step"]
    data = flow_state["data"]

    if step == "niche":
        niche_keys = cfg.list_niches()
        raw = text.strip()
        picked = None
        if raw.isdigit() and 1 <= int(raw) <= len(niche_keys):
            picked = niche_keys[int(raw) - 1]
        elif raw in niche_keys:
            picked = raw
        if not picked:
            send(chat, "❌ عدد معتبر بفرست.\n\n" + _niche_menu(), reply_to=mid)
            return
        data["niche_key"] = picked
        flow_state["step"] = "language"
        _save_state(state)
        send(chat, _language_menu(), reply_to=mid)
        return

    if step == "language":
        lang_keys = cfg.list_languages()
        raw = text.strip()
        picked = None
        if raw.isdigit() and 1 <= int(raw) <= len(lang_keys):
            picked = lang_keys[int(raw) - 1]
        elif raw in lang_keys:
            picked = raw
        if not picked:
            send(chat, "❌ عدد معتبر بفرست.\n\n" + _language_menu(), reply_to=mid)
            return
        data["language"] = picked
        flow_state["step"] = "name"
        _save_state(state)
        send(chat, "اسم نمایشی کانال چیه؟ (مثلاً «الینا لاکچری» یا «Mystery Files»)", reply_to=mid)
        return

    if step == "name":
        name = text.strip()
        if not name:
            send(chat, "یه اسم بفرست.", reply_to=mid)
            return
        data["name"] = name
        flow_state["step"] = "slug"
        _save_state(state)
        suggested = f"{data['niche_key']}_{data['language']}"
        data["suggested_slug"] = suggested
        _save_state(state)
        send(chat, f"شناسه کوتاه کانال (فقط حروف/عدد/آندرلاین، برای استفاده داخلی و در Secrets)?\n"
                   f"برای استفاده از پیشنهاد `{suggested}` فقط بنویس: -", reply_to=mid)
        return

    if step == "slug":
        raw = text.strip()
        slug = data["suggested_slug"] if raw == "-" else raw
        slug = "".join(c if (c.isalnum() or c == "_") else "_" for c in slug).strip("_").lower()
        if not slug:
            send(chat, "شناسه نامعتبره، دوباره بفرست.", reply_to=mid)
            return
        existing = ChannelSpawner().get_channel(slug)
        if existing:
            send(chat, f"❌ شناسه `{slug}` قبلاً استفاده شده. یه شناسه دیگه بفرست.", reply_to=mid)
            return

        placeholder_env = f"YOUTUBE_REFRESH_TOKEN_{slug.upper()}"
        entry = ChannelSpawner().register_channel(
            slug, data["name"], data["niche_key"], data["language"], placeholder_env,
        )
        del state[chat]
        _save_state(state)

        send(chat, f"✅ *کانال ثبت شد!*\n\n"
                   f"🆔 `{entry['id']}`\n"
                   f"📺 {entry['name']}\n"
                   f"🏷 نیچ: {entry['niche_label']} (RPM: {entry['rpm_estimate']})\n"
                   f"🌐 زبان: {entry['language']}\n\n"
                   f"مرحله بعد: اتصال به اکانت واقعی یوتیوب —\n"
                   f"`/oauth {entry['id']}`\n\n"
                   f"یا اگه فقط می‌خوای اول محتوا رو ببینی (بدون آپلود):\n"
                   f"`/testvideo {entry['id']}`", reply_to=mid)
        return


# --------------------------------------------------------------------------- #
# Main tick
# --------------------------------------------------------------------------- #
def main():
    _poll_pending_oauth()

    try:
        with open(_OFFSET_PATH) as f:
            offset = int(f.read().strip() or "0")
    except Exception:
        offset = 0

    def save_offset(v):
        try:
            os.makedirs(os.path.dirname(_OFFSET_PATH), exist_ok=True)
            with open(_OFFSET_PATH, "w") as f:
                f.write(str(v))
        except Exception as e:
            print("offset save error:", e)

    r = requests.get(f"{BASE}/getUpdates?offset={offset}&timeout=10", timeout=15).json()
    updates = r.get("result", [])
    print(f"📩 {len(updates)} messages")

    state = _load_state()

    for u in updates:
        offset = u["update_id"] + 1
        save_offset(offset)
        msg = u.get("message", {})
        text = (msg.get("text") or "").strip()
        chat = str(msg.get("chat", {}).get("id", ""))
        mid = msg.get("message_id", 0)
        if not text or not chat:
            continue
        print(f"   [{chat}] {text[:60]}")

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/start":
            handle_start(chat, mid)
        elif cmd == "/help":
            handle_help(chat, mid)
        elif cmd == "/newchannel":
            handle_newchannel(chat, mid, state)
        elif cmd == "/channels":
            handle_channels(chat, mid)
        elif cmd == "/oauth":
            handle_oauth(chat, mid, arg)
        elif cmd == "/pause":
            handle_pause_resume(chat, mid, arg, False)
        elif cmd == "/resume":
            handle_pause_resume(chat, mid, arg, True)
        elif cmd == "/remove":
            handle_remove(chat, mid, arg)
        elif cmd == "/testvideo":
            handle_test_or_make_video(chat, mid, arg, skip_upload=True)
        elif cmd == "/makevideo":
            handle_test_or_make_video(chat, mid, arg, skip_upload=False)
        elif cmd == "/runall":
            handle_runall(chat, mid)
        elif cmd == "/status":
            handle_status(chat, mid)
        elif cmd == "/cancel":
            handle_cancel(chat, mid, state)
        elif chat in state:
            handle_wizard_reply(chat, mid, text, state)
        elif cmd.startswith("/"):
            send(chat, "❓ دستور ناشناخته. `/help` رو بزن.", reply_to=mid)
        else:
            send(chat, "برای شروع `/help` رو بزن.", reply_to=mid)

    save_offset(offset)
    if updates:
        try:
            requests.get(f"{BASE}/getUpdates?offset={offset}&timeout=1", timeout=10)
        except Exception as e:
            print("offset confirm error:", e)


if __name__ == "__main__":
    main()
