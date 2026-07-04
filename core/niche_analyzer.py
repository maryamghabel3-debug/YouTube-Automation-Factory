"""NicheAnalyzer Agent — finds real trending topic ideas for a channel's niche.

Reads niche -> subreddits/evergreen-topics mapping from content_config.NICHES
(single source of truth — adding a new niche there is enough, no changes
needed here).

Uses free, no-key, no-sanctions-issue sources:
  * Reddit's public "top of week" RSS/Atom feeds for niche-relevant subreddits
    (real posts ranked by upvotes = a solid proxy for public interest).
  * Google Trends RSS (daily trending searches), filtered by niche keywords —
    a second, independent signal so a single subreddit having a quiet week
    doesn't starve the pipeline of topics.

Degrades gracefully to a small set of evergreen fallback topics per niche so
the pipeline never breaks even if both sources are unreachable/rate-limited.
"""

import re
import time
import html
import random
import xml.etree.ElementTree as ET

import requests

from . import content_config as cfg
from . import channel_memory
from . import content_bank
from .llm_router import LLMRouter

_ATOM = "http://www.w3.org/2005/Atom"
_UA = "YouTubeAutomationFactory/1.0 (topic research; +https://github.com/maryamghabel3-debug)"

# Words that flag a topic as too political/sensitive/tragic for a monetized,
# fully-automated channel with no human editorial review. This is a blunt
# safety net (inspired by RedditVideoMakerBot's "blocked-words" list — see
# docs/GITHUB-AGENTS-EVALUATION.md), not a substitute for occasional human
# spot-checks of output.
_BLOCKLIST_KEYWORDS = [
    "abortion", "suicide", "suicidal", "rape", "genocide", "war crime",
    "self-harm", "self harm", "murder", "shooting", "terroris", "election",
    "president trump", "president biden", "gaza", "israel", "palestine",
    "shot dead", "killed", "molest", "pedophil", "child abuse", "hostage",
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

    # ------------------------------------------------------------------ #
    # Source 1: Reddit
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Source 2: Google Trends RSS (independent signal from Reddit)
    # ------------------------------------------------------------------ #
    def _google_trends_topics(self, keywords: list, geo: str = "US") -> list:
        """Real trending Google searches, filtered to ones matching this
        niche's keywords. See docs/GITHUB-AGENTS-EVALUATION.md #16 for why
        this uses the RSS endpoint directly (pytrends-modern's approach)
        rather than the retired unofficial pytrends API."""
        url = f"https://trends.google.com/trending/rss?geo={geo}"
        r = self._get(url, timeout=8)
        if r is None:
            return []
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            return []
        topics = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            if not title:
                continue
            lowered = title.lower()
            if any(kw.split()[0].lower() in lowered for kw in keywords) and _is_safe_topic(title):
                topics.append(title)
        return topics

    # ------------------------------------------------------------------ #
    def analyze_market(self, niche_key: str, channel_id: str = "", language: str = "") -> str:
        """Returns ONE topic string to build a video around. Always passes
        through the safety blocklist, even for the evergreen fallback list,
        since a fully-automated channel has no human reviewing topics before
        a video gets made and uploaded.

        If channel_id is given, uses core/channel_memory.py to avoid
        re-picking a topic this channel already covered recently -- answers
        the user's request that the system "remember what video it made for
        each channel" and not repeat itself."""
        niche = cfg.NICHES.get(niche_key, {})
        subs = niche.get("subreddits", [])
        search_terms = niche.get("search_terms", [])
        print(f"[{self.name}] Analyzing trending topics for niche: {niche_key}")

        already_covered = set(channel_memory.recent_topics(channel_id)) if channel_id else set()

        # If NO LLM provider is configured at all (see LLMRouter.any_provider_
        # configured), a raw, unedited Reddit post title / Google Trends query
        # is a BAD topic to build a video around: there's no AI step left to
        # reframe it into a proper documentary-style angle, so it would fall
        # straight through to the generic 5-line offline template. In that
        # specific situation, skip the live-trending path entirely and go
        # straight to the curated evergreen list (core/content_bank.py has
        # real, hand-written, fact-checked scripts for those -- see
        # docs/CONTENT-BANK.md). The moment a working LLM key is added, this
        # skip no longer applies and live trending topics are used normally.
        llm_available = LLMRouter.any_provider_configured()

        if llm_available:
            topics = [t for t in (self._reddit_topics(subs) if subs else []) if _is_safe_topic(t)]
            # Independent second signal — combined with Reddit results so we're
            # not fully dependent on one source's rate limits or a quiet week.
            topics += self._google_trends_topics(search_terms) if search_terms else []

            fresh_topics = [t for t in topics if t not in already_covered]
            if fresh_topics:
                chosen = random.choice(fresh_topics[:10])
                print(f"[{self.name}] Found real trending topic: '{chosen}'")
                return chosen
            if topics:
                # Every trending topic found was already covered recently --
                # still better than crashing, but note it clearly in the log.
                chosen = random.choice(topics[:10])
                print(f"[{self.name}] All trending topics already covered recently; reusing: '{chosen}'")
                return chosen
        else:
            print(f"[{self.name}] No LLM provider configured -- skipping raw live-trending "
                  f"topics (they need an AI rewrite step to become a good script) and using "
                  f"the curated evergreen list instead. See docs/CONTENT-BANK.md.")

        evergreen = [t for t in niche.get("evergreen_topics", []) if _is_safe_topic(t)]
        fresh_evergreen = [t for t in evergreen if t not in already_covered]
        candidates = fresh_evergreen or evergreen or ["An interesting topic worth exploring"]


        # Prefer a topic that has a real, hand-written, fact-checked script
        # in core/content_bank.py (see that module's docstring -- written by
        # the agent per explicit user request while no LLM API key is
        # configured yet). This produces a genuinely good video instead of
        # the generic 5-line placeholder, with zero extra plumbing needed:
        # ScriptWriter._llm_script tries a real LLM first regardless, so the
        # moment a working key is added this preference has no effect.
        if language:
            curated = [t for t in candidates if content_bank.has_script(niche_key, language, t)]
            if curated:
                chosen = random.choice(curated)
                print(f"[{self.name}] Using evergreen topic with a curated script: '{chosen}'")
                return chosen

        fallback = random.choice(candidates)
        print(f"[{self.name}] Using evergreen fallback topic: '{fallback}'")
        return fallback


if __name__ == "__main__":
    analyzer = NicheAnalyzer()
    print(analyzer.analyze_market("psychology"))
