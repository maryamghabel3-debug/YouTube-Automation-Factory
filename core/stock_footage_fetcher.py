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
    def _pexels_video(self, query: str, needed_duration: float = 0.0) -> str:
        if not self.pexels_key:
            return ""
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
                return ""

            candidates = []
            for video in videos:
                # Pexels doesn't return tags per-video in this endpoint, but
                # the videographer's page URL slug often contains descriptive
                # words -- combined with the video's own "url" field, this
                # gives footage_quality.py SOME text signal for relevance
                # scoring beyond pure resolution/aspect/duration.
                description_hint = video.get("url", "")
                candidates.append({
                    "width": video.get("width", 0),
                    "height": video.get("height", 0),
                    "duration": video.get("duration", 0),
                    "description": description_hint,
                    "_video_files": video.get("video_files", []),
                })

            best = footage_quality.pick_best(query, candidates, needed_duration=needed_duration)
            if not best:
                return ""
            print(f"[StockFootageFetcher] Pexels video pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")

            files = sorted(
                [f for f in best["_video_files"] if f.get("width", 0) <= 1920],
                key=lambda f: f.get("width", 0),
                reverse=True,
            )
            if not files:
                return ""
            return self._download(files[0]["link"], ext="mp4")
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pexels video error: {e}")
            return ""

    def _pexels_photo(self, query: str, needed_duration: float = 0.0) -> str:
        if not self.pexels_key:
            return ""
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
                return ""

            candidates = [
                {
                    "width": p.get("width", 0),
                    "height": p.get("height", 0),
                    "description": p.get("alt", ""),
                    "_url": p["src"]["large2x"],
                }
                for p in photos
            ]
            best = footage_quality.pick_best(query, candidates)
            if not best:
                return ""
            print(f"[StockFootageFetcher] Pexels photo pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")
            return self._download(best["_url"], ext="jpg")
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pexels photo error: {e}")
            return ""

    # ------------------------------------------------------------------ #
    # Pixabay (fallback)
    # ------------------------------------------------------------------ #
    def _pixabay_video(self, query: str, needed_duration: float = 0.0) -> str:
        if not self.pixabay_key:
            return ""
        try:
            r = self.session.get(
                "https://pixabay.com/api/videos/",
                params={"key": self.pixabay_key, "q": query, "per_page": 10},
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return ""

            candidates = []
            for hit in hits:
                medium = hit.get("videos", {}).get("medium", {})
                candidates.append({
                    "width": medium.get("width", 0),
                    "height": medium.get("height", 0),
                    "duration": hit.get("duration", 0),
                    "description": " ".join(hit.get("tags", "").split(",")),
                    "_url": medium.get("url", ""),
                })
            best = footage_quality.pick_best(query, candidates, needed_duration=needed_duration)
            if not best or not best.get("_url"):
                return ""
            print(f"[StockFootageFetcher] Pixabay video pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")
            return self._download(best["_url"], ext="mp4")
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pixabay video error: {e}")
            return ""

    def _pixabay_photo(self, query: str, needed_duration: float = 0.0) -> str:
        if not self.pixabay_key:
            return ""
        try:
            r = self.session.get(
                "https://pixabay.com/api/",
                params={"key": self.pixabay_key, "q": query, "per_page": 10, "image_type": "photo"},
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return ""

            candidates = [
                {
                    "width": hit.get("imageWidth", 0),
                    "height": hit.get("imageHeight", 0),
                    "description": " ".join(hit.get("tags", "").split(",")),
                    "_url": hit.get("largeImageURL", ""),
                }
                for hit in hits
            ]
            best = footage_quality.pick_best(query, candidates)
            if not best or not best.get("_url"):
                return ""
            print(f"[StockFootageFetcher] Pixabay photo pick score={best['_quality_score']} "
                  f"breakdown={best['_quality_breakdown']}")
            return self._download(best["_url"], ext="jpg")
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pixabay photo error: {e}")
            return ""

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
    def fetch_clip(self, query: str, prefer_video: bool = True, needed_duration: float = 0.0) -> dict:
        """Returns {'path': ..., 'type': 'video'|'image', 'source': ...}.
        needed_duration (seconds): how long this scene's narration is, used
        by footage_quality.py to prefer video clips that don't need to loop."""
        order = (
            [("pexels_video", self._pexels_video), ("pixabay_video", self._pixabay_video),
             ("pexels_photo", self._pexels_photo), ("pixabay_photo", self._pixabay_photo)]
            if prefer_video
            else [("pexels_photo", self._pexels_photo), ("pixabay_photo", self._pixabay_photo),
                  ("pexels_video", self._pexels_video), ("pixabay_video", self._pixabay_video)]
        )
        for name, fn in order:
            path = fn(query, needed_duration) if "video" in name else fn(query)
            if path:
                return {"path": path, "type": "video" if "video" in name else "image", "source": name}

        placeholder = self._placeholder()
        return {"path": placeholder, "type": "image", "source": "placeholder"}

    def fetch_for_script(self, scenes: list) -> list:
        """For each scene dict {'text': ..., 'query': ...}, attach a real clip.
        Wrapped so a single failed fetch never crashes the whole pipeline."""
        results = []
        for scene in scenes:
            query = scene.get("query") or scene.get("text", "")[:40]
            # Rough duration estimate per scene: ~2.5 words/second of speech,
            # used only to bias footage_quality.py toward clips long enough
            # to avoid visible looping -- VideoAssembler computes the exact
            # duration later from real narration timing.
            estimated_duration = max(len(scene.get("text", "").split()) / 2.5, 1.5)
            try:
                clip = self.fetch_clip(query, needed_duration=estimated_duration)
            except Exception as e:
                print(f"[StockFootageFetcher] scene fetch failed ({query}): {e}")
                clip = {"path": self._placeholder(), "type": "image", "source": "placeholder"}
            results.append({**scene, "clip": clip})
        return results


if __name__ == "__main__":
    fetcher = StockFootageFetcher()
    print(fetcher.fetch_clip("meditation calm"))
