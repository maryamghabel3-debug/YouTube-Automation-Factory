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
                          upload_frequency: str = "weekly", active: bool = True) -> dict:
        """Register a real channel. niche_key must exist in content_config.NICHES."""
        if niche_key not in cfg.NICHES:
            raise ValueError(f"Unknown niche_key '{niche_key}'. Valid: {list(cfg.NICHES)}")
        if language not in cfg.VOICES:
            raise ValueError(f"Unknown language '{language}'. Valid: {list(cfg.VOICES)}")

        niche = cfg.NICHES[niche_key]
        entry = {
            "id": channel_id,
            "name": name,
            "niche_key": niche_key,
            "niche_label": niche["label_fa"] if language == "fa" else niche["label_en"],
            "language": language,
            "voice": cfg.VOICES[language],
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
              f"niche={niche_key}, language={language}")
        return entry

    def list_channels(self) -> list:
        return self._load_db().get("channels", [])


if __name__ == "__main__":
    import sys

    print(f"{ChannelSpawner().name} — register a real channel interactively.")
    print(f"Available niches: {list(cfg.NICHES)}")
    cid = input("Channel id (short slug, e.g. 'luxe_en'): ").strip()
    name = input("Channel display name: ").strip()
    niche = input("Niche key: ").strip()
    lang = input("Language (fa/en): ").strip()
    env_var = input("Refresh token env var name (from setup_youtube_oauth.py): ").strip()
    ChannelSpawner().register_channel(cid, name, niche, lang, env_var)
