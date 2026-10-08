import subprocess

import pytest

from chathandoffkit.core import HandoffError, checkpoint, create_project, init_workspace
from chathandoffkit.git_backend import commit_paths, init_git, sync_push


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def setup_git(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    init_workspace(root)
    init_git(root)
    run("git", "-C", str(root), "config", "user.email", "demo@example.invalid")
    run("git", "-C", str(root), "config", "user.name", "Demo Tester")
    create_project(root, "demo", "Demo", "Only fictional content")
    paths = ["START_HERE.md", "PROJECTS_INDEX.md", "OPERATING_RULES.md"]
    paths += ["projects/demo/" + n for n in ("START_HERE.md", "PROJECT_CONTEXT.md", "CURRENT_STATE.md", "DECISIONS.md", "PROMPTS.md", "ERRORS_AND_SOLUTIONS.md", "SESSION_LOG.md")]
    commit_paths(root, paths, "initial")
    return root


def test_commit_only_changed_paths(tmp_path):
    root = setup_git(tmp_path)
    (root / "private-not-staged.txt").write_text("Do not commit")
    cp = checkpoint(root, "demo", "Step complete", "Continue")
    sha = commit_paths(root, list(cp.changed_files), "checkpoint")
    assert len(sha) == 40
    committed = run("git", "-C", str(root), "show", "--pretty=format:", "--name-only", "HEAD")
    assert "private-not-staged" not in committed
    assert "CURRENT_STATE.md" in committed


def test_pre_staged_foreign_changes_refused(tmp_path):
    root = setup_git(tmp_path)
    (root / "other.txt").write_text("unrelated")
    run("git", "-C", str(root), "add", "other.txt")
    cp = checkpoint(root, "demo", "ready", "test")
    with pytest.raises(HandoffError, match="already contains staged changes"):
        commit_paths(root, list(cp.changed_files), "oops")


def test_push_to_empty_bare_and_reject_divergence(tmp_path):
    root = setup_git(tmp_path)
    bare = tmp_path / "remote.git"
    run("git", "init", "--bare", str(bare))
    run("git", "-C", str(root), "remote", "add", "origin", str(bare))
    assert len(sync_push(root)) == 40
    assert run("git", "--git-dir", str(bare), "rev-parse", "refs/heads/main") == run("git", "-C", str(root), "rev-parse", "HEAD")
    cp = checkpoint(root, "demo", "new", "next")
    commit_paths(root, list(cp.changed_files), "new checkpoint")
    assert sync_push(root, dry_run=True) == "DRY_RUN_OK"
    assert len(sync_push(root)) == 40
    # Parallel clone creates a remote commit that our local tree has not fetched.
    other = tmp_path / "other"
    run("git", "clone", "-b", "main", str(bare), str(other))
    run("git", "-C", str(other), "config", "user.email", "other@example.invalid")
    run("git", "-C", str(other), "config", "user.name", "Other Tester")
    (other / "new.txt").write_text("concurrent")
    run("git", "-C", str(other), "add", "new.txt")
    run("git", "-C", str(other), "commit", "-m", "remote change")
    run("git", "-C", str(other), "push", "origin", "main")
    cp = checkpoint(root, "demo", "conflicting", "reconcile")
    commit_paths(root, list(cp.changed_files), "local change")
    with pytest.raises(HandoffError, match="Remote contains newer"):
        sync_push(root)
