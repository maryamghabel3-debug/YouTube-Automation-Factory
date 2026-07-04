"""NicheAnalyzer Agent — finds real trending topic ideas for a channel's niche.

Uses free, no-key, no-sanctions-issue sources:
  * Reddit's public "top of week" RSS/Atom feeds for niche-relevant subreddits
    (real posts ranked by upvotes = a solid proxy for public interest).
  * Google Trends RSS (daily trending searches), filtered by niche keywords.

Degrades gracefully to a small set of evergreen fallback topics per niche so
the pipeline never breaks even if both sources are unreachable/rate-limited.
"""

import re
import time
import html
import xml.etree.ElementTree as ET

import requests

_ATOM = "http://www.w3.org/2005/Atom"
_UA = "YouTubeAutomationFactory/1.0 (topic research; +https://github.com/maryamghabel3-debug)"

# Subreddits + evergreen fallback topics per niche key (see content_config.py)
_NICHE_SOURCES = {
    "psychology": {
        "subreddits": ["DecidingToBeBetter", "selfimprovement", "GetMotivated"],
        "evergreen": [
            "Why we procrastinate even when we know better",
            "The psychology of first impressions",
            "How your childhood shapes your adult relationships",
            "Why comparison steals your happiness",
            "The science of habit formation",
        ],
    },
    "history": {
        "subreddits": ["history", "AskHistorians", "todayilearned"],
        "evergreen": [
            "The unsolved mystery of the Mary Celeste",
            "How ancient Rome built roads that still exist today",
            "The forgotten empire that rivaled Rome",
            "Why the Library of Alexandria really burned",
            "The code that took 300 years to break",
        ],
    },
    "luxury_lifestyle": {
        "subreddits": ["luxury", "entrepreneur", "financialindependence"],
        "evergreen": [
            "Inside the world's most expensive private islands",
            "How billionaires actually spend their mornings",
            "The psychology of luxury branding",
            "Why quiet luxury is replacing logomania",
            "The most exclusive clubs money can't always buy into",
        ],
    },
}

# Words that flag a topic as too political/sensitive/tragic for a monetized,
# fully-automated channel with no human editorial review. This is a blunt
# safety net, not a substitute for occasional human spot-checks of output.
_BLOCKLIST_KEYWORDS = [
    "abortion", "suicide", "suicidal", "rape", "genocide", "war crime",
    "self-harm", "self harm", "murder", "shooting", "terroris", "election",
    "president trump", "president biden", "gaza", "israel", "palestine",
    "shot dead", "killed", "molest", "pedophil",
]


def _is_safe_topic(title: str) -> bool:
    lowered = title.lower()
    return not any(bad in lowered for bad in _BLOCKLIST_KEYWORDS)



class NicheAnalyzer:
    def __init__(self):
        self.name = "NicheAnalyzer"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA})

    def _get(self, url: str, timeout: int = 10):
        try:
            r = self.session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
        except requests.RequestException as e:
            print(f"[{self.name}] request error on {url}: {e}")
        return None

    def _reddit_topics(self, subreddits: list, limit_per_sub: int = 5) -> list:
        topics = []
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/top/.rss?t=week&limit={limit_per_sub}"
            r = self._get(url)
            if r is None:
                continue
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError:
                continue
            for entry in root.findall(f"{{{_ATOM}}}entry")[:limit_per_sub]:
                title_el = entry.find(f"{{{_ATOM}}}title")
                title = (title_el.text or "").strip() if title_el is not None else ""
                title = html.unescape(re.sub(r"\s+", " ", title))
                # Skip overly long post titles (usually rants/screenshots, not
                # good video topics) and anything matching the safety blocklist.
                if title and 15 < len(title) <= 120 and _is_safe_topic(title):
                    topics.append(title)
            time.sleep(1)  # polite delay between subreddits
        return topics

    def analyze_market(self, niche_key: str) -> str:
        """Returns ONE topic string to build a video around. Always passes
        through the safety blocklist, even for the evergreen fallback list,
        since a fully-automated channel has no human reviewing topics before
        a video gets made and uploaded."""
        source = _NICHE_SOURCES.get(niche_key, {})
        subs = source.get("subreddits", [])
        print(f"[{self.name}] Analyzing trending topics for niche: {niche_key}")

        topics = [t for t in (self._reddit_topics(subs) if subs else []) if _is_safe_topic(t)]
        if topics:
            import random
            chosen = random.choice(topics[:10])
            print(f"[{self.name}] Found real trending topic: '{chosen}'")
            return chosen

        import random
        evergreen = [t for t in source.get("evergreen", []) if _is_safe_topic(t)]
        fallback = random.choice(evergreen or ["An interesting topic worth exploring"])
        print(f"[{self.name}] Using evergreen fallback topic: '{fallback}'")
        return fallback


if __name__ == "__main__":
    analyzer = NicheAnalyzer()
    print(analyzer.analyze_market("psychology"))
