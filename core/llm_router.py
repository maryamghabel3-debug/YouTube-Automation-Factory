"""LLMRouter — multi-provider free/cheap LLM fallback chain.

Why this exists: relying on a single provider (just Gemini) means the whole
script-writing step falls back to the offline template the moment that
provider's quota is exhausted for the day (this literally happened to the
sibling elina-radman project — see GAZARESH-BARRASI-1404.md). This router
tries several genuinely-free-or-near-free, no-international-card-required
providers in order, and only falls back to the offline template if every
single one fails.

Providers, in default preference order (fastest/most reliable free tier
first, based on live 2026 research — see docs/LLM-PROVIDERS-2026.md):
  1. groq       - free, no card, ~30 req/min, Llama 3.3 70B, extremely fast
  2. gemini     - free, no card, ~1500 req/day on Flash (shared quota with
                  elina-radman if using the SAME Google Cloud project/key —
                  use a separate GEMINI_API_KEY here to avoid competing for
                  the same quota)
  3. openrouter - free ":free" model IDs, no card, ~50 req/day (or 1000/day
                  with a one-time $10 top-up, never required)
  4. deepseek   - NOT free per-token, but every new account gets a 5M-token
                  grant (~30 days, no card) and after that is extremely
                  cheap ($0.14/$0.28 per million tokens) -- included because
                  the user explicitly asked for it
  5. moonshot   - Kimi K2 via Moonshot's own API is prepaid (needs a min $1
                  recharge, not purely free) -- included per user request,
                  but ALSO reachable for free via OpenRouter's
                  "moonshotai/kimi-k2:free" route, which this router prefers
                  automatically (see _kimi_via_openrouter)

All providers are OpenAI-compatible chat-completion style except Gemini,
which uses the google-generativeai SDK.
"""

import os
import re
import json

import requests

_TIMEOUT = 45


class LLMRouter:
    def __init__(self):
        self.name = "LLMRouter"

    # ------------------------------------------------------------------ #
    # Per-provider callers. Each returns the raw text response, or raises
    # on failure (caught centrally in generate()).
    # ------------------------------------------------------------------ #
    def _call_groq(self, system_prompt: str, user_prompt: str) -> str:
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")
        import google.generativeai as genai

        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        resp = model.generate_content(full_prompt)
        return resp.text

    def _call_openrouter(self, system_prompt: str, user_prompt: str, model: str = None) -> str:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")
        model = model or os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if "choices" not in data:
            err = data.get("error", {})
            msg = err.get("message", str(data)[:200]) if isinstance(err, dict) else str(err)[:200]
            raise RuntimeError(msg)
        return data["choices"][0]["message"]["content"]

    def _call_kimi_via_openrouter(self, system_prompt: str, user_prompt: str) -> str:
        """Kimi K2 has a genuinely free route through OpenRouter's
        'moonshotai/kimi-k2:free' model id -- preferred over the direct
        Moonshot API (which requires a prepaid balance)."""
        return self._call_openrouter(system_prompt, user_prompt, model="moonshotai/kimi-k2:free")

    def _call_moonshot_direct(self, system_prompt: str, user_prompt: str) -> str:
        """Direct Moonshot (Kimi) API -- requires MOONSHOT_API_KEY with a
        prepaid balance (min $1 recharge, not purely free). Kept as an
        explicit option since the user already has this key from
        elina-radman, but the free OpenRouter route is tried first."""
        key = os.environ.get("MOONSHOT_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")
        r = requests.post(
            "https://api.moonshot.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "kimi-k2.6",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        """Direct DeepSeek API -- new accounts get a 5M-token/30-day free
        grant (no card), then pay-per-token at very low rates ($0.14/$0.28
        per M tokens). Included per explicit user request."""
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------ #
    _PROVIDERS = [
        ("groq", "_call_groq"),
        ("gemini", "_call_gemini"),
        ("kimi_openrouter", "_call_kimi_via_openrouter"),
        ("openrouter", "_call_openrouter"),
        ("deepseek", "_call_deepseek"),
        ("moonshot_direct", "_call_moonshot_direct"),
    ]

    def generate(self, system_prompt: str, user_prompt: str, order: list = None) -> dict:
        """Tries each provider in order (default: self._PROVIDERS) until one
        succeeds. Returns {'text': ..., 'provider': ...} on success, or
        {'error': ..., 'attempts': [...]} if every provider failed/had no
        key configured -- caller should fall back to an offline template."""
        providers = order or [name for name, _ in self._PROVIDERS]
        method_map = dict(self._PROVIDERS)
        attempts = []

        for provider_name in providers:
            method_name = method_map.get(provider_name)
            if not method_name:
                continue
            method = getattr(self, method_name)
            try:
                text = method(system_prompt, user_prompt)
                if text and text.strip():
                    return {"text": text, "provider": provider_name}
                attempts.append(f"{provider_name}: empty_response")
            except RuntimeError as e:
                if str(e) != "no_key":
                    attempts.append(f"{provider_name}: {e}")
                # no_key is silent -- expected when a provider isn't configured
            except requests.RequestException as e:
                attempts.append(f"{provider_name}: {e}")
            except Exception as e:
                attempts.append(f"{provider_name}: {e}")

        return {"error": "all_providers_failed", "attempts": attempts}

    def generate_json(self, system_prompt: str, user_prompt: str, order: list = None) -> dict:
        """Same as generate() but strips markdown fences and json.loads()s
        the result. Returns {'data': <parsed>, 'provider': ...} or
        {'error': ...}."""
        result = self.generate(system_prompt, user_prompt, order=order)
        if "error" in result:
            return result
        raw = re.sub(r"^```(json)?|```$", "", result["text"].strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(raw)
            return {"data": data, "provider": result["provider"]}
        except (json.JSONDecodeError, ValueError) as e:
            return {"error": f"json_parse_failed: {e}", "raw": raw[:500], "provider": result["provider"]}


if __name__ == "__main__":
    router = LLMRouter()
    result = router.generate("You are a helpful assistant.", "Say hello in one short sentence.")
    print(json.dumps(result, indent=2, ensure_ascii=False))
