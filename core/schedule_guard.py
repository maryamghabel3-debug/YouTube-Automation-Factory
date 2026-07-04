"""ScheduleGuard — makes each channel's `upload_frequency` field
(daily/weekly/biweekly/monthly) actually mean something.

BUG FIXED (found during a monthly-cost review, 2026-07-04): channel
registration (channel_spawner.py) has accepted an `upload_frequency` field
since the very first version, but main.py's daily cron NEVER checked it --
every active channel got a brand-new video (full script + narration +
footage + thumbnail + 2-3 Shorts) EVERY SINGLE DAY regardless of what
upload_frequency said, silently multiplying both LLM token usage and
render time far beyond what the user intended when registering a channel
as "weekly".

This module tracks the last successful run timestamp per channel (in
channels/schedule_state.json, committed to git like the rest of channels/)
and answers a single question: is this channel due for a new video today?
"""

import os
import json
from datetime import datetime, timezone

_STATE_PATH = "channels/schedule_state.json"

# Minimum days between runs for each frequency value a channel can be
# registered with (see core/channel_spawner.py's upload_frequency param).
_FREQUENCY_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
}


def _load_state() -> dict:
    if os.path.exists(_STATE_PATH):
        try:
            with open(_STATE_PATH) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_state(data: dict):
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_due(channel_id: str, upload_frequency: str) -> bool:
    """True if this channel has never run, or enough days have passed
    since its last successful run for its configured frequency. Unknown
    frequency values default to 'weekly' (the channel_spawner.py default)
    rather than crashing or always/never running."""
    state = _load_state()
    last_run_iso = state.get(channel_id, {}).get("last_run")
    if not last_run_iso:
        return True

    min_days = _FREQUENCY_DAYS.get(upload_frequency, _FREQUENCY_DAYS["weekly"])
    try:
        last_run = datetime.fromisoformat(last_run_iso)
    except ValueError:
        return True

    elapsed_days = (datetime.now(timezone.utc) - last_run).total_seconds() / 86400
    return elapsed_days >= min_days


def mark_run(channel_id: str):
    """Call after a channel's video build (successful or not -- even a
    failed attempt used real API/LLM calls, so it still counts against the
    schedule to avoid hammering a broken channel daily)."""
    state = _load_state()
    state[channel_id] = {"last_run": datetime.now(timezone.utc).isoformat()}
    _save_state(state)


def days_until_due(channel_id: str, upload_frequency: str) -> float:
    """For /status-style reporting: how many days remain until this
    channel is next due (0 or negative if already due)."""
    state = _load_state()
    last_run_iso = state.get(channel_id, {}).get("last_run")
    if not last_run_iso:
        return 0.0
    min_days = _FREQUENCY_DAYS.get(upload_frequency, _FREQUENCY_DAYS["weekly"])
    try:
        last_run = datetime.fromisoformat(last_run_iso)
    except ValueError:
        return 0.0
    elapsed_days = (datetime.now(timezone.utc) - last_run).total_seconds() / 86400
    return round(min_days - elapsed_days, 2)


if __name__ == "__main__":
    print(json.dumps(_load_state(), indent=2, ensure_ascii=False))
