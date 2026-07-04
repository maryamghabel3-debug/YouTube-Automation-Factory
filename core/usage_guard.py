"""UsageGuard — hard spending/usage limits for paid LLM providers (AvalAI,
GapGPT, DeepSeek direct, etc.), so a bug, an infinite retry loop, or simply
running too many test videos can never rack up an unexpected bill.

Why this exists: the user explicitly asked for this after noticing a
handful of manual test runs exhausted a free daily quota in seconds. Once a
REAL paid API key (AvalAI/GapGPT) gets configured, an accidental loop or a
larger-than-expected batch of videos could otherwise burn through a
monthly budget in one run with zero warning.

Design: a tiny JSON ledger (channels/usage_ledger.json, committed to git
like everything else in channels/) tracks estimated USD cost per calendar
day and per calendar month. Every LLM call THROUGH THE PAID PROVIDERS
(avalai/gapgpt/deepseek/moonshot_direct -- NOT the genuinely-free groq/
gemini/openrouter-free-tier calls) is estimated by token count *
per-provider price and added to the ledger BEFORE the request is sent.
If either limit would be exceeded, the call is refused with a clean error
(caller falls through to the next provider, eventually the offline
template) instead of ever being sent.

Limits are configurable via env vars so they can be tuned from GitHub
Secrets without a code change:
  LLM_DAILY_BUDGET_USD    default 0.50
  LLM_MONTHLY_BUDGET_USD  default 5.00
"""

import os
import json
import time
from datetime import datetime, timezone

_LEDGER_PATH = "channels/usage_ledger.json"

# Rough $/1K-token estimates for paid providers, used ONLY to pre-check
# against the budget before sending a request (not for final billing --
# each provider's own dashboard is the source of truth for actual spend).
# Conservative (slightly high) on purpose so the guard is never surprised
# by an underestimate.
_PRICE_PER_1K_TOKENS_USD = {
    "avalai": 0.01,      # varies hugely by model; this assumes a mid-tier model
    "gapgpt": 0.01,
    "deepseek": 0.0003,   # deepseek-chat is very cheap
    "moonshot_direct": 0.003,
}

_DEFAULT_DAILY_BUDGET = 0.50
_DEFAULT_MONTHLY_BUDGET = 5.00


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load_ledger() -> dict:
    if os.path.exists(_LEDGER_PATH):
        try:
            with open(_LEDGER_PATH) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_ledger(data: dict):
    os.makedirs(os.path.dirname(_LEDGER_PATH), exist_ok=True)
    with open(_LEDGER_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 characters per token (a standard rule of thumb
    for English; slightly conservative for other languages)."""
    return max(len(text) // 4, 1)


class UsageGuard:
    def __init__(self):
        self.daily_budget = float(os.environ.get("LLM_DAILY_BUDGET_USD", _DEFAULT_DAILY_BUDGET))
        self.monthly_budget = float(os.environ.get("LLM_MONTHLY_BUDGET_USD", _DEFAULT_MONTHLY_BUDGET))

    def _current_spend(self, ledger: dict) -> tuple:
        day = ledger.get("days", {}).get(_today_key(), 0.0)
        month = ledger.get("months", {}).get(_month_key(), 0.0)
        return day, month

    def check_and_reserve(self, provider: str, system_prompt: str, user_prompt: str,
                           expected_output_tokens: int = 1500) -> dict:
        """Call BEFORE sending a request to a paid provider. Returns
        {'allowed': True} and records the estimated cost, or
        {'allowed': False, 'reason': ...} if either budget would be
        exceeded -- caller must NOT send the request in that case."""
        price_per_1k = _PRICE_PER_1K_TOKENS_USD.get(provider)
        if price_per_1k is None:
            # Unknown/free provider (groq, gemini, openrouter free tier) --
            # not subject to a dollar budget, only their own rate limits.
            return {"allowed": True, "estimated_cost": 0.0}

        input_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
        total_tokens = input_tokens + expected_output_tokens
        estimated_cost = (total_tokens / 1000.0) * price_per_1k

        ledger = _load_ledger()
        day_spend, month_spend = self._current_spend(ledger)

        if day_spend + estimated_cost > self.daily_budget:
            return {
                "allowed": False,
                "reason": f"daily_budget_exceeded: ${day_spend:.4f} + ${estimated_cost:.4f} > ${self.daily_budget:.2f}",
            }
        if month_spend + estimated_cost > self.monthly_budget:
            return {
                "allowed": False,
                "reason": f"monthly_budget_exceeded: ${month_spend:.4f} + ${estimated_cost:.4f} > ${self.monthly_budget:.2f}",
            }

        # Reserve the estimated cost immediately (pessimistic accounting --
        # better to under-spend than to race past the budget across
        # concurrent/rapid calls).
        ledger.setdefault("days", {})
        ledger.setdefault("months", {})
        ledger["days"][_today_key()] = day_spend + estimated_cost
        ledger["months"][_month_key()] = month_spend + estimated_cost
        # Keep the ledger from growing forever -- retain last 60 days / 12 months
        ledger["days"] = dict(list(ledger["days"].items())[-60:])
        ledger["months"] = dict(list(ledger["months"].items())[-12:])
        _save_ledger(ledger)

        return {"allowed": True, "estimated_cost": estimated_cost}

    def status(self) -> dict:
        ledger = _load_ledger()
        day_spend, month_spend = self._current_spend(ledger)
        return {
            "today_spend_usd": round(day_spend, 4),
            "daily_budget_usd": self.daily_budget,
            "month_spend_usd": round(month_spend, 4),
            "monthly_budget_usd": self.monthly_budget,
            "day_remaining_usd": round(self.daily_budget - day_spend, 4),
            "month_remaining_usd": round(self.monthly_budget - month_spend, 4),
        }


if __name__ == "__main__":
    guard = UsageGuard()
    print(json.dumps(guard.status(), indent=2))
