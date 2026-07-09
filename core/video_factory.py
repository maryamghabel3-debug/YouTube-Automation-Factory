"""VideoFactory Engine — the real pipeline with Cinematic Prompt Engineering.

Pipeline:
topic -> CompetitorAnalyzer -> ScriptWriter -> PromptEngineer (NEW) ->
VoiceEngine -> StockFootageFetcher -> VideoAssembler -> ThumbnailMaker -> ShortsMaker

The PromptEngineer now applies:
- Card Sovereign cinematic workflow (camera language, rhythm, pressure)
- 5-Part Formula (Subject/Setting/Style/Camera/Lighting) for images
- Character Reference Sheets for face consistency
- 8K Skin Realism for photorealistic close-ups
- Mood-based cinematic presets per niche
"""

from datetime import datetime

from .competitor_analyzer import CompetitorAnalyzer
from .script_writer import ScriptWriter
from .voice_engine import VoiceEngine
from .stock_footage_fetcher import StockFootageFetcher
from .video_assembler import VideoAssembler
from .thumbnail_maker import ThumbnailMaker
from .shorts_maker import ShortsMaker
from .prompt_engineer import PromptEngineer
from . import content_config as cfg
from . import channel_memory
from . import music_library


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
        self.prompt_engineer = PromptEngineer()

    def build_video(self, topic: str, channel_cfg: dict, target_minutes: int = 8,
                     make_shorts: bool = True, force_content_bank: bool = False) -> dict:
        """Full real pipeline for one channel/topic. Returns
        {'video_path', 'duration', 'thumbnail_path', 'shorts': [...], ...}
        or {'error': ...}."""
        language = channel_cfg.get("language", "en")
        niche_key = channel_cfg.get("niche_key", "")
        niche_label = channel_cfg.get("niche_label", "")
        voice = channel_cfg.get("voice", "en-US-ChristopherNeural")

        # --- Competitor/viral-pattern analysis
        search_terms = cfg.NICHES.get(niche_key, {}).get("search_terms", [topic])
        competitor_insights = ""
        try:
            competitor_insights = self.competitor_analyzer.analyze(search_terms, niche_label)
        except Exception:
            pass

        # --- Write the narration script
        script_data = self.script_writer.write_script(
            topic=topic,
            niche_label=niche_label,
            language=language,
            target_minutes=target_minutes,
            competitor_insights=competitor_insights,
        )

        if not script_data or "scenes" not in script_data:
            return {"error": "Script generation failed"}

        scenes = script_data["scenes"]
        title = script_data.get("title", topic)
        description = script_data.get("description", "")

        # === CINEMATIC PROMPT ENGINEERING (NEW) ===
        # For EACH scene, generate cinema-grade prompts using:
        # - Card Sovereign workflow (camera language, rhythm, atmosphere)
        # - Mood-based presets matched to the niche
        cinematic_directions = []
        for scene in scenes:
            direction = self.prompt_engineer.direct_scene(
                scene_text=scene.get("text", ""),
                niche=niche_key,
                channel_config=channel_cfg,
            )
            cinematic_directions.append(direction)

        # Attach cinematic directions to scenes for the assembler
        for i, scene in enumerate(scenes):
            if i < len(cinematic_directions):
                scene["cinematic"] = cinematic_directions[i]
                # Enhance stock query with cinematic atmosphere keywords
                scene["enhanced_query"] = (
                    f"{scene.get('query', '')} "
                    f"{cinematic_directions[i].get('atmosphere', '')}"
                )

        # --- Generate voiceover with timing
        full_text = " ".join(s["text"] for s in scenes)
        voice_result = self.voice_engine.generate(
            full_text, voice=voice, language=language
        )

        if "error" in voice_result:
            return voice_result

        # --- Fetch stock footage (using enhanced cinematic queries)
        clips = []
        for scene in scenes:
            query = scene.get("enhanced_query", scene.get("query", topic))
            clip = self.footage_fetcher.fetch(query, duration=scene.get("duration", 5))
            clips.append(clip)

        # --- Generate cinema-grade thumbnail
        thumbnail_prompt = cinematic_directions[0]["thumbnail_prompt"] if cinematic_directions else ""
        thumbnail_path = self.thumbnail_maker.make(
            title=title,
            niche=niche_key,
            custom_prompt=thumbnail_prompt,
        )

        # --- Assemble the final video with cinematic sound design
        sound_design = ""
        if cinematic_directions:
            sound_design = cinematic_directions[0].get("sound_design", "")

        video_path = self.assembler.assemble(
            scenes=scenes,
            clips=clips,
            voice_path=voice_result["audio_path"],
            word_timings=voice_result.get("word_timings", []),
            music_track=music_library.pick(niche_key, mood="cinematic"),
            sound_design_directives=sound_design,
            subtitle_style="cinematic",
        )

        if "error" in video_path:
            return video_path

        result = {
            "video_path": video_path["path"],
            "duration": video_path.get("duration", target_minutes * 60),
            "thumbnail_path": thumbnail_path,
            "title": title,
            "description": description,
            "scenes_count": len(scenes),
            "cinematic_mood": cinematic_directions[0]["mood"] if cinematic_directions else "default",
            "tags": script_data.get("tags", []),
        }

        # --- Make shorts from the best moments
        if make_shorts:
            shorts = self.shorts_maker.make_shorts(
                video_path=video_path["path"],
                scenes=scenes,
                voice_path=voice_result["audio_path"],
                language=language,
            )
            result["shorts"] = shorts

        return result
