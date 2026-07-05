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

# BUG FIXED (found by user review 2026-07-05): scene durations were being
# computed proportionally to narration text length with NO upper cap, so a
# single scene (one still image or one video clip) often held the screen
# for 10-14+ seconds straight -- far above the ~3-5 second visual-change
# interval research shows keeps faceless/documentary-style viewers engaged
# (see docs/YOUTUBE-GROWTH-AND-ENGAGEMENT.md and the cited retention-editing
# research). Any single visual block longer than this is now split into
# multiple shorter sub-cuts of the SAME source clip (different Ken Burns
# pan/zoom direction for images, different start offset for videos) --
# this needs zero extra footage-API calls and still counts as a real visual
# change for retention, not padding.
_MAX_SEGMENT_SECONDS = 6.0


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
    def _render_image_segment(self, image_path: str, duration: float, out_path: str,
                               pan_direction: str = "in") -> bool:
        """Ken Burns effect: continuous zoom/pan on a still image for the
        FULL `duration` seconds.

        BUG FIXED (found by user review 2026-07-05): the old fixed zoom
        rate (+0.0008/frame) hit its 1.15x cap after ~6.25 seconds at 30fps
        REGARDLESS of the scene's actual duration -- since most scenes ran
        10-14 seconds (see the char-length-proportional split below), the
        image visibly FROZE completely still for the second half of nearly
        every scene, which is exactly the "boring, doesn't seem to change"
        complaint. The zoom rate is now computed per-scene so the motion
        finishes exactly when the segment ends, no matter how long it runs.

        pan_direction: 'in' (zoom in, centered), 'out' (zoom out from a
        tight crop), 'left' or 'right' (zoom in while panning) -- used by
        the scene-splitting logic below so consecutive sub-cuts of the SAME
        source image visibly look like different shots, not a repeat.
        """
        frames = max(int(duration * _FPS), 1)
        target_zoom = 1.15
        rate = (target_zoom - 1.0) / frames

        if pan_direction == "out":
            z_expr = f"if(eq(on,0),{target_zoom},max(zoom-{rate:.8f},1.0))"
        else:
            z_expr = f"min(zoom+{rate:.8f},{target_zoom})"

        x_expr, y_expr = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"  # centered (default 'in')
        if pan_direction == "left":
            x_expr = "iw/2-(iw/zoom/2)-(on/{})*40".format(max(frames, 1))
        elif pan_direction == "right":
            x_expr = "iw/2-(iw/zoom/2)+(on/{})*40".format(max(frames, 1))

        vf = (
            f"scale=3840:2160,zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={frames}:s={_W}x{_H}:fps={_FPS}"
        )
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-vf", vf, "-t", f"{duration:.3f}",
            "-pix_fmt", "yuv420p", "-an", out_path,
        ]
        return self._run(cmd, f"Ken Burns render ({image_path})")

    def _render_video_segment(self, video_path: str, duration: float, out_path: str,
                               start_offset: float = 0.0) -> bool:
        """Scale/crop a stock video clip to 1920x1080 and trim/loop to
        `duration`, starting from `start_offset` seconds into the source
        clip -- used by the scene-splitting logic below so consecutive
        sub-cuts of the SAME source clip show different moments of it
        rather than repeating the identical opening frames."""
        src_dur = self._probe_duration(video_path)
        vf = f"scale={_W}:{_H}:force_original_aspect_ratio=increase,crop={_W}:{_H},fps={_FPS}"
        # Only seek if the source is long enough to have real content left
        # after the offset; otherwise fall back to the start (avoids seeking
        # past the end of a short clip and getting a black/empty segment).
        safe_offset = start_offset if (src_dur and start_offset < max(src_dur - 0.5, 0)) else 0.0
        if src_dur and (src_dur - safe_offset) < duration:
            # Loop short clips so they cover the full narration duration
            cmd = [
                "ffmpeg", "-y", "-ss", f"{safe_offset:.3f}", "-stream_loop", "-1", "-i", video_path,
                "-vf", vf, "-t", f"{duration:.3f}",
                "-pix_fmt", "yuv420p", "-an", out_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-ss", f"{safe_offset:.3f}", "-i", video_path,
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

        # Alternating pan directions/video-offsets so consecutive sub-cuts
        # of the SAME source clip look like distinct shots instead of an
        # obvious repeat (see _MAX_SEGMENT_SECONDS split below).
        _IMAGE_PAN_CYCLE = ["in", "left", "out", "right"]

        for i, (scene, tlen) in enumerate(zip(scenes_with_clips, text_lengths)):
            duration = max(audio_duration * (tlen / total_len), 1.5)
            clip = scene.get("clip", {})
            has_clip = bool(clip.get("path") and os.path.exists(clip["path"]))

            # BUG FIXED (found by user review 2026-07-05, round 1): a single
            # scene used to hold ONE static shot for its entire (often
            # 10-14s) duration with no cut -- far above the ~3-5s
            # visual-change interval that keeps faceless-channel viewers
            # engaged (see docs/YOUTUBE-GROWTH-AND-ENGAGEMENT.md). Split any
            # scene longer than _MAX_SEGMENT_SECONDS into multiple shorter
            # sub-cuts.
            #
            # BUG FIXED (round 2, same review): the round-1 fix reused the
            # SAME source clip for every sub-cut (only varying Ken Burns pan
            # direction), which still visually reads as "the same picture
            # shown again," not a real cut. core/stock_footage_fetcher.py's
            # fetch_for_script() now pre-fetches genuinely DIFFERENT real
            # clips for a long scene (in scene['extra_clips']) -- use those
            # for sub-cuts 2, 3, ... instead of repeating sub-cut 1's clip.
            # Only fall back to re-using the primary clip (with a different
            # pan) if fewer extra clips came back than sub-cuts needed
            # (e.g. a very narrow query with few real results available).
            extra_clips = scene.get("extra_clips", [])
            num_subcuts = max(1, int(duration // _MAX_SEGMENT_SECONDS) + (1 if duration % _MAX_SEGMENT_SECONDS > 1.0 else 0))
            sub_duration = duration / num_subcuts

            for sub_i in range(num_subcuts):
                seg_out = os.path.join(work_dir, f"seg_{i:03d}_{sub_i:02d}.mp4")
                ok = False

                if sub_i == 0:
                    sub_clip, is_fallback_repeat = clip, False
                elif sub_i - 1 < len(extra_clips):
                    sub_clip, is_fallback_repeat = extra_clips[sub_i - 1], False
                else:
                    sub_clip, is_fallback_repeat = clip, True  # no more distinct clips available

                sub_has_clip = bool(sub_clip.get("path") and os.path.exists(sub_clip.get("path", "")))
                if sub_has_clip:
                    if sub_clip.get("type") == "video":
                        # Only need an artificial start-offset when we're
                        # forced to repeat the same source video (real
                        # sub-cuts already show a different clip entirely).
                        start_offset = (sub_i * sub_duration * 0.6) if is_fallback_repeat else 0.0
                        ok = self._render_video_segment(sub_clip["path"], sub_duration, seg_out, start_offset=start_offset)
                    else:
                        pan = _IMAGE_PAN_CYCLE[sub_i % len(_IMAGE_PAN_CYCLE)]
                        ok = self._render_image_segment(sub_clip["path"], sub_duration, seg_out, pan_direction=pan)
                elif has_clip:
                    # extra_clips entry failed to download -- fall back to
                    # the scene's primary clip rather than dropping the cut.
                    pan = _IMAGE_PAN_CYCLE[sub_i % len(_IMAGE_PAN_CYCLE)]
                    if clip.get("type") == "video":
                        ok = self._render_video_segment(clip["path"], sub_duration, seg_out,
                                                         start_offset=sub_i * sub_duration * 0.6)
                    else:
                        ok = self._render_image_segment(clip["path"], sub_duration, seg_out, pan_direction=pan)

                if ok and os.path.exists(seg_out):
                    segment_paths.append(seg_out)
                else:
                    print(f"[VideoAssembler] scene {i} sub-cut {sub_i} render failed or missing clip; skipping")

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
            # BUG FIXED (found by user review 2026-07-05, round 4 -- "couldn't
            # understand what he's saying"): ffmpeg's amix filter defaults to
            # normalize=1 (true), which SILENTLY rescales every input by
            # 1/inputs (i.e. cuts narration to 50% of its set volume for a
            # 2-input mix) to guarantee no clipping -- regardless of the
            # per-track volume= filters applied beforehand. Measured live:
            # normalize=1 produced a mix ~6 dB quieter than normalize=0 for
            # the exact same inputs -- an very audible "half as loud"
            # difference, exactly matching the complaint. Fixed by adding
            # normalize=0 (we already explicitly control each track's
            # loudness via volume=1.0 / volume=0.12) plus a limiter on the
            # final mix to prevent any clipping now that amix stops doing
            # it for us.
            filter_complex = (
                "[1:a]volume=1.0[narr];"
                "[2:a]volume=0.12,aloop=loop=-1:size=2e9[music];"
                "[narr][music]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[premix];"
                "[premix]alimiter=limit=0.95[aout]"
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
