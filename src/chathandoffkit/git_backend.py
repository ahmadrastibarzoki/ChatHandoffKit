"""Git transport. GitHub works through a user-configured Git remote, not our API key."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .core import HandoffError, root_check

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root_check(root)), *args],
        text=True, capture_output=True, check=False, timeout=60,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        # Errors can contain remote URLs with embedded credentials. Don't echo them.
        raise HandoffError(f"Git command failed ({proc.returncode}): {' '.join(args[:2])}. Check git remote/auth/status. (Details withheld to avoid leaking remote credentials.)")
    return proc.stdout.strip()


def init_git(root: Path) -> str:
    root = root_check(root)
    git(root, "init", "-b", "main")
    return git(root, "branch", "--show-current")


def commit_paths(root: Path, files: list[str], message: str) -> str:
    """Stage only explicit managed files; no `git add .` and no push."""
    root = root_check(root)
    if not files:
        raise HandoffError("No files specified for commit")
    if not (root / ".git").exists():
        raise HandoffError("Not a Git repository. Run git init or chathandoff init --git.")
    # Refuse staged unrelated changes; they could otherwise sneak into this commit.
    staged = git(root, "diff", "--cached", "--name-only").splitlines()
    if staged:
        raise HandoffError("Git index already contains staged changes. Commit/unstage them first.")
    for f in files:
        path = Path(f)
        if path.is_absolute() or ".." in path.parts:
            raise HandoffError("Unsafe staged path")
    git(root, "add", "--", *files)
    if not git(root, "diff", "--cached", "--name-only"):
        return "NO_CHANGES"
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def sync_push(root: Path, remote: str = "origin", branch: str = "main", dry_run: bool = False) -> str:
    """Explicit push. Fetch and refuse divergence/non-fast-forward before push."""
    root = root_check(root)
    if not SAFE_NAME.fullmatch(remote) or not SAFE_NAME.fullmatch(branch):
        raise HandoffError("Invalid remote or branch")
    if git(root, "status", "--porcelain"):
        raise HandoffError("Uncommitted work exists. Commit or stash first.")
    remotes = git(root, "remote").splitlines()
    if remote not in remotes:
        raise HandoffError(f"Remote {remote!r} does not exist. Configure it yourself.")
    if git(root, "branch", "--show-current") != branch:
        raise HandoffError(f"Current branch is not {branch}")
    # The very first push to an empty remote does not have a remote branch.
    git(root, "fetch", remote)
    tracking = f"refs/remotes/{remote}/{branch}"
    exists = subprocess.run(["git", "-C", str(root), "show-ref", "--verify", "--quiet", tracking], check=False).returncode == 0
    if exists:
        is_ancestor = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", tracking, "HEAD"], check=False).returncode == 0
        if not is_ancestor:
            raise HandoffError("Remote contains newer/divergent commits. Fetch and reconcile manually; force push is disabled.")
    args = ("push", "--dry-run", remote, f"HEAD:refs/heads/{branch}") if dry_run else ("push", remote, f"HEAD:refs/heads/{branch}")
    git(root, *args)
    return "DRY_RUN_OK" if dry_run else git(root, "rev-parse", "HEAD")
