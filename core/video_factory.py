"""VideoFactory Engine — the real pipeline (no mocks).

topic -> ScriptWriter -> VoiceEngine -> StockFootageFetcher -> VideoAssembler
"""

from datetime import datetime

from .script_writer import ScriptWriter
from .voice_engine import VoiceEngine
from .stock_footage_fetcher import StockFootageFetcher
from .video_assembler import VideoAssembler


class VideoFactory:
    def __init__(self):
        self.name = "VideoFactory"
        self.script_writer = ScriptWriter()
        self.voice_engine = VoiceEngine()
        self.footage_fetcher = StockFootageFetcher()
        self.assembler = VideoAssembler()

    def build_video(self, topic: str, channel_cfg: dict, target_minutes: int = 8) -> dict:
        """Full real pipeline for one channel/topic. Returns
        {'video_path', 'duration', 'script', ...} or {'error': ...}."""
        language = channel_cfg.get("language", "en")
        niche_label = channel_cfg.get("niche_label", "")
        voice = channel_cfg.get("voice", "en-US-ChristopherNeural")

        print(f"[{self.name}] Writing script for '{topic}' ({niche_label}, {language})")
        script = self.script_writer.write_script(topic, niche_label, language, target_minutes)
        if not script.get("scenes"):
            return {"error": "script_generation_failed"}

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

        return {
            "video_path": video_result["video_path"],
            "duration": video_result["duration"],
            "scenes_rendered": video_result["scenes_rendered"],
            "topic": topic,
            "script_engine": script["engine"],
            "built_at": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    import json

    factory = VideoFactory()
    demo_channel = {
        "language": "en",
        "niche_label": "Psychology & Self-Improvement",
        "voice": "en-US-ChristopherNeural",
    }
    result = factory.build_video("why we procrastinate", demo_channel, target_minutes=1)
    print(json.dumps(result, indent=2, ensure_ascii=False))
