"""VoiceEngine — real narration via edge-tts (100% free, no API key, no
sanctions/card issues since it's Microsoft's public Edge read-aloud service).

Captures word-level timing (WordBoundary events) while synthesizing, so we can
build accurate word-by-word subtitles without needing a separate transcription
step (no Whisper/GPU required).
"""

import os
import asyncio
import time

import edge_tts

_OUT_DIR = "assets/audio"


class VoiceEngine:
    def __init__(self):
        os.makedirs(_OUT_DIR, exist_ok=True)

    async def _synthesize(self, text: str, voice: str, out_path: str) -> list:
        communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
        words = []
        with open(out_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # offset/duration are in 100-nanosecond units -> seconds
                    words.append({
                        "text": chunk["text"],
                        "start": chunk["offset"] / 1e7,
                        "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                    })
        return words

    def generate_voiceover(self, text: str, voice: str) -> dict:
        """Synthesizes narration audio and returns {'audio_path', 'words', 'duration'}.
        Falls back to a silent placeholder if edge-tts's endpoint is unreachable
        (e.g. offline test environment), so the pipeline never hard-crashes."""
        out_path = os.path.join(_OUT_DIR, f"voice_{int(time.time()*1000)}.mp3")
        try:
            words = asyncio.run(self._synthesize(text, voice, out_path))
            duration = words[-1]["end"] if words else 0.0
            return {"audio_path": out_path, "words": words, "duration": duration, "engine": "edge-tts"}
        except Exception as e:
            print(f"[VoiceEngine] edge-tts failed ({e}); no audio produced")
            return {"audio_path": "", "words": [], "duration": 0.0, "engine": "error", "error": str(e)}


if __name__ == "__main__":
    import json

    engine = VoiceEngine()
    result = engine.generate_voiceover("This is a real test of the voice engine.", "en-US-ChristopherNeural")
    print(json.dumps({k: v for k, v in result.items() if k != "words"}, indent=2))
    print(f"Words captured: {len(result['words'])}")
