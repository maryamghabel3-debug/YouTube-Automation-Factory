"""VideoAssembler — builds a REAL, playable long-form MP4 using FFmpeg.

Pipeline per video:
  1. For each scene, normalize its stock clip (image -> Ken Burns zoom/pan,
     video -> scaled/cropped/looped) to a fixed-duration 1920x1080 segment
     matching how long the narration takes to say that scene's line.
  2. Concatenate all scene segments into one silent video track.
  3. Burn in word-by-word subtitles (from VoiceEngine's word timings) via
     FFmpeg's ASS subtitle filter.
  4. Mux the narration audio (+ optional background music, ducked under
     narration) onto the video track.

No mocks: every step invokes a real `ffmpeg`/`ffprobe` subprocess and the
final file is verified to exist and be non-trivial in size before returning.
"""

import os
import glob
import json
import shutil
import subprocess
import time

_OUT_DIR = "output"
_WORK_DIR = "assets/work"

_W, _H = 1920, 1080
_FPS = 30


class VideoAssembler:
    def __init__(self):
        os.makedirs(_OUT_DIR, exist_ok=True)
        os.makedirs(_WORK_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    def _run(self, cmd: list, label: str) -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"[VideoAssembler] {label} failed: {result.stderr[-800:]}")
                return False
            return True
        except subprocess.TimeoutExpired:
            print(f"[VideoAssembler] {label} timed out")
            return False
        except FileNotFoundError:
            print(f"[VideoAssembler] ffmpeg/ffprobe not found on this system")
            return False

    def _probe_duration(self, path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=30,
            )
            return float(result.stdout.strip() or 0)
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            return 0.0

    # ------------------------------------------------------------------ #
    def _render_image_segment(self, image_path: str, duration: float, out_path: str) -> bool:
        """Ken Burns effect: slow zoom-in on a still image for `duration` seconds."""
        frames = max(int(duration * _FPS), 1)
        # zoompan needs a slightly upscaled source to avoid edge artifacts while zooming
        vf = (
            f"scale=3840:2160,zoompan=z='min(zoom+0.0008,1.15)':"
            f"d={frames}:s={_W}x{_H}:fps={_FPS}"
        )
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-vf", vf, "-t", f"{duration:.3f}",
            "-pix_fmt", "yuv420p", "-an", out_path,
        ]
        return self._run(cmd, f"Ken Burns render ({image_path})")

    def _render_video_segment(self, video_path: str, duration: float, out_path: str) -> bool:
        """Scale/crop a stock video clip to 1920x1080 and trim/loop to `duration`."""
        src_dur = self._probe_duration(video_path)
        vf = f"scale={_W}:{_H}:force_original_aspect_ratio=increase,crop={_W}:{_H},fps={_FPS}"
        if src_dur and src_dur < duration:
            # Loop short clips so they cover the full narration duration
            cmd = [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", video_path,
                "-vf", vf, "-t", f"{duration:.3f}",
                "-pix_fmt", "yuv420p", "-an", out_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", vf, "-t", f"{duration:.3f}",
                "-pix_fmt", "yuv420p", "-an", out_path,
            ]
        return self._run(cmd, f"video segment render ({video_path})")

    # ------------------------------------------------------------------ #
    def _build_ass_subtitles(self, words: list, out_path: str, language: str = "en") -> bool:
        """Burns bold, centered, word-by-word (Hormozi-style) subtitles from
        edge-tts's word-boundary timings — no separate transcription needed."""
        def ts(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h:d}:{m:02d}:{s:05.2f}"

        font = "Vazirmatn" if language == "fa" else "Arial"
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {_W}
PlayResY: {_H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginV
Style: Default,{font},72,&H00FFFFFF,&H00000000,&H80000000,1,4,2,2,120

[Events]
Format: Layer, Start, End, Style, Text
"""
        lines = [header]
        # Group words into short 3-4 word bursts for readability
        chunk = []
        chunk_start = None
        for w in words:
            if chunk_start is None:
                chunk_start = w["start"]
            chunk.append(w["text"])
            if len(chunk) >= 3:
                lines.append(
                    f"Dialogue: 0,{ts(chunk_start)},{ts(w['end'])},Default,{' '.join(chunk)}\n"
                )
                chunk, chunk_start = [], None
        if chunk:
            lines.append(
                f"Dialogue: 0,{ts(chunk_start)},{ts(words[-1]['end'])},Default,{' '.join(chunk)}\n"
            )

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
        except OSError as e:
            print(f"[VideoAssembler] subtitle write failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    def build_video(self, scenes_with_clips: list, audio_path: str, words: list,
                     language: str = "en", music_path: str = "") -> dict:
        """Full pipeline: render each scene, concat, burn subtitles, mux audio.
        Returns {'video_path': ..., 'duration': ...} or {'error': ...}."""
        session_id = int(time.time() * 1000)
        work_dir = os.path.join(_WORK_DIR, str(session_id))
        os.makedirs(work_dir, exist_ok=True)

        audio_duration = self._probe_duration(audio_path)
        if audio_duration <= 0:
            return {"error": "invalid_or_missing_audio"}

        # Distribute total narration time across scenes proportionally to
        # each scene's text length (longer lines get more screen time).
        text_lengths = [max(len(s.get("text", "")), 1) for s in scenes_with_clips]
        total_len = sum(text_lengths)
        segment_paths = []

        for i, (scene, tlen) in enumerate(zip(scenes_with_clips, text_lengths)):
            duration = max(audio_duration * (tlen / total_len), 1.5)
            clip = scene.get("clip", {})
            seg_out = os.path.join(work_dir, f"seg_{i:03d}.mp4")
            ok = False
            if clip.get("path") and os.path.exists(clip["path"]):
                if clip.get("type") == "video":
                    ok = self._render_video_segment(clip["path"], duration, seg_out)
                else:
                    ok = self._render_image_segment(clip["path"], duration, seg_out)
            if ok and os.path.exists(seg_out):
                segment_paths.append(seg_out)
            else:
                print(f"[VideoAssembler] scene {i} render failed or missing clip; skipping")

        if not segment_paths:
            return {"error": "no_segments_rendered"}

        # Concat all scene segments (silent) into one video track
        concat_list = os.path.join(work_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for p in segment_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")
        silent_video = os.path.join(work_dir, "silent.mp4")
        if not self._run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
             "-c", "copy", silent_video],
            "concat segments",
        ):
            return {"error": "concat_failed"}

        # Burn subtitles (if we have word timings)
        video_with_subs = silent_video
        if words:
            ass_path = os.path.join(work_dir, "subs.ass")
            if self._build_ass_subtitles(words, ass_path, language):
                subbed = os.path.join(work_dir, "subbed.mp4")
                escaped = ass_path.replace(":", "\\:")
                if self._run(
                    ["ffmpeg", "-y", "-i", silent_video, "-vf", f"ass={escaped}",
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", subbed],
                    "burn subtitles",
                ):
                    video_with_subs = subbed

        # Mux narration audio (+ optional ducked background music) onto video
        final_path = os.path.join(_OUT_DIR, f"video_{session_id}.mp4")
        if music_path and os.path.exists(music_path):
            # Narration full volume, music ducked to 12% and looped to match length
            filter_complex = (
                "[1:a]volume=1.0[narr];"
                "[2:a]volume=0.12,aloop=loop=-1:size=2e9[music];"
                "[narr][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            ok = self._run(
                ["ffmpeg", "-y", "-i", video_with_subs, "-i", audio_path, "-i", music_path,
                 "-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]",
                 "-c:v", "copy", "-c:a", "aac", "-shortest", final_path],
                "mux audio+music",
            )
        else:
            ok = self._run(
                ["ffmpeg", "-y", "-i", video_with_subs, "-i", audio_path,
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                 "-shortest", final_path],
                "mux audio",
            )

        if not ok or not os.path.exists(final_path) or os.path.getsize(final_path) < 1000:
            return {"error": "mux_failed"}

        # Cleanup intermediate work files to save disk (keep only final output)
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except OSError:
            pass

        return {
            "video_path": final_path,
            "duration": self._probe_duration(final_path),
            "scenes_rendered": len(segment_paths),
        }


if __name__ == "__main__":
    print("VideoAssembler is a library module; use core/video_factory.py to run the full pipeline.")
