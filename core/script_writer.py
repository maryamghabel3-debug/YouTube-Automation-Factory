"""ScriptWriter Agent — generates a real, original long-form narration script
broken into timed scenes, using a multi-provider LLM fallback chain (see
core/llm_router.py: Groq -> Gemini -> Kimi K2 (free via OpenRouter) ->
OpenRouter -> DeepSeek -> Moonshot direct) so a single provider's exhausted
quota never stops content production. Falls back to an offline template if
every provider is unavailable/unconfigured, so the pipeline never crashes.

Each scene has: {"text": narration line, "query": stock-footage search term}
so StockFootageFetcher can fetch relevant b-roll for every beat of the video.

Optionally takes a `competitor_insights` string (see core/competitor_analyzer.py)
summarizing what made recently-trending videos in this niche successful --
the writer is instructed to apply those patterns (stronger hooks, pacing,
structure) without copying any specific video's content.
"""

import os

from .llm_router import LLMRouter


class ScriptWriter:
    def __init__(self):
        self.router = LLMRouter()

    def _build_prompt(self, topic: str, niche_label: str, language: str,
                       target_minutes: int, competitor_insights: str = "") -> tuple:
        lang_name = "Persian (Farsi)" if language == "fa" else "English" if language == "en" else language

        system_prompt = (
            "You are a professional scriptwriter for a faceless YouTube documentary "
            "channel. You write ORIGINAL, engaging, factually-grounded narration scripts. "
            "You never copy or closely paraphrase any specific existing video -- you only "
            "apply general storytelling patterns (hook style, pacing, structure) that are "
            "known to perform well."
        )

        insights_block = ""
        if competitor_insights:
            insights_block = (
                f"\n\nHere is a summary of what makes currently high-performing videos in "
                f"this niche successful (use these PATTERNS as inspiration for hook/pacing/"
                f"structure, but do NOT copy any specific facts, phrasing, or claims from "
                f"them):\n{competitor_insights}\n"
            )

        user_prompt = f"""Write an ORIGINAL, engaging, factually-grounded narration script
in {lang_name} for a "{niche_label}" channel about: "{topic}".
{insights_block}
Target length: about {target_minutes} minutes of spoken narration (~{target_minutes * 130} words).
Structure: a strong hook (first line grabs attention within 3 seconds), then body broken into
8-14 short scenes, then a call-to-action outro (subscribe).

Respond ONLY with a JSON array, each item shaped exactly like:
{{"text": "one or two narration sentences for this beat", "query": "2-4 word English stock-footage search term matching this beat visually"}}

The "query" field must ALWAYS be in English (for stock footage search), even
if "text" is in {lang_name}. Do not include markdown fences, only the JSON array."""

        return system_prompt, user_prompt

    def _llm_script(self, topic: str, niche_label: str, language: str,
                     target_minutes: int, competitor_insights: str = "") -> tuple:
        system_prompt, user_prompt = self._build_prompt(
            topic, niche_label, language, target_minutes, competitor_insights
        )
        result = self.router.generate_json(system_prompt, user_prompt)
        if "data" in result and isinstance(result["data"], list) and result["data"]:
            return result["data"], result["provider"]
        if "error" in result:
            print(f"[ScriptWriter] All LLM providers failed, using fallback: {result['error']}")
        return [], ""

    def _fallback_script(self, topic: str, language: str) -> list:
        """Offline-safe template so the pipeline always produces something."""
        if language == "fa":
            return [
                {"text": f"آیا تا حالا درباره {topic} فکر کرده‌اید؟", "query": "person thinking"},
                {"text": "بذارید امروز با هم این موضوع رو عمیق‌تر بررسی کنیم.", "query": "open book pages"},
                {"text": f"{topic} یکی از جذاب‌ترین مباحثیه که کمتر بهش پرداخته شده.", "query": "close up eyes"},
                {"text": "در ادامه این ویدیو، نکات کلیدی رو با هم مرور می‌کنیم.", "query": "walking alone nature"},
                {"text": "اگر این ویدیو براتون مفید بود، حتما کانال رو دنبال کنید.", "query": "sunset silhouette"},
            ]
        return [
            {"text": f"Have you ever wondered about {topic}?", "query": "person thinking"},
            {"text": "Let's dive deeper into this topic together today.", "query": "open book pages"},
            {"text": f"{topic} is one of the most fascinating subjects rarely discussed in depth.", "query": "close up eyes"},
            {"text": "In this video, we'll walk through the key insights.", "query": "walking alone nature"},
            {"text": "If you found this valuable, make sure to subscribe for more.", "query": "sunset silhouette"},
        ]

    def write_script(self, topic: str, niche_label: str = "", language: str = "en",
                      target_minutes: int = 8, competitor_insights: str = "") -> dict:
        scenes, provider = self._llm_script(topic, niche_label, language, target_minutes, competitor_insights)
        engine = provider or "fallback_template"
        if not scenes:
            scenes = self._fallback_script(topic, language)
            engine = "fallback_template"

        full_text = " ".join(s["text"] for s in scenes)
        return {
            "topic": topic,
            "language": language,
            "scenes": scenes,
            "full_text": full_text,
            "engine": engine,
        }


if __name__ == "__main__":
    import json

    writer = ScriptWriter()
    script = writer.write_script("why we procrastinate", "Psychology", "en", target_minutes=3)
    print(json.dumps(script, indent=2, ensure_ascii=False))
