"""WorkflowEditor — lets the factory bot wire a brand-new per-channel GitHub
Secret (e.g. YOUTUBE_REFRESH_TOKEN_LUXURY_EN) into the Actions workflow YAML
files automatically.

Why this is needed: GitHub Actions does NOT support wildcard/dynamic secret
injection — every ${{ secrets.NAME }} reference must be spelled out literally
in the workflow file. So when a brand-new channel gets a brand-new refresh
token, something has to add a new explicit line to the workflow's `env:`
block, or the token would sit in GitHub Secrets unused forever. This module
does that edit (regex/text based, not a full YAML parser, to preserve
formatting/comments exactly) so a new channel really can be added start-to-
finish from a Telegram chat with zero manual github.com clicking.
"""

import re

_ANCHOR_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)YOUTUBE_OAUTH_CLIENT_SECRET:.*$", re.MULTILINE
)


def ensure_secret_in_workflow(workflow_path: str, secret_name: str) -> bool:
    """Idempotently inserts `SECRET_NAME: ${{ secrets.SECRET_NAME }}` right
    after the YOUTUBE_OAUTH_CLIENT_SECRET line (or after the last existing
    YOUTUBE_REFRESH_TOKEN_* line, whichever comes later) in workflow_path.
    Returns True if a change was made, False if it was already present or
    the anchor couldn't be found."""
    with open(workflow_path, "r", encoding="utf-8") as f:
        text = f.read()

    if f"secrets.{secret_name}" in text:
        return False  # already wired, nothing to do

    # Find every existing per-channel refresh-token line so we insert after
    # the LAST one (keeps them grouped together and in a sane order).
    token_line_pattern = re.compile(
        r"^(?P<indent>[ \t]*)YOUTUBE_REFRESH_TOKEN_\w+:.*$", re.MULTILINE
    )
    matches = list(token_line_pattern.finditer(text))

    if matches:
        last = matches[-1]
        indent = last.group("indent")
        insert_pos = last.end()
        new_line = f"\n{indent}{secret_name}: ${{{{ secrets.{secret_name} }}}}"
        text = text[:insert_pos] + new_line + text[insert_pos:]
    else:
        anchor = _ANCHOR_PATTERN.search(text)
        if not anchor:
            return False
        indent = anchor.group("indent")
        insert_pos = anchor.end()
        new_line = f"\n{indent}{secret_name}: ${{{{ secrets.{secret_name} }}}}"
        text = text[:insert_pos] + new_line + text[insert_pos:]

    with open(workflow_path, "w", encoding="utf-8") as f:
        f.write(text)
    return True
