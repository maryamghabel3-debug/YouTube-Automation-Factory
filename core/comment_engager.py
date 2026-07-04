"""CommentEngager — automatic, AI-generated replies to viewer comments.

Why this matters (see docs/YOUTUBE-GROWTH-AND-ENGAGEMENT.md for the full
research writeup the user asked for): comments are the single
highest-weighted engagement signal in YouTube's 2026 ranking algorithm, and
replying to comments in the first 1-2 hours after posting measurably lifts
early reach. A fully-automated, no-human channel can't realistically
monitor comments manually, so this module:

  1. Pulls new top-level comments on a channel's recent videos via
     commentThreads().list (read-only, works with a plain OAuth service).
  2. Generates a short, specific, on-brand reply for each NEW comment
     using core/llm_router.py (never a generic "thanks!" -- explicitly
     instructed to reference something specific from the comment).
  3. Posts the reply via comments().insert().
  4. Tracks which comment IDs have already been replied to (a small JSON
     ledger, channels/replied_comments.json) so the same comment is never
     replied to twice across separate runs.

IMPORTANT LIMITATION (confirmed via research, not assumed): the YouTube
Data API v3 has NO endpoint to "pin" a comment -- commentThreads.insert/
comments.insert can only POST a new top-level comment or reply, never set
the pinned flag. Pinning is a UI-only action. This module therefore does
NOT attempt to pin anything; instead, the factory's own pinned-comment-style
CTA (asking a specific question) is baked directly into the video's
description (see AutoPublisher.generate_metadata) and into the script's
outro, which achieves the same practical goal (surfacing a specific
question to answer) without needing an unsupported API call.
"""

import os
import json

try:
    from googleapiclient.errors import HttpError
    _HAS_GOOGLE_LIBS = True
except ImportError:
    _HAS_GOOGLE_LIBS = False

from .llm_router import LLMRouter

_REPLIED_LEDGER_PATH = "channels/replied_comments.json"


def _load_replied() -> dict:
    if os.path.exists(_REPLIED_LEDGER_PATH):
        try:
            with open(_REPLIED_LEDGER_PATH) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_replied(data: dict):
    os.makedirs(os.path.dirname(_REPLIED_LEDGER_PATH), exist_ok=True)
    # Keep the ledger bounded -- only need enough history to avoid double-replying
    trimmed = {vid: ids[-300:] for vid, ids in data.items()}
    with open(_REPLIED_LEDGER_PATH, "w") as f:
        json.dump(trimmed, f, indent=2, ensure_ascii=False)


class CommentEngager:
    def __init__(self):
        self.name = "CommentEngager"
        self.router = LLMRouter()

    def _generate_reply(self, comment_text: str, video_topic: str, language: str) -> str:
        lang_name = "Persian (Farsi)" if language == "fa" else "English"
        system_prompt = (
            "You reply to YouTube comments as the friendly, knowledgeable voice behind a "
            "documentary-style channel. Replies are SHORT (1-2 sentences), reference "
            "something SPECIFIC from the comment (never generic 'thanks for watching!'), "
            "and where natural, end with a light follow-up question to keep the "
            "conversation going (this drives more replies, which the algorithm rewards)."
        )
        user_prompt = (
            f"Video topic: \"{video_topic}\"\n"
            f"Viewer comment: \"{comment_text}\"\n\n"
            f"Write a short reply in {lang_name}."
        )
        result = self.router.generate(system_prompt, user_prompt)
        if "text" in result:
            return result["text"].strip()[:500]
        return ""

    def reply_to_new_comments(self, service, video_id: str, video_topic: str,
                               language: str = "en", max_replies: int = 10) -> dict:
        """Fetches recent top-level comments on video_id, replies to any not
        already answered (tracked in channels/replied_comments.json), and
        returns {'replied': [...comment_ids...], 'error': ... if applicable}.
        Never raises -- a single comment failure is skipped, not fatal."""
        if not _HAS_GOOGLE_LIBS or service is None:
            return {"error": "oauth_not_configured", "replied": []}

        replied_ledger = _load_replied()
        already_replied = set(replied_ledger.get(video_id, []))

        try:
            resp = service.commentThreads().list(
                part="snippet", videoId=video_id, order="time", maxResults=max_replies,
            ).execute()
        except HttpError as e:
            print(f"[{self.name}] Could not fetch comments for {video_id} (often just disabled comments): {e}")
            return {"error": f"http_error: {e}", "replied": []}
        except Exception as e:
            print(f"[{self.name}] Unexpected comment-fetch error: {e}")
            return {"error": str(e), "replied": []}

        newly_replied = []
        for item in resp.get("items", []):
            comment_id = item["id"]
            if comment_id in already_replied:
                continue
            top_comment = item["snippet"]["topLevelComment"]["snippet"]
            comment_text = top_comment.get("textDisplay", "")
            if not comment_text:
                continue

            reply_text = self._generate_reply(comment_text, video_topic, language)
            if not reply_text:
                continue  # no LLM provider available right now -- try again next run

            try:
                service.comments().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "parentId": comment_id,
                            "textOriginal": reply_text,
                        }
                    },
                ).execute()
                newly_replied.append(comment_id)
                print(f"[{self.name}] Replied to comment {comment_id} on {video_id}")
            except HttpError as e:
                print(f"[{self.name}] Failed to reply to comment {comment_id}: {e}")
            except Exception as e:
                print(f"[{self.name}] Unexpected reply error for {comment_id}: {e}")

        if newly_replied:
            replied_ledger[video_id] = list(already_replied | set(newly_replied))
            _save_replied(replied_ledger)

        return {"replied": newly_replied}


if __name__ == "__main__":
    print("CommentEngager is a library module -- called automatically from "
          "main.py after upload, and periodically for recent videos via the "
          "Telegram bot's /engage command.")
