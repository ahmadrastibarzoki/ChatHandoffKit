# Roadmap

## v0.1 — released 2026-10-08
- [x] Markdown project scaffold, checkpoints, resume, local Git history and explicit sync.
- [x] Python CLI, synthetic demo, pytest, GitHub Actions on Python 3.10–3.13.

## v0.2 — source implementation (2026-10-10)
- [x] Optional Drive v3 API integration with desktop OAuth using scoped `drive.file`.
- [x] Explicit Drive folder setup, Markdown push/pull, SHA-256 baseline conflict refusals and dry run.
- [x] Offline fake Drive API tests for upload, restore, divergence and duplicate safety.
- [ ] Real-account OAuth acceptance test (user must connect their Google Cloud OAuth app).
- [ ] Concurrency-safe write preconditions / transactions; current conflict detection is best effort.

## Later
- [ ] Provider abstraction with more robust transactional semantics and native GitHub API support.
- [ ] Google Picker/native Docs integration if needed and appropriate scopes/verification.
- [ ] Better automated context extraction with human review, cross-provider reconciliation.
- [ ] Optional MCP interface, UI, semantic retrieval and schema migration.

No feature is considered production-ready solely because it is in the roadmap.
