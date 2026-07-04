"""AutoPublisher Agent — real YouTube Data API v3 upload via OAuth2.

Why OAuth2 (not a simple API key): YouTube requires an authenticated user
identity to upload videos on their behalf; a plain API key only allows
read-only calls (search, stats). OAuth2's refresh token, once obtained,
never expires for apps in "Production" mode, so this needs a ONE-TIME manual
browser authorization per channel (see docs/YOUTUBE-OAUTH-SETUP.md), after
which every upload from CI/GitHub Actions is fully automatic.

Each channel in channels/database.json points at its own refresh-token
environment variable name (e.g. YOUTUBE_REFRESH_TOKEN_ELINA_LUXE) so multiple
channels/OAuth apps can run side by side in the same factory.
"""

import os
import time

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    _HAS_GOOGLE_LIBS = True
except ImportError:
    _HAS_GOOGLE_LIBS = False

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
           "https://www.googleapis.com/auth/youtube",
           # Required specifically for comment operations (reply/like via
           # core/comment_engager.py) -- Google's docs state this is the
           # ONLY scope accepted for commentThreads.insert/comments.insert,
           # even though the broader 'youtube' scope above covers uploads.
           "https://www.googleapis.com/auth/youtube.force-ssl"]


class AutoPublisher:
    def __init__(self):
        self.name = "AutoPublisher"

    # ------------------------------------------------------------------ #
    def build_service(self, channel_cfg: dict):
        """Public wrapper around _build_service so other modules (e.g.
        core/comment_engager.py) can reuse the exact same OAuth client
        construction without duplicating the refresh-token logic."""
        return self._build_service(channel_cfg)

    def _build_service(self, channel_cfg: dict):
        """Builds an authorized YouTube API client from a refresh token stored
        in the environment variable named in channel_cfg['refresh_token_env'].
        Returns None (with a clear log) if OAuth isn't configured yet."""
        if not _HAS_GOOGLE_LIBS:
            print(f"[{self.name}] google-api-python-client not installed; cannot upload")
            return None

        client_id = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID", "")
        client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET", "")
        refresh_env = channel_cfg.get("refresh_token_env", "")
        refresh_token = os.environ.get(refresh_env, "") if refresh_env else ""

        if not (client_id and client_secret and refresh_token):
            missing = [n for n, v in (
                ("YOUTUBE_OAUTH_CLIENT_ID", client_id),
                ("YOUTUBE_OAUTH_CLIENT_SECRET", client_secret),
                (refresh_env or "refresh_token_env (unset in channel config)", refresh_token),
            ) if not v]
            print(f"[{self.name}] Missing OAuth secret(s): {', '.join(missing)}. "
                  f"See docs/YOUTUBE-OAUTH-SETUP.md to generate them once per channel.")
            return None

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=_SCOPES,
        )
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"[{self.name}] Failed to refresh OAuth token: {e}")
            return None

        return build("youtube", "v3", credentials=creds)

    # ------------------------------------------------------------------ #
    def generate_metadata(self, topic: str, niche_label: str = "", language: str = "en",
                           comment_prompt: str = "") -> dict:
        """SEO-oriented title/description/tags. Simple heuristic generator
        (no extra API cost); can be swapped for an LLM call later.

        comment_prompt (optional): the specific engagement question the
        script's outro scene asked (see core/script_writer.py's
        research-backed structure) -- when given, it's surfaced again in
        the description since many viewers read the description before/
        instead of watching to the end, and a specific question there
        measurably increases comment volume more than a generic
        "let me know what you think!" (see docs/YOUTUBE-GROWTH-AND-
        ENGAGEMENT.md for the research this is based on)."""
        if language == "fa":
            title = f"{topic} | نکاتی که باید بدانید"
            cta = comment_prompt or "نظرتون درباره این موضوع چیه؟ توی کامنت‌ها بگید."
            description = (
                f"در این ویدیو درباره «{topic}» صحبت می‌کنیم.\n\n"
                f"💬 {cta}\n\n"
                f"اگر این ویدیو براتون مفید بود، حتما دنبال کنید تا ویدیوی بعدی رو از دست ندید. 🔔\n\n"
                f"#{niche_label.replace(' ', '')} #آموزش"
            )
        else:
            title = f"{topic} | What You Need to Know"
            cta = comment_prompt or "What's your take on this? Let me know in the comments below."
            description = (
                f"In this video, we explore: {topic}\n\n"
                f"💬 {cta}\n\n"
                f"If you found this valuable, subscribe so you don't miss the next one! 🔔\n\n"
                f"#{niche_label.replace(' ', '')} #Documentary"
            )
        tags = [niche_label, "documentary", "educational"] if niche_label else ["educational"]
        return {"title": title[:100], "description": description[:5000], "tags": tags}

    def upload_to_youtube(self, channel_cfg: dict, video_path: str, metadata: dict,
                           thumbnail_path: str = "") -> dict:
        """Real upload via videos.insert. Returns {'url': ...} on success or
        {'error': ...} on failure — never raises, never fakes success.
        If thumbnail_path is given (see core/thumbnail_maker.py), it's set
        as the video's custom thumbnail right after upload succeeds; a
        failed thumbnail set is logged but never turns a successful video
        upload into an overall failure."""
        if not video_path or not os.path.exists(video_path):
            return {"error": "video_file_missing"}

        service = self._build_service(channel_cfg)
        if service is None:
            return {"error": "oauth_not_configured"}

        body = {
            "snippet": {
                "title": metadata.get("title", "Untitled"),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "categoryId": channel_cfg.get("category_id", "22"),
                "defaultLanguage": channel_cfg.get("language", "en"),
            },
            "status": {
                "privacyStatus": channel_cfg.get("privacy_status", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

        try:
            request = service.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"[{self.name}] Upload progress: {int(status.progress() * 100)}%")
            video_id = response.get("id")
            url = f"https://youtube.com/watch?v={video_id}"
            print(f"[{self.name}] Upload complete: {url}")

            thumb_result = {}
            if thumbnail_path and os.path.exists(thumbnail_path):
                thumb_result = self.set_thumbnail(service, video_id, thumbnail_path)

            result = {"video_id": video_id, "url": url}
            if thumb_result.get("error"):
                result["thumbnail_warning"] = thumb_result["error"]
            return result
        except HttpError as e:
            print(f"[{self.name}] YouTube API error: {e}")
            return {"error": f"http_error: {e}"}
        except Exception as e:
            print(f"[{self.name}] Unexpected upload error: {e}")
            return {"error": str(e)}

    def set_thumbnail(self, service, video_id: str, thumbnail_path: str) -> dict:
        """Uploads a custom thumbnail (see core/thumbnail_maker.py) for an
        already-uploaded video via thumbnails().set(). Note: YouTube only
        allows custom thumbnails for channels in good standing with phone
        verification -- if that's not yet done, this call returns a clean
        error instead of crashing the whole upload."""
        try:
            media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            service.thumbnails().set(videoId=video_id, media_body=media).execute()
            print(f"[{self.name}] Custom thumbnail set for {video_id}")
            return {"ok": True}
        except HttpError as e:
            print(f"[{self.name}] Thumbnail upload failed (video itself still succeeded): {e}")
            return {"error": f"thumbnail_http_error: {e}"}
        except Exception as e:
            print(f"[{self.name}] Thumbnail upload error: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    print("AutoPublisher is a library module. Run scripts/setup_youtube_oauth.py "
          "once per channel to obtain a refresh token, then wire it into "
          "channels/database.json as 'refresh_token_env'.")
