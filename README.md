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

Run the five-case synthetic Bedrock smoke suite:

```powershell
.\.venv\Scripts\python scripts\run_smoke.py
```

The frozen 2026-07-30 Qwen3 32B run produced schema-valid, evidence-linked
drafts for all five cases. It used 6,858 total tokens, completed in 12.6 seconds
wall-clock time, and had an estimated inference cost of $0.00262350 at the
recorded reference rates. Raw responses and normalized records are retained in
[`artifacts/smoke/20260730T083148.678843Z`](artifacts/smoke/20260730T083148.678843Z).
This is a smoke result, not a final accuracy or safety evaluation.

## Tested trust boundary

The runnable vertical slice separates AI assistance from authority:

```text
synthetic evidence -> AI draft -> human review -> synthetic source check
  -> deterministic activation -> signed claim -> deterministic authorization
  -> revocation -> subsequent denial
```

Only the first draft-extraction step calls a language model. Review, source
status, activation, signing, authorization, and revocation are explicit typed
services. The registry simulator has no network client, and the demo generates
its Ed25519 signing key in memory.

Run the deterministic demonstration:

```powershell
.\.venv\Scripts\python scripts\demo_vertical_slice.py
```

The recorded milestone at commit
[`d76a38f`](https://github.com/caretrust-hub/caretrust-poc/commit/d76a38f1e397a1cde944d9e85aa3e3c03e964c26)
passed 45 automated tests and demonstrated:

- reviewer approval plus a synthetic registry match followed by a policy permit;
- a synthetic registry mismatch denied with `SOURCE_MISMATCH`;
- deferred human review denied with `REVIEW_DEFERRED`; and
- a previously permitted request denied with `TOKEN_REVOKED` after revocation.

The machine-readable record is
[`artifacts/validation/vertical-slice.json`](artifacts/validation/vertical-slice.json).

## Current limitations

CareTrust is a controlled synthetic proof of concept. It does not perform
identity proofing, contact Hawaii's live registry, process real credentials or
health data, establish W3C VC or healthcare protocol conformance, or demonstrate
cross-organization federation. Those remain separately governed Phase 2 or
Phase 3 activities.
