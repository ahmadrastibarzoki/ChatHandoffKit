"""Offline tests against a deterministic fake Google Drive v3 service."""
from __future__ import annotations

import io
import sys
import types
from pathlib import Path

import pytest

from chathandoffkit.core import HandoffError, checkpoint, create_project, init_workspace
from chathandoffkit.drive_backend import DriveStore, connect, connection, init_remote, transfer


class Request:
    def __init__(self, thunk):
        self.thunk = thunk

    def execute(self):
        return self.thunk()


class FakeFiles:
    def __init__(self):
        self.data = {}
        self.counter = 1
        self.calls = []

    def create(self, body=None, fields=None, media_body=None):
        def run():
            key = f"fid{self.counter}"
            self.counter += 1
            self.data[key] = {
                "id": key, "name": body["name"],
                "mimeType": body["mimeType"], "parents": body.get("parents", []),
                "content": media_body.stream.getvalue() if media_body else None,
            }
            self.calls.append("create:" + body["name"])
            return {"id": key}
        return Request(run)

    def update(self, fileId, media_body, fields=None):
        def run():
            self.data[fileId]["content"] = media_body.stream.getvalue()
            self.calls.append("update:" + self.data[fileId]["name"])
            return {"id": fileId}
        return Request(run)

    def list(self, q, fields, pageSize, pageToken=None):
        import re
        parent = re.match(r"'([^']+)' in parents", q)[1]
        return Request(lambda: {"files": [
            {"id": x["id"], "name": x["name"], "mimeType": x["mimeType"]}
            for x in self.data.values() if parent in x["parents"]
        ]})

    def get_media(self, fileId):
        return Request(lambda: self.data[fileId]["content"])


class FakeService:
    def __init__(self):
        self.files_api = FakeFiles()

    def files(self):
        return self.files_api


@pytest.fixture
def provider(monkeypatch):
    mod = types.ModuleType("googleapiclient")
    http = types.ModuleType("googleapiclient.http")

    class MediaIoBaseUpload:
        def __init__(self, stream, mimetype, resumable):
            assert mimetype == "text/markdown"
            self.stream = stream

    http.MediaIoBaseUpload = MediaIoBaseUpload
    monkeypatch.setitem(sys.modules, "googleapiclient", mod)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", http)
    service = FakeService()
    return service, DriveStore(service)


def project(tmp_path):
    root = tmp_path / "memory"
    init_workspace(root)
    create_project(root, "demo", "Demo", "A safe synthetic test")
    return root


def test_end_to_end_push_pull_and_update(tmp_path, provider):
    service, store = provider
    root = project(tmp_path)
    folder_id = init_remote(root, store)
    assert connection(root)["folder_id"] == folder_id
    dry = transfer(root, store, "push", dry_run=True)
    assert len(dry.changed) == 10
    assert transfer(root, store, "push").changed == dry.changed
    assert not transfer(root, store, "push").changed
    checkpoint(root, "demo", "An API was validated", "Write user documentation")
    assert "projects/demo/CURRENT_STATE.md" in transfer(root, store, "push").changed
    new = tmp_path / "another-device"
    new.mkdir()
    connect(new, folder_id)
    restored = transfer(new, store, "pull")
    assert len(restored.changed) == 10
    assert (new / "projects/demo/CURRENT_STATE.md").read_text().find("An API was validated") > -1
    assert not transfer(new, store, "pull").changed
    assert len(service.files_api.data) == 13  # 10 md + root, projects, demo folders


def test_conflicting_remote_edit_blocks_push(tmp_path, provider):
    service, store = provider
    root = project(tmp_path)
    init_remote(root, store)
    transfer(root, store, "push")
    checkpoint(root, "demo", "New work", "Check again")
    target = next(x for x in service.files_api.data.values() if x["name"] == "CURRENT_STATE.md")
    target["content"] = b"# Edited outside app\n"
    with pytest.raises(HandoffError, match="Remote changed"):
        transfer(root, store, "push")


def test_conflicting_local_edit_blocks_pull(tmp_path, provider):
    service, store = provider
    root = project(tmp_path)
    folder_id = init_remote(root, store)
    transfer(root, store, "push")
    other = tmp_path / "other"
    other.mkdir()
    connect(other, folder_id)
    transfer(other, store, "pull")
    path = other / "projects/demo/CURRENT_STATE.md"
    path.write_text(path.read_text() + "\nchanged locally\n")
    remote_id = next(x["id"] for x in service.files_api.data.values() if x["name"] == "CURRENT_STATE.md")
    service.files_api.data[remote_id]["content"] += b"\nchanged remotely\n"
    with pytest.raises(HandoffError, match="Local changed"):
        transfer(other, store, "pull")


def test_dry_run_has_no_remote_side_effect(tmp_path, provider):
    service, store = provider
    root = project(tmp_path)
    init_remote(root, store)
    before = len(service.files_api.data)
    plan = transfer(root, store, "push", dry_run=True)
    assert len(plan.changed) == 10
    assert len(service.files_api.data) == before
    assert connection(root)["baseline"] == {}


def test_symlink_refused_on_push(tmp_path, provider):
    service, store = provider
    root = project(tmp_path)
    init_remote(root, store)
    target = root / "projects/demo/PROMPTS.md"
    target.unlink()
    try:
        target.symlink_to(root / "PROJECTS_INDEX.md")
    except OSError:
        pytest.skip("Symlink not supported")
    with pytest.raises(HandoffError, match="invalid|symlink|unsafe"):
        transfer(root, store, "push")


def test_conflicting_existing_remote_content_requires_pull(tmp_path, provider):
    service, store = provider
    root = project(tmp_path)
    fid=init_remote(root, store)
    store.write(fid, "PROJECTS_INDEX.md", "Existing remote content", None)
    with pytest.raises(HandoffError, match="Existing remote file"):
        transfer(root, store, "push")
