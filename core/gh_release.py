"""GitHubRelease — publishes a rendered video as a downloadable GitHub
Release asset. Used as the delivery channel when a video is too big for
Telegram's ~50MB bot upload limit (or as an explicit "give me a link"
option). No storage cost, no third-party host, and it keeps a permanent
public archive of everything the factory has ever produced.
"""

import os
import time

import requests

_API = "https://api.github.com"
_UPLOADS = "https://uploads.github.com"


class GitHubRelease:
    def __init__(self, owner: str = None, repo: str = None, token: str = None):
        self.owner = owner or os.environ.get("REPO_OWNER", "")
        self.repo = repo or os.environ.get("REPO_NAME", "")
        self.token = token or os.environ.get("GH_PAT", "")

    def _headers(self):
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def publish_video(self, video_path: str, title: str, body: str = "") -> dict:
        """Creates a new (uniquely-tagged) release and uploads video_path as
        its only asset. Returns {'ok': True, 'url': <asset browser_download_url>,
        'release_url': <html release page>} or {'ok': False, 'error': ...}."""
        if not (self.owner and self.repo and self.token):
            return {"ok": False, "error": "missing_owner_repo_or_token"}
        if not os.path.exists(video_path):
            return {"ok": False, "error": "video_file_missing"}

        tag = f"video-{int(time.time())}"
        try:
            r = requests.post(
                f"{_API}/repos/{self.owner}/{self.repo}/releases",
                headers=self._headers(),
                json={
                    "tag_name": tag,
                    "name": title[:200] or tag,
                    "body": body[:5000],
                    "draft": False,
                    "prerelease": False,
                },
                timeout=30,
            )
            if r.status_code != 201:
                return {"ok": False, "error": f"create_release_http_{r.status_code}: {r.text[:300]}"}
            release = r.json()
            release_id = release["id"]

            filename = os.path.basename(video_path)
            with open(video_path, "rb") as f:
                data = f.read()
            r2 = requests.post(
                f"{_UPLOADS}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets",
                headers={**self._headers(), "Content-Type": "video/mp4"},
                params={"name": filename},
                data=data,
                timeout=300,
            )
            if r2.status_code != 201:
                return {"ok": False, "error": f"upload_asset_http_{r2.status_code}: {r2.text[:300]}"}
            asset = r2.json()
            return {
                "ok": True,
                "url": asset.get("browser_download_url", ""),
                "release_url": release.get("html_url", ""),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
