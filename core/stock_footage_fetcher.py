"""StockFootageFetcher — real, free, commercially-licensed b-roll.

Uses Pexels and Pixabay (both free, no credit card, no sanctions issues —
signup is email-only). Both licenses allow commercial use without
attribution. Falls back Pexels -> Pixabay -> a solid-color placeholder frame
so the pipeline never crashes even with no keys configured.

Set PEXELS_API_KEY and/or PIXABAY_API_KEY as environment variables.

QUALITY SELECTION: rather than picking randomly among the raw search
results (the previous, honest-but-crude behavior), every candidate returned
by the API is scored by core/footage_quality.py on resolution, aspect-ratio
fit, duration fit (for video), and query-tag relevance, and the
highest-scoring one is downloaded. See that module's docstring for the full
explicit criteria -- this directly answers "how does the system know if a
photo/video is good or bad for this video."

NO-REPEAT-WITHIN-A-VIDEO (added 2026-07-05, found via user review): the
previous version scored candidates independently per scene, with no memory
of what had already been picked earlier in the SAME video. Since
footage_quality.pick_best() is deterministic, any two scenes that searched
the same or a similar query (e.g. two "city skyline night" scenes in one
script) always got the literal identical top-scoring clip downloaded and
shown twice -- looking like a rendering mistake to a viewer. fetch_for_script()
now tracks every clip id used so far in `_used_ids` and passes it through to
pick_best()'s `exclude_ids`, so a repeated query still returns a *different*
(the next-best) real clip instead of literally re-using the same one.
"""

import os
import time
import random

import requests

from . import footage_quality

_OUT_DIR = "assets/footage"


class StockFootageFetcher:
    def __init__(self):
        self.pexels_key = os.environ.get("PEXELS_API_KEY", "")
        self.pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
        self.session = requests.Session()
        os.makedirs(_OUT_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Pexels
    # ------------------------------------------------------------------ #
    def _pexels_video(self, query: str, needed_duration: float = 0.0, exclude_ids: set = None) -> tuple:
        """Returns (path, candidate_id) or ("", None)."""
        if not self.pexels_key:
            return "", None
        try:
            r = self.session.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": 10, "orientation": "landscape"},
                timeout=20,
            )
            r.raise_for_status()
            videos = r.json().get("videos", [])
            if not videos:
                return "", None

            candidates = []
            for video in videos:
                # Pexels doesn't return tags per-video in this endpoint, but
                # the videographer's page URL slug often contains descriptive
                # words -- combined with the video's own "url" field, this
                # gives footage_quality.py SOME text signal for relevance
                # scoring beyond pure resolution/aspect/duration.
                description_hint = video.get("url", "")
                candidates.append({
                    "_id": f"pexels_video_{video.get('id')}",
                    "width": video.get("width", 0),
                    "height": video.get("height", 0),
                    "duration": video.get("duration", 0),
                    "description": description_hint,
                    "_video_files": video.get("video_files", []),
                })

            best = footage_quality.pick_best(
                query, candidates, needed_duration=needed_duration, exclude_ids=exclude_ids,
            )
            if not best:
                return "", None
            print(f"[StockFootageFetcher] Pexels video pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")

            files = sorted(
                [f for f in best["_video_files"] if f.get("width", 0) <= 1920],
                key=lambda f: f.get("width", 0),
                reverse=True,
            )
            if not files:
                return "", None
            return self._download(files[0]["link"], ext="mp4"), best["_id"]
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pexels video error: {e}")
            return "", None

    def _pexels_photo(self, query: str, needed_duration: float = 0.0, exclude_ids: set = None) -> tuple:
        if not self.pexels_key:
            return "", None
        try:
            r = self.session.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": 10, "orientation": "landscape"},
                timeout=20,
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos:
                return "", None

            candidates = [
                {
                    "_id": f"pexels_photo_{p.get('id')}",
                    "width": p.get("width", 0),
                    "height": p.get("height", 0),
                    "description": p.get("alt", ""),
                    "_url": p["src"]["large2x"],
                }
                for p in photos
            ]
            best = footage_quality.pick_best(query, candidates, exclude_ids=exclude_ids)
            if not best:
                return "", None
            print(f"[StockFootageFetcher] Pexels photo pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")
            return self._download(best["_url"], ext="jpg"), best["_id"]
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pexels photo error: {e}")
            return "", None

    # ------------------------------------------------------------------ #
    # Pixabay (fallback)
    # ------------------------------------------------------------------ #
    def _pixabay_video(self, query: str, needed_duration: float = 0.0, exclude_ids: set = None) -> tuple:
        if not self.pixabay_key:
            return "", None
        try:
            r = self.session.get(
                "https://pixabay.com/api/videos/",
                params={"key": self.pixabay_key, "q": query, "per_page": 10},
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return "", None

            candidates = []
            for hit in hits:
                medium = hit.get("videos", {}).get("medium", {})
                candidates.append({
                    "_id": f"pixabay_video_{hit.get('id')}",
                    "width": medium.get("width", 0),
                    "height": medium.get("height", 0),
                    "duration": hit.get("duration", 0),
                    "description": " ".join(hit.get("tags", "").split(",")),
                    "_url": medium.get("url", ""),
                })
            best = footage_quality.pick_best(
                query, candidates, needed_duration=needed_duration, exclude_ids=exclude_ids,
            )
            if not best or not best.get("_url"):
                return "", None
            print(f"[StockFootageFetcher] Pixabay video pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")
            return self._download(best["_url"], ext="mp4"), best["_id"]
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pixabay video error: {e}")
            return "", None

    def _pixabay_photo(self, query: str, needed_duration: float = 0.0, exclude_ids: set = None) -> tuple:
        if not self.pixabay_key:
            return "", None
        try:
            r = self.session.get(
                "https://pixabay.com/api/",
                params={"key": self.pixabay_key, "q": query, "per_page": 10, "image_type": "photo"},
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return "", None

            candidates = [
                {
                    "_id": f"pixabay_photo_{hit.get('id')}",
                    "width": hit.get("imageWidth", 0),
                    "height": hit.get("imageHeight", 0),
                    "description": " ".join(hit.get("tags", "").split(",")),
                    "_url": hit.get("largeImageURL", ""),
                }
                for hit in hits
            ]
            best = footage_quality.pick_best(query, candidates, exclude_ids=exclude_ids)
            if not best or not best.get("_url"):
                return "", None
            print(f"[StockFootageFetcher] Pixabay photo pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")
            return self._download(best["_url"], ext="jpg"), best["_id"]
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pixabay photo error: {e}")
            return "", None

    # ------------------------------------------------------------------ #
    # Openverse (no-API-key-required fallback, 2026-07-05) -- when neither
    # PEXELS_API_KEY nor PIXABAY_API_KEY is configured in this environment,
    # every scene used to fall straight to a flat gray placeholder frame,
    # which looks broken to a viewer. Openverse (openverse.org, run by
    # WordPress/Automattic) indexes openly-licensed (CC/public-domain)
    # photos from Flickr, museums, etc. and its search API works fully
    # anonymously with no signup/key at all (rate-limited to ~100
    # requests/day per IP without a key, which is fine for occasional runs
    # in this environment -- a real production deployment should still get
    # free Pexels/Pixabay keys for higher-quality curated stock footage).
    # license_type=commercial only returns images cleared for commercial
    # reuse (no NC-restricted licenses), matching the free-and-legal
    # standard already used for Pexels/Pixabay elsewhere in this file.
    # ------------------------------------------------------------------ #
    def _openverse_photo(self, query: str, needed_duration: float = 0.0, exclude_ids: set = None) -> tuple:
        try:
            r = self.session.get(
                "https://api.openverse.org/v1/images/",
                params={
                    "q": query, "page_size": 10, "license_type": "commercial",
                    "aspect_ratio": "wide", "mature": "false",
                },
                timeout=20,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if not results:
                return "", None

            candidates = [
                {
                    "_id": f"openverse_photo_{img.get('id')}",
                    "width": img.get("width") or 0,
                    "height": img.get("height") or 0,
                    "description": img.get("title", "") + " " +
                                   " ".join(t.get("name", "") for t in (img.get("tags") or [])),
                    "_url": img.get("url", ""),
                }
                for img in results
                if img.get("url")
            ]
            if not candidates:
                return "", None
            best = footage_quality.pick_best(query, candidates, exclude_ids=exclude_ids)
            if not best or not best.get("_url"):
                return "", None
            print(f"[StockFootageFetcher] Openverse photo pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")
            return self._download(best["_url"], ext="jpg"), best["_id"]
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Openverse photo error: {e}")
            return "", None

    # ------------------------------------------------------------------ #
    def _download(self, url: str, ext: str) -> str:
        out_path = os.path.join(_OUT_DIR, f"clip_{int(time.time()*1000)}_{random.randint(0,9999)}.{ext}")
        try:
            r = self.session.get(url, timeout=60, stream=True)
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
            return out_path
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] download error: {e}")
            return ""

    def _placeholder(self) -> str:
        """Last-resort: a solid dark-gray still frame so rendering never breaks."""
        try:
            from PIL import Image

            out_path = os.path.join(_OUT_DIR, f"placeholder_{int(time.time()*1000)}.jpg")
            Image.new("RGB", (1920, 1080), (30, 30, 35)).save(out_path)
            return out_path
        except Exception as e:
            print(f"[StockFootageFetcher] placeholder error: {e}")
            return ""

    # ------------------------------------------------------------------ #
    def fetch_clip(self, query: str, prefer_video: bool = True, needed_duration: float = 0.0,
                    exclude_ids: set = None) -> dict:
        """Returns {'path': ..., 'type': 'video'|'image', 'source': ..., 'id': ...}.
        needed_duration (seconds): how long this scene's narration is, used
        by footage_quality.py to prefer video clips that don't need to loop.
        exclude_ids (optional): candidate ids already used earlier in this
        same video (see fetch_for_script) -- skipped so the same clip is
        never shown twice in one video."""
        order = (
            [("pexels_video", self._pexels_video), ("pixabay_video", self._pixabay_video),
             ("pexels_photo", self._pexels_photo), ("pixabay_photo", self._pixabay_photo),
             ("openverse_photo", self._openverse_photo)]
            if prefer_video
            else [("pexels_photo", self._pexels_photo), ("pixabay_photo", self._pixabay_photo),
                  ("openverse_photo", self._openverse_photo),
                  ("pexels_video", self._pexels_video), ("pixabay_video", self._pixabay_video)]
        )
        for name, fn in order:
            if "video" in name:
                path, cid = fn(query, needed_duration, exclude_ids=exclude_ids)
            else:
                path, cid = fn(query, exclude_ids=exclude_ids)
            if path:
                return {"path": path, "type": "video" if "video" in name else "image",
                        "source": name, "id": cid}

        placeholder = self._placeholder()
        return {"path": placeholder, "type": "image", "source": "placeholder", "id": None}

    def fetch_for_script(self, scenes: list) -> list:
        """For each scene dict {'text': ..., 'query': ...}, attaches:
          - 'clip': the primary clip (backwards-compatible single clip)
          - 'extra_clips': additional DIFFERENT real clips for the SAME
            query, used by VideoAssembler when a scene's narration is long
            enough to be split into multiple sub-cuts (see
            core.video_assembler._MAX_SEGMENT_SECONDS).

        BUG FIXED (found by user review 2026-07-05, round 2): the first fix
        only prevented the exact same clip from being reused ACROSS scenes.
        But VideoAssembler's scene-splitting (for scenes longer than ~6s)
        was still re-using that ONE clip for every sub-cut of that same
        scene, just with a different pan/zoom -- which visually still reads
        as "the same picture shown again" to a viewer, not a real cut. Now
        each long scene gets several genuinely different real clips
        up-front (same search query, different results), one per sub-cut.

        Wrapped so a single failed fetch never crashes the whole pipeline.
        Tracks every clip id already used earlier in THIS call (across ALL
        scenes and all their extra_clips) so nothing repeats anywhere in
        the finished video."""
        results = []
        used_ids = set()
        for scene in scenes:
            query = scene.get("query") or scene.get("text", "")[:40]
            # Rough duration estimate per scene: ~2.5 words/second of speech,
            # used only to bias footage_quality.py toward clips long enough
            # to avoid visible looping -- VideoAssembler computes the exact
            # duration later from real narration timing.
            words = len(scene.get("text", "").split())
            estimated_duration = max(words / 2.5, 1.5)
            # Same _MAX_SEGMENT_SECONDS logic VideoAssembler uses to decide
            # how many sub-cuts a scene this long will need, so we fetch
            # exactly that many DIFFERENT real clips up-front.
            approx_subcuts = max(1, round(estimated_duration / 6.0))

            try:
                clip = self.fetch_clip(query, needed_duration=estimated_duration / approx_subcuts,
                                        exclude_ids=used_ids)
            except Exception as e:
                print(f"[StockFootageFetcher] scene fetch failed ({query}): {e}")
                clip = {"path": self._placeholder(), "type": "image", "source": "placeholder", "id": None}
            if clip.get("id"):
                used_ids.add(clip["id"])

            extra_clips = []
            for _ in range(approx_subcuts - 1):
                try:
                    extra = self.fetch_clip(query, needed_duration=estimated_duration / approx_subcuts,
                                             exclude_ids=used_ids)
                except Exception as e:
                    print(f"[StockFootageFetcher] extra sub-cut fetch failed ({query}): {e}")
                    extra = {}
                if extra.get("path"):
                    if extra.get("id"):
                        used_ids.add(extra["id"])
                    extra_clips.append(extra)

            results.append({**scene, "clip": clip, "extra_clips": extra_clips})
        return results


if __name__ == "__main__":
    fetcher = StockFootageFetcher()
    print(fetcher.fetch_clip("meditation calm"))
