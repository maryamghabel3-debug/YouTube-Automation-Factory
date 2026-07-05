"""text_normalizer — converts raw digits in narration text to spoken words
BEFORE handing text to edge-tts.

WHY THIS EXISTS: the user reviewed a real Persian test video and reported
"تلفظ فارسی در اعداد و بعضی کلمات ایراد داشت" (Persian pronunciation of
numbers and some words was off). Verified live: edge-tts's Persian voices
(fa-IR-FaridNeural/DilaraNeural) read multi-digit numbers digit-by-digit or
with an unnatural cadence when given raw numerals (e.g. "۱۹۷۶" or "1976"),
instead of the natural spoken form a human narrator would use ("هزار و
نهصد و هفتاد و شش"). This is a well-known text-to-speech localization gap,
not something fixable by choosing a different edge-tts voice.

FIX: convert every run of digits (Persian ۰-۹ or Western 0-9 -- content_bank
scripts use Persian digits, but this handles both) to its spoken word form
using num2words BEFORE synthesis, per language. English is left mostly
alone since edge-tts's English voices already read numbers naturally; the
fix specifically targets fa (and is trivially extensible to ar/tr/etc. if
those languages get their own channels later).
"""

import re

try:
    from num2words import num2words
except ImportError:  # pragma: no cover - dependency always present per requirements.txt
    num2words = None

_FA_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _to_western_digits(s: str) -> str:
    return s.translate(_FA_DIGIT_MAP)


def normalize_numbers(text: str, language: str = "en") -> str:
    """Replaces every run of digits in `text` with its spoken-word form in
    `language`. Falls back to leaving the original digits untouched if
    num2words is unavailable or a specific number can't be converted (never
    raises -- a slightly-off pronunciation is far better than a crash)."""
    if not text or num2words is None:
        return text

    # English narration from edge-tts already pronounces plain numbers
    # naturally; only Persian was reported as broken. Keep this explicit
    # (rather than "else: normalize everything") so it's easy to extend to
    # another language later without guessing whether it needs this.
    if language not in ("fa",):
        return text

    lang_code = {"fa": "fa"}.get(language, "en")

    def _replace(match: "re.Match") -> str:
        raw = match.group(0)
        western = _to_western_digits(raw)
        try:
            n = int(western)
        except ValueError:
            return raw  # e.g. a lone digit inside a longer token; leave as-is
        try:
            return num2words(n, lang=lang_code)
        except (NotImplementedError, OverflowError):
            return raw

    return re.sub(r"[۰-۹0-9]+", _replace, text)


if __name__ == "__main__":
    samples = [
        ("سال ۱۸۷۲ یه کشتی وسط اقیانوس اطلس پیدا شد.", "fa"),
        ("بین سال‌های ۱۹۷۶ تا ۱۹۸۶ کل محله‌ها رو به وحشت انداخت.", "fa"),
        ("This happened in 1976, a long time ago.", "en"),
    ]
    for text, lang in samples:
        print(f"[{lang}] {text}\n  -> {normalize_numbers(text, lang)}\n")
