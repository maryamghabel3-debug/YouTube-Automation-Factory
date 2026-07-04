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
from . import channel_memory
from . import content_bank



class ScriptWriter:
    def __init__(self):
        self.router = LLMRouter()

    def _build_prompt(self, topic: str, niche_label: str, language: str,
                       target_minutes: int, competitor_insights: str = "",
                       memory_note: str = "") -> tuple:
        lang_name = "Persian (Farsi)" if language == "fa" else "English" if language == "en" else language

        system_prompt = (
            "You are a professional scriptwriter for a faceless YouTube documentary "
            "channel. You write ORIGINAL, engaging, factually-grounded narration scripts. "
            "You never copy or closely paraphrase any specific existing video -- you only "
            "apply general storytelling patterns (hook style, pacing, structure) that are "
            "known to perform well. You also write scripts that actively drive audience "
            "engagement (comments, likes, subscriptions) using proven, research-backed "
            "placement -- never generic, low-effort asks."
        )

        insights_block = ""
        if competitor_insights:
            insights_block = (
                f"\n\nHere is a summary of what makes currently high-performing videos in "
                f"this niche successful (use these PATTERNS as inspiration for hook/pacing/"
                f"structure, but do NOT copy any specific facts, phrasing, or claims from "
                f"them):\n{competitor_insights}\n"
            )

        memory_block = f"\n\n{memory_note}\n" if memory_note else ""

        user_prompt = f"""Write an ORIGINAL, engaging, factually-grounded narration script
in {lang_name} for a "{niche_label}" channel about: "{topic}".
{insights_block}{memory_block}
Target length: about {target_minutes} minutes of spoken narration (~{target_minutes * 130} words).

Structure (research-backed engagement placement -- see docs/YOUTUBE-GROWTH-AND-ENGAGEMENT.md):
1. A strong hook (first line grabs attention within 3 seconds -- no channel intro, no "hi guys").
2. Body broken into 8-14 short scenes with a clear narrative arc.
3. EARLY (right after the hook resolves its first mini-payoff): one ultra-light,
   specific subscribe mention tied to a concrete future payoff (NOT "please subscribe" --
   instead something like "stick around, because what happens next changes everything").
4. MIDDLE (after the most surprising/valuable beat): one specific, easy-to-answer engagement
   question the viewer can answer in a comment (e.g. "which of these would you have guessed?"
   -- never a vague "what do you think?").
5. OUTRO: a call-to-action that (a) restates ONE specific reason to subscribe tied to this
   channel's niche, and (b) asks a second, different comment question to maximize comment
   volume (comments are the highest-weighted engagement signal for the algorithm).

Respond ONLY with a JSON array, each item shaped exactly like:
{{"text": "one or two narration sentences for this beat", "query": "2-4 word English stock-footage search term matching this beat visually"}}

The "query" field must ALWAYS be in English (for stock footage search), even
if "text" is in {lang_name}. Do not include markdown fences, only the JSON array."""

        return system_prompt, user_prompt

    def _llm_script(self, topic: str, niche_label: str, language: str,
                     target_minutes: int, competitor_insights: str = "",
                     memory_note: str = "") -> tuple:
        system_prompt, user_prompt = self._build_prompt(
            topic, niche_label, language, target_minutes, competitor_insights, memory_note
        )
        result = self.router.generate_json(system_prompt, user_prompt)
        if "data" in result and isinstance(result["data"], list) and result["data"]:
            return result["data"], result["provider"]
        if "error" in result:
            attempts = result.get("attempts", [])
            detail = f" | attempts: {attempts}" if attempts else " (no configured provider raised an error -- check API keys)"
            print(f"[ScriptWriter] All LLM providers failed, using fallback: {result['error']}{detail}")
        return [], ""

    def _fallback_script(self, topic: str, language: str) -> list:
        """Offline-safe template so the pipeline always produces something.
        Includes the same research-backed engagement structure (early light
        subscribe mention + mid-video comment question + outro CTA) even
        without an LLM available."""
        if language == "fa":
            return [
                {"text": f"آیا تا حالا درباره {topic} فکر کرده‌اید؟", "query": "person thinking"},
                {"text": "بذارید امروز با هم این موضوع رو عمیق‌تر بررسی کنیم؛ تا آخر بمونید چون قسمت بعدی غافلگیرتون می‌کنه.", "query": "open book pages"},
                {"text": f"{topic} یکی از جذاب‌ترین مباحثیه که کمتر بهش پرداخته شده.", "query": "close up eyes"},
                {"text": "شما کدوم بخش این ماجرا رو حدس نمی‌زدید؟ توی کامنت‌ها بگید.", "query": "walking alone nature"},
                {"text": "اگر این ویدیو براتون مفید بود، حتما دنبال کنید تا ویدیوی بعدی رو از دست ندید؛ و بگید دوست دارید کدوم موضوع رو بعداً بررسی کنیم.", "query": "sunset silhouette"},
            ]
        return [
            {"text": f"Have you ever wondered about {topic}?", "query": "person thinking"},
            {"text": "Let's dive deeper into this topic together today -- stick around, because what comes next changes everything.", "query": "open book pages"},
            {"text": f"{topic} is one of the most fascinating subjects rarely discussed in depth.", "query": "close up eyes"},
            {"text": "Which part of this would you NOT have guessed? Let me know in the comments.", "query": "walking alone nature"},
            {"text": "If you found this valuable, subscribe so you don't miss the next one -- and tell me which topic you want covered next.", "query": "sunset silhouette"},
        ]

    def write_script(self, topic: str, niche_label: str = "", language: str = "en",
                      target_minutes: int = 8, competitor_insights: str = "",
                      channel_id: str = "", niche_key: str = "") -> dict:
        # channel_memory.py: avoid the script rehashing the same angle this
        # channel already used recently (user-requested "system memory").
        memory_note = channel_memory.summary_for_prompt(channel_id) if channel_id else ""

        scenes, provider = self._llm_script(
            topic, niche_label, language, target_minutes, competitor_insights, memory_note
        )
        engine = provider or ""

        if not scenes:
            # No LLM provider is configured/working (e.g. no AVALAI_API_KEY /
            # GAPGPT_API_KEY / GROQ_API_KEY / GEMINI_API_KEY yet -- see
            # docs/LLM-PROVIDERS-2026.md). Rather than immediately dropping
            # to the generic 5-line placeholder, try core/content_bank.py --
            # a set of real, hand-written, fact-checked scripts the agent
            # authored directly (per explicit user request: "do the AI work
            # yourself until I add a real key"). These are full 10-11 scene
            # scripts with the same research-backed engagement structure an
            # LLM would be asked to produce, not placeholders.
            scenes = content_bank.get_script(niche_key, language, topic)
            if scenes:
                engine = "content_bank"

        if not scenes and niche_key:
            # The topic NicheAnalyzer picked has no exact curated script AND
            # every LLM failed (this happens for a raw live-trending topic
            # slipping through, or an evergreen topic outside the curated
            # set). Rather than settle for the generic placeholder built
            # around a topic we can't actually write anything good about,
            # swap to a DIFFERENT topic we know has a real, good,
            # fact-checked script -- a genuinely good video about a slightly
            # different (but still real, still niche-appropriate) topic beats
            # a mediocre 5-line video about the "correct" topic. The caller
            # (VideoFactory) is told about this via the returned "topic" key
            # so title/description/memory all stay consistent with what was
            # actually narrated.
            substitute_topic = content_bank.random_topic_for_niche(niche_key, language)
            if substitute_topic:
                scenes = content_bank.get_script(niche_key, language, substitute_topic)
                if scenes:
                    print(f"[ScriptWriter] No LLM and no curated script for '{topic}' -- "
                          f"substituting curated topic '{substitute_topic}' instead.")
                    topic = substitute_topic
                    engine = "content_bank"

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
