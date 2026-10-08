# Security Policy

## Release status

ChatHandoffKit v0.1 is an early-stage local CLI. It is **not a secure vault** and its pattern-based secret checks are incomplete. Do not rely on `validate` alone to keep confidential information safe.

## Principles

- Keep workspace folders private by default. Use a private Git remote unless your content was explicitly prepared for public release.
- Never put GitHub PATs, Google credentials, personal cookies, emails containing private data, company records or raw conversations in project files.
- Configure Git credentials through your own system credential manager, not embedded in git remotes.
- Review `git diff --cached` and `git status` before pushing, even if `validate` passes.
- The CLI refuses symlinked project directories and does not automatically force-push.
- Manual checkpoints and human review remain required; don't treat generated chat summaries as fully verified.

## Reporting vulnerabilities

For sensitive issues, do not open a public issue containing an exploit with secrets. Contact the maintainer through the private contact route listed on https://ahmadrastibarzoki.ir; coordinate a private disclosure before details are published.

## Threat model limitations

This release does not implement encryption at rest, permissions management, granular content policy, comprehensive secret scanning, or transactional multi-file rollback. The optional SHA-256 state precondition avoids *some* stale edits but is not an interprocess lock. Never promise secure multi-writer synchronization.
