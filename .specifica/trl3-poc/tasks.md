# TRL 3 Proof of Concept - Tasks

This is the authoritative technical backlog. Tasks are ordered by dependency.
Check a task only when its stated evidence exists in the repository or saved
validation record.

- [x] **T001 [Codex]** Create the public `caretrust-poc` repository with an
  Apache-2.0 license. **Evidence:** repository root and `LICENSE`.
- [x] **T002 [Codex]** Establish CareTrust principles, requirements, design, and
  this Specifica task list. **Evidence:** `.specifica/`.
- [x] **T003 [Codex]** Add a defensive `.gitignore`, `.env.example`, Python project
  metadata, pinned runtime assumptions, and a reproducible setup command.
  **Done when:** a clean clone can install the declared dependencies without
  receiving secrets.
- [x] **T004 [Codex]** Define Pydantic domain models and export the draft-claim JSON
  Schema. **Done when:** schemas cover evidence, extraction, draft, review,
  registry result, active claim, authorization request/decision, and audit event.
- [x] **T005 [Codex]** Create five synthetic Hawaii CNA smoke fixtures and expected
  outputs: clean, ambiguous date, missing identifier, cropped restriction, and
  unsupported issuer. **Done when:** fixture content and hashes are committed.
- [x] **T006 [Codex]** Implement the provider-neutral `ModelAdapter` and Bedrock
  Converse adapter. **Done when:** no provider-specific response escapes the
  adapter and usage/latency metadata is captured.
- [x] **T007 [Codex]** Run the frozen five-case Qwen3 32B smoke test in `us-west-2`.
  **Done when:** raw responses, schema results, latency, token usage, estimated
  cost, and configuration hashes are saved without exceeding the $10 cumulative
  Phase 1 ceiling.
- [x] **T008 [Codex]** Freeze Qwen or perform the single allowed Claude 3 Haiku
  fallback test. **Done when:** one model and configuration are recorded for final
  validation; models will not be mixed.
- [x] **T009 [Codex]** Implement evidence intake, schema validation, forbidden-state
  rejection, evidence references, uncertainty, extraction records, and JSONL
  logging. **Done when:** clean, malformed, ambiguous, and forbidden-state unit
  tests pass.
- [x] **T010 [Codex]** Implement reviewer correct, approve, reject, and defer
  actions with immutable original output and recorded corrections. **Done when:**
  reviewer tests pass and one correction is visible in an audit record.
- [x] **T011 [Codex]** Implement the synthetic registry simulator for match,
  mismatch, not-found, and unavailable. **Done when:** it never calls the live
  registry and all four states have tests.
- [x] **T012 [Codex]** Implement the deterministic activation gate. **Done when:**
  approval plus match can activate and every missing prerequisite fails closed
  with a reason code.
- [x] **T013 [Codex]** Implement signed CareTrust JWT issuance, validation, expiry,
  status, and revocation using a local test key excluded from Git. **Done when:**
  valid, expired, tampered, and revoked tests pass.
- [x] **T014 [Codex]** Implement deterministic authorization for claim, audience,
  purpose, validity, and status. **Done when:** drafts and revoked claims produce
  zero permits in automated tests.
- [x] **T015 [Codex]** Complete the smallest end-to-end API or CLI vertical slice.
  **Done when:** one command or documented sequence demonstrates clean permit,
  mismatch denial, review deferral, revocation, and post-revocation denial.
- [x] **T016 [Codex]** Commit the vertical-slice milestone. **Done when:** the commit
  hash is recorded in the validation manifest.
- [x] **T017 [Codex]** Expand and freeze the final controlled fixture set.
  **Done when:** at least 20 predeclared cases meet the distribution in `spec.md`
  and have gold fields, uncertainty, review, registry, activation, and
  authorization expectations.
- [x] **T018 [Codex]** Freeze prompt, schema, model, inference settings, policy, and
  fixture hashes. **Done when:** a machine-readable run manifest is committed
  before final evaluation.
- [x] **T019 [Codex]** Implement the consecutive evaluation runner and metric
  calculator. **Done when:** it retains failures and calculates all metrics named
  in `spec.md` without manual result editing.
- [x] **T020 [Codex]** Run the final evaluation exactly once for the frozen
  configuration, repeating only if a configuration change creates a separately
  labeled full run. **Done when:** raw JSONL, run manifest, and summary metrics are
  saved.
- [x] **T021 [Codex]** Verify TRL 3 safety assertions. **Done when:** there are zero
  draft-based permits, zero activations without approval plus match, zero
  post-revocation permits, and detected signature tampering.
- [x] **T022 [Codex]** Generate the readable data-output-log report and limitations
  summary from actual results. **Done when:** every narrative metric traces to a
  raw run record.
- [x] **T023 [Codex]** Publish CareTrust schemas, reason codes, example requests,
  example decisions, and standards-status table. **Done when:** each artifact is
  labeled implemented, tested artifact, mapped, or planned.
- [x] **T024 [Codex]** Add a minimal accessible demonstration surface and capture
  judge-readable screenshots. **Done when:** uncertainty, human correction,
  activation status, authorization reason, and revocation are understandable
  without color alone.
- [x] **T025 [Codex]** Replace the placeholder README with setup, architecture,
  safety boundary, evaluation command, measured results, limitations, license,
  and submission-demo links. **Done when:** a reviewer can reproduce the tested
  path from a clean clone.
- [x] **T026 [Codex]** Run secret, dependency, unit, workflow, and reproducibility
  checks. **Done when:** results are saved and no real personal or health data is
  present.
- [ ] **T027 [Codex]** Tag the exact submission code and evidence state.
  **Done when:** an immutable version tag resolves to the commit referenced in the
  application.

## Deadline rule

If timing slips, omit optional OCR, general UI polish, full FHIR validation,
OID4VC runtime, federation runtime, wallets, and production identity proofing.
Never omit real model output, frozen gold labels, human/source gates,
deterministic safety tests, actual metrics, or honest limitations.
