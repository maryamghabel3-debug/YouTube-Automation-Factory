"""ScriptWriter Agent — generates a real, original long-form narration script
broken into timed scenes, using Gemini (falls back to a template so the
pipeline never crashes without a key).

Each scene has: {"text": narration line, "query": stock-footage search term}
so StockFootageFetcher can fetch relevant b-roll for every beat of the video.
"""

import os
import json
import re


class ScriptWriter:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")

    def _gemini_script(self, topic: str, niche_label: str, language: str, target_minutes: int) -> list:
        if not self.api_key:
            return []
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")

            lang_name = "Persian (Farsi)" if language == "fa" else "English"
            prompt = f"""You are a professional scriptwriter for a faceless YouTube documentary channel
about "{niche_label}". Write an ORIGINAL, engaging, factually-grounded narration script
in {lang_name} about: "{topic}".

Target length: about {target_minutes} minutes of spoken narration (~{target_minutes * 130} words).
Structure: a strong hook (first line grabs attention), then body broken into
8-14 short scenes, then a call-to-action outro (subscribe).

Respond ONLY with a JSON array, each item shaped exactly like:
{{"text": "one or two narration sentences for this beat", "query": "2-4 word English stock-footage search term matching this beat visually"}}

The "query" field must ALWAYS be in English (for stock footage search), even
if "text" is in {lang_name}. Do not include markdown fences, only the JSON array."""

            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            # Strip markdown code fences if the model added them anyway
            raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            scenes = json.loads(raw)
            if isinstance(scenes, list) and scenes:
                return scenes
        except Exception as e:
            print(f"[ScriptWriter] Gemini generation failed, using fallback: {e}")
        return []

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
                      target_minutes: int = 8) -> dict:
        scenes = self._gemini_script(topic, niche_label, language, target_minutes)
        engine = "gemini"
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
    writer = ScriptWriter()
    script = writer.write_script("why we procrastinate", "Psychology", "en", target_minutes=3)
    print(json.dumps(script, indent=2, ensure_ascii=False))
