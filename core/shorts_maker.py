"""ShortsMaker — auto-generates 2-3 vertical Shorts/Reels clips from every
long-form video the factory produces, using the pattern documented from
SamurAIGPT/AI-Youtube-Shorts-Generator (see docs/GITHUB-AGENTS-EVALUATION.md
#9): use an LLM to find the most "hook-worthy" moments in the script, then
crop/re-encode just those moments into vertical 1080x1920 clips.

Why this matters for the "pay attention to high-view videos" strategy the
user asked for: Shorts/Reels get their own separate discovery feed with
much higher random-reach potential than long-form uploads, so a handful of
punchy vertical clips extracted from a video that already exists (zero
extra footage/voice cost) is one of the highest-leverage additions we can
make -- same content, far more surface area for going viral.

Input: the ALREADY-BUILT long-form video (from VideoAssembler) plus the
original script's per-scene text + word-level timings (from VoiceEngine),
so we know exactly which seconds of narration correspond to which sentence.
"""

import os
import json
import subprocess

from .llm_router import LLMRouter

_OUT_DIR = "output/shorts"
_SHORT_W, _SHORT_H = 1080, 1920
_MIN_CLIP_SECONDS = 15
_MAX_CLIP_SECONDS = 59  # under YouTube Shorts' 60s classification threshold


class ShortsMaker:
    def __init__(self):
        os.makedirs(_OUT_DIR, exist_ok=True)
        self.router = LLMRouter()

    # ------------------------------------------------------------------ #
    def _pick_hook_moments(self, scenes: list, num_clips: int = 3) -> list:
        """Asks the LLM which scene-index ranges make the best standalone
        hooks (self-contained, curiosity-driving, no missing context).
        Returns a list of {"start_scene": i, "end_scene": j, "reason": ...}.
        Falls back to a simple heuristic (first scene + one middle scene +
        last non-outro scene) if every LLM provider is unavailable."""
        numbered = "\n".join(f"{i}: {s['text']}" for i, s in enumerate(scenes))

        system_prompt = (
            "You select the most engaging, self-contained excerpts from a video "
            "script to repurpose as standalone vertical short-form clips (YouTube "
            "Shorts/Instagram Reels/TikTok). A good excerpt has a strong hook, makes "
            "sense without the rest of the video, and creates curiosity or delivers "
            "a complete mini-payoff."
        )
        user_prompt = f"""Here is a narration script broken into numbered scenes:

{numbered}

Pick the {num_clips} BEST short, contiguous scene-ranges (2-5 consecutive scenes each)
that would work as standalone vertical short clips. Prefer ranges that start with a
strong hook and don't overlap each other.

Respond ONLY with a JSON array like:
[{{"start_scene": 0, "end_scene": 2, "reason": "short reason"}}, ...]"""

        result = self.router.generate_json(system_prompt, user_prompt)
        if "data" in result and isinstance(result["data"], list) and result["data"]:
            picks = []
            for item in result["data"][:num_clips]:
                try:
                    s, e = int(item["start_scene"]), int(item["end_scene"])
                    if 0 <= s <= e < len(scenes):
                        picks.append({"start_scene": s, "end_scene": e, "reason": item.get("reason", "")})
                except (KeyError, ValueError, TypeError):
                    continue
            if picks:
                return picks

        # Heuristic fallback: opening hook, one middle chunk, one late chunk
        # (skipping the final outro/CTA scene which rarely works standalone).
        n = len(scenes)
        if n < 3:
            return [{"start_scene": 0, "end_scene": max(0, n - 1), "reason": "fallback: whole script"}]
        picks = [{"start_scene": 0, "end_scene": min(2, n - 2), "reason": "fallback: opening hook"}]
        mid = n // 2
        picks.append({"start_scene": mid, "end_scene": min(mid + 2, n - 2), "reason": "fallback: middle beat"})
        return picks[:num_clips]

    # ------------------------------------------------------------------ #
    def _scene_time_range(self, scene_index_start: int, scene_index_end: int,
                           scenes: list, words: list, full_text: str) -> tuple:
        """Maps a scene-index range to a (start_seconds, end_seconds) pair
        using the word-level timings VoiceEngine already captured, by
        finding where each scene's text begins/ends within the full
        narration text."""
        if not words:
            return 0.0, 0.0

        # Build a rough word-index boundary per scene by cumulative word counts
        # (full_text is scenes joined by " ", same order as `words`).
        scene_word_counts = [len(s["text"].split()) for s in scenes]
        cumulative = [0]
        for c in scene_word_counts:
            cumulative.append(cumulative[-1] + c)

        start_word_idx = cumulative[scene_index_start]
        end_word_idx = min(cumulative[scene_index_end + 1], len(words)) - 1
        end_word_idx = max(end_word_idx, start_word_idx)

        if start_word_idx >= len(words):
            return 0.0, 0.0

        start_time = words[start_word_idx]["start"]
        end_time = words[min(end_word_idx, len(words) - 1)]["end"]
        return start_time, end_time

    # ------------------------------------------------------------------ #
    def _crop_vertical_clip(self, source_video: str, start: float, end: float, out_path: str) -> bool:
        """Crops a horizontal 1920x1080 video down to a centered vertical
        1080x1920 clip covering [start, end] seconds -- keeps the existing
        burned-in subtitles roughly centered (they were placed centered in
        the original render)."""
        duration = max(end - start, _MIN_CLIP_SECONDS)
        duration = min(duration, _MAX_CLIP_SECONDS)
        vf = f"crop=ih*9/16:ih,scale={_SHORT_W}:{_SHORT_H}"
        cmd = [
            "ffmpeg", "-y", "-ss", f"{max(start, 0):.3f}", "-i", source_video,
            "-t", f"{duration:.3f}", "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            out_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                print(f"[ShortsMaker] crop failed: {result.stderr[-500:]}")
                return False
            return os.path.exists(out_path) and os.path.getsize(out_path) > 1000
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"[ShortsMaker] crop error: {e}")
            return False

    # ------------------------------------------------------------------ #
    def make_shorts(self, long_video_path: str, scenes: list, words: list,
                     full_text: str, num_clips: int = 3, topic: str = "") -> list:
        """Main entry point. Returns a list of
        {'path': ..., 'reason': ..., 'duration': ...} for each successfully
        produced Short. Never raises -- a failed clip is just skipped."""
        if not os.path.exists(long_video_path):
            print("[ShortsMaker] source video missing, skipping")
            return []
        if not words or not scenes:
            print("[ShortsMaker] no word timings/scenes available, skipping")
            return []

        picks = self._pick_hook_moments(scenes, num_clips=num_clips)
        results = []
        base = os.path.splitext(os.path.basename(long_video_path))[0]

        for i, pick in enumerate(picks):
            start, end = self._scene_time_range(
                pick["start_scene"], pick["end_scene"], scenes, words, full_text
            )
            if end <= start:
                continue
            out_path = os.path.join(_OUT_DIR, f"{base}_short{i+1}.mp4")
            if self._crop_vertical_clip(long_video_path, start, end, out_path):
                results.append({
                    "path": out_path,
                    "reason": pick.get("reason", ""),
                    "duration": min(max(end - start, _MIN_CLIP_SECONDS), _MAX_CLIP_SECONDS),
                })
                print(f"[ShortsMaker] Built short {i+1}/{len(picks)}: {out_path}")

        return results


if __name__ == "__main__":
    print("ShortsMaker is a library module -- called automatically from main.py "
          "after a long-form video is built. See core/video_factory.py.")
