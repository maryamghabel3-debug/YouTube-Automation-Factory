#!/usr/bin/env python3
"""Master Controller (The CEO) — real pipeline, no mocks.

Loops through every active channel in channels/database.json, finds a real
trending topic, builds a real narrated+subtitled video from free stock
footage, and uploads it to the real YouTube channel via OAuth2.

Set SKIP_UPLOAD=1 to build videos without uploading (useful for testing).
Set TARGET_MINUTES to control how long each video's narration should be.
"""

import os
import json
import sys

from core.niche_analyzer import NicheAnalyzer
from core.video_factory import VideoFactory
from core.auto_publisher import AutoPublisher
from core.performance_analyzer import PerformanceAnalyzer

_DB_PATH = "channels/database.json"


def load_channels() -> list:
    if not os.path.exists(_DB_PATH):
        print(f"❌ {_DB_PATH} not found. Run core/channel_spawner.py first to register a channel.")
        return []
    with open(_DB_PATH) as f:
        return json.load(f).get("channels", [])


def run_factory():
    print("=" * 60)
    print("🏭 YOUTUBE AUTOMATION FACTORY — REAL PIPELINE 🏭")
    print("=" * 60)

    channels = load_channels()
    if not channels:
        print("⚠️  No channels registered. Nothing to do.")
        return

    skip_upload = os.environ.get("SKIP_UPLOAD") == "1"
    target_minutes = int(os.environ.get("TARGET_MINUTES", "8"))

    analyzer = NicheAnalyzer()
    factory = VideoFactory()
    publisher = AutoPublisher()
    perf = PerformanceAnalyzer()

    for ch in channels:
        if not ch.get("active", True):
            print(f"\n⏸️  Skipping inactive channel: {ch['name']}")
            continue

        print(f"\n📺 Processing Channel: {ch['name']} (niche: {ch['niche_key']}, lang: {ch['language']})")
        print("-" * 50)

        topic = analyzer.analyze_market(ch["niche_key"])
        video_result = factory.build_video(topic, ch, target_minutes=target_minutes)

        if video_result.get("error"):
            print(f"❌ Video build failed for {ch['name']}: {video_result['error']}")
            continue

        print(f"✅ Video built: {video_result['video_path']} "
              f"({video_result['duration']:.1f}s, {video_result['scenes_rendered']} scenes)")

        if skip_upload:
            print("⏭️  SKIP_UPLOAD=1 set — not uploading.")
            continue

        metadata = publisher.generate_metadata(topic, ch.get("niche_label", ""), ch["language"])
        upload_result = publisher.upload_to_youtube(ch, video_result["video_path"], metadata)

        if upload_result.get("error"):
            print(f"⚠️  Upload skipped/failed for {ch['name']}: {upload_result['error']}")
            continue

        perf.log_upload(ch["id"], topic, upload_result["video_id"], upload_result["url"])
        print(f"🎉 Channel {ch['name']} updated successfully! {upload_result['url']}")


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    run_factory()
