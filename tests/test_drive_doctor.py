"""Offline tests of OAuth doctor; no Google account or network is used."""
import json
import os
from pathlib import Path

import pytest

from chathandoffkit.cli import main
from chathandoffkit.core import HandoffError
from chathandoffkit.drive_backend import DRIVE_SCOPE, FOLDER_MIME, connect
from chathandoffkit import drive_doctor


CLIENT_ID = "example-desktop.apps.googleusercontent.com"


def client_json(tmp_path, *, kind="installed", auth_uri="https://accounts.google.com/o/oauth2/auth",
                token_uri="https://oauth2.googleapis.com/token", redirects=None,
                client_id=CLIENT_ID):
    path = tmp_path / "desktop-client.json"
    path.write_text(json.dumps({kind: {
        "client_id": client_id,
        "client_secret": "client-secret-not-to-print",
        "auth_uri": auth_uri,
        "token_uri": token_uri,
        "redirect_uris": redirects or ["http://localhost"],
    }}), encoding="utf-8")
    return path


def token_json(tmp_path, *, client_id=CLIENT_ID, scopes=None):
    path = tmp_path / "oauth-token.json"
    path.write_text(json.dumps({
        "client_id": client_id,
        "client_secret": "secret-must-not-appear",
        "token": "access-token-must-not-appear",
        "refresh_token": "refresh-token-must-not-appear",
        "scopes": [DRIVE_SCOPE] if scopes is None else scopes,
    }), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    return path


def test_offline_preflight_reports_missing_token_without_claiming_live_oauth(tmp_path):
    client = client_json(tmp_path)
    result = drive_doctor.diagnose(client_secrets=client, token_file=tmp_path / "missing-token.json")
    assert result == {
        "desktop_client": "CHECKED",
        "local_token": "MISSING",
        "drive_api": "NOT_CHECKED",
        "connected_folder": "NOT_CHECKED",
    }


@pytest.mark.parametrize("config", [
    {"kind": "web"},
    {"auth_uri": "https://evil.example.com/authorize"},
    {"token_uri": "http://oauth2.googleapis.com/token"},
    {"redirects": ["https://example.com/callback"]},
])
def test_invalid_client_rejected(tmp_path, config):
    path = client_json(tmp_path, **config)
    with pytest.raises(HandoffError):
        drive_doctor.diagnose(client_secrets=path, token_file=tmp_path / "missing.json")


def test_scope_must_be_exactly_drive_file(tmp_path):
    path = token_json(tmp_path, scopes=[DRIVE_SCOPE, "https://www.googleapis.com/auth/drive"])
    with pytest.raises(HandoffError, match="only the drive.file"):
        drive_doctor.diagnose(token_file=path)


def test_mismatched_oauth_clients_rejected(tmp_path):
    path = client_json(tmp_path)
    token = token_json(tmp_path, client_id="other.apps.googleusercontent.com")
    with pytest.raises(HandoffError, match="different Desktop client"):
        drive_doctor.diagnose(client_secrets=path, token_file=token)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not authoritative on Windows")
def test_world_readable_token_refused(tmp_path):
    token = token_json(tmp_path)
    token.chmod(0o644)
    with pytest.raises(HandoffError, match="permissions are too broad"):
        drive_doctor.diagnose(token_file=token)


def test_symlinked_token_refused(tmp_path):
    token = token_json(tmp_path)
    link = tmp_path / "symlink.json"
    try:
        link.symlink_to(token)
    except OSError:
        pytest.skip("Symlinks unsupported on this filesystem")
    with pytest.raises(HandoffError, match="symlinked"):
        drive_doctor.diagnose(token_file=link)


def test_online_requires_token_and_check_folder_requires_online(tmp_path):
    with pytest.raises(HandoffError, match="OAuth token missing"):
        drive_doctor.diagnose(token_file=tmp_path / "missing.json", online=True)
    with pytest.raises(HandoffError, match="requires --online"):
        drive_doctor.diagnose(token_file=tmp_path / "missing.json", check_folder=True)


class Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class Files:
    def __init__(self, *, folder_mime=FOLDER_MIME, trashed=False):
        self.calls = []
        self.folder_mime = folder_mime
        self.trashed = trashed

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return Request({"files": []})

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return Request({"id": kwargs["fileId"], "mimeType": self.folder_mime, "trashed": self.trashed})

    def create(self, **kwargs):
        pytest.fail("OAuth doctor must not create files")

    def update(self, **kwargs):
        pytest.fail("OAuth doctor must not update files")

    def delete(self, **kwargs):
        pytest.fail("OAuth doctor must not delete files")


class Service:
    def __init__(self, files):
        self.files_api = files

    def files(self):
        return self.files_api


def test_online_smoke_test_reads_metadata_only_and_does_not_write(tmp_path, monkeypatch):
    token = token_json(tmp_path)
    files = Files()
    monkeypatch.setattr(drive_doctor, "live_service", lambda _: Service(files))
    result = drive_doctor.diagnose(token_file=token, online=True)
    assert result["drive_api"] == "READ_OK"
    assert result["connected_folder"] == "NOT_CHECKED"
    assert [name for name, _ in files.calls] == ["list"]
    assert files.calls[0][1] == {"pageSize": 1, "fields": "nextPageToken,files(id)"}


def test_online_folder_check_reads_only_folder_metadata(tmp_path, monkeypatch):
    token = token_json(tmp_path)
    root = tmp_path / "synthetic-workspace"
    root.mkdir()
    connect(root, "synthetic-folder-id")
    files = Files()
    monkeypatch.setattr(drive_doctor, "live_service", lambda _: Service(files))
    result = drive_doctor.diagnose(token_file=token, online=True, root=root, check_folder=True)
    assert result["drive_api"] == "READ_OK"
    assert result["connected_folder"] == "READ_OK"
    assert [name for name, _ in files.calls] == ["list", "get"]
    assert files.calls[1][1] == {
        "fileId": "synthetic-folder-id", "fields": "id,mimeType,trashed"
    }


def test_trashed_folder_is_rejected(tmp_path, monkeypatch):
    token = token_json(tmp_path)
    root = tmp_path / "synthetic-workspace"
    root.mkdir()
    connect(root, "synthetic-folder-id")
    monkeypatch.setattr(drive_doctor, "live_service", lambda _: Service(Files(trashed=True)))
    with pytest.raises(HandoffError, match="missing, trashed"):
        drive_doctor.diagnose(token_file=token, online=True, root=root, check_folder=True)


def test_cli_does_not_print_sensitive_config(tmp_path, capsys):
    client = client_json(tmp_path)
    token = token_json(tmp_path)
    rc = main(["drive", "doctor", "--client-secrets", str(client), "--token-file", str(token)])
    out = capsys.readouterr()
    assert rc == 0
    assert "desktop_client: CHECKED" in out.out
    assert "local_token: PRESENT" in out.out
    assert "drive_api: NOT_CHECKED" in out.out
    assert "secret-must-not-appear" not in out.out
    assert "refresh-token-must-not-appear" not in out.out
    assert "client-secret-not-to-print" not in out.out
    assert not out.err
