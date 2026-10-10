"""Optional Google Drive adapter for explicitly reviewed Markdown project memories.

The Drive API account is accessed only after a user supplies OAuth desktop app
credentials and grants the narrowly scoped ``drive.file`` permission.
No Google Docs conversion or automatic chat ingestion is performed.
"""
from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .core import HandoffError, PROJECT_FILES, digest, list_projects, root_check, validate_workspace

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
FOLDER_MIME = "application/vnd.google-apps.folder"
MARKDOWN_MIME = "text/markdown"
ROOT_FILES = ("START_HERE.md", "OPERATING_RULES.md", "PROJECTS_INDEX.md")
CONFIG_DIR = ".chathandoff"
CONFIG_NAME = "drive.json"
DEFAULT_TOKEN = Path.home() / ".config" / "chathandoffkit" / "google-drive-token.json"


def _private_json(path: Path, obj: dict) -> None:
    """Keep the local connection config/token private; refuse symlinks."""
    if path.is_symlink() or path.parent.is_symlink():
        raise HandoffError(f"Refusing symlinked configuration: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists() or tmp.is_symlink():
        raise HandoffError(f"Temporary configuration already exists: {tmp}")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(obj, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(tmp, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise HandoffError(f"Missing or unsafe configuration: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as err:
        raise HandoffError(f"Invalid JSON configuration: {path}") from err
    if not isinstance(data, dict):
        raise HandoffError("Configuration must be a JSON object")
    return data


def _local_files(root: Path) -> dict[str, str]:
    """Return an explicit allowlist of portable memory files, never arbitrary files."""
    root = root_check(root)
    problems = validate_workspace(root)
    if problems:
        raise HandoffError("Local workspace invalid: " + "; ".join(problems))
    files: dict[str, str] = {}
    for name in ROOT_FILES:
        path = root / name
        if path.is_symlink():
            raise HandoffError(f"Refusing symlinked file: {path}")
        files[name] = path.read_text(encoding="utf-8")
    for slug in list_projects(root):
        folder = root / "projects" / slug
        if folder.is_symlink():
            raise HandoffError(f"Refusing symlinked folder: {folder}")
        for name in PROJECT_FILES:
            path = folder / name
            if path.is_symlink():
                raise HandoffError(f"Refusing symlinked file: {path}")
            files[f"projects/{slug}/{name}"] = path.read_text(encoding="utf-8")
    return files


def _config_path(root: Path) -> Path:
    return root_check(root) / CONFIG_DIR / CONFIG_NAME


def connect(root: Path, folder_id: str) -> None:
    """Bind the current workspace to a *user-chosen, app-accessible* Drive folder."""
    if not folder_id or not folder_id.strip() or any(c.isspace() for c in folder_id):
        raise HandoffError("A Google Drive folder ID is required")
    root = root_check(root)
    if not root.is_dir():
        raise HandoffError("Initialize local workspace first")
    path = _config_path(root)
    if path.exists():
        raise HandoffError("Drive connection already exists; refusing to replace it")
    _private_json(path, {"schema": 1, "folder_id": folder_id.strip(), "baseline": {}})


def connection(root: Path) -> dict:
    result = _read_json(_config_path(root))
    if result.get("schema") != 1 or not isinstance(result.get("folder_id"), str) or not isinstance(result.get("baseline"), dict):
        raise HandoffError("Invalid Drive connection schema")
    return result


def authorize(client_secrets: Path, token_file: Path = DEFAULT_TOKEN) -> None:
    """OAuth desktop browser flow; token remains outside version-controlled memory."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as err:
        raise HandoffError("Drive dependencies missing. Install: pip install -e '.[drive]'") from err
    if not client_secrets.is_file() or client_secrets.is_symlink():
        raise HandoffError("OAuth desktop client JSON not found or is symlinked")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), [DRIVE_SCOPE])
    creds = flow.run_local_server(port=0)
    _private_json(token_file.expanduser(), json.loads(creds.to_json()))


def live_service(token_file: Path = DEFAULT_TOKEN):
    """Load/refresh consented credentials and build a real Google Drive v3 client."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as err:
        raise HandoffError("Drive dependencies missing. Install: pip install -e '.[drive]'") from err
    token_file = token_file.expanduser()
    token = _read_json(token_file)
    creds = Credentials.from_authorized_user_info(token, [DRIVE_SCOPE])
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _private_json(token_file, json.loads(creds.to_json()))
        else:
            raise HandoffError("Drive credentials expired; run: chathandoff drive auth")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _q_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class DriveStore:
    """Small, mockable transport that uses only app-visible Drive files."""

    def __init__(self, service):
        self.service = service

    def children(self, folder_id: str) -> dict[str, dict]:
        found = {}
        page = None
        while True:
            response = self.service.files().list(
                q=f"'{_q_literal(folder_id)}' in parents and trashed = false",
                fields="nextPageToken,files(id,name,mimeType)",
                pageSize=1000, pageToken=page,
            ).execute()
            for item in response.get("files", []):
                if item["name"] in found:
                    raise HandoffError("Ambiguous duplicate Drive name: " + item["name"])
                found[item["name"]] = item
            page = response.get("nextPageToken")
            if not page:
                return found

    def create_folder(self, parent: str, name: str) -> str:
        item = self.service.files().create(body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}, fields="id").execute()
        return item["id"]

    def text(self, file_id: str) -> str:
        raw = self.service.files().get_media(fileId=file_id).execute()
        if not isinstance(raw, bytes):
            raise HandoffError("Drive returned unexpected non-binary response")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as err:
            raise HandoffError("Remote Markdown is not UTF-8") from err

    def write(self, parent: str, name: str, data: str, existing_id: str | None) -> str:
        try:
            from googleapiclient.http import MediaIoBaseUpload
        except ImportError as err:
            raise HandoffError("Drive dependencies missing. Install: pip install -e '.[drive]'") from err
        media = MediaIoBaseUpload(io.BytesIO(data.encode("utf-8")), mimetype=MARKDOWN_MIME, resumable=False)
        if existing_id:
            obj = self.service.files().update(fileId=existing_id, media_body=media, fields="id").execute()
        else:
            obj = self.service.files().create(
                body={"name": name, "mimeType": MARKDOWN_MIME, "parents": [parent]},
                media_body=media, fields="id",
            ).execute()
        return obj["id"]


def _remote_tree(store: DriveStore, root_id: str) -> dict[str, tuple[str, str]]:
    """Map only known portable project-memory file paths and their current contents."""
    files: dict[str, tuple[str, str]] = {}
    root_children = store.children(root_id)
    for name in ROOT_FILES:
        obj = root_children.get(name)
        if obj:
            if obj["mimeType"] != MARKDOWN_MIME:
                raise HandoffError("Unexpected remote file MIME type: " + name)
            files[name] = (obj["id"], store.text(obj["id"]))
    projects = root_children.get("projects")
    if projects:
        if projects["mimeType"] != FOLDER_MIME:
            raise HandoffError("Remote projects entry is not a folder")
        for slug, folder in store.children(projects["id"]).items():
            if folder["mimeType"] != FOLDER_MIME:
                continue
            from .core import SLUG_PATTERN
            if not SLUG_PATTERN.fullmatch(slug):
                continue
            for name, item in store.children(folder["id"]).items():
                if name not in PROJECT_FILES:
                    continue
                if item["mimeType"] != MARKDOWN_MIME:
                    raise HandoffError("Unexpected remote file MIME type: " + name)
                files[f"projects/{slug}/{name}"] = (item["id"], store.text(item["id"]))
    return files


def _remote_folders(store: DriveStore, folder_id: str, names: set[str]) -> dict[str, str]:
    ids={"": folder_id}
    root = store.children(folder_id)
    for slug in sorted(names):
        projects = root.get("projects")
        if not projects:
            projects_id = store.create_folder(folder_id, "projects")
            root["projects"]={"id":projects_id,"mimeType":FOLDER_MIME}
        elif projects["mimeType"] != FOLDER_MIME:
            raise HandoffError("Remote projects entry isn't a folder")
        projects_id = root["projects"]["id"]
        if "projects" not in ids:
            ids["projects"] = projects_id
        sub = store.children(projects_id)
        item = sub.get(slug)
        if item and item["mimeType"] != FOLDER_MIME:
            raise HandoffError(f"Remote project {slug} is not a folder")
        ids[f"projects/{slug}"] = item["id"] if item else store.create_folder(projects_id, slug)
    return ids


@dataclass(frozen=True)
class TransferPlan:
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]


def transfer(root: Path, store: DriveStore, direction: str, *, dry_run: bool = False) -> TransferPlan:
    """No destructive deletes. Baseline checks prevent accidental two-way overwrites.

    Remote file updates aren't an atomic CAS; editing the same file concurrently during
    upload remains a risk. Revisions and multiple Drive accounts are not merged.
    """
    if direction not in ("push", "pull"):
        raise HandoffError("Direction must be push or pull")
    root = root_check(root)
    cfg = connection(root)
    baseline = cfg["baseline"]
    remote = _remote_tree(store, cfg["folder_id"])
    if direction == "pull":
        missing_root = set(ROOT_FILES) - set(remote)
        if missing_root:
            raise HandoffError("Incomplete remote memory: " + ", ".join(sorted(missing_root)))
        slugs = {name.split("/")[1] for name in remote if name.startswith("projects/")}
        for slug in slugs:
            missing = {f"projects/{slug}/{name}" for name in PROJECT_FILES} - set(remote)
            if missing:
                raise HandoffError("Incomplete remote project: " + slug)
    if direction == "push":
        local = _local_files(root)
        names = set(local)
    else:
        local = {}
        names = set(remote)
        for name in names:
            file = root / name
            if file.is_symlink() or file.parent.is_symlink():
                raise HandoffError("Refusing symlinked destination")
            if file.is_file():
                local[name] = file.read_text(encoding="utf-8")
            elif file.exists():
                raise HandoffError("Local destination isn't a regular file: " + name)
    changes, stable = [], []
    for name in sorted(names):
        before = baseline.get(name)
        remote_value = remote.get(name)
        remote_text = remote_value[1] if remote_value else None
        local_text = local.get(name)
        remote_hash = digest(remote_text) if remote_text is not None else None
        local_hash = digest(local_text) if local_text is not None else None
        if before is not None and not isinstance(before, str):
            raise HandoffError("Invalid Drive baseline entry: " + name)
        if direction == "push":
            if before is None and remote_hash is not None and remote_hash != local_hash:
                raise HandoffError("Existing remote file has no matching baseline: " + name)
            if before is not None and remote_hash != before and remote_hash != local_hash:
                raise HandoffError("Remote changed since last transfer: " + name)
            if remote_hash == local_hash:
                stable.append(name)
            else:
                changes.append(name)
        else:
            if local_hash != before and local_hash != remote_hash:
                raise HandoffError("Local changed since last transfer: " + name)
            if before is None and local_hash is not None and local_hash != remote_hash:
                raise HandoffError("Existing local file has no matching baseline: " + name)
            if local_hash == remote_hash:
                stable.append(name)
            else:
                changes.append(name)
    if dry_run:
        return TransferPlan(tuple(changes), tuple(stable))
    if direction == "push" and changes:
        folders = _remote_folders(store, cfg["folder_id"], {name.split("/")[1] for name in changes if name.startswith("projects/")})
        for name in changes:
            parent,name_only = name.rsplit("/",1) if "/" in name else ("",name)
            prior = remote.get(name)
            store.write(folders[parent], name_only, local[name], prior[0] if prior else None)
    elif direction == "pull":
        for name in changes:
            file = root / name
            # Never write through existing/parent symlink. No overwrite of untracked divergent files.
            for parent in file.parents:
                if parent == root.parent:
                    break
                if parent.is_symlink():
                    raise HandoffError("Refusing symlinked folder")
            file.parent.mkdir(parents=True, exist_ok=True)
            temp = file.with_name(file.name + ".drive-tmp")
            if temp.exists() or temp.is_symlink():
                raise HandoffError("Drive temporary file exists: " + str(temp))
            try:
                with temp.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(remote[name][1])
                os.replace(temp, file)
            finally:
                if temp.exists():
                    temp.unlink()
    # Track only paths handled by this transfer; other paths may be out of scope.
    for name in names:
        baseline[name] = digest(local[name] if direction == "push" else remote[name][1])
    _private_json(_config_path(root), cfg)
    return TransferPlan(tuple(changes), tuple(stable))


def init_remote(root: Path, store: DriveStore, name: str = "ChatHandoffKit Memory") -> str:
    """Create a new app-owned Drive folder and bind it locally; no content uploaded."""
    root = root_check(root)
    if not root.is_dir() or not (root / "PROJECTS_INDEX.md").is_file():
        raise HandoffError("Initialize the local workspace before Drive setup")
    if _config_path(root).exists():
        raise HandoffError("Drive is already connected")
    folder_id = store.service.files().create(body={"name": name, "mimeType": FOLDER_MIME}, fields="id").execute()["id"]
    connect(root, folder_id)
    return folder_id
