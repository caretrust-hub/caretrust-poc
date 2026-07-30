# TRL 3 Proof of Concept - Specification

## Intent

Demonstrate in a controlled environment that an AI-assisted credential-intake
workflow can reduce repeated direct-care workforce administration without allowing
AI output to become verified authority or application access.

The proof of concept uses a fully synthetic Hawaii Certified Nurse Aide credential
pattern. The broader CareTrust federation, representative-authority, identity
proofing, and multi-application ecosystem remain future architecture.

## Primary outcome

A synthetic CNA credential is converted into an evidence-linked draft by an Amazon
Bedrock model, reviewed by a human, matched by a synthetic source-registry
simulator, activated as a signed claim, evaluated by deterministic authorization,
revoked, and then denied on the next authorization request.

## Actors

- **Direct care worker:** supplies credential evidence and reviews extracted data.
- **Authorized reviewer:** corrects, approves, or rejects a draft.
- **Issuing-source simulator:** returns match, mismatch, not-found, or unavailable.
- **Care application:** requests a minimum set of claims for a stated purpose.
- **CareTrust services:** preserve evidence, enforce state transitions, sign claims,
  evaluate policy, and record audit events.

## Functional requirements

- [x] **REQ-001 - Synthetic intake:** Accept a synthetic Hawaii CNA document or
  frozen OCR text plus document metadata.
- [x] **REQ-002 - Provider-neutral inference:** Invoke the selected Bedrock model
  through a replaceable `ModelAdapter` contract.
- [x] **REQ-003 - Structured draft:** Require model output to validate against the
  published draft-claim JSON Schema.
- [x] **REQ-004 - Evidence linkage:** Associate each material extracted field with
  source text or a source-region reference.
- [x] **REQ-005 - Uncertainty:** Represent confidence, missing fields,
  contradictions, unsupported issuers, ambiguous dates, and unreadable evidence
  explicitly.
- [x] **REQ-006 - No model activation:** Reject or ignore any model attempt to set
  verified, active, registry-matched, or authorized state.
- [x] **REQ-007 - Human review:** Allow an authorized reviewer to correct, approve,
  reject, or defer a draft while preserving the original output and changes.
- [x] **REQ-008 - Source verification:** Simulate source responses of `match`,
  `mismatch`, `not_found`, and `unavailable` without accessing the live Hawaii
  registry.
- [x] **REQ-009 - Safe activation:** Activate only a schema-valid, human-approved,
  unexpired draft with an authoritative simulated match.
- [x] **REQ-010 - Signed claim:** Create a tamper-evident, signed CareTrust claim
  with issuer, subject, credential type, jurisdiction, validity, status, and
  evidence references.
- [x] **REQ-011 - Deterministic authorization:** Evaluate active status, requested
  claim, audience, purpose, time bounds, and revocation without an LLM decision.
- [x] **REQ-012 - Revocation:** Change claim status and deny subsequent requests
  with a stable reason code.
- [x] **REQ-013 - Auditability:** Record model configuration, prompt/schema
  versions, evidence, review action, source result, activation, authorization, and
  revocation in structured logs.
- [x] **REQ-014 - Evaluation:** Run a frozen consecutive evaluation set and retain
  every result, including failures.
- [x] **REQ-015 - Interoperability artifacts:** Publish the CareTrust JSON schemas,
  API contracts, reason codes, claim-status semantics, and a documented mapping to
  relevant healthcare and credential standards.
- [x] **REQ-016 - Minimal demonstration:** Provide a reproducible API, CLI, or
  minimal accessible interface that exposes the end-to-end workflow.

## Safety requirements

- [x] **SAFE-001:** A draft can never satisfy authorization policy.
- [x] **SAFE-002:** Human approval without a source match cannot activate a claim.
- [x] **SAFE-003:** A source match without human approval cannot activate a claim.
- [x] **SAFE-004:** Expired, rejected, mismatched, unavailable, revoked, or
  signature-invalid claims cannot authorize access.
- [x] **SAFE-005:** Model output cannot overwrite source-verification or reviewer
  records.
- [x] **SAFE-006:** Prompt injection or text embedded in evidence cannot change the
  system contract or produce active state.
- [x] **SAFE-007:** Logs and fixtures contain no real credentials, PHI, secrets, or
  production identifiers.

## Non-functional requirements

- [x] **NFR-001 - Reproducibility:** Pin runtime and dependency versions and record
  model ID, region, inference settings, prompt hash, schema hash, fixture hash,
  token usage, latency, and estimated cost.
- [x] **NFR-002 - Inspectability:** Keep schemas, policy, reason codes, fixtures,
  evaluation logic, and model-adapter interface public and readable.
- [x] **NFR-003 - Portability:** No downstream component may depend on
  provider-specific model output outside the adapter boundary.
- [x] **NFR-004 - Accessibility:** Critical status, uncertainty, corrections, and
  denial reasons must be available as text and usable without color alone.
- [x] **NFR-005 - Failure handling:** Provider errors, malformed output, schema
  failures, and unavailable verification must fail closed and remain visible.
- [x] **NFR-006 - Cost observability:** Report actual Bedrock use and estimated cost
  for the smoke and final evaluation runs. Stop before estimated cumulative
  Phase 1 inference spend exceeds $10 unless the team leader explicitly approves a
  higher ceiling.

## TRL 3 acceptance criteria

The prototype is acceptable for a TRL 3 claim only when all of the following are
true:

- [x] A real Bedrock inference produces a saved, schema-validated draft from
  synthetic evidence.
- [x] One clean case completes intake through signed claim and permitted request.
- [x] At least one ambiguous or incomplete case is routed to human review.
- [x] At least one registry mismatch is blocked.
- [x] Automated tests prove zero permits from drafts.
- [x] Automated tests prove zero permits after revocation.
- [x] Signature tampering is detected.
- [x] The final run uses one frozen model, prompt, schema, policy, and fixture set.
- [x] The final run contains a target of 40 cases and no fewer than 20 predeclared
  controlled cases.
- [x] Raw JSONL logs and calculated summary metrics are retained.
- [x] Results distinguish observations from targets and disclose limitations.

## Completion evidence

Checked items above are supported by executable or retained evidence, not by
design intent alone:

| Requirement group | Primary evidence |
|---|---|
| Intake, draft schema, evidence links, uncertainty, and forbidden state | `src/caretrust/models.py`, `src/caretrust/workflow.py`, `tests/test_models.py`, `tests/test_workflow.py` |
| Provider-neutral inference and failure retention | `src/caretrust/adapters/bedrock.py`, `src/caretrust/evaluation.py`, `tests/test_bedrock_adapter.py`, `tests/test_evaluation.py` |
| Human review, source simulation, and activation | `src/caretrust/workflow.py`, `tests/test_workflow.py`, `artifacts/validation/vertical-slice.json` |
| Signing, deterministic authorization, tamper detection, and revocation | `src/caretrust/security.py`, `src/caretrust/authorization.py`, `tests/test_security_authorization.py` |
| Frozen model evaluation, raw logs, metrics, cost, and limitations | `artifacts/evaluation/20260730T085655.959974Z/`, `artifacts/validation/release-readiness.json` |
| Interoperability contracts and precise standards boundary | `schemas/`, `docs/standards/`, `tests/test_interoperability_artifacts.py` |
| Accessible text-first demonstration and browser record | `demo/`, `tests/test_demo.py`, `artifacts/validation/demo-browser-qa-screenshots.json` |
| Synthetic-only data and public-repository checks | `tests/test_final_fixtures.py`, `tests/test_interoperability_artifacts.py`, `artifacts/validation/release-readiness.json` |

The checked accessibility item means the critical prototype states are
keyboard-operable and conveyed in text without color alone. It is not a claim of
formal WCAG conformance or usability validation with caregivers.

## Evaluation scenarios

The minimum 20-case final set must be frozen before the consecutive run:

| Scenario group | Minimum |
|---|---:|
| Clean and harmless layout/text variations | 10 |
| Missing, cropped, or ambiguous fields | 4 |
| Unsupported issuer, mismatch, expiration, or unavailable source | 4 |
| Prompt-injection or forbidden-state attempts | 2 |

Report field precision, recall, and F1; exact-record match; uncertainty recall;
false-clear rate; reviewer corrections; latency; token usage; estimated cost;
false active claims; policy accuracy; and false permits.

## Standards posture

The POC may implement or publish:

- a CareTrust-defined JSON claim and signed JWT;
- a mapping to FHIR `Practitioner` and `Practitioner.qualification`;
- a mapping to W3C Verifiable Credentials Data Model 2.0;
- illustrative OID4VCI/OID4VP configuration or request artifacts;
- illustrative OpenID Federation entity metadata.

Only tested behavior may be called implemented. Mappings and illustrative artifacts
must not be described as full protocol conformance.

## Explicitly out of scope

- Real identity proofing, biometrics, or driver-license verification.
- Live Hawaii registry automation, scraping, or CAPTCHA bypass.
- Real PHI, production credentials, or care-recipient data.
- Medical power-of-attorney interpretation or activation.
- Production wallet, OID4VC issuance/presentation, UMA, SMART, or Shared Signals.
- Two-hub federation runtime.
- Universal or instantaneous invalidation of already issued access tokens.
- Production security certification, high availability, or legal determinations.

## Edge cases

- Multiple dates with no labeled expiration date.
- Name variation or OCR confusion.
- Missing identifier or cropped restriction.
- Unsupported or inconsistent issuer.
- Credential expired between review and activation.
- Registry unavailable after human approval.
- Model returns prose or malformed JSON.
- Model inserts `verified`, `active`, or `authorized`.
- Evidence contains instructions addressed to the model.
- Claim is revoked between two application requests.
- Signed claim payload is altered after issuance.
