"""PerformanceAnalyzer Agent — reads real YouTube Analytics for each channel
(via the YouTube Data API's videos.list statistics endpoint) so the factory
can learn which topics/niches perform best over time. This was a 0-byte stub
in the original blueprint; this is a real, working implementation.
"""

import os
import json

try:
    from googleapiclient.discovery import build
    _HAS_GOOGLE_LIBS = True
except ImportError:
    _HAS_GOOGLE_LIBS = False

_LOG_PATH = "channels/performance_log.json"


class PerformanceAnalyzer:
    def __init__(self):
        self.name = "PerformanceAnalyzer"
        self.api_key = os.environ.get("YOUTUBE_API_KEY", "")

    def get_video_stats(self, video_id: str) -> dict:
        """Real view/like/comment counts for a single uploaded video.
        Uses the read-only YOUTUBE_API_KEY (no OAuth needed for public stats)."""
        if not self.api_key or not _HAS_GOOGLE_LIBS:
            return {"error": "no_api_key_or_missing_google_libs"}
        try:
            youtube = build("youtube", "v3", developerKey=self.api_key)
            resp = youtube.videos().list(part="statistics,snippet", id=video_id).execute()
            items = resp.get("items", [])
            if not items:
                return {"error": "video_not_found"}
            stats = items[0]["statistics"]
            return {
                "video_id": video_id,
                "title": items[0]["snippet"]["title"],
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }
        except Exception as e:
            print(f"[{self.name}] stats fetch error: {e}")
            return {"error": str(e)}

    def log_upload(self, channel_id: str, topic: str, video_id: str, url: str):
        """Append a record of what was produced/uploaded so future analysis
        can correlate topics with performance."""
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        log = []
        if os.path.exists(_LOG_PATH):
            try:
                with open(_LOG_PATH) as f:
                    log = json.load(f)
            except (OSError, json.JSONDecodeError):
                log = []
        log.append({"channel_id": channel_id, "topic": topic, "video_id": video_id, "url": url})
        with open(_LOG_PATH, "w") as f:
            json.dump(log[-500:], f, indent=2, ensure_ascii=False)

    def best_performing_topics(self, channel_id: str = None, top_n: int = 5) -> list:
        """Looks up real stats for every logged upload and returns the
        top-performing topics by view count. Skips entries with API errors."""
        if not os.path.exists(_LOG_PATH):
            return []
        with open(_LOG_PATH) as f:
            log = json.load(f)
        if channel_id:
            log = [e for e in log if e["channel_id"] == channel_id]

        scored = []
        for entry in log:
            stats = self.get_video_stats(entry["video_id"])
            if "error" not in stats:
                scored.append({**entry, **stats})
        scored.sort(key=lambda e: e.get("views", 0), reverse=True)
        return scored[:top_n]


if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    print(json.dumps(analyzer.best_performing_topics(), indent=2, ensure_ascii=False))
