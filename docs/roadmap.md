# Roadmap

Version labels are intentions, not shipped promises.

## v0.1 — Implemented locally
- [x] Python CLI (stdlib, Python 3.10+).
- [x] Markdown project templates and project index.
- [x] Explicit manual checkpoints, append-only logs and resume output.
- [x] Basic validation, secret heuristics, local state SHA precondition.
- [x] Selective Git commits and guarded explicit Git push.
- [x] Synthetic demo, local tests, CI workflow configuration.
- [ ] Live GitHub hosted CI and remote-push verification (until first successful published run).

## v0.2 — Hardening
- [ ] Atomic multi-document checkpoint transaction / rollback strategy.
- [ ] Robust multi-writer conflict detection and reconciliation UI/CLI.
- [ ] Versioned context schema/migrations and expanded document integrity rules.
- [ ] Full packaging/install smoke tests across supported OSes.
- [ ] Coverage metrics and dedicated security tests.

## v0.3 — Storage interface
- [ ] Provider abstraction and explicit source-of-truth configuration.
- [ ] Native GitHub API adapter (optional) and richer revision handling.
- [ ] Google Drive adapter tested end-to-end, least-privilege OAuth.
- [ ] Optional snapshot/export/import workflow.

## Beyond
- [ ] MCP server, only after access control and write-approval design.
- [ ] Browser/desktop workflow; semantic search with explicit opt-in.
- [ ] Optional AI-assisted extraction with provenance and review.
- [ ] Conflict-safe cross-provider migration (not automatic bidirectional sync).

## Non-goals

No claims of full chat-memory recovery, autonomous AI agent, guaranteed truth, enterprise security or automatic cloud sync without implementation and tests.
