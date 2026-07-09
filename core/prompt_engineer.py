"""
Cinematic Prompt Engineer Agent
Generates highly structured, professional prompts for video & image generation
based on the "Card Sovereign" cinematic workflow, the "5-Part Formula" (Aduni),
and the "Cinematic AI Food Film" pipeline.

Sources learned from:
- THE CARD SOVEREIGN workflow (Nano Banana 2 + Seedance 2.0)
- 5-Part Formula (Subject / Setting / Style / Camera / Lighting)
- Cinematic AI Food Film (Character Reference Sheets + 8K Skin Realism)
"""

from .llm_router import LLMRouter


class PromptEngineer:
    """
    Translates a simple topic/idea into cinema-grade prompts for:
    1. Character Reference Sheets (locks identity before video production)
    2. Photorealistic Images (5-Part Formula)
    3. Cinematic Video Scenes (Card Sovereign workflow)
    """

    def __init__(self):
        self.name = "PromptEngineer"
        self.router = LLMRouter()

    # ================================================================== #
    # TECHNIQUE 1: CHARACTER REFERENCE SHEET (from Food Film guide)
    # Before ANY video, generate a multi-angle reference sheet to lock
    # identity consistency across every scene.
    # ================================================================== #
    def generate_character_reference_prompt(self, character_description: str) -> str:
        """
        Generates a prompt to create a professional character reference sheet
        (front, left profile, right profile, back + 3 close-ups).
        This is the #1 technique for face consistency in AI video.
        """
        return (
            f"Create a professional character reference sheet based strictly "
            f"on the following character: {character_description}. "
            f"Use a clean neutral plain background and present the sheet as a "
            f"technical model turnaround while matching the exact realistic "
            f"visual style. Arrange the composition into two horizontal rows. "
            f"Top row: four full-body standing views \u2014 front, left profile, "
            f"right profile, back. Bottom row: three close-up portraits \u2014 "
            f"front, left profile, right profile. Maintain perfect identity "
            f"consistency across every panel. Keep the subject in a relaxed "
            f"A-pose with consistent scale and alignment, accurate anatomy, "
            f"and clear silhouette. Lighting should be consistent across all "
            f"panels. Output a crisp, ultra-realistic, print-ready reference "
            f"sheet. No writings."
        )

    # ================================================================== #
    # TECHNIQUE 2: 8K SKIN REALISM (from Food Film guide)
    # AI images look plastic without skin imperfections. This technique
    # adds pores, skin texture, and subtle imperfections for photorealism.
    # ================================================================== #
    def enhance_skin_realism(self, base_prompt: str, is_closeup: bool = False) -> str:
        """Adds 8K skin realism directives to any close-up portrait prompt."""
        if is_closeup:
            return (
                f"{base_prompt}. Enhance facial skin realism while preserving "
                f"all facial features and expressions, add pores, skin "
                f"imperfections, 8K image details, ultra-realistic skin texture."
            )
        return base_prompt

    # ================================================================== #
    # TECHNIQUE 3: 5-PART FORMULA (from Aduni guide)
    # Subject / Setting / Style / Camera / Lighting
    # ================================================================== #
    def generate_photo_prompt(self, subject: str, setting: str, style: str,
                               camera: str, lighting: str) -> str:
        """
        Builds a photorealistic image prompt using the 5-Part Formula.
        Avoids generic prompts that produce plastic, identity-less outputs.
        """
        prompt = (
            f"SUBJECT: {subject}. "
            f"SETTING: {setting}. "
            f"STYLE: {style}. "
            f"CAMERA: {camera}. "
            f"LIGHTING: {lighting}. "
            f"Ultra-realistic, photorealistic, no anime, no animation, no 3D render."
        )
        return prompt

    # ================================================================== #
    # TECHNIQUE 4: CARD SOVEREIGN CINEMATIC VIDEO WORKFLOW
    # Builds structured, block-based video prompts with:
    # - Camera Language (low-angle, orbit, depth of field)
    # - Atmosphere & Lighting (dark, single light source, chiaroscuro)
    # - Rhythm & Motion Control (slow-mo -> fast cut -> freeze)
    # - Sound Design directives (bass hits, reverb, ambient hum)
    # - Performance direction (slow deliberate movement, cold energy)
    # ================================================================== #
    def generate_cinematic_video_prompt(
        self,
        scene_description: str,
        mood: str = "dramatic",
        duration_seconds: int = 15,
        reference_sheet_path: str = None,
        language: str = "en",
    ) -> dict:
        """
        Generates a full cinematic video prompt following the Card Sovereign
        structure: Atmosphere -> Camera Language -> Performance ->
        Rhythm -> Sound Design.

        Returns a dict with:
        - 'video_prompt': the full structured prompt for Kling/Seedance/Hunyuan
        - 'sound_design': directives for VideoAssembler/AudioEditor
        - 'thumbnail_prompt': separate prompt for ThumbnailMaker
        """
        # Mood -> Atmosphere mapping
        mood_map = {
            "dramatic": {
                "atmosphere": "dark neo-noir, steampunk shadow atmosphere, overwhelming pressure, visually explosive tension",
                "lighting": "single dramatic light source, deep shadow carving across the face, one eye catching light",
                "camera": "extreme low-angle upshots, 360-degree orbit, heavy depth of field, handheld breathing feel",
                "performance": "slow deliberate movement, cold composed energy, every gesture intentional",
                "rhythm": "full speed launches, extreme slow motion hover, snap back to full speed for impact",
                "sound": "deep resonant voice with reverb, sharp whoosh sounds, low-frequency audio stretch, sub-bass impact hit",
            },
            "luxury": {
                "atmosphere": "elegant minimal luxury, warm golden tones, refined and sophisticated",
                "lighting": "soft golden hour light, gentle rim lighting, warm ambient glow",
                "camera": "smooth gimbal tracking, medium close-up, shallow depth of field f/2.8, elegant slow push-in",
                "performance": "graceful, unhurried, confident posture, subtle smile",
                "rhythm": "smooth continuous motion, gentle slow-motion on key moments",
                "sound": "elegant ambient score, soft natural ambient sounds, warm sub-tones",
            },
            "energetic": {
                "atmosphere": "vibrant, high-energy, dynamic, fast-paced modern aesthetic",
                "lighting": "bright colorful lighting, neon accents, high contrast",
                "camera": "rapid multi-angle cuts, fast zoom-ins, kinetic handheld, whip pans",
                "performance": "energetic, fast movements, expressive gestures",
                "rhythm": "ultra fast cuts every 2 seconds, rapid montage, freeze frames on impacts",
                "sound": "upbeat electronic score, sharp transitions, bass drops on cuts",
            },
            "mysterious": {
                "atmosphere": "foggy, mysterious, tense, unknown territory, suspenseful",
                "lighting": "low-key lighting, fog diffused light, silhouette-heavy compositions",
                "camera": "slow creeping dolly, voyeuristic distance shots, rack focus shifts",
                "performance": "cautious movements, searching eyes, whispered tone",
                "rhythm": "extremely slow build, tension accumulation, sudden reveal moments",
                "sound": "low ambient drone, whispered narration, heartbeat-like bass, sudden silence for tension",
            },
            "educational": {
                "atmosphere": "clean, professional, modern studio or library setting",
                "lighting": "bright even studio lighting, clean white balance, natural window light",
                "camera": "medium shots, steady tripod, clean headroom, occasional b-roll cutaways",
                "performance": "clear articulation, confident eye contact, occasional hand gestures",
                "rhythm": "steady pace, visual change every 4-5 seconds, smooth transitions",
                "sound": "clean voiceover, light background music (lo-fi or ambient), subtle sound effects",
            },
        }

        config = mood_map.get(mood, mood_map["dramatic"])

        # Reference locking (Card Sovereign: "Weak reference = weak output")
        ref_instruction = ""
        if reference_sheet_path:
            ref_instruction = (
                f"Use the uploaded character reference sheet "
                f"({reference_sheet_path}) as strict live-action character "
                f"reference. Full live-action throughout. No anime, no animation, "
                f"no 3D render, no text or symbols anywhere. "
            )

        # Build the full cinematic prompt
        video_prompt = (
            f"{ref_instruction}"
            f"Generate a {duration_seconds}-second cinematic video. "
            f"Style: {config['atmosphere']}. "
            f"Scene: {scene_description}. "
            f"\n\nCAMERA LANGUAGE: {config['camera']}. "
            f"Every move feels intentional and weighted. Smooth cinematic "
            f"transitions \u2014 no abrupt or jarring cuts. "
            f"\n\nPERFORMANCE: {config['performance']}. "
            f"\n\nRHYTHM: {config['rhythm']}. "
            f"If motion feels flat, regenerate. Rhythm = cinematic tension. "
            f"\n\nLIGHTING: {config['lighting']}."
        )

        # Sound design directives (for VideoAssembler to implement)
        sound_design = (
            f"SOUND DESIGN: {config['sound']}. "
            f"Sound should feel like a trailer, not a video. "
            f"Final moment: deep bass impact hit, then silence."
        )

        # Thumbnail prompt (high-CTR style, optimized for YouTube)
        thumbnail_prompt = (
            f"YouTube thumbnail, high contrast, vivid colors, shocking expression, "
            f"mood: {config['atmosphere']}, single focal point, red arrow or "
            f"highlight element, text-free, ultra-sharp 8K, eye-catching composition."
        )

        return {
            "video_prompt": video_prompt,
            "sound_design": sound_design,
            "thumbnail_prompt": thumbnail_prompt,
            "mood": mood,
            "atmosphere": config["atmosphere"],
            "camera_language": config["camera"],
            "performance": config["performance"],
            "rhythm": config["rhythm"],
        }

    # ================================================================== #
    # MASTER METHOD: Full cinematic pipeline for a single scene
    # ================================================================== #
    def direct_scene(self, scene_text: str, niche: str, channel_config: dict) -> dict:
        """
        Takes a scene narration line and niche context, returns a complete
        cinematic direction package:
        - video_prompt (for AI video model)
        - sound_design (for VideoAssembler)
        - thumbnail_prompt (for ThumbnailMaker)
        - skin_realism_prompt (for close-up image generation)
        """
        # Determine mood based on niche
        niche_mood_map = {
            "true_crime": "mysterious",
            "history": "dramatic",
            "luxury": "luxury",
            "tech_ai": "energetic",
            "psychology": "mysterious",
            "space_science": "dramatic",
            "finance": "educational",
            "motivation": "energetic",
            "horror": "dramatic",
            "relationships": "educational",
        }

        mood = niche_mood_map.get(niche, "dramatic")
        language = channel_config.get("language", "en")

        result = self.generate_cinematic_video_prompt(
            scene_description=scene_text,
            mood=mood,
            duration_seconds=15,
            language=language,
        )

        # Add skin realism for any close-up requirements
        result["skin_realism_prompt"] = self.enhance_skin_realism(
            f"Close-up portrait capturing emotion from: {scene_text}",
            is_closeup=True,
        )

        return result


if __name__ == "__main__":
    engineer = PromptEngineer()

    # Test: Character reference sheet
    print("=== CHARACTER REFERENCE SHEET ===")
    print(engineer.generate_character_reference_prompt(
        "A confident 30-year-old male tech reviewer with sharp features"
    )[:200] + "...\n")

    # Test: Cinematic video prompt
    print("=== CINEMATIC VIDEO PROMPT ===")
    result = engineer.direct_scene(
        "The hacker types furiously as the countdown reaches zero",
        niche="true_crime",
        channel_config={"language": "en"}
    )
    print("Mood:", result["mood"])
    print("Video Prompt (first 300 chars):", result["video_prompt"][:300])
    print("\nSound Design:", result["sound_design"][:200])
    print("\nThumbnail:", result["thumbnail_prompt"][:150])
