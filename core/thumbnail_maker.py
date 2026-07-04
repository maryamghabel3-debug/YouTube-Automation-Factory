"""ThumbnailMaker — real, high-CTR-style YouTube thumbnails, built entirely
with free stock footage + PIL text overlay. No paid AI image generation
needed (avoids the exact quota/card problems that blocked Elina's photo
generation).

Approach (based on what consistently works for high-view faceless channels
-- MrBeast-style, Mystery/Documentary channels, etc.):
  1. Take a real frame from the video's own footage (a Pexels/Pixabay image,
     or an extracted frame from a Pexels/Pixabay video via ffmpeg) as the
     background -- keeps it visually consistent with the video itself.
  2. Darken/gradient the frame for text readability (a semi-transparent
     black gradient from the bottom, and a slight overall darken).
  3. Overlay a short, bold, high-contrast headline (2-5 words, auto-derived
     from the video topic, ALL CAPS for English, using yellow/white with a
     black outline -- the highest-contrast combination for small thumbnail
     previews) using a real bold font (Bebas/Anton-style weight preferred,
     falls back to DejaVu Sans Bold; Vazirmatn Bold for Persian).
  4. Saves a 1280x720 JPEG (YouTube's required thumbnail size).

This is intentionally simple and deterministic (no AI image generation) so
it costs $0 and never hits a rate limit.
"""

import os
import glob
import random
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter

_OUT_DIR = "output/thumbnails"
_W, _H = 1280, 720

# Font search order: prefer a real installed bold display font, fall back to
# DejaVu Sans Bold (always present on Debian/Ubuntu CI images) or Vazirmatn
# for Persian (installed via apt in the workflow; see .github/workflows/*.yml).
_FONT_CANDIDATES_EN = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_CANDIDATES_FA = [
    "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf",
    "/usr/share/fonts/opentype/vazirmatn/Vazirmatn-Bold.ttf",
] + _FONT_CANDIDATES_EN

_ACCENT_COLORS = [
    (255, 214, 10),   # high-visibility yellow (most common in top-performing thumbnails)
    (255, 255, 255),  # clean white
    (255, 59, 48),     # attention red
]


def _find_font(language: str) -> str:
    candidates = _FONT_CANDIDATES_FA if language == "fa" else _FONT_CANDIDATES_EN
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""  # PIL will use its built-in bitmap default as a last resort


def _extract_video_frame(video_path: str, out_path: str, at_seconds: float = 1.0) -> bool:
    """Grabs a single representative frame from a stock video clip via ffmpeg."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(at_seconds), "-i", video_path,
             "-frames:v", "1", "-q:v", "2", out_path],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0 and os.path.exists(out_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _shorten_headline(topic: str, language: str, max_words: int = 5) -> str:
    """BUG FIXED (2026-07-05, found by user review): this used to hard-cut
    the topic to `max_words` BEFORE _wrap_text ever ran, so any topic longer
    than 5 words produced a broken, grammatically-incomplete headline (e.g.
    'How billionaires actually spend their mornings' -> 'HOW BILLIONAIRES
    ACTUALLY SPEND THEIR', missing the word 'MORNINGS' entirely). Every
    single evergreen topic in content_config.py is 6+ words, so this bug
    fired on literally every thumbnail ever produced.

    Fix: return the FULL topic untouched (still uppercased for English) and
    let make_thumbnail()'s existing _wrap_text() + font-auto-shrink loop
    (already designed to fit up to 3 lines) do the actual layout. This
    param is kept for backwards compatibility but no longer used to
    pre-truncate."""
    text = topic.strip()
    return text.upper() if language != "fa" else text



def _wrap_text(draw, text: str, font, max_width: int) -> list:
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = f"{current} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


class ThumbnailMaker:
    def __init__(self):
        os.makedirs(_OUT_DIR, exist_ok=True)

    def _pick_background(self, scenes_with_clips: list) -> str:
        """Prefers the first scene's clip; extracts a frame if it's a video."""
        for scene in scenes_with_clips:
            clip = scene.get("clip", {})
            path = clip.get("path", "")
            if not path or not os.path.exists(path):
                continue
            if clip.get("type") == "image":
                return path
            frame_path = os.path.join(_OUT_DIR, f"frame_{os.path.basename(path)}.jpg")
            if _extract_video_frame(path, frame_path):
                return frame_path
        return ""

    def make_thumbnail(self, topic: str, scenes_with_clips: list, language: str = "en",
                        out_name: str = None) -> dict:
        """Returns {'path': ...} on success or {'error': ...}."""
        bg_path = self._pick_background(scenes_with_clips)
        try:
            if bg_path:
                img = Image.open(bg_path).convert("RGB")
            else:
                img = Image.new("RGB", (_W, _H), (25, 25, 30))
        except Exception as e:
            return {"error": f"background_load_failed: {e}"}

        # Cover-crop to 1280x720
        img_ratio = img.width / img.height
        target_ratio = _W / _H
        if img_ratio > target_ratio:
            new_height = _H
            new_width = int(new_height * img_ratio)
        else:
            new_width = _W
            new_height = int(new_width / img_ratio)
        img = img.resize((new_width, new_height))
        left = (new_width - _W) // 2
        top = (new_height - _H) // 2
        img = img.crop((left, top, left + _W, top + _H))

        # Slight darken overall + stronger gradient at the bottom for text contrast
        img = img.point(lambda p: int(p * 0.75))
        gradient = Image.new("L", (1, _H), color=0)
        for y in range(_H):
            gradient.putpixel((0, y), int(200 * (y / _H) ** 2))
        gradient = gradient.resize((_W, _H))
        black = Image.new("RGB", (_W, _H), (0, 0, 0))
        img = Image.composite(black, img, gradient)

        draw = ImageDraw.Draw(img)
        headline = _shorten_headline(topic, language)
        font_path = _find_font(language)
        font_size = 110
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()

        # Shrink font until the (possibly multi-line) headline fits within margins
        max_text_width = _W - 120
        lines = _wrap_text(draw, headline, font, max_text_width)
        while len(lines) > 3 and font_size > 40:
            font_size -= 10
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            lines = _wrap_text(draw, headline, font, max_text_width)

        accent = random.choice(_ACCENT_COLORS)
        line_height = int(font_size * 1.15)
        total_height = line_height * len(lines)
        y = _H - total_height - 60

        for line in lines:
            text_width = draw.textlength(line, font=font)
            x = (_W - text_width) // 2
            # Bold black outline (stroke) behind the accent-colored fill --
            # the single highest-impact technique for thumbnail readability
            # at small preview sizes.
            draw.text((x, y), line, font=font, fill=accent,
                      stroke_width=8, stroke_fill=(0, 0, 0))
            y += line_height

        out_name = out_name or f"thumb_{abs(hash(topic)) % 100000}.jpg"
        out_path = os.path.join(_OUT_DIR, out_name)
        img.save(out_path, "JPEG", quality=92)
        return {"path": out_path, "headline": headline}


if __name__ == "__main__":
    maker = ThumbnailMaker()
    demo_scenes = [{"clip": {"path": "", "type": "image"}}]
    print(maker.make_thumbnail("The Cold Case That Took 50 Years To Solve", demo_scenes, "en"))
