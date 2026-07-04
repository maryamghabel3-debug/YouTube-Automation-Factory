#!/usr/bin/env python3
"""Interactive wizard to add a new YouTube channel to the factory — any
niche, any language, in under a minute. Run this any time you create a new
channel and want the factory to start producing videos for it.

Usage:
    python scripts/add_channel_wizard.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import content_config as cfg
from core.channel_spawner import ChannelSpawner


def _pick(options: list, prompt: str) -> str:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("Enter number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Invalid choice, try again.")


def main():
    print("=" * 60)
    print("🧙 Add a New Channel to the YouTube Automation Factory")
    print("=" * 60)

    # --- Niche ---
    niche_keys = cfg.list_niches()
    print("\nAvailable niches (with 2026 RPM estimates):")
    for k in niche_keys:
        n = cfg.NICHES[k]
        print(f"  - {k}: {n['label_en']} / {n['label_fa']}  (RPM: {n['rpm_estimate']})")
    print("\n💡 Don't see a niche you want? Add it to core/content_config.py's")
    print("   NICHES dict first (label_fa/label_en/rpm_estimate/subreddits/")
    print("   search_terms/evergreen_topics), then re-run this wizard.")
    niche = _pick(niche_keys, "Pick a niche:")

    # --- Language ---
    lang_keys = cfg.list_languages()
    print("\nAvailable languages:")
    for k in lang_keys:
        print(f"  - {k}: {cfg.LANGUAGES[k]['label']}")
    print("\n💡 Don't see a language you want? Add it to core/content_config.py's")
    print("   LANGUAGES dict (needs an edge-tts voice id — run")
    print("   `python -m edge_tts --list-voices` to find one), then re-run.")
    language = _pick(lang_keys, "Pick a language:")

    # --- Channel identity ---
    channel_id = input("\nChannel id (short slug, e.g. 'luxe_en'): ").strip()
    name = input("Channel display name: ").strip()

    # --- OAuth ---
    print("\nHave you already run scripts/setup_youtube_oauth.py for this "
          "channel's YouTube account? (See docs/YOUTUBE-OAUTH-SETUP.md)")
    has_oauth = input("(y/n): ").strip().lower() == "y"
    if has_oauth:
        refresh_env = input(
            "Paste the refresh-token env var name it gave you "
            "(e.g. YOUTUBE_REFRESH_TOKEN_LUXE): "
        ).strip()
    else:
        suggested = f"YOUTUBE_REFRESH_TOKEN_{channel_id.upper()}"
        print(f"No problem — run scripts/setup_youtube_oauth.py before the first "
              f"real upload. For now this channel is registered with a "
              f"placeholder env var name: {suggested}")
        refresh_env = suggested

    variant = input("\nVoice variant if you're running 2 channels in the same "
                     "language [default/alt] (Enter = default): ").strip() or "default"

    entry = ChannelSpawner().register_channel(
        channel_id, name, niche, language, refresh_env, voice_variant=variant
    )

    print("\n" + "=" * 60)
    print("✅ Channel registered!")
    print("=" * 60)
    for k, v in entry.items():
        print(f"  {k}: {v}")
    print("\nNext steps:")
    print("  1. If you haven't yet: python scripts/setup_youtube_oauth.py")
    print(f"  2. Add '{refresh_env}' to GitHub Secrets with the real refresh token")
    print("  3. Test a dry run:  SKIP_UPLOAD=1 TARGET_MINUTES=2 python main.py")


if __name__ == "__main__":
    main()
