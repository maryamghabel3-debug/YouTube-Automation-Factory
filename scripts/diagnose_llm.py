#!/usr/bin/env python3
"""One-off diagnostic: calls each configured LLM provider directly (not
through the silent-fallback LLMRouter) and prints the RAW response/error for
each, so a misconfigured key or unexpected API error is immediately visible
instead of being swallowed into a generic 'all_providers_failed'.

Run via GitHub Actions workflow_dispatch (see
.github/workflows/diagnose-llm.yml) with the real secrets injected, since
API keys never leave GitHub Secrets into this sandbox otherwise.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_router import LLMRouter


def main():
    router = LLMRouter()
    system_prompt = "You are a helpful assistant."
    user_prompt = "Reply with exactly the word: OK"

    providers = [
        ("groq", "GROQ_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("kimi_openrouter", "OPENROUTER_API_KEY"),
        ("openrouter", "OPENROUTER_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
        ("moonshot_direct", "MOONSHOT_API_KEY"),
    ]

    print("=" * 60)
    print("LLM PROVIDER DIAGNOSTIC")
    print("=" * 60)

    for provider_name, key_env in providers:
        has_key = bool(os.environ.get(key_env, ""))
        print(f"\n--- {provider_name} (key env: {key_env}, configured: {has_key}) ---")
        if not has_key:
            print("  SKIPPED (no key set)")
            continue
        try:
            result = router.generate(system_prompt, user_prompt, order=[provider_name])
            if "text" in result:
                print(f"  SUCCESS: {result['text'][:200]!r}")
            else:
                print(f"  FAILED: {result}")
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
