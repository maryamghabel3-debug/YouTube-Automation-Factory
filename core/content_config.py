"""Single source of truth for channel niches, RPM data, and stock-footage
search-term mapping. Keeping this separate means niche_analyzer, script_writer
and stock_footage_fetcher all stay in sync instead of drifting apart.
"""

# Niches ranked by 2026 RPM research (see PLAN-VIDEO-BA-FOOTAGE-AMADEH.md).
# 'search_terms' feed the StockFootageFetcher (Pexels/Pixabay) so each niche
# always has visually-relevant b-roll available.
NICHES = {
    "psychology": {
        "label_fa": "روانشناسی و خودشناسی",
        "label_en": "Psychology & Self-Improvement",
        "rpm_estimate": "$8-15",
        "search_terms": [
            "person thinking", "human brain", "meditation calm",
            "therapy session", "emotional portrait", "silhouette sunset",
            "journal writing", "walking alone nature", "close up eyes",
        ],
    },
    "history": {
        "label_fa": "تاریخ و اسرارآمیز",
        "label_en": "History & Mysteries",
        "rpm_estimate": "$5-12",
        "search_terms": [
            "ancient ruins", "old map", "castle aerial", "museum artifact",
            "old book pages", "historic city", "statue monument",
            "archive documents", "ancient civilization",
        ],
    },
    "luxury_lifestyle": {
        "label_fa": "لایف‌استایل لاکچری",
        "label_en": "Luxury Lifestyle",
        "rpm_estimate": "$6-14",
        "search_terms": [
            "luxury car", "private jet", "penthouse view", "yacht ocean",
            "designer fashion", "fine dining", "city skyline night",
            "watch closeup", "champagne pour",
        ],
    },
}

# Voice profiles per language (edge-tts voice ids). One narrator voice per
# channel keeps the "persona" consistent across every video.
VOICES = {
    "fa": "fa-IR-FaridNeural",
    "en": "en-US-ChristopherNeural",
}

# YouTube category id for "People & Blogs" (safe default for narrated
# documentary-style content). See https://developers.google.com/youtube/v3/docs/videoCategories
YOUTUBE_CATEGORY_ID = "22"
