"""ChannelSpawner Agent — registers a new channel config into the factory
database. Unlike the original mock version, this does NOT invent a fake
YouTube channel: you must have already created the channel on youtube.com
and run scripts/setup_youtube_oauth.py once to get its refresh token env
var name. This agent just writes a real, validated config entry.
"""

import os
import json

from . import content_config as cfg

_DB_PATH = "channels/database.json"


class ChannelSpawner:
    def __init__(self):
        self.name = "ChannelSpawner"
        self.db_path = _DB_PATH

    def _load_db(self) -> dict:
        if os.path.exists(self.db_path):
            with open(self.db_path) as f:
                return json.load(f)
        return {"channels": []}

    def _save_db(self, data: dict):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def register_channel(self, channel_id: str, name: str, niche_key: str,
                          language: str, refresh_token_env: str,
                          upload_frequency: str = "weekly", active: bool = True,
                          voice_variant: str = "default") -> dict:
        """Register a real channel. niche_key must exist in
        content_config.NICHES, language must exist in content_config.LANGUAGES.
        voice_variant: 'default' or 'alt' (see LANGUAGES[lang]['voice_alt']) —
        lets two channels in the same language use different-sounding
        narrators."""
        if niche_key not in cfg.NICHES:
            raise ValueError(f"Unknown niche_key '{niche_key}'. Valid: {cfg.list_niches()}")
        if language not in cfg.LANGUAGES:
            raise ValueError(f"Unknown language '{language}'. Valid: {cfg.list_languages()}")

        lang_cfg = cfg.LANGUAGES[language]
        voice = lang_cfg["voice_alt"] if voice_variant == "alt" else lang_cfg["voice"]

        entry = {
            "id": channel_id,
            "name": name,
            "niche_key": niche_key,
            "niche_label": cfg.niche_label(niche_key, language),
            "rpm_estimate": cfg.NICHES[niche_key]["rpm_estimate"],
            "language": language,
            "voice": voice,
            "category_id": cfg.YOUTUBE_CATEGORY_ID,
            "refresh_token_env": refresh_token_env,
            "upload_frequency": upload_frequency,
            "active": active,
        }

        db = self._load_db()
        db["channels"] = [c for c in db["channels"] if c["id"] != channel_id]  # replace if exists
        db["channels"].append(entry)
        self._save_db(db)
        print(f"[{self.name}] Registered channel '{name}' ({channel_id}) — "
              f"niche={niche_key}, language={language}, voice={voice}")
        return entry

    def list_channels(self) -> list:
        return self._load_db().get("channels", [])

    def get_channel(self, channel_id: str) -> dict:
        for c in self.list_channels():
            if c["id"] == channel_id:
                return c
        return {}

    def set_active(self, channel_id: str, active: bool) -> bool:
        db = self._load_db()
        found = False
        for c in db.get("channels", []):
            if c["id"] == channel_id:
                c["active"] = active
                found = True
        if found:
            self._save_db(db)
        return found

    def set_refresh_token_env(self, channel_id: str, refresh_token_env: str) -> bool:
        """Used once OAuth is completed via the device flow so the channel's
        placeholder env-var name is confirmed/updated."""
        db = self._load_db()
        found = False
        for c in db.get("channels", []):
            if c["id"] == channel_id:
                c["refresh_token_env"] = refresh_token_env
                found = True
        if found:
            self._save_db(db)
        return found

    def remove_channel(self, channel_id: str) -> bool:
        db = self._load_db()
        before = len(db.get("channels", []))
        db["channels"] = [c for c in db.get("channels", []) if c["id"] != channel_id]
        changed = len(db["channels"]) != before
        if changed:
            self._save_db(db)
        return changed


if __name__ == "__main__":
    print(f"{ChannelSpawner().name} — register a real channel interactively.")
    print(f"Available niches: {cfg.list_niches()}")
    print(f"Available languages: {cfg.list_languages()}")
    cid = input("Channel id (short slug, e.g. 'luxe_en'): ").strip()
    name = input("Channel display name: ").strip()
    niche = input("Niche key: ").strip()
    lang = input("Language code: ").strip()
    env_var = input("Refresh token env var name (from setup_youtube_oauth.py): ").strip()
    variant = input("Voice variant [default/alt] (Enter = default): ").strip() or "default"
    ChannelSpawner().register_channel(cid, name, niche, lang, env_var, voice_variant=variant)

