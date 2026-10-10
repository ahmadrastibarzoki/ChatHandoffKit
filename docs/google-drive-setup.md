# Google Drive adapter — experimental v0.2

> **Status:** Real Drive v3 API calls are implemented, and offline/fake API tests passed. Live OAuth and a real Drive account have **not yet been acceptance-tested**. GitHub and Google Drive are alternative storage destinations; there is no automatic two-way GitHub↔Drive sync.

## Requirements

- Python 3.10+, ChatHandoffKit v0.2 installed with `python -m pip install -e ".[drive]"` (PowerShell uses the same double-quoted syntax).
- Your own Google Cloud project and enabled **Google Drive API**.
- An **OAuth 2.0 Desktop application** client ID (not a web app, and no service-account key is required).
- Configure OAuth consent screen and add yourself as a test user if the app is in testing mode.
- Local browser to complete OAuth (the CLI opens a localhost callback server on a random port).

Use Google's official [Python quickstart](https://developers.google.com/workspace/drive/api/quickstart/python) for consent screen and desktop client setup. Review [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth). The tool requests **only** `https://www.googleapis.com/auth/drive.file`, allowing it to work with files it creates or those explicitly opened/authorized for that OAuth app.

## Single-machine walkthrough

**Keep downloaded OAuth client JSON OUTSIDE the public repository.** Do not paste the JSON into chats or issues.

```bash
python -m pip install -e '.[drive]'
chathandoff init --root my-memory
chathandoff create demo --title "Demo" --objective "Fictional sample" --root my-memory
chathandoff drive auth --client-secrets /absolute/private/path/oauth-client.json
chathandoff drive init --root my-memory
chathandoff drive status --root my-memory
chathandoff drive push --root my-memory --dry-run
chathandoff drive push --root my-memory
```

On Windows PowerShell, use an absolute Windows path to `--client-secrets` and quote it if it contains spaces. The browser may display a Google **unverified app** warning during testing; follow Google's verification/testing guidance and verify that it is **your own OAuth application**, not a third-party client. OAuth testing mode can have short refresh-token lifetimes.

## Resume on a second machine

1. Install the tool and authenticate using the **same OAuth app/client** that can see the original files.
2. Create a **new empty directory** (do not `chathandoff init` first); find your remote folder ID with `drive status` on the original machine.
3. Run:

```bash
mkdir memory-restored
chathandoff drive connect --root memory-restored --folder-id YOUR_DRIVE_FOLDER_ID
chathandoff drive pull --root memory-restored --dry-run
chathandoff drive pull --root memory-restored
chathandoff validate --root memory-restored
```

The `drive.file` scope does not give access to all Drive files: the folder must be accessible to this OAuth client (normally one created by this app). Connecting with a folder ID is not a way to bypass sharing or authorization.

## Conflict behavior and limitations

- Upload/pull is **explicit**, not automatic. Use `--dry-run` to inspect changed paths.
- Local `.chathandoff/drive.json` tracks SHA-256 baselines; this directory is excluded from Git. The OAuth refresh token defaults to `~/.config/chathandoffkit/google-drive-token.json` and should have restrictive filesystem access. Treat both token and OAuth client JSON as sensitive.
- The adapter uploads **only** known workspace Markdown files and does not delete anything on Drive.
- If a file changed on the other side since last transfer, the tool **refuses to overwrite it**. Inspect manually and reconcile; no automated merging.
- An upload of many files is **not atomic**. A concurrent edit during an API request may still race; timestamps and file IDs are not a distributed lock. Avoid concurrent writers.
- Plain Markdown files use Drive `text/markdown` MIME; Google Docs native documents are out of scope.
- If setup succeeds but transfer fails partway, re-run after reviewing both sides. No rollback guarantee.
- Sensitive source data and secrets should never be stored in a public Git repository. This adapter is not a backup/security vault.
- CI uses an offline fake Drive service and does not authenticate with a real Google account.

## Troubleshooting

- `Drive dependencies missing`: run `pip install -e ".[drive]"` in your active environment.
- Consent/client error: enable Drive API, ensure Desktop OAuth client, correct test users and scopes.
- OAuth token expired: run `chathandoff drive auth --client-secrets <local-json>` again.
- `Remote changed` / `Local changed`: do not force. Compare and reconcile contents manually.
- `Incomplete remote`: Drive folder is missing one or more required Markdown documents; complete it before pull.
