"""Command-line interface for local-first, Git-versioned project memory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import (
    HandoffError, checkpoint, create_project, init_workspace, list_projects,
    project_dir, resume_project, validate_workspace,
)
from .git_backend import commit_paths, init_git, sync_push


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chathandoff", description="Versionable project memory for AI conversations")
    parser.add_argument("--version", action="version", version=f"chathandoff {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a standalone Markdown memory workspace")
    init.add_argument("--root", type=Path, default=Path("."))
    init.add_argument("--git", action="store_true", help="Also initialize Git; never pushes automatically")

    create = sub.add_parser("create", help="Create one project with standard documents")
    create.add_argument("slug")
    create.add_argument("--title", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--root", type=Path, default=Path("."))
    create.add_argument("--commit", action="store_true", help="Commit only new project files when Git configured")

    cp = sub.add_parser("checkpoint", help="Record an explicit, reviewable project state checkpoint")
    cp.add_argument("slug")
    cp.add_argument("--root", type=Path, default=Path("."))
    cp.add_argument("--state", required=True, help="Verified current status (quote it in shell)")
    cp.add_argument("--next", required=True, dest="next_action", help="One concrete next step")
    cp.add_argument("--decision", help="Optional verified decision to append")
    cp.add_argument("--expected-state-sha256", help="Optimistic concurrency precondition")
    cp.add_argument("--dry-run", action="store_true", help="Validate proposed checkpoint without writing")
    cp.add_argument("--commit", action="store_true", help="Commit changed files, but do not push")

    show = sub.add_parser("resume", help="Print project re-entry context")
    show.add_argument("slug")
    show.add_argument("--root", type=Path, default=Path("."))
    show.add_argument("--output", type=Path, help="Optional destination text file")

    status = sub.add_parser("status", help="List known projects")
    status.add_argument("--root", type=Path, default=Path("."))

    val = sub.add_parser("validate", help="Check required documents, state markers and basic secret patterns")
    val.add_argument("--root", type=Path, default=Path("."))

    sync = sub.add_parser("sync", help="Push committed memory to a configured Git remote (e.g., GitHub)")
    sync.add_argument("--root", type=Path, default=Path("."))
    sync.add_argument("--remote", default="origin")
    sync.add_argument("--branch", default="main")
    sync.add_argument("--dry-run", action="store_true")
    drive = sub.add_parser("drive", help="Optional OAuth-based Google Drive Markdown storage")
    action = drive.add_subparsers(dest="drive_action", required=True)
    auth = action.add_parser("auth", help="Authorize with a desktop OAuth client JSON")
    auth.add_argument("--client-secrets", required=True, type=Path)
    auth.add_argument("--token-file", type=Path)
    setup = action.add_parser("init", help="Create a new app-owned Drive folder")
    setup.add_argument("--root", type=Path, default=Path("."))
    setup.add_argument("--name", default="ChatHandoffKit Memory")
    setup.add_argument("--token-file", type=Path)
    bind = action.add_parser("connect", help="Bind an existing app-accessible Drive folder ID")
    bind.add_argument("--root", type=Path, default=Path("."))
    bind.add_argument("--folder-id", required=True)
    for act in ("push", "pull", "status"):
        cmd = action.add_parser(act, help=f"Drive {act}; no implicit deletes")
        cmd.add_argument("--root", type=Path, default=Path("."))
        cmd.add_argument("--token-file", type=Path)
        if act != "status":
            cmd.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "drive":
            from .drive_backend import (
                DEFAULT_TOKEN, DriveStore, authorize, connection, connect,
                init_remote, live_service, transfer,
            )
            token_file = args.token_file or DEFAULT_TOKEN if hasattr(args, "token_file") else DEFAULT_TOKEN
            if args.drive_action == "auth":
                authorize(args.client_secrets, token_file)
                print("Google Drive OAuth token saved locally (never commit it).")
                return 0
            if args.drive_action == "connect":
                connect(args.root, args.folder_id)
                print("Drive folder connected (no data transferred):", args.folder_id)
                return 0
            if args.drive_action == "status":
                print("Connected Drive folder:", connection(args.root)["folder_id"])
                return 0
            store = DriveStore(live_service(token_file))
            if args.drive_action == "init":
                print("Created app-owned Drive folder:", init_remote(args.root, store, args.name))
                return 0
            plan = transfer(args.root, store, args.drive_action, dry_run=args.dry_run)
            print("Drive", args.drive_action, "preview" if args.dry_run else "complete")
            print("Changed:", ", ".join(plan.changed) or "none")
            print("Unchanged:", len(plan.unchanged))
            return 0
        if args.command == "init":
            created = init_workspace(args.root)
            print("Workspace initialized. New files:", ", ".join(created) or "none")
            if args.git:
                print("Git branch:", init_git(args.root))
            return 0
        if args.command == "create":
            paths = create_project(args.root, args.slug, args.title, args.objective)
            print("Created project", args.slug)
            if args.commit:
                print("Commit:", commit_paths(args.root, paths, f"docs(memory): initialize {args.slug}"))
            return 0
        if args.command == "checkpoint":
            if args.dry_run and args.commit:
                raise HandoffError("Choose --dry-run OR --commit, not both")
            result = checkpoint(args.root, args.slug, args.state, args.next_action,
                decision=args.decision, expected_sha256=args.expected_state_sha256,
                dry_run=args.dry_run)
            print("Checkpoint", "validated (dry run)" if args.dry_run else "recorded")
            print("Previous state SHA256:", result.previous_hash)
            print("Current state SHA256: ", result.new_hash)
            print("Changed files:", ", ".join(result.changed_files))
            if args.commit:
                print("Commit:", commit_paths(args.root, list(result.changed_files), f"docs(memory): checkpoint {args.slug}"))
            return 0
        if args.command == "resume":
            data = resume_project(args.root, args.slug)
            if args.output:
                if args.output.exists():
                    raise HandoffError("Output exists: refusing overwrite")
                args.output.write_text(data, encoding="utf-8")
                print(f"Re-entry context saved to {args.output}")
            else:
                print(data)
            return 0
        if args.command == "status":
            print("Projects:", ", ".join(list_projects(args.root)) or "(none)")
            return 0
        if args.command == "validate":
            issues = validate_workspace(args.root)
            if issues:
                for issue in issues:
                    print("ERROR:", issue, file=sys.stderr)
                return 1
            print("Validation passed (structure + basic secret checks only).")
            return 0
        if args.command == "sync":
            print("Git push:", sync_push(args.root, args.remote, args.branch, dry_run=args.dry_run))
            return 0
    except (HandoffError, OSError, ValueError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 2
    except Exception as error:
        if args.command != "drive":
            raise
        # OAuth/Google API request failures should not print a stack trace containing
        # sensitive local configuration. Never include credential values in errors.
        print("ERROR: Google Drive operation failed:", type(error).__name__, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
