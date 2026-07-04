#!/usr/bin/env python3
"""Periodic comment-engagement sweep across every channel's recent uploads.

Why this exists separately from main.py's immediate post-upload reply:
comments keep arriving for days after a video goes live, and replying
promptly (even if not within the first hour) still measurably helps the
algorithm's satisfaction signal and builds real community. This script is
meant to run on its own schedule (see
.github/workflows/engage-comments.yml, e.g. every few hours) and sweeps the
last N videos logged in each channel's core/channel_memory.py history.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.channel_spawner import ChannelSpawner
from core.auto_publisher import AutoPublisher
from core.comment_engager import CommentEngager
from core import channel_memory


def main():
    channels = ChannelSpawner().list_channels()
    if not channels:
        print("No channels registered -- nothing to engage with.")
        return

    publisher = AutoPublisher()
    engager = CommentEngager()
    videos_per_channel = int(os.environ.get("ENGAGE_RECENT_VIDEOS", "5"))

    for ch in channels:
        if not ch.get("active", True):
            continue

        service = publisher.build_service(ch)
        if service is None:
            print(f"[{ch['name']}] OAuth not configured -- skipping comment engagement.")
            continue

        history = channel_memory.channel_history(ch["id"])
        recent_with_video_id = [h for h in reversed(history) if h.get("video_id")][:videos_per_channel]

        if not recent_with_video_id:
            print(f"[{ch['name']}] No uploaded videos in memory yet.")
            continue

        for record in recent_with_video_id:
            result = engager.reply_to_new_comments(
                service, record["video_id"], record["topic"], ch["language"]
            )
            if result.get("replied"):
                print(f"[{ch['name']}] Replied to {len(result['replied'])} comment(s) "
                      f"on {record['video_id']} ({record['topic'][:50]})")
            elif result.get("error"):
                print(f"[{ch['name']}] {record['video_id']}: {result['error']}")


if __name__ == "__main__":
    main()
