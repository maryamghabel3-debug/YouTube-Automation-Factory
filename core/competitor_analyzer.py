"""CompetitorAnalyzer — looks at currently high-performing YouTube videos in
a channel's niche BEFORE writing a script, and produces a short summary of
WHY they're working (hook style, structure, pacing) so ScriptWriter can
apply those patterns to a brand-new, original script.

This directly implements the strategy the user asked for: "we should pay
attention to videos that get high views when building our strategy."

Uses the read-only YOUTUBE_API_KEY (search.list + videos.list) -- the same
key already configured for PerformanceAnalyzer, no extra credential needed.
Never copies specific content: only titles/stats/top-comment excerpts are
fed to the LLM, and the LLM is explicitly instructed (in script_writer.py)
to extract PATTERNS, not facts or phrasing, from them.
"""

import os

import requests

from .llm_router import LLMRouter

_YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
_YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


class CompetitorAnalyzer:
    def __init__(self):
        self.name = "CompetitorAnalyzer"
        self.api_key = os.environ.get("YOUTUBE_API_KEY", "")
        self.router = LLMRouter()

    def _search_top_videos(self, query: str, max_results: int = 6) -> list:
        """Finds recent, relevant videos for a search query, then fetches
        their view/like counts to rank by actual popularity (search.list
        alone only ranks by 'relevance', not views)."""
        if not self.api_key:
            return []
        try:
            r = requests.get(
                _YT_SEARCH,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "viewCount",
                    "maxResults": max_results,
                    "key": self.api_key,
                },
                timeout=15,
            )
            r.raise_for_status()
            video_ids = [it["id"]["videoId"] for it in r.json().get("items", []) if it.get("id", {}).get("videoId")]
        except (requests.RequestException, KeyError) as e:
            print(f"[{self.name}] search error: {e}")
            return []

        if not video_ids:
            return []

        try:
            r2 = requests.get(
                _YT_VIDEOS,
                params={
                    "part": "snippet,statistics",
                    "id": ",".join(video_ids),
                    "key": self.api_key,
                },
                timeout=15,
            )
            r2.raise_for_status()
            out = []
            for item in r2.json().get("items", []):
                sn, stats = item.get("snippet", {}), item.get("statistics", {})
                out.append({
                    "title": sn.get("title", ""),
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                })
            out.sort(key=lambda v: v["views"], reverse=True)
            return out
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"[{self.name}] video-details error: {e}")
            return []

    def analyze(self, niche_label: str, search_terms: list) -> str:
        """Returns a short natural-language summary of successful patterns
        in this niche right now, or '' if no data / no API key configured
        (ScriptWriter simply skips the extra context in that case)."""
        if not self.api_key:
            return ""

        query = f"{niche_label} " + (search_terms[0] if search_terms else "")
        top_videos = self._search_top_videos(query.strip())
        if not top_videos:
            return ""

        titles_block = "\n".join(
            f"- \"{v['title']}\" ({v['views']:,} views, {v['likes']:,} likes)"
            for v in top_videos[:6]
        )

        system_prompt = (
            "You analyze YouTube video titles and stats to identify GENERAL success "
            "patterns (hook style, title structure, pacing/tone implied), never facts "
            "about the specific videos themselves."
        )
        user_prompt = (
            f"Here are currently popular video titles in the '{niche_label}' niche, "
            f"with view/like counts:\n\n{titles_block}\n\n"
            f"In 3-4 short bullet points, summarize the PATTERNS that seem to drive "
            f"engagement here (e.g. hook phrasing style, use of numbers/mystery/questions "
            f"in titles, implied pacing). Do not mention or reference the specific titles "
            f"or channels. Keep it under 100 words total."
        )

        result = self.router.generate(system_prompt, user_prompt)
        if "text" in result:
            return result["text"].strip()
        return ""


if __name__ == "__main__":
    analyzer = CompetitorAnalyzer()
    print(analyzer.analyze("True Crime & Cold Cases", ["unsolved mystery", "cold case"]))
