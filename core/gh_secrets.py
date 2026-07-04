"""GitHubSecrets — lets the factory itself write GitHub Actions repo secrets
(e.g. a freshly-obtained YouTube refresh token) via the REST API, using
libsodium/PyNaCl sealed-box encryption as required by GitHub.

Why this exists: the whole point of the Telegram bot ("chat with the
project") is that the user should NEVER have to open GitHub's website to
paste a secret by hand when adding a new channel. This module is what makes
that possible — the bot obtains a refresh token via the OAuth device flow
(see oauth_device.py) and immediately calls set_secret() to store it.

Needs a GitHub Personal Access Token with the 'repo' scope stored as GH_PAT
(classic PAT; fine-grained tokens need 'Secrets' repository permission).
"""

import base64
import os

import requests

try:
    from nacl import encoding, public
    _HAS_NACL = True
except ImportError:
    _HAS_NACL = False

_API = "https://api.github.com"


def _default_owner_repo():
    """Falls back to parsing GITHUB_REPOSITORY (auto-set by GitHub Actions,
    e.g. 'maryamghabel3-debug/YouTube-Automation-Factory') if REPO_OWNER/
    REPO_NAME secrets weren't explicitly provided — one less secret to
    configure per repo."""
    owner = os.environ.get("REPO_OWNER", "")
    repo = os.environ.get("REPO_NAME", "")
    if not (owner and repo):
        full = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in full:
            owner, repo = full.split("/", 1)
    return owner, repo


class GitHubSecrets:
    def __init__(self, owner: str = None, repo: str = None, token: str = None):
        default_owner, default_repo = _default_owner_repo()
        self.owner = owner or default_owner
        self.repo = repo or default_repo
        self.token = token or os.environ.get("GH_PAT", "")

    def _headers(self):
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def _get_public_key(self) -> dict:
        r = requests.get(
            f"{_API}/repos/{self.owner}/{self.repo}/actions/secrets/public-key",
            headers=self._headers(), timeout=20,
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _encrypt(public_key_b64: str, secret_value: str) -> str:
        pub = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
        box = public.SealedBox(pub)
        encrypted = box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def set_secret(self, name: str, value: str) -> dict:
        """Creates or updates a repo secret. Returns {'ok': True} or
        {'ok': False, 'error': ...} — never raises."""
        if not _HAS_NACL:
            return {"ok": False, "error": "pynacl_not_installed"}
        if not (self.owner and self.repo and self.token):
            return {"ok": False, "error": "missing_owner_repo_or_token"}
        try:
            pk = self._get_public_key()
            enc_value = self._encrypt(pk["key"], value)
            r = requests.put(
                f"{_API}/repos/{self.owner}/{self.repo}/actions/secrets/{name}",
                headers=self._headers(),
                json={"encrypted_value": enc_value, "key_id": pk["key_id"]},
                timeout=20,
            )
            if r.status_code in (201, 204):
                return {"ok": True}
            return {"ok": False, "error": f"http_{r.status_code}: {r.text[:300]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_secrets(self) -> list:
        try:
            r = requests.get(
                f"{_API}/repos/{self.owner}/{self.repo}/actions/secrets",
                headers=self._headers(), timeout=20,
            )
            r.raise_for_status()
            return [s["name"] for s in r.json().get("secrets", [])]
        except Exception:
            return []
