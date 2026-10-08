# Google Drive Adapter — Design Proposal (NOT IMPLEMENTED)

Google Drive is a **planned storage provider**, not a working component of v0.1. Do not present this document as a setup guide for a current feature.

## Proposed approach

- Store Markdown files in a dedicated project folder per user-selected workspace.
- OAuth with least-privilege Drive scopes; avoid storing tokens within project-memory files.
- Provider interface: list_projects, read_document, write_document, create_project, verify_write, history where supported.
- Include an explicit canonical-source setting per project. **Bidirectional GitHub↔Drive sync is out of scope** until conflict resolution exists.
- For a first adapter, upload/download `.md` files rather than converting to native Google Docs. Treat native Docs editing as a separate later milestone.

## Acceptance criteria before marking available

1. Authenticate without exposing credentials in the repository.
2. Initialize a synthetic project and verify exact file contents.
3. Record a checkpoint and verify the post-write content hash/revision.
4. Fetch and resume in a new session.
5. Detect conflicting concurrent edits without silently losing data.
6. Pass privacy/security checks and document limitations.

Until these tests pass, use the existing local/Git workflow.
