"""FootageQuality — real, explicit scoring criteria for choosing WHICH stock
photo/video candidate to use, instead of picking randomly among the raw API
results (the previous behavior in core/stock_footage_fetcher.py).

Directly answers the user's question: "what criteria decides if a photo/
video is good or bad for the video being made?" Before this module existed,
the honest answer was "none -- it's a random.choice() over the first 5
search results." This module makes the criteria explicit, so every choice
can be explained.

Scoring criteria (each candidate gets a 0-100 score, highest wins):
  1. RESOLUTION (up to 35 points) -- prefer clips that meet or exceed 1080p
     (1920x1080) without being unnecessarily huge (huge 4K source files
     slow down ffmpeg re-encoding for no visible benefit at 1080p output).
     Below 720p is penalized heavily since it will look visibly soft when
     upscaled to the video's 1920x1080 canvas.
  2. ASPECT RATIO FIT (up to 25 points) -- landscape footage close to 16:9
     (the video's actual output aspect ratio) needs the least cropping,
     which means less of the frame is thrown away and composition is
     preserved. Extreme aspect ratios (near-square, very wide/panoramic)
     lose the most content when force-cropped to 16:9.
  3. DURATION FIT, video only (up to 20 points) -- a clip at least as long
     as the scene's narration duration is preferred (avoids visible looping
     within a single scene, which looks repetitive/cheap); clips much
     longer than needed are fine but score slightly lower than a close
     match (mild preference for using more of what's actually relevant
     rather than an arbitrary long clip).
  4. QUERY RELEVANCE (up to 20 points) -- how many of the search query's
     words appear in the source's own tags/description (Pexels/Pixabay
     both return this). This is a cheap, real proxy for "does this footage
     actually show what the scene is about" without needing paid image
     recognition -- a candidate literally tagged with the query words is
     much more likely to be on-topic than one that merely matched a fuzzy
     full-text search.

This is a REAL, deterministic, explainable scoring function -- not a vague
heuristic. Every score component is logged so a specific choice can always
be explained after the fact (see StockFootageFetcher's use of this module).
"""

_TARGET_ASPECT = 16 / 9
_MIN_ACCEPTABLE_WIDTH = 1280   # below 720p-equivalent width is heavily penalized
_IDEAL_MIN_WIDTH = 1920         # 1080p -- the sweet spot for our output canvas
_IDEAL_MAX_WIDTH = 3840         # beyond 4K, no visible benefit, just slower processing


def score_resolution(width: int, height: int) -> float:
    if not width or not height:
        return 0.0
    if width < _MIN_ACCEPTABLE_WIDTH:
        return 5.0  # still usable (fallback), but heavily penalized
    if _IDEAL_MIN_WIDTH <= width <= _IDEAL_MAX_WIDTH:
        return 35.0
    if width < _IDEAL_MIN_WIDTH:
        # Between 720p and 1080p -- linearly scale from 15 to 35
        span = _IDEAL_MIN_WIDTH - _MIN_ACCEPTABLE_WIDTH
        progress = (width - _MIN_ACCEPTABLE_WIDTH) / span
        return 15.0 + progress * 20.0
    # Above 4K -- still fine, mild penalty for unnecessary processing cost
    return 28.0


def score_aspect_ratio(width: int, height: int) -> float:
    if not width or not height:
        return 0.0
    aspect = width / height
    deviation = abs(aspect - _TARGET_ASPECT)
    # Perfect 16:9 match -> 25 points; deviation of 0.5+ (e.g. near-square
    # or ultra-panoramic) -> approaches 0.
    score = max(0.0, 25.0 - deviation * 40.0)
    return round(score, 2)


def score_duration_fit(clip_duration: float, needed_duration: float) -> float:
    if not clip_duration or not needed_duration:
        return 10.0  # neutral score when duration is unknown (e.g. photos)
    if clip_duration >= needed_duration:
        # Prefer a close match over an arbitrarily long clip, but don't
        # punish "long enough" too harshly -- looping is the real problem,
        # not slight excess length.
        excess_ratio = clip_duration / needed_duration
        if excess_ratio <= 1.5:
            return 20.0
        if excess_ratio <= 4.0:
            return 16.0
        return 12.0
    # Clip shorter than needed -- will require looping (visible repetition)
    shortfall_ratio = clip_duration / needed_duration
    return max(0.0, shortfall_ratio * 10.0)


def score_query_relevance(query: str, tags_or_description: str) -> float:
    if not query or not tags_or_description:
        return 0.0
    query_words = {w.lower() for w in query.split() if len(w) > 2}
    if not query_words:
        return 0.0
    haystack = tags_or_description.lower()
    matched = sum(1 for w in query_words if w in haystack)
    return round((matched / len(query_words)) * 20.0, 2)


def score_candidate(query: str, width: int, height: int, duration: float = 0.0,
                     needed_duration: float = 0.0, tags_or_description: str = "") -> dict:
    """Returns {'total': float, 'breakdown': {...}} -- always call this
    instead of hand-rolling ad-hoc scoring so criteria stay consistent and
    documented in ONE place."""
    breakdown = {
        "resolution": score_resolution(width, height),
        "aspect_ratio": score_aspect_ratio(width, height),
        "duration_fit": score_duration_fit(duration, needed_duration),
        "query_relevance": score_query_relevance(query, tags_or_description),
    }
    return {"total": round(sum(breakdown.values()), 2), "breakdown": breakdown}


def pick_best(query: str, candidates: list, needed_duration: float = 0.0,
              exclude_ids: set = None) -> dict:
    """candidates: list of dicts each with at minimum 'width'/'height', and
    optionally 'duration' (videos) and 'tags'/'description' (both APIs
    provide at least one of these). Returns the single best-scoring
    candidate dict (with a '_quality_score' key added) or {} if the list
    is empty.

    exclude_ids (optional): a set of candidate '_id' values to skip entirely
    -- used by StockFootageFetcher to avoid picking the SAME clip twice
    within one video (found via user review 2026-07-05: the previous
    behavior always deterministically re-picked the literal top-scoring
    result for a repeated search query, so any script re-using a query like
    'city skyline night' in two different scenes got the identical clip
    twice, looking like an editing mistake). If every candidate is
    excluded, falls back to the best-scoring one anyway (a repeated clip is
    still better than no clip)."""
    if not candidates:
        return {}

    exclude_ids = exclude_ids or set()
    scored = []
    for c in candidates:
        result = score_candidate(
            query,
            width=c.get("width", 0),
            height=c.get("height", 0),
            duration=c.get("duration", 0.0),
            needed_duration=needed_duration,
            tags_or_description=c.get("tags", "") or c.get("description", "") or c.get("alt", ""),
        )
        scored.append({**c, "_quality_score": result["total"], "_quality_breakdown": result["breakdown"]})

    scored.sort(key=lambda c: c["_quality_score"], reverse=True)

    fresh = [c for c in scored if c.get("_id") not in exclude_ids]
    return fresh[0] if fresh else scored[0]

