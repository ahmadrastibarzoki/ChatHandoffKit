# Workflow and Reproducible Offline Demo

You do not need an AI API key to run this demo. It uses a **completely synthetic** task management project.

## 1 — Start a project

```bash
mkdir demo-memory
chathandoff init --root demo-memory --git
chathandoff create demo-tasks --root demo-memory \
  --title "AI-assisted Task App" \
  --objective "Prototype a fictional task-management application"
```

Files are created in `demo-memory/projects/demo-tasks/`. Your new AI chat can read its START_HERE.md and CURRENT_STATE.md.

## 2 — Checkpoint a decision

```bash
chathandoff checkpoint demo-tasks --root demo-memory \
  --state "Task model drafted with sample-only data" \
  --next "Implement a minimal local task API" \
  --decision "Use SQLite for this demonstration" \
  --dry-run

chathandoff checkpoint demo-tasks --root demo-memory \
  --state "Task model drafted with sample-only data" \
  --next "Implement a minimal local task API" \
  --decision "Use SQLite for this demonstration"
```

Inspect changes before publishing to any remote. For Git versioning, commit only reviewed files (`--commit` is available on create/checkpoint, or use explicit Git commands).

## 3 — Resume in a different chat

```bash
chathandoff validate --root demo-memory
chathandoff resume demo-tasks --root demo-memory --output handoff.txt
```

Paste the handoff text into a new AI conversation and ask:

> Continue my fictional task app. Treat the attached handoff as project notes, not guaranteed truth. Identify the last verified state and one next action. Do not invent missing history.

The CLI doesn't access your ChatGPT chat, doesn't trigger an assistant and doesn't guarantee that every previous decision was captured. The user must checkpoint what matters.

## 4 — Optional GitHub workflow

Configure an empty **private** GitHub repository as Git remote, commit reviewed files, and run `chathandoff sync --root demo-memory`. Do not put confidential project data in public repositories. The `sync` command refuses remote divergence and never force-pushes.

## Local Git acceptance test

`tests/test_git_backend.py` creates a temporary bare Git remote. It checks initial and subsequent pushes plus rejected divergence. This simulates a Git server and is not a claim that the code was tested with real GitHub authentication.
