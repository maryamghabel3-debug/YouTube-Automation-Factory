"""StockFootageFetcher — real, free, commercially-licensed b-roll.

Uses Pexels and Pixabay (both free, no credit card, no sanctions issues —
signup is email-only). Both licenses allow commercial use without
attribution. Falls back Pexels -> Pixabay -> a solid-color placeholder frame
so the pipeline never crashes even with no keys configured.

Set PEXELS_API_KEY and/or PIXABAY_API_KEY as environment variables.
"""

import os
import time
import random

import requests

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
    def _pexels_video(self, query: str) -> str:
        if not self.pexels_key:
            return ""
        try:
            r = self.session.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": 5, "orientation": "landscape"},
                timeout=20,
            )
            r.raise_for_status()
            videos = r.json().get("videos", [])
            if not videos:
                return ""
            video = random.choice(videos)
            # Pick the highest-resolution file under ~1080p to keep downloads fast
            files = sorted(
                [f for f in video.get("video_files", []) if f.get("width", 0) <= 1920],
                key=lambda f: f.get("width", 0),
                reverse=True,
            )
            if not files:
                return ""
            url = files[0]["link"]
            return self._download(url, ext="mp4")
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pexels video error: {e}")
            return ""

    def _pexels_photo(self, query: str) -> str:
        if not self.pexels_key:
            return ""
        try:
            r = self.session.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": 5, "orientation": "landscape"},
                timeout=20,
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos:
                return ""
            photo = random.choice(photos)
            url = photo["src"]["large2x"]
            return self._download(url, ext="jpg")
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pexels photo error: {e}")
            return ""

    # ------------------------------------------------------------------ #
    # Pixabay (fallback)
    # ------------------------------------------------------------------ #
    def _pixabay_video(self, query: str) -> str:
        if not self.pixabay_key:
            return ""
        try:
            r = self.session.get(
                "https://pixabay.com/api/videos/",
                params={"key": self.pixabay_key, "q": query, "per_page": 5},
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return ""
            hit = random.choice(hits)
            url = hit["videos"]["medium"]["url"]
            return self._download(url, ext="mp4")
        except requests.RequestException as e:
            print(f"[StockFootageFetcher] Pixabay video error: {e}")
            return ""

    def _pixabay_photo(self, query: str) -> str:
        if not self.pixabay_key:
            return ""
        try:
            r = self.session.get(
                "https://pixabay.com/api/",
                params={"key": self.pixabay_key, "q": query, "per_page": 5, "image_type": "photo"},
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return ""
            hit = random.choice(hits)
            url = hit["largeImageURL"]
            return self._download(url, ext="jpg")
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
    def fetch_clip(self, query: str, prefer_video: bool = True) -> dict:
        """Returns {'path': ..., 'type': 'video'|'image', 'source': ...}."""
        order = (
            [("pexels_video", self._pexels_video), ("pixabay_video", self._pixabay_video),
             ("pexels_photo", self._pexels_photo), ("pixabay_photo", self._pixabay_photo)]
            if prefer_video
            else [("pexels_photo", self._pexels_photo), ("pixabay_photo", self._pixabay_photo),
                  ("pexels_video", self._pexels_video), ("pixabay_video", self._pixabay_video)]
        )
        for name, fn in order:
            path = fn(query)
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
            try:
                clip = self.fetch_clip(query)
            except Exception as e:
                print(f"[StockFootageFetcher] scene fetch failed ({query}): {e}")
                clip = {"path": self._placeholder(), "type": "image", "source": "placeholder"}
            results.append({**scene, "clip": clip})
        return results


if __name__ == "__main__":
    fetcher = StockFootageFetcher()
    print(fetcher.fetch_clip("meditation calm"))
