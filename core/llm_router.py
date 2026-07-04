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
  3. openrouter - free ":free" model IDs, no card. IMPORTANT (confirmed via
                  a live diagnostic run on 2026-07-04): OpenRouter's free
                  model catalog ROTATES -- a model id that was free last
                  month can 404 today. _call_openrouter() therefore tries a
                  short list of historically-stable free ids (Llama 3.3 70B,
                  GPT-OSS 120B, Qwen3-Next 80B) and falls through the list on
                  a 404 instead of giving up on the first one.
  4. deepseek   - NOT free per-token; new accounts are SUPPOSED to get a
                  5M-token/30-day free grant, but this can return
                  HTTP 402 "Insufficient Balance" if that grant wasn't
                  applied to your account/region -- confirmed live in
                  production here. If you see this, add a small balance at
                  platform.deepseek.com; after that it's extremely cheap
                  ($0.14/$0.28 per million tokens). Included because the
                  user explicitly asked for it.
  5. avalai     - Iranian OpenAI-compatible aggregator, Rial payment (no
                  international card needed), 400+ models at official
                  provider pricing (no markup). Recommended paid fallback
                  -- see docs/LLM-PROVIDERS-2026.md for the full comparison
                  against GapGPT that led to this choice.
  6. gapgpt     - Another Iranian aggregator, same Rial-payment model,
                  slightly narrower model catalog than AvalAI but a
                  reasonable second paid option.
  7. deepseek   - NOT free per-token; new accounts are SUPPOSED to get a
                  5M-token/30-day free grant, but this can return
                  HTTP 402 "Insufficient Balance" if that grant wasn't
                  applied to your account/region -- confirmed live in
                  production here. If you see this, add a small balance at
                  platform.deepseek.com; after that it's extremely cheap
                  ($0.14/$0.28 per million tokens). Included because the
                  user explicitly asked for it.
  8. moonshot   - Kimi K2 via Moonshot's own API is prepaid (needs a min $1
                  recharge, not purely free) -- included per user request.
                  _call_kimi_via_openrouter() also tries OpenRouter's
                  "moonshotai/kimi-k2:free" id first in case it's
                  temporarily free again, but as of 2026-07-04 this id is
                  NOT in OpenRouter's free catalog (confirmed live) so it
                  will usually fail through to the paid direct API.

SPENDING SAFETY: every call to a paid provider (avalai/gapgpt/deepseek/
moonshot_direct) is checked against core/usage_guard.py's daily/monthly
dollar budget BEFORE the request is sent. This exists because early manual
testing burned through a free daily quota in seconds with no limit in
place -- see docs/LLM-PROVIDERS-2026.md for the full monthly cost estimate
and how to tune LLM_DAILY_BUDGET_USD / LLM_MONTHLY_BUDGET_USD.

All providers are OpenAI-compatible chat-completion style except Gemini,
which uses the google-generativeai SDK.
"""

import os
import re
import json

import requests

from .usage_guard import UsageGuard

_TIMEOUT = 45

# Providers subject to a real dollar budget (UsageGuard) before every call
# -- i.e. anything that isn't a genuinely free tier. See
# docs/LLM-PROVIDERS-2026.md for the reasoning behind each provider's
# classification.
_PAID_PROVIDERS = {"avalai", "gapgpt", "deepseek", "moonshot_direct"}


class LLMRouter:
    def __init__(self):
        self.name = "LLMRouter"
        self.usage_guard = UsageGuard()

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
        """Tries a short list of well-known, historically-stable free model
        IDs on OpenRouter (falling back through the list on a 404, since
        OpenRouter's free-model catalog rotates over time -- verified live
        via GET /api/v1/models that model availability genuinely changes
        week to week, which is what caused a real 404 in production here).
        A single explicit `model` argument (e.g. from _call_kimi_via_openrouter)
        skips the fallback list and tries only that one."""
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")

        candidates = [model] if model else [
            os.environ.get("OPENROUTER_MODEL", ""),
            "meta-llama/llama-3.3-70b-instruct:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
        ]
        candidates = [c for c in candidates if c]

        last_error = None
        for candidate_model in candidates:
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": candidate_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                    timeout=_TIMEOUT,
                )
                if r.status_code == 404:
                    # This specific model id is no longer available on
                    # OpenRouter's free tier -- try the next candidate
                    # instead of giving up (their free catalog rotates).
                    last_error = f"{candidate_model}: 404 model_not_found"
                    continue
                r.raise_for_status()
                data = r.json()
                if "choices" not in data:
                    err = data.get("error", {})
                    msg = err.get("message", str(data)[:200]) if isinstance(err, dict) else str(err)[:200]
                    last_error = f"{candidate_model}: {msg}"
                    continue
                return data["choices"][0]["message"]["content"]
            except requests.RequestException as e:
                last_error = f"{candidate_model}: {e}"
                continue

        raise RuntimeError(last_error or "no_candidate_models_available")

    def _call_kimi_via_openrouter(self, system_prompt: str, user_prompt: str) -> str:
        """Kimi K2 on OpenRouter is NOT reliably free (its free-tier ':free'
        route rotates on/off; verified via a live GET /api/v1/models call on
        2026-07-04 that returned zero free Kimi model ids). Kept as a
        best-effort attempt at the ':free' id in case it's back, but this is
        no longer guaranteed -- _call_openrouter's fallback list of
        consistently-free models is the reliable path."""
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

    def _call_avalai(self, system_prompt: str, user_prompt: str) -> str:
        """AvalAI -- Iranian OpenAI-compatible aggregator (Rial payment, no
        international card needed, official-provider pricing pass-through).
        Recommended default paid model here is a cheap OpenAI-family model;
        override with AVALAI_MODEL env var (e.g. 'deepseek-chat' or
        'gpt-4o-mini') to pick something else from AvalAI's 400+ catalog."""
        key = os.environ.get("AVALAI_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")
        # os.environ.get(name, default) does NOT catch an empty string --
        # and GitHub Actions passes an unset secret through as '' rather
        # than omitting the env var entirely (see core/usage_guard.py's
        # docstring for the same bug found live in production 2026-07-04).
        model = os.environ.get("AVALAI_MODEL", "").strip() or "gpt-4o-mini"
        r = requests.post(
            "https://api.avalai.ir/v1/chat/completions",
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
        return r.json()["choices"][0]["message"]["content"]

    def _call_gapgpt(self, system_prompt: str, user_prompt: str) -> str:
        """GapGPT -- another Iranian OpenAI-compatible aggregator (Rial
        payment). Override GAPGPT_MODEL to pick a specific model."""
        key = os.environ.get("GAPGPT_API_KEY", "")
        if not key:
            raise RuntimeError("no_key")
        # Same empty-string-secret gotcha as AVALAI_MODEL above -- GitHub
        # Actions passes an unset secret through as '' rather than omitting
        # the env var entirely, so a naive .get(name, default) is not safe.
        model = os.environ.get("GAPGPT_MODEL", "").strip() or "gpt-4o-mini"
        r = requests.post(
            "https://gapgpt.app/api/v1/chat/completions",
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
        return r.json()["choices"][0]["message"]["content"]

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        """Direct DeepSeek API -- new accounts get a 5M-token/30-day free
        grant (no card), then pay-per-token at very low rates ($0.14/$0.28
        per M tokens). Included per explicit user request.

        NOTE: if this returns HTTP 402 ('Insufficient Balance'), the
        account's free-token grant either hasn't been applied or has run
        out -- this requires manually adding a small balance at
        platform.deepseek.com, since 402 is DeepSeek's own billing system
        rejecting the request, not a bug in this code."""
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
        if r.status_code == 402:
            raise RuntimeError("402 Insufficient Balance -- add funds at platform.deepseek.com")
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------ #
    # Free providers first (groq/gemini/openrouter), then paid Iranian
    # aggregators (avalai/gapgpt -- Rial payment, no card needed, official
    # provider pricing), then the two originally-requested paid options
    # (deepseek/moonshot_direct) last since AvalAI/GapGPT already offer the
    # same underlying models at the same price with less individual-account
    # balance-management overhead.
    _PROVIDERS = [
        ("groq", "_call_groq"),
        ("gemini", "_call_gemini"),
        ("kimi_openrouter", "_call_kimi_via_openrouter"),
        ("openrouter", "_call_openrouter"),
        ("avalai", "_call_avalai"),
        ("gapgpt", "_call_gapgpt"),
        ("deepseek", "_call_deepseek"),
        ("moonshot_direct", "_call_moonshot_direct"),
    ]

    def generate(self, system_prompt: str, user_prompt: str, order: list = None) -> dict:
        """Tries each provider in order (default: self._PROVIDERS) until one
        succeeds. Returns {'text': ..., 'provider': ...} on success, or
        {'error': ..., 'attempts': [...]} if every provider failed/had no
        key configured -- caller should fall back to an offline template.

        Paid providers (see _PAID_PROVIDERS) are checked against
        UsageGuard's daily/monthly dollar budget BEFORE the request is
        sent -- if the estimated cost would exceed either limit, that
        provider is skipped (logged in `attempts`) without ever making the
        network call, so a runaway loop or an unexpectedly large batch can
        never overspend."""
        providers = order or [name for name, _ in self._PROVIDERS]
        method_map = dict(self._PROVIDERS)
        attempts = []

        for provider_name in providers:
            method_name = method_map.get(provider_name)
            if not method_name:
                continue

            if provider_name in _PAID_PROVIDERS:
                guard_result = self.usage_guard.check_and_reserve(provider_name, system_prompt, user_prompt)
                if not guard_result.get("allowed"):
                    attempts.append(f"{provider_name}: budget_guard_blocked ({guard_result.get('reason')})")
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
