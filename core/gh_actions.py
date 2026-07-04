"""GitHubActions — lets the bot trigger a `workflow_dispatch` run of
run-factory.yml (e.g. "make me a test video for this channel right now")
instead of waiting for the daily cron.
"""

import os

import requests

_API = "https://api.github.com"


def _owner_repo_token():
    owner = os.environ.get("REPO_OWNER", "")
    repo = os.environ.get("REPO_NAME", "")
    if not (owner and repo):
        full = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in full:
            owner, repo = full.split("/", 1)
    token = os.environ.get("GH_PAT", "")
    return owner, repo, token


def trigger_run_factory(inputs: dict, workflow_file: str = "run-factory.yml", ref: str = "main") -> dict:
    """Fires a workflow_dispatch event. Returns {'ok': True} on HTTP 204
    (GitHub gives no run id synchronously) or {'ok': False, 'error': ...}."""
    owner, repo, token = _owner_repo_token()
    if not (owner and repo and token):
        return {"ok": False, "error": "missing_owner_repo_or_token"}
    try:
        r = requests.post(
            f"{_API}/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            json={"ref": ref, "inputs": inputs},
            timeout=20,
        )
        if r.status_code == 204:
            return {"ok": True}
        return {"ok": False, "error": f"http_{r.status_code}: {r.text[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
