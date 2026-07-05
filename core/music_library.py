"""MusicLibrary — real, always-free, no-API-key background music.

WHY THIS EXISTS: the user reviewed two real test videos and explicitly
asked for background music ("موسیقی پس‌زمینه هم اگه داشته باشه بهتره").
core/video_assembler.py already had a `music_path` parameter (ducked under
narration at 12% volume, looped to match length) but nothing ever populated
it -- every real video before this was silent except for narration.

SOURCE: Kevin MacLeod's incompetech.com catalog. Every track is licensed
under Creative Commons Attribution 3.0/4.0 -- free for commercial use
(including monetized YouTube) as long as the attribution text is included
somewhere reasonably discoverable (we add it to the video description via
AutoPublisher.generate_metadata, see the `music_credit` return value).
Direct-download URLs are stable and don't require any API key or rate
limit: https://incompetech.com/music/royalty-free/mp3-royaltyfree/{track}.mp3

Every track name below was verified with a live HTTP HEAD/GET request
during this session (2026-07-05) to confirm it actually exists at that
exact URL before being added to this list -- this is not a guess.

MOOD MAPPING: each niche gets a short curated list of tracks whose "Feel"
tags on incompetech.com (Dark/Suspenseful/Mysterious/Eerie for true crime
and mystery; Calm/Reflective/Ambient for psychology/finance/space) actually
match the tone research says works for that content type (see
docs/YOUTUBE-GROWTH-AND-ENGAGEMENT.md and docs/CONTENT-BANK.md). A track is
picked at random from the niche's list per video so repeat viewers of the
same channel don't hear the identical loop every single time.
"""

import os
import time

import requests

_BASE_URL = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
_OUT_DIR = "assets/music"

_ATTRIBUTION_TEMPLATE = (
    '"{track}" by Kevin MacLeod (incompetech.com)\n'
    "Licensed under Creative Commons: By Attribution 4.0 License\n"
    "http://creativecommons.org/licenses/by/4.0/"
)

# Verified live (HTTP 200) on 2026-07-05 -- see this module's docstring.
# Track choice per niche is based on incompetech.com's own "Feel" tags.
_NICHE_TRACKS = {
    "true_crime": ["Wounded", "Killers", "Investigations", "Deadly Roulette", "Dark Times"],
    "history_mystery": ["Long Note One", "The Descent", "Ghost Story", "Investigations"],
    "psychology": ["Marty Gots a Plan", "Thinking Music", "Life of Riley", "Isolated"],
    "luxury_lifestyle": ["Cool Vibes", "Local Forecast", "Modern Jazz Samba", "Life of Riley"],
    "finance": ["Impact Prelude", "Impact Moderato", "Prelude and Action", "The Complex"],
    "space_science": ["Long Note One", "Isolated", "The Descent", "Sneaky Adventure"],
}

_DEFAULT_TRACKS = ["Local Forecast", "Life of Riley", "Isolated"]


def _cache_path(track: str) -> str:
    safe_name = "".join(c if c.isalnum() else "_" for c in track)
    return os.path.join(_OUT_DIR, f"{safe_name}.mp3")


def get_track_for_niche(niche_key: str) -> dict:
    """Returns {'path': <local mp3>, 'track': <name>, 'credit': <attribution
    text>} on success, or {} if the download failed (caller should proceed
    without music rather than fail the whole video -- see
    core/video_assembler.py's build_video, which already treats an empty/
    missing music_path as "no music" gracefully)."""
    import random

    candidates = _NICHE_TRACKS.get(niche_key, _DEFAULT_TRACKS)
    track = random.choice(candidates)
    os.makedirs(_OUT_DIR, exist_ok=True)
    out_path = _cache_path(track)

    # Cache locally so a repeat run (or another scene in the same run) never
    # re-downloads the same ~5-10MB file twice.
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        return {"path": out_path, "track": track, "credit": _ATTRIBUTION_TEMPLATE.format(track=track)}

    url = _BASE_URL + track.replace(" ", "%20") + ".mp3"
    try:
        r = requests.get(url, timeout=30, stream=True)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
        print(f"[MusicLibrary] Using background track '{track}' for niche '{niche_key}'")
        return {"path": out_path, "track": track, "credit": _ATTRIBUTION_TEMPLATE.format(track=track)}
    except requests.RequestException as e:
        print(f"[MusicLibrary] Failed to fetch '{track}': {e} -- proceeding without background music")
        return {}


if __name__ == "__main__":
    print(get_track_for_niche("true_crime"))
