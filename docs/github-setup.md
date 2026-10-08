# GitHub Setup (Git transport, v0.1)

**What works:** standard `git` commits and explicit pushes from a local memory directory to any Git remote, including a properly configured GitHub repository.

**What does not exist yet:** independent GitHub REST adapter, programmatic repo creation, OAuth app installation, GitHub Actions as a memory-service backend, conflict-free cloud sync, or automatic AI chat capture.

## Steps

1. Create a new **empty private GitHub repository** in your account (no README, LICENSE or gitignore selected for the new remote).
2. Install Git and Python 3.10+ and configure Git authentication using Git Credential Manager or SSH. **Never paste a PAT into a memory document.**
3. Create a workspace: `chathandoff init --root my-memory --git` then `chathandoff create ...`.
4. `cd my-memory`; set your Git identity with `git config user.name "Your Name"` and `git config user.email "you@example.com"`.
5. Stage only reviewed content: `git add -- START_HERE.md OPERATING_RULES.md PROJECTS_INDEX.md projects/your-project/`.
6. Check `git diff --cached` and `git status`. Commit with `git commit -m "docs: initial memory"`.
7. Add remote: `git remote add origin git@github.com:YOUR_ACCOUNT/YOUR_REPOSITORY.git`.
8. Test: `chathandoff sync --root . --dry-run` then `chathandoff sync --root .`.
9. Verify repository contents and commit SHA on GitHub. Future manual checkpoints may use `--commit` and explicit `sync`.

## Concurrent edits

`sync` runs `git fetch` and refuses to push when the remote tracking branch is not an ancestor of the local HEAD. It intentionally does not auto-merge or rebase conflicting history, and it does not force-push. Resolve conflicts manually with normal Git tooling, re-run validation and review the updated content before trying again.

## Security

- Prefer private repository for real project memory.
- Exclude credentials and third-party data; a private repo is not an encrypted vault.
- The built-in secret checks are heuristic only. Review all staged diffs.
- For open-source demos, use only synthetic fixtures.
