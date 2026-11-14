"""Read-only OAuth diagnostics for the experimental Google Drive adapter.

Never prints OAuth client secrets, access/refresh tokens or Drive file names.
The offline check is NOT evidence that a real Google account was authorized.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from urllib.parse import urlparse

from .core import HandoffError
from .drive_backend import (
    DEFAULT_TOKEN, DRIVE_SCOPE, FOLDER_MIME, _read_json, connection, live_service,
)


def _google_endpoint(uri: object, hosts: set[str]) -> bool:
    if not isinstance(uri, str):
        return False
    parsed = urlparse(uri)
    return parsed.scheme == "https" and parsed.hostname in hosts and not parsed.username and not parsed.password


def _check_client(path: Path) -> dict:
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise HandoffError("OAuth client JSON must be a regular, non-symlinked file")
    data = _read_json(path)
    client = data.get("installed")
    if not isinstance(client, dict):
        raise HandoffError("Expected a Google OAuth Desktop application JSON, not a Web client")
    for field in ("client_id", "client_secret"):
        if not isinstance(client.get(field), str) or not client[field].strip():
            raise HandoffError("OAuth Desktop client JSON is missing required fields")
    if not _google_endpoint(client.get("auth_uri"), {"accounts.google.com"}):
        raise HandoffError("OAuth authorization endpoint is not the expected Google endpoint")
    if not _google_endpoint(client.get("token_uri"), {"oauth2.googleapis.com", "accounts.google.com"}):
        raise HandoffError("OAuth token endpoint is not the expected Google endpoint")
    redirects = client.get("redirect_uris")
    if not isinstance(redirects, list) or not redirects:
        raise HandoffError("OAuth Desktop client is missing loopback redirect URIs")
    for uri in redirects:
        parsed = urlparse(uri) if isinstance(uri, str) else None
        if not parsed or parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise HandoffError("OAuth Desktop client must use loopback redirect URIs")
    return client


def _check_token(path: Path) -> dict | None:
    if path.is_symlink() or path.parent.is_symlink():
        raise HandoffError("Refusing symlinked OAuth token location")
    if not path.exists():
        return None
    if not path.is_file():
        raise HandoffError("OAuth token location is not a regular file")
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise HandoffError("OAuth token file permissions are too broad; restrict access to the owner (chmod 600)")
    info = _read_json(path)
    if not isinstance(info.get("client_id"), str) or not info["client_id"]:
        raise HandoffError("OAuth token is missing client identity")
    scopes = info.get("scopes")
    if not isinstance(scopes, list) or set(scopes) != {DRIVE_SCOPE} or len(scopes) != 1:
        raise HandoffError("OAuth token must use only the drive.file scope; re-authorize with this application")
    return info


def diagnose(
    *,
    client_secrets: Path | None = None,
    token_file: Path = DEFAULT_TOKEN,
    online: bool = False,
    check_folder: bool = False,
    root: Path = Path("."),
) -> dict[str, str]:
    """Run local checks; optionally call only Google Drive read API endpoints.

    Real OAuth authorization must be initiated by the user separately using
    chathandoff drive auth. No remote create/update/delete occurs here.
    """
    if check_folder and not online:
        raise HandoffError("--check-folder requires --online")
    token_file = token_file.expanduser()
    client = _check_client(client_secrets.expanduser()) if client_secrets else None
    token = _check_token(token_file)
    if client and token and client["client_id"] != token["client_id"]:
        raise HandoffError("OAuth token belongs to a different Desktop client")
    result = {
        "desktop_client": "CHECKED" if client else "NOT_PROVIDED",
        "local_token": "PRESENT" if token else "MISSING",
        "drive_api": "NOT_CHECKED",
        "connected_folder": "NOT_CHECKED",
    }
    if not online:
        return result
    if token is None:
        raise HandoffError("OAuth token missing; run chathandoff drive auth on your own computer first")

    service = live_service(token_file)
    # OAuth/API smoke test. No names or file contents are fetched or logged.
    service.files().list(pageSize=1, fields="nextPageToken,files(id)").execute()
    result["drive_api"] = "READ_OK"

    if check_folder:
        folder_id = connection(root)["folder_id"]
        folder = service.files().get(
            fileId=folder_id, fields="id,mimeType,trashed"
        ).execute()
        if folder.get("mimeType") != FOLDER_MIME or folder.get("trashed", False):
            raise HandoffError("Connected Drive folder is missing, trashed or not a folder")
        result["connected_folder"] = "READ_OK"
    return result
