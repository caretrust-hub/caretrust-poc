# CareTrust

Open-source TRL 3 proof of concept for portable, interoperable caregiver workforce
trust claims.

## Development control

CareTrust uses the repo-native [Specifica](https://specifica.org/) Markdown format:

- [Principles](.specifica/principles.md)
- [TRL 3 requirements](.specifica/trl3-poc/spec.md)
- [Technical design](.specifica/trl3-poc/design.md)
- [Implementation tasks](.specifica/trl3-poc/tasks.md)

The Specifica task list is the authoritative technical backlog. The Phase 1 proof
of concept uses only synthetic identities, credentials, registry responses, and
care data.

## Development setup

The deadline-critical scaffold is pinned to Python 3.13. Create an isolated
environment and install the exact declared dependencies with standard Python and
pip tooling:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip==26.2
.\.venv\Scripts\python -m pip install -e ".[aws,dev]"
```

No AWS secret belongs in the repository or `.env`. Copy `.env.example` to `.env`
only for non-secret local configuration; the AWS SDK resolves credentials through
its normal credential chain.

Export the structured-output schema and run the focused contract tests:

```powershell
.\.venv\Scripts\python scripts\export_schema.py
.\.venv\Scripts\python -m pytest
```
