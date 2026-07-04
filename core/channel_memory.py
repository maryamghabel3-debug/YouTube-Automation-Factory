"""ChannelMemory — persistent per-channel memory of every video the factory
has ever produced (topic, title, script summary, footage queries used,
performance once known). Answers the user's explicit request: "the system
should remember what video it made for each channel."

Why this matters beyond just record-keeping:
  1. Avoids repeating the same topic/title on a channel (checked by
     NicheAnalyzer before finalizing a topic).
  2. Avoids reusing the exact same stock-footage query too often in a row
     (keeps visual variety across consecutive uploads).
  3. Feeds ScriptWriter a short "don't repeat these angles" note so a
     channel doesn't publish near-duplicate videos over time.
  4. Gives PerformanceAnalyzer a durable place to store which topics
     actually performed well once real view/like data comes in --
     something a fire-and-forget CI run alone could never accumulate.

Storage: channels/channel_memory.json, committed to git like the rest of
channels/, keyed by channel_id -> list of video records (newest last).
"""

import os
import json
from datetime import datetime, timezone

_MEMORY_PATH = "channels/channel_memory.json"
_MAX_RECORDS_PER_CHANNEL = 200  # keep the file from growing unbounded forever


def _load() -> dict:
    if os.path.exists(_MEMORY_PATH):
        try:
            with open(_MEMORY_PATH) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(_MEMORY_PATH), exist_ok=True)
    with open(_MEMORY_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_video(channel_id: str, topic: str, title: str, video_path: str,
                  footage_queries: list, script_engine: str, video_id: str = "",
                  video_url: str = "") -> None:
    """Called by main.py right after a video is built (and again after
    upload, if you want to backfill video_id/video_url -- pass the same
    topic to update the matching record instead of duplicating it)."""
    data = _load()
    records = data.setdefault(channel_id, [])

    # If this exact topic was just recorded (e.g. upload happened right
    # after build in the same run), update it in place instead of
    # duplicating -- keeps the "recent topics" list meaningful.
    for rec in reversed(records):
        if rec["topic"] == topic and not rec.get("video_id") and video_id:
            rec["video_id"] = video_id
            rec["video_url"] = video_url
            _save(data)
            return

    records.append({
        "topic": topic,
        "title": title,
        "video_path": video_path,
        "footage_queries": footage_queries,
        "script_engine": script_engine,
        "video_id": video_id,
        "video_url": video_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    data[channel_id] = records[-_MAX_RECORDS_PER_CHANNEL:]
    _save(data)


def recent_topics(channel_id: str, limit: int = 20) -> list:
    """Returns the most recent topic strings for a channel -- used by
    NicheAnalyzer to avoid picking a topic that was already covered."""
    data = _load()
    records = data.get(channel_id, [])
    return [r["topic"] for r in records[-limit:]]


def recent_footage_queries(channel_id: str, limit: int = 10) -> list:
    """Flat list of recently-used footage search queries -- used to nudge
    variety in stock footage selection across consecutive videos."""
    data = _load()
    records = data.get(channel_id, [])
    queries = []
    for r in records[-limit:]:
        queries.extend(r.get("footage_queries", []))
    return queries


def channel_history(channel_id: str) -> list:
    """Full history for a channel -- used by /history in the Telegram bot."""
    return _load().get(channel_id, [])


def summary_for_prompt(channel_id: str, limit: int = 8) -> str:
    """Short natural-language summary of recent topics, meant to be
    injected into ScriptWriter's prompt so it can explicitly avoid
    repeating the same angle twice in a row."""
    topics = recent_topics(channel_id, limit=limit)
    if not topics:
        return ""
    bullet_list = "\n".join(f"- {t}" for t in topics)
    return (
        f"This channel has RECENTLY covered these topics -- do not repeat "
        f"any of them or produce a near-duplicate angle:\n{bullet_list}"
    )


if __name__ == "__main__":
    print(json.dumps(_load(), indent=2, ensure_ascii=False))
