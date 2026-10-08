"""Deterministic local project memory with safe, explicit checkpoints."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_FILES = (
    "START_HERE.md",
    "PROJECT_CONTEXT.md",
    "CURRENT_STATE.md",
    "DECISIONS.md",
    "PROMPTS.md",
    "ERRORS_AND_SOLUTIONS.md",
    "SESSION_LOG.md",
)
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
BEGIN_MARKER = "<!-- CHATHANDOFF:CURRENT_STATE:BEGIN -->"
END_MARKER = "<!-- CHATHANDOFF:CURRENT_STATE:END -->"
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
)


class HandoffError(Exception):
    """User-facing validation or conflict error."""


@dataclass(frozen=True)
class CheckpointResult:
    changed_files: tuple[str, ...]
    previous_hash: str
    new_hash: str


def validate_slug(slug: str) -> str:
    if not SLUG_PATTERN.fullmatch(slug) or "--" in slug or slug.endswith("-"):
        raise HandoffError("Project slug must be lowercase letters, numbers and single hyphens (max 63 chars).")
    return slug


def safe_text(text: str, *, max_length: int = 10000) -> str:
    text = text.strip()
    if not text:
        raise HandoffError("Checkpoint text cannot be empty.")
    if len(text) > max_length:
        raise HandoffError(f"Checkpoint text must be at most {max_length} characters.")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise HandoffError("Potential secret detected. Redact it before saving.")
    return text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_path(parent: Path, leaf: Path) -> None:
    """Don't read/write through symlinked project directories or target files."""
    if parent.is_symlink() or leaf.is_symlink():
        raise HandoffError(f"Refusing symlink path: {leaf}")
    if leaf.exists() and not leaf.is_file():
        raise HandoffError(f"Expected a regular file: {leaf}")


def _write_new(path: Path, text: str) -> None:
    _check_path(path.parent, path)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _write_update(path: Path, text: str) -> None:
    _check_path(path.parent, path)
    # The temporary file must live on the same volume to support atomic replace.
    temp = path.with_name(path.name + ".tmp")
    if temp.exists() or temp.is_symlink():
        raise HandoffError(f"Refusing to overwrite leftover temporary file: {temp}")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as f:
            f.write(text)
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def root_check(root: Path) -> Path:
    root = root.expanduser().absolute()
    if root.is_symlink():
        raise HandoffError("Refusing symlink workspace root")
    return root


def init_workspace(root: Path) -> list[str]:
    root = root_check(root)
    if root.exists() and not root.is_dir():
        raise HandoffError("Workspace root is not a directory")
    root.mkdir(parents=True, exist_ok=True)
    projects_dir = root / "projects"
    if projects_dir.is_symlink():
        raise HandoffError("Refusing symlink projects directory")
    projects_dir.mkdir(exist_ok=True)
    assets = {
        "START_HERE.md": "# AI Project Memory — Start Here\n\nRead OPERATING_RULES.md, PROJECTS_INDEX.md, then the selected project's START_HERE.md and CURRENT_STATE.md.\n",
        "OPERATING_RULES.md": "# Operating Rules\n\n- Verified source and current files outrank recollection.\n- Checkpoint manually; do not claim automatic chat sync.\n- Do not store secrets or private third-party records.\n- Confirm destructive changes before applying them.\n- Treat each project as a portable Markdown folder.\n",
        "PROJECTS_INDEX.md": "# Projects Index\n\n| Project | Path | Status |\n|---|---|---|\n",
    }
    created = []
    for name, content in assets.items():
        path = root / name
        if not path.exists():
            _write_new(path, content)
            created.append(name)
    return created


def project_dir(root: Path, slug: str) -> Path:
    root = root_check(root)
    validate_slug(slug)
    projects = root / "projects"
    if projects.is_symlink():
        raise HandoffError("Refusing symlink projects directory")
    target = projects / slug
    if target.is_symlink():
        raise HandoffError("Refusing symlink project directory")
    return target


def create_project(root: Path, slug: str, title: str, objective: str) -> list[str]:
    title, objective = safe_text(title, max_length=160), safe_text(objective, max_length=2000)
    root = root_check(root)
    project = project_dir(root, slug)
    index = root / "PROJECTS_INDEX.md"
    if not index.is_file() or index.is_symlink():
        raise HandoffError("Initialize workspace first (chathandoff init).")
    if project.exists():
        raise HandoffError(f"Project already exists: {slug}")
    _check_path(index.parent, index)
    index_text = index.read_text(encoding="utf-8")
    project.mkdir(parents=True)
    body = {
        "START_HERE.md": f"# {title} — START HERE\n\n- Slug: `{slug}`\n- Purpose: {objective}\n\nRead CURRENT_STATE.md before continuing.\n",
        "PROJECT_CONTEXT.md": f"# Project Context — {title}\n\n## Purpose\n{objective}\n\n## Scope and constraints\nAdd verified details as the project develops.\n",
        "CURRENT_STATE.md": f"# Current State — {title}\n\n{BEGIN_MARKER}\n**Status:** Initialized\n\n**Objective:** {objective}\n\n**Next action:** Define the first work item.\n{END_MARKER}\n\n## Notes (preserved across checkpoints)\n",
        "DECISIONS.md": f"# Decisions — {title}\n\nRecord meaningful, dated decisions here.\n",
        "PROMPTS.md": f"# Prompts — {title}\n\nAdd reusable prompts only when validated.\n",
        "ERRORS_AND_SOLUTIONS.md": f"# Errors and Solutions — {title}\n\nDocument confirmed causes and fixes, not guesses.\n",
        "SESSION_LOG.md": f"# Session Log — {title}\n\nAppend-only history of checkpoints.\n",
    }
    for name, content in body.items():
        _write_new(project / name, content)
    line = f"| {title} | [projects/{slug}/](projects/{slug}/START_HERE.md) | Active |\n"
    _write_update(index, index_text + ("" if index_text.endswith("\n") else "\n") + line)
    return [f"projects/{slug}/{p}" for p in PROJECT_FILES] + ["PROJECTS_INDEX.md"]


def checkpoint(root: Path, slug: str, state: str, next_action: str,
               *, decision: str | None = None, expected_sha256: str | None = None,
               now: datetime | None = None, dry_run: bool = False) -> CheckpointResult:
    state = safe_text(state)
    next_action = safe_text(next_action, max_length=2000)
    if decision is not None:
        decision = safe_text(decision, max_length=4000)
    project = project_dir(root, slug)
    needed = ["CURRENT_STATE.md", "SESSION_LOG.md", "DECISIONS.md"]
    for name in needed:
        path = project / name
        _check_path(project, path)
        if not path.is_file():
            raise HandoffError(f"Missing required file: {path}")
    current_path = project / "CURRENT_STATE.md"
    old = current_path.read_text(encoding="utf-8")
    old_hash = digest(old)
    if expected_sha256 and expected_sha256 != old_hash:
        raise HandoffError("Concurrent update detected: CURRENT_STATE hash mismatch")
    if old.count(BEGIN_MARKER) != 1 or old.count(END_MARKER) != 1:
        raise HandoffError("Missing or duplicated managed state markers; refusing destructive rewrite")
    begin, end = old.index(BEGIN_MARKER), old.index(END_MARKER)
    if begin >= end:
        raise HandoffError("Invalid managed state marker order")
    now = now or datetime.now(timezone.utc)
    date = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    new_section = (
        f"{BEGIN_MARKER}\n**Status:** Active — checkpointed {date}\n\n"
        f"**Current status:** {state}\n\n**Next action:** {next_action}\n{END_MARKER}"
    )
    updated = old[:begin] + new_section + old[end + len(END_MARKER):]
    log_path = project / "SESSION_LOG.md"
    log = log_path.read_text(encoding="utf-8")
    log_update = log.rstrip("\n") + f"\n\n## {date}\n- Status: {state}\n- Next: {next_action}\n"
    changed = [f"projects/{slug}/CURRENT_STATE.md", f"projects/{slug}/SESSION_LOG.md"]
    dec_update = None
    if decision:
        dec_path = project / "DECISIONS.md"
        dec = dec_path.read_text(encoding="utf-8")
        dec_update = dec.rstrip("\n") + f"\n\n## {date}\n{decision}\n"
        changed.append(f"projects/{slug}/DECISIONS.md")
    if not dry_run:
        _write_update(current_path, updated)
        _write_update(log_path, log_update)
        if dec_update is not None:
            _write_update(project / "DECISIONS.md", dec_update)
    return CheckpointResult(tuple(changed), old_hash, digest(updated))


def list_projects(root: Path) -> list[str]:
    directory = root_check(root) / "projects"
    if not directory.exists():
        return []
    if directory.is_symlink():
        raise HandoffError("Refusing symlink projects directory")
    return sorted(p.name for p in directory.iterdir() if p.is_dir() and not p.is_symlink() and SLUG_PATTERN.fullmatch(p.name))


def resume_project(root: Path, slug: str) -> str:
    project = project_dir(root, slug)
    contents = []
    for name in ("START_HERE.md", "CURRENT_STATE.md", "DECISIONS.md", "SESSION_LOG.md"):
        path = project / name
        _check_path(project, path)
        if not path.is_file():
            raise HandoffError(f"Missing {name}")
        text = path.read_text(encoding="utf-8")
        if name == "SESSION_LOG.md" and len(text) > 8000:
            text = "[Older log truncated for context budget]\n" + text[-8000:]
        if name == "DECISIONS.md" and len(text) > 8000:
            text = "[Older decisions truncated for context budget]\n" + text[-8000:]
        contents.append(f"--- {name} ---\n{text}")
    return "\n".join(contents)


def validate_workspace(root: Path) -> list[str]:
    root = root_check(root)
    issues = []
    for required in ("START_HERE.md", "OPERATING_RULES.md", "PROJECTS_INDEX.md"):
        f = root / required
        if not f.is_file() or f.is_symlink():
            issues.append(f"Missing/unsafe root file: {required}")
    for slug in list_projects(root):
        p = project_dir(root, slug)
        for filename in PROJECT_FILES:
            f = p / filename
            if not f.is_file() or f.is_symlink():
                issues.append(f"Missing/unsafe file: projects/{slug}/{filename}")
                continue
            contents = f.read_text(encoding="utf-8")
            if filename == "CURRENT_STATE.md" and (contents.count(BEGIN_MARKER) != 1 or contents.count(END_MARKER) != 1):
                issues.append(f"Missing managed-state markers: projects/{slug}/{filename}")
            for pat in SECRET_PATTERNS:
                if pat.search(contents):
                    issues.append(f"Potential secret: projects/{slug}/{filename}")
                    break
    return issues
