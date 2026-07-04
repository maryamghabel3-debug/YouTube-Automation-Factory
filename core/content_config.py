"""Single source of truth for channel niches, RPM data, voice profiles, and
stock-footage search-term mapping. Keeping this separate means
niche_analyzer, script_writer and stock_footage_fetcher all stay in sync
instead of drifting apart.

Adding a new niche or language is a ONE-TIME edit here — no other file needs
to change. See docs/ADDING-A-NEW-CHANNEL.md for the full guide.
"""

# --------------------------------------------------------------------------- #
# Niches ranked by 2026 RPM research (see PLAN-VIDEO-BA-FOOTAGE-AMADEH.md and
# docs/GITHUB-AGENTS-EVALUATION.md). 'search_terms' feed the
# StockFootageFetcher (Pexels/Pixabay) so each niche always has
# visually-relevant b-roll available. 'subreddits' feed the NicheAnalyzer.
# --------------------------------------------------------------------------- #
NICHES = {
    "psychology": {
        "label_fa": "روانشناسی و خودشناسی",
        "label_en": "Psychology & Self-Improvement",
        "rpm_estimate": "$8-15",
        "subreddits": ["DecidingToBeBetter", "selfimprovement", "GetMotivated"],
        "search_terms": [
            "person thinking", "human brain", "meditation calm",
            "therapy session", "emotional portrait", "silhouette sunset",
            "journal writing", "walking alone nature", "close up eyes",
        ],
        "evergreen_topics": [
            "Why we procrastinate even when we know better",
            "The psychology of first impressions",
            "How your childhood shapes your adult relationships",
            "Why comparison steals your happiness",
            "The science of habit formation",
        ],
    },
    "history_mystery": {
        "label_fa": "تاریخ و اسرارآمیز",
        "label_en": "History & Unsolved Mysteries",
        "rpm_estimate": "$5-12",
        "subreddits": ["UnresolvedMysteries", "history", "AskHistorians"],
        "search_terms": [
            "ancient ruins", "old map", "castle aerial", "museum artifact",
            "old book pages", "historic city", "statue monument",
            "archive documents", "ancient civilization", "foggy forest night",
        ],
        "evergreen_topics": [
            "The unsolved mystery of the Mary Celeste",
            "How ancient Rome built roads that still exist today",
            "The forgotten empire that rivaled Rome",
            "Why the Library of Alexandria really burned",
            "The code that took 300 years to break",
        ],
    },
    "true_crime": {
        "label_fa": "جنایی و رمزآلود",
        "label_en": "True Crime & Cold Cases",
        "rpm_estimate": "$7-12",
        "subreddits": ["UnresolvedMysteries", "TrueCrimeDiscussion", "coldcases"],
        "search_terms": [
            "police tape night", "detective office", "old case files",
            "empty street fog", "courtroom", "magnifying glass evidence",
            "city noir night", "rain window night", "flashlight dark room",
        ],
        "evergreen_topics": [
            "The cold case that was solved decades later by DNA",
            "How forensic accounting cracked an impossible fraud",
            "The heist that baffled investigators for 50 years",
            "What really happens during a missing persons investigation",
            "The forgery that fooled the world's top experts",
        ],
    },
    "luxury_lifestyle": {
        "label_fa": "لایف‌استایل لاکچری",
        "label_en": "Luxury Lifestyle",
        "rpm_estimate": "$6-14",
        "subreddits": ["luxury", "entrepreneur", "financialindependence"],
        "search_terms": [
            "luxury car", "private jet", "penthouse view", "yacht ocean",
            "designer fashion", "fine dining", "city skyline night",
            "watch closeup", "champagne pour",
        ],
        "evergreen_topics": [
            "Inside the world's most expensive private islands",
            "How billionaires actually spend their mornings",
            "The psychology of luxury branding",
            "Why quiet luxury is replacing logomania",
            "The most exclusive clubs money can't always buy into",
        ],
    },
    "finance": {
        "label_fa": "مالی و ثروت‌سازی",
        "label_en": "Finance & Wealth Building",
        "rpm_estimate": "$10-25 (highest RPM niche)",
        "subreddits": ["personalfinance", "financialindependence", "investing"],
        "search_terms": [
            "stock market chart", "city financial district", "gold bars",
            "handshake business", "calculator desk", "coins stack",
            "office skyscraper", "graph growth", "bank building",
        ],
        "evergreen_topics": [
            "The compound interest trick banks don't advertise",
            "Why most lottery winners go broke within years",
            "How the wealthy legally minimize what they owe",
            "The simple index fund strategy that beats most experts",
            "What separates people who build wealth from those who don't",
        ],
    },
    "space_science": {
        "label_fa": "فضا و علم",
        "label_en": "Space & Science",
        "rpm_estimate": "$6-12",
        "subreddits": ["space", "askscience", "Astronomy"],
        "search_terms": [
            "galaxy stars", "nebula space", "rocket launch", "planet surface",
            "telescope observatory", "aurora borealis", "milky way night sky",
            "astronaut spacewalk", "solar system",
        ],
        "evergreen_topics": [
            "What would actually happen if you fell into a black hole",
            "The Fermi Paradox: where is everybody?",
            "How close humanity really is to visiting Mars",
            "The strangest planets we've discovered so far",
            "Why the universe might be bigger than we can ever observe",
        ],
    },
}

# --------------------------------------------------------------------------- #
# Languages: each maps to an edge-tts voice (free, no key) and a display
# name. Add a new language here and every channel-creation flow immediately
# supports it — no other code changes needed.
# --------------------------------------------------------------------------- #
LANGUAGES = {
    "fa": {"label": "فارسی (Persian)", "voice": "fa-IR-FaridNeural", "voice_alt": "fa-IR-DilaraNeural"},
    "en": {"label": "English", "voice": "en-US-ChristopherNeural", "voice_alt": "en-US-GuyNeural"},
    "ar": {"label": "العربية (Arabic)", "voice": "ar-SA-HamedNeural", "voice_alt": "ar-EG-ShakirNeural"},
    "es": {"label": "Español (Spanish)", "voice": "es-ES-AlvaroNeural", "voice_alt": "es-MX-JorgeNeural"},
    "tr": {"label": "Türkçe (Turkish)", "voice": "tr-TR-AhmetNeural", "voice_alt": "tr-TR-EmelNeural"},
    "de": {"label": "Deutsch (German)", "voice": "de-DE-ConradNeural", "voice_alt": "de-DE-KillianNeural"},
    "fr": {"label": "Français (French)", "voice": "fr-FR-HenriNeural", "voice_alt": "fr-FR-RemyMultilingualNeural"},
}

# Backward-compat alias (older code imported VOICES directly)
VOICES = {code: cfg["voice"] for code, cfg in LANGUAGES.items()}

# YouTube category id for "People & Blogs" (safe default for narrated
# documentary-style content). See https://developers.google.com/youtube/v3/docs/videoCategories
YOUTUBE_CATEGORY_ID = "22"


def list_niches() -> list:
    return list(NICHES.keys())


def list_languages() -> list:
    return list(LANGUAGES.keys())


def niche_label(niche_key: str, language: str) -> str:
    niche = NICHES[niche_key]
    return niche["label_fa"] if language == "fa" else niche["label_en"]
