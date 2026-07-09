"""ThumbnailMaker — generates high-CTR cinematic YouTube thumbnails.

Uses cinematic prompt engineering (from Card Sovereign workflow) to create
thumbnails that maximize Click-Through Rate (CTR). Key principles applied:
- High contrast and vivid colors for visibility at small sizes
- Shocking/curious facial expressions (emotional trigger)
- Single clear focal point
- Red/yellow accent elements (proven to increase CTR)
- No text clutter (YouTube compresses small text badly)
- 8K ultra-sharp quality

If no image generation API is configured, generates a descriptive prompt
and saves it for manual use.
"""

import os
import json
import requests as _requests
from datetime import datetime

_OUT_DIR = "output/thumbnails"


class ThumbnailMaker:
    def __init__(self):
        os.makedirs(_OUT_DIR, exist_ok=True)

    # CTR-optimized mood presets (from AlgorithmHacker research + Card Sovereign)
    CTR_PRESETS = {
        "true_crime": {
            "visual": "dark ominous atmosphere, single dramatic spotlight on subject, deep shadows, red accent glow, mysterious silhouette in background",
            "emotion": "shocked wide-eyed expression, hand covering mouth in disbelief",
            "accent": "glowing red question mark or red circle highlighting hidden detail",
        },
        "history": {
            "visual": "epic dramatic lighting, golden hour glow on ancient ruins, dust particles in air, warm sepia tones with deep contrast",
            "emotion": "awe-struck expression, eyes wide with wonder",
            "accent": "golden arrow pointing to hidden ancient symbol",
        },
        "tech_ai": {
            "visual": "futuristic neon blue and purple lighting, holographic interface elements, dark tech background, glowing circuit patterns",
            "emotion": "excited confident smirk, pointing forward",
            "accent": "bright cyan highlight on futuristic gadget or screen",
        },
        "luxury": {
            "visual": "warm golden luxury lighting, marble and gold textures, soft bokeh background, elegant minimal composition",
            "emotion": "sophisticated confident smile, chin slightly raised",
            "accent": "subtle gold sparkle effect on luxury item",
        },
        "psychology": {
            "visual": "moody atmospheric lighting, split lighting (half face in shadow), deep blue and purple tones, abstract mind imagery",
            "emotion": "intense knowing stare, slight mysterious smile",
            "accent": "white glow highlighting a psychological concept or brain visual",
        },
        "space_science": {
            "visual": "cosmic deep space background, nebula colors, planet or galaxy behind subject, dramatic rim lighting from star",
            "emotion": "mind-blown expression, eyes reflecting cosmic light",
            "accent": "bright white circle highlighting a distant planet or anomaly",
        },
        "finance": {
            "visual": "clean modern lighting, green and gold upward arrows in background, financial charts glowing, professional setting",
            "emotion": "confident knowing smile, holding or gesturing toward money/chart",
            "accent": "bright green upward arrow or dollar sign highlight",
        },
        "motivation": {
            "visual": "powerful dramatic backlight, sunrise/sunset behind subject on mountain, lens flare, epic scale",
            "emotion": "determined fierce expression, fists clenched",
            "accent": "bright orange/yellow sun burst effect",
        },
        "horror": {
            "visual": "near-black darkness, single flickering light source, fog/mist, creepy environment barely visible",
            "emotion": "pure terror expression, eyes wide with fear, pale skin",
            "accent": "faint red glow from an unseen threat",
        },
        "relationships": {
            "visual": "warm soft lighting, cozy intimate setting, shallow depth of field, relatable everyday scenario",
            "emotion": "surprised or emotional expression, relatable reaction",
            "accent": "soft pink/red heart accent or highlight on key element",
        },
    }

    def make(self, title: str, niche: str, custom_prompt: str = "") -> str:
        """Generate a cinematic high-CTR thumbnail.
        Returns path to the generated image, or path to a .txt file
        containing the prompt if no image API is configured."""
        preset = self.CTR_PRESETS.get(niche, self.CTR_PRESETS["history"])

        # Build the cinematic thumbnail prompt
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = (
                f"YouTube thumbnail, 1280x720, high contrast, vivid saturated colors. "
                f"VISUAL: {preset['visual']}. "
                f"EMOTION: {preset['emotion']}. "
                f"ACCENT: {preset['accent']}. "
                f"Composition: rule of thirds, single clear focal point, "
                f"eye-catching, ultra-sharp 8K, professional color grading. "
                f"No text, no watermark."
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(_OUT_DIR, f"thumb_{niche}_{timestamp}")

        # Check for image generation API keys
        # (Cloudflare, HuggingFace, or local ComfyUI)
        cf_token = os.environ.get("CF_API_TOKEN")
        hf_token = os.environ.get("HF_TOKEN")

        if cf_token:
            return self._generate_cloudflare(prompt, output_path, cf_token)
        elif hf_token:
            return self._generate_huggingface(prompt, output_path, hf_token)
        else:
            # Fallback: save prompt for manual generation
            txt_path = output_path + "_prompt.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"CINEMATIC THUMBNAIL PROMPT:\n\n{prompt}\n\n")
                f.write(f"Niche: {niche}\n")
                f.write(f"Title: {title}\n")
                f.write(f"\nGenerated by YouTube-Automation-Factory ThumbnailMaker\n")
                f.write(f"(Card Sovereign + CTR-optimized cinematic workflow)\n")
            return txt_path

    def _generate_cloudflare(self, prompt: str, output_path: str, token: str) -> str:
        """Generate thumbnail via Cloudflare Workers AI (free tier)."""
        try:
            account_id = os.environ.get("CF_ACCOUNT_ID", "")
            url = (
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/"
                f"ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"
            )
            headers = {"Authorization": f"Bearer {token}"}
            payload = {"prompt": prompt}

            response = _requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "image" in result["result"]:
                    img_path = output_path + ".png"
                    import base64
                    with open(img_path, "wb") as f:
                        f.write(base64.b64decode(result["result"]["image"]))
                    return img_path
            return self._fallback_prompt(prompt, output_path)
        except Exception as e:
            return self._fallback_prompt(prompt, output_path)

    def _generate_huggingface(self, prompt: str, output_path: str, token: str) -> str:
        """Generate thumbnail via HuggingFace Inference API (free tier)."""
        try:
            from gradio_client import Client
            client = Client("black-forest-labs/FLUX.1-schnell", hf_token=token)
            result = client.predict(
                prompt=prompt,
                seed=42,
                randomize_seed=True,
                num_inference_steps=4,
                api_name="/infer",
            )
            image_path = result[0] if isinstance(result, tuple) else result
            if os.path.exists(image_path):
                import shutil
                final_path = output_path + ".png"
                shutil.copy(image_path, final_path)
                return final_path
            return self._fallback_prompt(prompt, output_path)
        except Exception:
            return self._fallback_prompt(prompt, output_path)

    def _fallback_prompt(self, prompt: str, output_path: str) -> str:
        txt_path = output_path + "_prompt.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"CINEMATIC THUMBNAIL PROMPT:\n\n{prompt}\n")
        return txt_path
