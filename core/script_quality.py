"""script_quality — validates that an LLM-generated script is actually
written in the language it was asked for, BEFORE it gets voiced/rendered.

WHY THIS EXISTS: the user reported that a real Persian test video's
narration was "بی‌سروته" (incoherent/nonsensical) and that they "couldn't
understand anything from the whole text." That video's script came from
OpenRouter's free ":free" models (Llama 3.3 70B / GPT-OSS 120B / Qwen3).
Live research done in this session found DOCUMENTED, first-hand reports
that these exact free models have measurably poor Arabic/Persian output
quality (e.g. a GPT-OSS-120B GitHub discussion: "i tested this model and
it have low quality in translation task like in arabic and persian
language, gemma and aya work better in this case even with 32B and 27B
parameters"). Non-Latin-script languages are a documented weak point for
these specific free models -- they can silently mix in English words,
produce garbled/non-grammatical Persian, or otherwise degrade quality in
ways that are hard to catch just by checking "did the API call succeed."

This module doesn't need a language-quality model to catch the failure
mode that actually happened: script text that claims to be Persian but is
majority non-Persian characters (English words mixed in, or literal
mistranslation artifacts) is trivially detectable by counting Persian
Unicode characters vs. total non-whitespace characters. This is a real,
cheap, deterministic, explainable check -- not a vague heuristic -- and
directly targets the specific failure mode found via user review.
"""

import re

# Persian/Arabic-script Unicode block (covers Persian text; Arabic loanwords
# used in Persian also fall in this range, which is expected and fine).
_PERSIAN_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")

# Below this fraction of Persian-script characters (of all non-whitespace,
# non-digit, non-punctuation characters), a scene that's supposed to be
# Persian is considered contaminated with too much non-Persian text (garbled
# LLM output, accidental English mixed in, etc.) to use as-is.
_MIN_PERSIAN_CHAR_RATIO = 0.75

# A script this short for its claimed scene count is almost certainly a
# broken/truncated LLM response, not a real narration beat.
_MIN_CHARS_PER_SCENE = 8


def persian_char_ratio(text: str) -> float:
    """Fraction of non-whitespace, letter-bearing characters that are in
    the Persian/Arabic Unicode script. Digits and punctuation are excluded
    from the denominator since both scripts share them equally (excluding
    them avoids penalizing a scene just for containing e.g. an English
    stock-footage-style year written in Western digits)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 1.0  # nothing to judge (e.g. a scene that's pure punctuation/digits)
    persian_count = sum(1 for c in letters if _PERSIAN_SCRIPT_RE.match(c))
    return persian_count / len(letters)


def validate_script_language(scenes: list, language: str) -> dict:
    """Checks every scene's 'text' field is actually written in the
    requested language. Returns {'ok': True} if every scene passes, or
    {'ok': False, 'reason': ..., 'bad_scenes': [...]} listing which scene
    indices failed and why -- the caller (ScriptWriter) should treat a
    failure exactly like the LLM call itself failing (reject this script,
    fall through to core/content_bank.py's curated content instead of
    shipping a garbled/wrong-language video).

    Only Persian is checked for now (the specific, confirmed real-world
    failure) -- other languages pass through unchecked since English
    narration from these same providers was reviewed as fine."""
    if language != "fa":
        return {"ok": True}

    if not scenes:
        return {"ok": False, "reason": "no_scenes"}

    bad_scenes = []
    for i, scene in enumerate(scenes):
        text = scene.get("text", "")
        if len(text.strip()) < _MIN_CHARS_PER_SCENE:
            bad_scenes.append({"index": i, "reason": "too_short", "text": text})
            continue
        ratio = persian_char_ratio(text)
        if ratio < _MIN_PERSIAN_CHAR_RATIO:
            bad_scenes.append({
                "index": i, "reason": f"low_persian_ratio ({ratio:.2f} < {_MIN_PERSIAN_CHAR_RATIO})",
                "text": text,
            })

    if bad_scenes:
        return {
            "ok": False,
            "reason": f"{len(bad_scenes)}/{len(scenes)} scene(s) failed Persian-language validation",
            "bad_scenes": bad_scenes,
        }
    return {"ok": True}


if __name__ == "__main__":
    good_scenes = [{"text": "بیش از سی سال، یه مرد حداقل دوازده قتل مرتکب شد."}]
    bad_scenes = [{"text": "The man committed murders در کالیفرنیا and فرار کرد."}]
    print("good:", validate_script_language(good_scenes, "fa"))
    print("bad:", validate_script_language(bad_scenes, "fa"))
