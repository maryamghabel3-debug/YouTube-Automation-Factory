"""VideoFactory Engine — the real pipeline (no mocks).

topic -> CompetitorAnalyzer -> ScriptWriter -> VoiceEngine ->
StockFootageFetcher -> VideoAssembler -> ThumbnailMaker -> ShortsMaker
"""

from datetime import datetime

from .competitor_analyzer import CompetitorAnalyzer
from .script_writer import ScriptWriter
from .voice_engine import VoiceEngine
from .stock_footage_fetcher import StockFootageFetcher
from .video_assembler import VideoAssembler
from .thumbnail_maker import ThumbnailMaker
from .shorts_maker import ShortsMaker
from . import content_config as cfg
from . import channel_memory


class VideoFactory:
    def __init__(self):
        self.name = "VideoFactory"
        self.competitor_analyzer = CompetitorAnalyzer()
        self.script_writer = ScriptWriter()
        self.voice_engine = VoiceEngine()
        self.footage_fetcher = StockFootageFetcher()
        self.assembler = VideoAssembler()
        self.thumbnail_maker = ThumbnailMaker()
        self.shorts_maker = ShortsMaker()

    def build_video(self, topic: str, channel_cfg: dict, target_minutes: int = 8,
                     make_shorts: bool = True) -> dict:
        """Full real pipeline for one channel/topic. Returns
        {'video_path', 'duration', 'thumbnail_path', 'shorts': [...], ...}
        or {'error': ...}."""
        language = channel_cfg.get("language", "en")
        niche_key = channel_cfg.get("niche_key", "")
        niche_label = channel_cfg.get("niche_label", "")
        voice = channel_cfg.get("voice", "en-US-ChristopherNeural")

        # --- Competitor/viral-pattern analysis (see docs on RPM/high-view
        # strategy) -- informs the script's hook/pacing without copying any
        # specific video's content. Degrades silently to '' if no
        # YOUTUBE_API_KEY or every LLM provider is unavailable.
        search_terms = cfg.NICHES.get(niche_key, {}).get("search_terms", [])
        print(f"[{self.name}] Analyzing high-performing videos in this niche for patterns")
        competitor_insights = self.competitor_analyzer.analyze(niche_label, search_terms)
        if competitor_insights:
            print(f"[{self.name}] Competitor insights: {competitor_insights[:150]}...")

        channel_id = channel_cfg.get("id", "")
        print(f"[{self.name}] Writing script for '{topic}' ({niche_label}, {language})")
        script = self.script_writer.write_script(
            topic, niche_label, language, target_minutes, competitor_insights,
            channel_id=channel_id, niche_key=niche_key,
        )
        if not script.get("scenes"):
            return {"error": "script_generation_failed"}

        # ScriptWriter may have SUBSTITUTED the topic (see its docstring --
        # this happens when the topic NicheAnalyzer picked has no curated
        # content_bank script AND every LLM failed). Use whatever topic was
        # actually narrated for everything downstream (thumbnail, title,
        # memory record, description) so nothing references the original,
        # unused topic string.
        if script.get("topic") and script["topic"] != topic:
            print(f"[{self.name}] Topic substituted by ScriptWriter: '{topic}' -> '{script['topic']}'")
            topic = script["topic"]

        print(f"[{self.name}] Generating narration ({script['engine']} script, "
              f"{len(script['scenes'])} scenes)")
        voice_result = self.voice_engine.generate_voiceover(script["full_text"], voice)
        if not voice_result.get("audio_path"):
            return {"error": "voiceover_generation_failed", "detail": voice_result.get("error")}

        print(f"[{self.name}] Fetching stock footage for {len(script['scenes'])} scenes")
        scenes_with_clips = self.footage_fetcher.fetch_for_script(script["scenes"])

        print(f"[{self.name}] Assembling final video (subtitles + audio mux)")
        video_result = self.assembler.build_video(
            scenes_with_clips,
            voice_result["audio_path"],
            voice_result["words"],
            language=language,
        )
        if video_result.get("error"):
            return video_result

        print(f"[{self.name}] Generating thumbnail")
        thumb_result = self.thumbnail_maker.make_thumbnail(topic, scenes_with_clips, language)
        thumbnail_path = thumb_result.get("path", "")
        if thumb_result.get("error"):
            print(f"[{self.name}] Thumbnail generation failed (non-fatal): {thumb_result['error']}")

        shorts = []
        if make_shorts:
            print(f"[{self.name}] Generating Shorts/Reels clips from this video")
            shorts = self.shorts_maker.make_shorts(
                video_result["video_path"], script["scenes"], voice_result["words"],
                script["full_text"], num_clips=3, topic=topic,
            )

        footage_queries = [s.get("query", "") for s in script["scenes"] if s.get("query")]
        title_guess = topic  # AutoPublisher.generate_metadata() computes the real title;
        # this is just a readable placeholder for memory until main.py updates it post-upload.
        if channel_id:
            channel_memory.record_video(
                channel_id, topic, title_guess, video_result["video_path"],
                footage_queries, script["engine"],
            )

        # The outro scene (last one) is where ScriptWriter's prompt asks for
        # a specific comment question -- surfaced separately so
        # AutoPublisher.generate_metadata() can echo it in the description
        # (see docs/YOUTUBE-GROWTH-AND-ENGAGEMENT.md).
        outro_text = script["scenes"][-1]["text"] if script["scenes"] else ""

        return {
            "video_path": video_result["video_path"],
            "duration": video_result["duration"],
            "scenes_rendered": video_result["scenes_rendered"],
            "thumbnail_path": thumbnail_path,
            "shorts": shorts,
            "topic": topic,
            "script_engine": script["engine"],
            "competitor_insights": competitor_insights,
            "outro_text": outro_text,
            "built_at": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    import json

    factory = VideoFactory()
    demo_channel = {
        "language": "en",
        "niche_key": "psychology",
        "niche_label": "Psychology & Self-Improvement",
        "voice": "en-US-ChristopherNeural",
    }
    result = factory.build_video("why we procrastinate", demo_channel, target_minutes=1)
    print(json.dumps({k: v for k, v in result.items() if k != "shorts"}, indent=2, ensure_ascii=False))
