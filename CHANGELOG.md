# Changelog

## 0.2.0 — 2026-10-10
- Added optional Google Drive API v3 Markdown provider with desktop OAuth (drive.file).
- Added `drive auth`, `drive init`, `drive connect`, `drive push`, `drive pull`, and `drive status`.
- Added SHA-256 baseline conflict checks, dry runs and no-delete semantics.
- Added offline fake Drive API tests and Google Cloud setup documentation.
- **Limitation:** Real Google-account OAuth acceptance testing remains pending. Cross-provider auto-sync is not implemented.

# Changelog

## 0.1.0 — 2026-10-08 (initial experimental version)

- Added local-first Markdown CLI: init/create/checkpoint/resume/status/validate.
- Added Git workflow: explicit selective-file commits and explicit guarded sync.
- Added time-stamped append-only session logs, optional decision entries and managed current-state section.
- Added optimistic SHA-256 state precondition, basic secret-pattern warnings and symlink safety checks.
- Added synthetic examples, architecture diagrams and local automated tests.
- Documented Google Drive, hosted provider APIs and MCP as future work, not shipped capabilities.
