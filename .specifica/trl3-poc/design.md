# TRL 3 Proof of Concept - Design

## Controlling design

This file defines the implementation decisions for the deadline-critical proof of
concept. `spec.md` defines required behavior. `tasks.md` is the authoritative
implementation backlog. Broader CareTrust plans are informative and must not add
scope unless this design and its task list are deliberately changed.

## End-to-end flow

```text
synthetic CNA evidence
  -> fixed OCR text or optional local OCR
  -> Bedrock ModelAdapter
  -> schema validation
  -> evidence-linked DraftCredentialClaim
  -> reviewer correct / approve / reject / defer
  -> synthetic registry match / mismatch / unavailable
  -> deterministic activation gate
  -> signed active claim
  -> deterministic authorization decision
  -> revocation
  -> subsequent authorization denied
```

## Technology decisions

| Layer | Decision |
|---|---|
| Runtime | Python 3.13, pinned to the declared project range |
| Interface | Dependency-free static demonstration plus CLI vertical slice |
| Schemas | Pydantic models with exported JSON Schema |
| Inference | Amazon Bedrock Converse through `ModelAdapter` |
| Primary model | `qwen.qwen3-32b-v1:0` in `us-west-2` |
| One-time fallback | `anthropic.claude-3-haiku-20240307-v1:0` |
| OCR | Fixed synthetic OCR text first; PaddleOCR only if it does not threaten gates |
| Storage | JSONL audit/evaluation records; in-memory synthetic registry and revocation seams |
| Signing | Compact EdDSA JWS/JWT profile with ephemeral local test keys |
| Policy | Deterministic Python functions with stable reason codes |
| Tests | pytest plus a consecutive batch-evaluation runner |

## Model-selection gate

1. Build one adapter contract and one draft JSON Schema.
2. Run the same five frozen smoke fixtures through Qwen3 32B.
3. Accept Qwen only if it returns schema-valid, evidence-linked drafts, flags
   uncertainty safely, and has acceptable observed latency and cost.
4. If Qwen fails, run the same five fixtures once through Claude 3 Haiku.
5. Freeze the first passing model.
6. Never mix models in the reported final run.

The final evidence record contains model ID, region, API, inference settings, usage,
latency, estimated cost, prompt hash, schema hash, and fixture hashes.

The default Phase 1 Bedrock inference ceiling is $10. Pause for team-leader
approval before a planned run would exceed that cumulative estimate.

## Component boundaries

### Evidence intake

Stores a synthetic artifact identifier, content hash, document type, OCR text, and
source spans. It never labels the evidence as verified.

### Model adapter

Accepts the normalized extraction request and draft JSON Schema. It returns the raw
provider response, token/latency metadata, and a candidate structured result. No
provider-specific fields escape this boundary.

### Extraction service

Validates structured output, rejects forbidden state, attaches evidence references,
and creates an immutable extraction-run record plus a draft claim.

### Review service

Records the reviewer identity or synthetic role, decision, corrections, reason, and
timestamp without altering the original model response.

### Registry simulator

Returns a content-hashed synthetic result of `match`, `mismatch`, `not_found`,
or `unavailable`. It models the public verification workflow without contacting
the live registry. The hash supports local trace comparison; it is not a source
signature or production authentication claim.

### Activation service

Creates an active claim only when:

```text
schema_valid
AND reviewer_decision == approved
AND registry_result == match
AND credential_not_expired
AND no_unresolved_blocking_issue
```

### Claim service

Signs a CareTrust-defined JWT claim, validates signature and status, and records
revocation. The claim is not called a W3C Verifiable Credential unless a selected
VC securing method is actually implemented and tested.

### Authorization service

Evaluates deterministic policy against the request and active claim. It emits
`permit` or `deny` plus stable reason codes. The LLM is not invoked.

### Evaluation service

Runs frozen fixtures consecutively, retains failures, calculates metrics, and emits
machine-readable JSONL plus a human-readable summary.

## State model

```text
evidence_received
  -> extraction_succeeded | extraction_failed
  -> draft_pending_review
  -> approved | corrected | rejected | deferred
  -> source_match | source_mismatch | source_not_found | source_unavailable
  -> active | activation_denied
  -> revoked | expired
```

Only `active` can be considered by authorization. Revoked and expired are terminal
for new requests.

## Future service API surface

```text
POST /api/evidence
POST /api/evidence/{evidence_id}/extract
GET  /api/drafts/{draft_id}
POST /api/drafts/{draft_id}/review
POST /api/drafts/{draft_id}/registry-check
POST /api/drafts/{draft_id}/activate
GET  /api/claims/{claim_id}
POST /api/claims/{claim_id}/revoke
POST /api/authorize
POST /api/evaluation/run
GET  /api/evaluation/runs/{run_id}
```

This HTTP surface is a Phase 2 integration target, not an implemented Phase 1
claim. The tested Phase 1 CLI calls the same domain functions directly, and the
browser demonstration is a dependency-free communication surface with no live
backend.

## Proposed repository layout

```text
src/caretrust/
  models.py
  adapters/bedrock.py
  workflow.py
  security.py
  authorization.py
  evaluation.py
schemas/
fixtures/cna/
tests/
demo/
scripts/run_evaluation.py
artifacts/
.specifica/
```

Generated logs containing only synthetic data may be committed under a clearly
labeled reproducibility directory. Local secrets, AWS profiles, environment files,
and private submission artifacts are ignored.

## Key reason codes

- `DRAFT_NOT_ACTIVE`
- `REVIEW_REQUIRED`
- `REVIEW_REJECTED`
- `SOURCE_MISMATCH`
- `SOURCE_NOT_FOUND`
- `SOURCE_UNAVAILABLE`
- `CREDENTIAL_EXPIRED`
- `UNRESOLVED_BLOCKING_ISSUE`
- `CLAIM_REVOKED`
- `SIGNATURE_INVALID`
- `AUDIENCE_MISMATCH`
- `PURPOSE_NOT_ALLOWED`
- `CLAIM_NOT_REQUESTED`

## Evaluation design

- Freeze fixtures, expected values, expected uncertainty, prompt, schema, policy,
  and model before the final run.
- Use one consecutive run with no cherry-picking.
- Preserve the raw model response and parsed result for every case.
- Calculate metrics from machine-readable logs.
- Demonstrate at least one reviewer correction and two safe deferrals.
- Assert zero active claims without both approval and match.
- Assert zero authorization permits from drafts or revoked claims.
- Report all limitations and configuration changes.

## Standards boundary

CareTrust's interoperable core is the claim/evidence/status contract and deterministic
request/decision contract. FHIR, W3C VC, OID4VC, and OpenID Federation artifacts are
added as mappings or validator-tested artifacts only after the core tests pass.

## Security and privacy boundary

- Only synthetic evidence is sent to Bedrock.
- Test signing keys are generated locally and excluded from Git.
- AWS credentials are resolved by the SDK and never written to logs.
- Estimated cumulative Bedrock spend is checked before batch execution.
- Logs redact secrets and avoid raw environment configuration.
- Error messages disclose no credential evidence beyond the synthetic test case.
- Model output is untrusted input and is schema-validated before persistence.
