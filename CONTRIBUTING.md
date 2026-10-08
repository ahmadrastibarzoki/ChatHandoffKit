# Contributing

Thanks for helping make project handoffs more reliable.

## Before contributing

1. Open an issue describing the problem or proposed change.
2. Avoid submitting real conversations, work-client information, API keys, passwords or customer records.
3. Prefer deterministic functionality with tests and synthetic fixtures.
4. Separate implemented behavior from proposed capabilities in docs and pull requests.

## Development

```bash
python -m pip install -e . pytest
python -m pytest -q
```

Please add a test for each behavior change, keep the public CLI backward compatible when possible, and explain any schema migration. Contributions to Google Drive, MCP and automatic capture need threat modeling and explicit human review before default enablement.

## Pull requests

- Use a descriptive title and brief motivation.
- Include exact reproduction steps/tests.
- Do not commit tokens or secrets, even into sample files or git history.
- Do not introduce automated destructive actions without an opt-in and safeguards.

The MIT license applies to contributions to this repository.
