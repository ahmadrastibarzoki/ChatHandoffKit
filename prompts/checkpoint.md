# Project Checkpoint — Assistant Prompt

You are preparing a **manual** checkpoint for an AI-assisted project.

- First read the existing project's START_HERE.md, CURRENT_STATE.md, DECISIONS.md and the most recent SESSION_LOG entry.
- Use only visible conversation details and verified code/tests; explicitly separate CONFIRMED, PLANNED and UNKNOWN.
- Identify new decisions, tested outcomes, technical constraints, current state and the single next action.
- Do not overwrite unrelated manual notes or invent missing history.
- Strip secrets, private keys, tokens, proprietary company details, sensitive customer information and unnecessary personal data.
- Propose an exact checkpoint text and optional decision. If the user approves, run `chathandoff checkpoint PROJECT --state '...' --next '...' [--decision '...']` against the correct workspace. Optional `--expected-state-sha256` guards against a stale snapshot.
- Validate the generated files; inspect the diff before opting into `--commit` and explicit `sync`.
- Never treat a successful local write as proof of a remote GitHub commit. If writing remotely, verify commit and readback separately.
