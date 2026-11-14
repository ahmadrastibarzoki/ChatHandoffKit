# Live Google Drive OAuth acceptance: local-first checklist

**Status:** This is an operator-run acceptance procedure, NOT a completed live test.
ChatGPT's own connected Google Drive account is not a substitute for authenticating
ChatHandoffKit's Google OAuth Desktop application on the operator's computer.

## What the new doctor checks

The command chathandoff drive doctor has two modes:

- **Default (offline):** Check an optional Google Desktop client JSON, ensure OAuth
  endpoints and redirect URIs are the expected Google/loopback values, inspect an
  existing local token without printing it, and require exactly the drive.file scope.
  On POSIX, refuse a token readable by group/others.
- **With --online:** Use a locally authorized token to call the Google Drive API
  read-only list endpoint, requesting IDs only. With --check-folder, also verify
  the connected app-visible folder's metadata. The doctor does not upload, edit,
  delete or fetch any Markdown content.

The online mode may refresh an expired access token and update the **local**
token file. It does not create/modify files on Drive. A passing online diagnostic
does NOT prove that push, pull, authorization renewals, sharing or conflict
handling work end-to-end with a real Google account.

## Before you start

1. Python 3.10 or newer, Git and a working local browser.
2. A Google Cloud project with Google Drive API enabled; a Google OAuth consent
   screen and a **Desktop application** OAuth client. If it is in Testing mode,
   add your own Google account as an authorized test user.
3. Download your own client JSON and store it **outside Git and project memory**.
   Do not post it, or the resulting token, in a chat, issue, PR, screenshot or log.
4. Run in a dedicated **synthetic workspace**, not actual private project files.
5. Install: python -m pip install -e ".[drive]"

See the official Google documentation:

- https://developers.google.com/workspace/drive/api/quickstart/python
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/identity/protocols/oauth2

In commands below replace CLIENT_JSON_PATH with an **absolute path** to the
private desktop OAuth JSON. On PowerShell quote the path if it has spaces.

## Phase A — preflight and interactive authorization

1. Run:

   chathandoff drive doctor --client-secrets CLIENT_JSON_PATH

   Expected: desktop_client: CHECKED; local_token can be MISSING;
   drive_api: NOT_CHECKED. **This does not authenticate anything.**

2. Run on YOUR computer, and approve the consent in YOUR browser:

   chathandoff drive auth --client-secrets CLIENT_JSON_PATH

   Confirm that the consent screen belongs to your own Google Cloud project
   and requests only the per-file Drive scope. No command should request a
   GitHub token for this Drive flow.

3. Verify the locally issued token and read-only API access:

   chathandoff drive doctor --client-secrets CLIENT_JSON_PATH --online

   Expected: desktop_client: CHECKED, local_token: PRESENT,
   drive_api: READ_OK. Record PASS for OAuth/API smoke-test only.

   If it fails, do not copy token/client JSON to anyone. Report only the
   sanitized error category, the Python version and whether the Google
   Cloud OAuth consent screen was configured for testing.

## Phase B — explicit live round trip with a fake project

**This phase makes real, authorized writes to your Drive account.** It is a
separate manual action; the doctor itself remains read-only. Use an isolated
app-owned folder and fictional text only.

1. Create a new local directory outside the repository, for example
   a directory named memory-acceptance, and initialize:

   chathandoff init --root memory-acceptance
   chathandoff create demo --title "Synthetic demo" --objective "OAuth acceptance only" --root memory-acceptance

2. Create an app-owned Drive folder:

   chathandoff drive init --root memory-acceptance

   Copy the folder ID from the command output to your **private local notes**.

3. Inspect access without uploading data:

   chathandoff drive doctor --root memory-acceptance --online --check-folder

   Expected: drive_api: READ_OK, connected_folder: READ_OK.

4. Preview and explicitly transfer **only** the generated synthetic Markdown:

   chathandoff drive push --root memory-acceptance --dry-run
   chathandoff drive push --root memory-acceptance
   chathandoff drive push --root memory-acceptance --dry-run

   The last preview should report no changed files.

5. Create a separate, empty directory memory-acceptance-restored and run:

   chathandoff drive connect --root memory-acceptance-restored --folder-id YOUR_FOLDER_ID
   chathandoff drive pull --root memory-acceptance-restored --dry-run
   chathandoff drive pull --root memory-acceptance-restored
   chathandoff validate --root memory-acceptance-restored

   Do not run chathandoff init in the empty restore directory before pull.

6. Compare the restored, fictional Markdown with the original. Run a small
   change in one workspace and use push --dry-run to verify previews;
   do not deliberately modify valuable Drive data. For conflict behavior,
   rely on the deterministic offline tests unless you have a disposable
   remote folder and a separate planned test.

## Acceptance record (fill in only after actually running)

| Check | Expected | Actual |
| --- | --- | --- |
| Desktop OAuth local config | CHECKED | NOT RUN |
| Browser consent + local token | User-approved | NOT RUN |
| Read-only Drive API smoke test | READ_OK | NOT RUN |
| App-owned folder metadata | READ_OK | NOT RUN |
| Synthetic push and no-op repeat | PASS | NOT RUN |
| Restore to empty workspace | PASS | NOT RUN |
| Validation of restored files | PASS | NOT RUN |

Do NOT report these as passing based only on offline CI or a successful
ChatGPT Google Drive connector call.

## Limitations and known risks

- A Drive OAuth consent screen in external Testing mode may produce refresh
  tokens expiring after seven days; this is a Google policy, not a CLI defect.
- The drive.file scope grants access to app-created or user-approved files,
  not an arbitrary user's entire Drive.
- Offline mocked tests do not prove that real-account network integration
  will succeed in all environments.
- Transfers are explicit, can be partially completed, and are not atomic.
  No automatic GitHub↔Drive synchronization is provided.
