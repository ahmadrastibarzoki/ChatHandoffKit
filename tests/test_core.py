from datetime import datetime, timezone
from pathlib import Path
import pytest

from chathandoffkit.core import (
    HandoffError, checkpoint, create_project, digest, init_workspace,
    list_projects, resume_project, validate_workspace,
)


def setup(tmp_path):
    init_workspace(tmp_path)
    create_project(tmp_path, "demo-app", "Demo App", "Build a fictional task app")


def test_initialize_create_and_validate(tmp_path):
    setup(tmp_path)
    assert list_projects(tmp_path) == ["demo-app"]
    assert validate_workspace(tmp_path) == []
    with pytest.raises(HandoffError, match="already exists"):
        create_project(tmp_path, "demo-app", "Again", "Duplicated")
    with pytest.raises(HandoffError):
        create_project(tmp_path, "../../escape", "Invalid", "Not safe")


def test_checkpoint_history_and_resume(tmp_path):
    setup(tmp_path)
    current = tmp_path / "projects/demo-app/CURRENT_STATE.md"
    current.write_text(current.read_text() + "\n## Manual annotation\nKeep this paragraph!\n")
    old = current.read_text()
    cp = checkpoint(tmp_path, "demo-app", "API prototype validated", "Write tests",
                    decision="Use SQLite for synthetic demo",
                    expected_sha256=digest(old),
                    now=datetime(2026, 10, 8, tzinfo=timezone.utc))
    assert len(cp.changed_files) == 3
    assert "Keep this paragraph!" in current.read_text()
    assert "API prototype validated" in current.read_text()
    assert "SQLite" in (tmp_path / "projects/demo-app/DECISIONS.md").read_text()
    checkpoint(tmp_path, "demo-app", "Tests passed", "Prepare README")
    out = resume_project(tmp_path, "demo-app")
    assert "Tests passed" in out and "API prototype validated" in out
    assert validate_workspace(tmp_path) == []


def test_concurrent_write_refused(tmp_path):
    setup(tmp_path)
    old = (tmp_path / "projects/demo-app/CURRENT_STATE.md").read_text()
    checkpoint(tmp_path, "demo-app", "a", "b")
    with pytest.raises(HandoffError, match="Concurrent"):
        checkpoint(tmp_path, "demo-app", "c", "d", expected_sha256=digest(old))


def test_dry_run_has_no_side_effects(tmp_path):
    setup(tmp_path)
    f = tmp_path / "projects/demo-app/CURRENT_STATE.md"
    old = f.read_text()
    checkpoint(tmp_path, "demo-app", "a", "b", dry_run=True)
    assert f.read_text() == old


def test_secrets_refused(tmp_path):
    setup(tmp_path)
    with pytest.raises(HandoffError, match="Potential secret"):
        checkpoint(tmp_path, "demo-app", "key ghp_" + "x" * 30, "redact")
    f = tmp_path / "projects/demo-app/PROMPTS.md"
    f.write_text("-----BEGIN PRIVATE KEY-----\nunsafe\n")
    assert any("Potential secret" in v for v in validate_workspace(tmp_path))


def test_missing_marker_prevents_overwrite(tmp_path):
    setup(tmp_path)
    f = tmp_path / "projects/demo-app/CURRENT_STATE.md"
    f.write_text("# Manual state\n")
    with pytest.raises(HandoffError, match="managed state markers"):
        checkpoint(tmp_path, "demo-app", "a", "b")
    assert f.read_text() == "# Manual state\n"


def test_symlinked_project_blocked(tmp_path):
    init_workspace(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "projects/evil").symlink_to(outside, target_is_directory=True)
    with pytest.raises(HandoffError, match="symlink"):
        create_project(tmp_path, "evil", "Bad", "Never")
