# TRL 3 Proof of Concept - Design

## Controlling design

This file defines the current Track 2/v0.3 implementation decisions.
`trl3-poc-v0.2.0` remains
the frozen credential-focused baseline. `spec.md` defines required behavior and
`tasks.md` is the authoritative implementation backlog. v0.3 intentionally
expands the prototype into an inspectable care-trust network reference design;
aspirational edges are allowed only when their evidence class and missing work
are explicit. The primary product surface is the care-organization dashboard.
A synthetic mobile reference client is test/demo infrastructure only.

The architecture is split into three planes:

```text
AI compiler plane
  intent compiler | evidence compiler | app-onboarding compiler
          | draft artifacts + evidence + uncertainty only
          v
deterministic authority and policy plane
  review | relationship/delegation | status | authorize | revoke
          | canonical messages and receipts
          v
experience and adapter plane
  care-organization dashboard (primary)
  synthetic mobile reference client (test/demo)
  standards inspector + submission appendix
  optional MCP adapter over APIs
  future external OIDC/OAuth and OpenID Federation 1.0 topology
```

## Hero end-to-end flow

```text
care-organization dashboard opens one synthetic patient case
  -> multiple caregiver relationship/grant projections
  -> synthetic patient intent from reference client
  -> phrase spans + immutable intent hash
  -> provider-neutral intent ModelAdapter
  -> schema-valid DelegationDraft only
  -> deterministic clarification questions
  -> revised draft with preserved version history
  -> expiring, single-use patient invite + acceptance
  -> patient review and hash-bound approval
  -> separate CareRelationshipClaim + DelegationGrant
  -> independent App A / App B deterministic decisions
  -> invited relative supplies synthetic discharge scan
  -> AI drafts page/region/quote-linked coordination items only
  -> patient approves administrative intent; coordinator confirms routing
  -> clinical content remains blocked for accountable source review
  -> disjoint purpose-minimized Task candidates reach independent apps
  -> FHIR Consent/RelatedPerson/Provenance + OAuth RAR projections
  -> revocation
  -> fresh request denied; historical receipts retained
  -> dashboard and standards inspector render the same canonical receipts
```

Patient approval establishes only the locally profiled synthetic authority basis
for the bounded grant. It does not establish identity, capacity, MPOA,
guardianship, legal validity, clinical authority, or universal app access.

## Secondary legacy-evidence flow

```text
synthetic CNA image
  -> retained Amazon Textract OCR evidence
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

The actual retained Textract-to-Qwen trace and the deterministic complete
lifecycle are separate trace lineages unless a future same-input run genuinely
links them. The currently retained live Qwen draft has blocking findings and must
terminate visibly without activation.

## Technology decisions

| Layer | Decision |
|---|---|
| Runtime | Python 3.13, pinned to the declared project range |
| Primary interface | Integrated static care-provider operations console over generated multi-caregiver, compiler, authorization, FHIR, and federation artifacts; no field-outcome or deployed-organization claim |
| Reference client | Synthetic mobile client for message tests/demo only; not a production product |
| Schemas | Pydantic models with exported JSON Schema |
| Inference | Amazon Bedrock Converse through purpose-specific provider-neutral adapters |
| Primary model | `qwen.qwen3-32b-v1:0` in `us-west-2` |
| One-time fallback | `anthropic.claude-3-haiku-20240307-v1:0` |
| OCR | Provider-neutral evidence adapter; patient-provided packet on-ramp plus retained credential trace, never a source-authority decision |
| Storage | JSONL audit/evaluation records; in-memory synthetic registry and revocation seams |
| Signing | Compact EdDSA JWS/JWT profile with ephemeral local test keys |
| Policy | Deterministic Python functions with stable reason codes |
| Tests | pytest plus a consecutive batch-evaluation runner |
| Standards projections | Deterministic local FHIR R4 generators and contract-tested OAuth RAR/OID4VC artifacts |
| Network horizon | Local OpenID Federation-shaped trust simulation plus explicitly planned distributed deployment |
| External authentication | Standards-based OIDC/OAuth server and IdP are planned deployment dependencies, not Phase 1 implementations |
| Optional agent adapter | CareTrust MCP tools over the same APIs; planned and non-authority-bearing initially |
| Standards repository | Separate Apache-2.0 `caretrust-spec` public draft; published at `https://github.com/caretrust-hub/caretrust-spec`, initial commit `56ff896` |

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

### Intent evidence and model adapter

Stores the exact synthetic utterance, language, content hash, phrase spans, and
version. The intent adapter receives only a governed action/resource vocabulary
and a strict output schema. It may create an evidence-linked draft and material
uncertainties; it cannot approve, activate, widen, infer legal authority, or
decide application access.

### Clarification service

Turns structured uncertainty into bounded questions. Material questions block
invite and approval. Answers produce a new immutable draft version while the
original intent, model response, draft hash, and changes remain inspectable.

### Invite and acceptance service

Creates a nonce-bearing, expiring, single-use synthetic invite. Only a recipient
hint hash is retained. Acceptance proves control of a synthetic account in this
prototype; it is not identity proofing or relationship/authority verification.

### Patient review and approval service

Presents “you said / CareTrust interpreted / excluded” and allows the patient to
narrow or correct the draft. Approval binds the exact final draft, intent,
clarification, invite acceptance, approving account, and timestamp. Any mutation
after approval invalidates the approval record.

### Relationship and delegation activation

Creates two different artifacts:

- `CareRelationshipClaim` records the locally asserted relationship and its
  authority basis/period.
- `DelegationGrant` records only allowed actions, data/resource categories,
  audiences, purposes, exclusions, and validity.

Exclusions win. Unknown vocabulary fails closed. Revoking a grant does not erase
the relationship claim; the two lifecycles remain independent.

### Evidence intake

Stores a synthetic artifact identifier, content hash, document type, OCR text, and
source spans. It never labels the evidence as verified.

### Model adapter

Accepts the normalized extraction request and draft JSON Schema. It returns the raw
provider response, token/latency metadata, and a candidate structured result. No
provider-specific fields escape this boundary.

### AI compiler plane

The compiler plane has three purpose-specific, provider-neutral adapters:

- **Intent compiler:** patient language to an evidence-linked delegation draft
  and bounded clarification candidates.
- **Evidence compiler:** OCR/document text to evidence-linked credential or care
  coordination candidates.
- **Application-onboarding compiler:** application documentation and policy
  descriptions to a draft registration/profile and requested claim vocabulary.

All compiler outputs are untrusted drafts. Every material output binds source
evidence, compiler/model configuration, schema version, uncertainty, and a
content hash. A compiler cannot create or widen a relationship or grant, approve
review, activate/sign a trust artifact, issue status, return an authorization
permit, or revoke anything. Credential inference has `retained_aws` evidence;
uploaded-care extraction is a `contract_tested` deterministic replay; intent and
application-onboarding compiler executions remain `planned`.

### Deterministic authority and policy plane

Accountable actors and deterministic services own every authority-bearing
transition. They validate schemas and hashes, bind patient/reviewer action,
activate separate relationship/grant/credential artifacts, evaluate
audience/purpose/action/data/time/status, emit stable reason codes, and append
revocation/status events. This plane never calls an LLM to decide authority or
access. Current credential, delegation, uploaded-care, and fresh-denial behavior
is `executed_local`; production identity, legal, clinical, and external
authorization-server decisions are not represented.

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

The delegation policy additionally evaluates requested action, resource/data
category, explicit exclusions, audience, purpose, period, approval binding, and
grant status. Patient approval is necessary but not sufficient: each application
retains its own policy.

### Trace service

Emits append-only envelopes containing sequence, actor, receiver, trust boundary,
message type, exact payload, evidence class, standards/profile references,
linked IDs, and hashes. Browser receipts and message inspectors consume this
artifact directly. Historical permits are never overwritten by later revocation
or denial events.

### Standards projection service

Projects a native approved grant into:

- FHIR R4 `RelatedPerson` for the relationship representation;
- FHIR R4 `Consent` for patient choices, actors, actions, purposes, exclusions,
  and period under a local CareTrust profile;
- FHIR R4 `Provenance` for the source intent, approval, grant, and projection;
- a locally defined OAuth RAR `authorization_details` type for a fine-grained
  authorization contract.

Every projection produces semantic-loss accounting. FHIR output is generated and
locally tested but is not an HL7 conformance result or EHR exchange. The RAR
object is contract-tested; no authorization server, access token, or enforcement
flow is deployed.

### Network explorer

Provides three synchronized lenses: `Now — local prototype`, `Phase 2 — one
operator/two real apps`, and `Network — neutral federated trust domains`. Future
edges expose concrete candidate messages and standards gaps but cannot use the
visual treatment or language of executed edges. OID4VC, FHIR, and federation
artifacts are never presented as one executed distributed transaction.

### Care-organization dashboard and application trust gateway

The Track 2 reference deployment has one accountable care-organization dashboard
and many independent applications. This is the primary product and judging
surface. The dashboard manages human work: referrals, evidence
readiness, invitations, policy review, exceptions, trust records, application
registration, receipts, and revocation. The trust gateway exposes open claim,
status, request, decision, and metadata contracts. It does not require a mobile
app to share the operator's internal database or receive underlying evidence.

The canonical case supports one patient and multiple caregivers. Care-team and
permission views are projections derived from `CareRelationshipClaim`,
`DelegationGrant`, professional/legal evidence where applicable, status events,
and fresh application decisions. The UI cannot hand-edit an “allowed” flag
outside those artifacts. The current repository proves a one-patient,
three-care-context case with family, agency-CNA, and community-respite
permission lifecycles, fresh deterministic decisions, and a generated dashboard
projection. The browser console is a synthetic presentation layer, not an
operational organization deployment.

The initial organization scenario is modeled after the public service pattern of
ALU LIKE's Native Hawaiian Caregiver Support Program: an organization connects
family caregivers with information, supportive-service access, counseling/
support/training referrals, respite, and supplemental services while applying
its own eligibility rules. This is an illustrative reference only, not an
endorsement or partnership. See
`docs/use-cases/alulike-caregiver-support-reference-scenario.md`.

### Patient/case navigator

The operator console projects one append-only trust trace into three linked
views rather than maintaining three competing sources of truth:

- **Care team roster:** people and organizations, role/relationship basis,
  issuer, validity, status, and provenance.
- **Permission matrix:** grantee × application × action/data category/purpose,
  including exclusions, expiry, status, and the latest app-local decision.
- **Case history:** ordered intent, clarification, invitation, acceptance,
  evidence, approval, claim, decision, correction, expiration, and revocation
  events.

Every projection preserves stable IDs back to the exact trace envelope and raw
JSON available to the operator's role. Corrections append superseding events;
revocation changes fresh authorization state without deleting history. The
navigator is a CareTrust trust/service-coordination record, not a clinical chart.

FHIR `CareTeam` is a candidate outward projection of participating people and
organizations. `RelatedPerson`, `Consent`, and `Provenance` retain their narrower
meanings. `AuditEvent` is a candidate security-event projection. `Task`,
`ServiceRequest`, and `EpisodeOfCare` remain planned profiling work; the native
trace is authoritative for the v0.3 case history.

### Synthetic mobile reference client

The reference client exists only to exercise patient/caregiver invite,
acceptance, approval, upload, status, and revocation messages against the same
APIs used by the dashboard. It stores no independent authority state and is not
the Track 2 product, a production identity wallet, or a distributed app claim.
Its implementation and UI remain `planned`/external mockup work.

### Patient-provided care-packet on-ramp

The near-term clinical-information workflow begins with a patient or invited
relative loading a built-in synthetic discharge packet or phone scan. CareTrust
retains the original artifact hash, uploader/account context, timestamps,
sensitivity classification, and malware/file-validation state. An AI adapter may
draft candidate follow-up appointments, instructions, medication-list changes,
warning-sign text, and coordination tasks only when every value links to an exact
page/region/text span.

AI output is neither a verified clinical fact nor a care instruction. An
accountable reviewer confirms transcription against the source, corrects or
defers ambiguous items, and selects which reviewed items may be disclosed to
which application and purpose. Reviewing the transcription does not establish
that the document was authored by the named hospital, is clinically correct, or
is current. The original packet remains restricted and is not sent to apps by
default.

FHIR `DocumentReference` and `Provenance` are candidate outward projections for
the indexed packet and its derivation. `Task`, `CarePlan`, medication resources,
or other clinical resources remain draft/planned unless an accountable clinical
workflow establishes their semantics. The CareTrust native trace remains the
authority for item review and disclosure receipts in v0.3.

### Long-term HIE/EHR clinical-data edge

The network architecture permits an HIE or EHR to act as a separate clinical
data resource server. CareTrust presents the patient-approved delegation,
purpose, audience, requested action/data categories, status, and provenance.
The HIE/EHR remains responsible for patient matching, participant agreements,
app/client registration, applicable consent and disclosure rules, minimum-
necessary filtering, auditing, and the final data decision.

For v0.3 this remains secondary technical evidence: a synthetic local adapter
only, with participant/client/authorized-user gates, a FHIR request/response
fixture, a data-holder policy receipt, and fail-closed examples. It does not
appear as the primary care workflow. Hawaiʻi HIE is a plausible long-term
discovery/integration stakeholder, not a connected or endorsing party.

### OpenID Federation 1.0 multi-hub topology

The future network uses OpenID Federation 1.0 metadata and trust chains for
discovering CareTrust hubs, applications, issuers, and policy metadata. Trust
anchors and entity statements establish bounded metadata trust only. They do not
carry patient consent, activate caregiver authority, or force disclosure.

Each hub, application, and data holder retains its own deterministic policy,
participant/client eligibility, patient match, minimum-necessary, status, and
revocation checks. Current evidence is a two-entity, one-process
`local_simulation`; key rotation, expiry, trust marks, multi-hub discovery, and
independent network exchange remain `planned`.

### Optional CareTrust MCP adapter

MCP is an optional agent-facing adapter over the normal CareTrust APIs and
canonical contracts, never the core interoperability protocol. The initial tool
allowlist is:

- `draft` — create an explicitly non-authoritative compiler draft;
- `read` — retrieve role/purpose-filtered artifacts and receipts;
- `validate` — validate shape, linkage, status, and requested scope;
- `simulate` — return a non-binding policy simulation with reason codes.

Initial MCP tools cannot approve, activate, sign, authorize, revoke, or mutate an
authority-bearing artifact. Any future mutation tool would require separate
governance, strong authentication, accountable confirmation, idempotency, audit,
and deterministic API enforcement. No MCP implementation exists today.

### Standards inspector and submission appendix

The judge-facing inspector synchronizes a workflow step with the exact message,
contract, actor/receiver, trust boundary, evidence status, standard reference,
CareTrust profile constraint, candidate gap, semantic loss, and explicit
non-claim. It consumes the canonical trace and schemas; it does not maintain
workflow state.

The standards/auth submission appendix has been generated locally in Markdown
and DOCX. The integrated provider console and exact-message inspector consume
retained local artifacts and are browser-tested. They demonstrate synthetic
workflow integration only; public deployment, production connections, and
measured workforce outcomes remain planned.

### Separate public-draft standards repository

`C:\Users\mike\Documents\caretrust-spec` is the Apache-2.0 standards-facing
working tree, published at `https://github.com/caretrust-hub/caretrust-spec`
from initial commit `56ff896`, for Core, profiles, schemas, examples, conformance design,
governance, and gap register. It clearly separates unchanged base standards,
CareTrust constraints at extension points, and candidate missing semantics.
Basic JSON/link validation has executed locally. The repository has zero commits,
zero remotes, and is not published; it therefore supports no adoption,
endorsement, or conformance claim.

### Evaluation service

Runs frozen fixtures consecutively, retains failures, calculates metrics, and emits
machine-readable JSONL plus a human-readable summary.

## State model

### Delegation lane

```text
intent_received
  -> draft_created | draft_failed
  -> clarification_required | draft_ready_for_invite
  -> invite_created
  -> invite_accepted | invite_expired | invite_replayed | recipient_mismatch
  -> patient_approved | approval_withdrawn
  -> relationship_active + delegation_active | activation_denied
  -> app_permit | app_deny
  -> delegation_revoked | delegation_expired
  -> fresh_request_denied
```

### Credential lane

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
POST /api/intents
POST /api/intents/{intent_id}/draft
POST /api/drafts/{draft_id}/clarifications
POST /api/invites
POST /api/invites/{invite_id}/accept
POST /api/delegations/{draft_id}/approve
GET  /api/relationships/{relationship_id}
GET  /api/delegations/{grant_id}
POST /api/delegations/{grant_id}/authorize
POST /api/delegations/{grant_id}/revoke
GET  /api/traces/{trace_id}
GET  /api/traces/{trace_id}/projections/fhir-r4
GET  /api/traces/{trace_id}/projections/oauth-rar
POST /api/evaluation/run
GET  /api/evaluation/runs/{run_id}
```

This HTTP surface is a Phase 2 integration target, not an implemented Phase 1
claim. The tested Phase 1 CLI calls the same domain functions directly, and the
browser demonstration is a dependency-free communication surface with no live
backend.

A production deployment is expected to place a standards-based external
OIDC/OAuth authorization server and IdP in front of these APIs. No such server,
token endpoint, dynamic client registration, user federation, or production IdP
is implemented in Phase 1. The optional MCP adapter calls these APIs after normal
authentication/authorization; it does not bypass them.

## CareTrust Core 0.1 normalization target

Core 0.1 is intentionally smaller than the current workflow model:

| Core contract | Minimum responsibility |
|---|---|
| `MessageEnvelope` | Versioned sender, receiver, time, purpose, linked IDs, payload type/hash, evidence/provenance references |
| `TrustArtifact` | Common artifact identity, subject/issuer, type, validity, status reference, provenance, integrity |
| `AuthorizationRequest` | Requester, subject, audience, purpose, requested action/data/artifacts, context, request time |
| `AuthorizationDecision` | Permit/deny, stable reasons, minimum projection, policy version, supporting artifacts, decision time |
| `StatusEvent` | Append-only transition, actor, reason, effective time, supersession, target artifact |
| `CareRelationshipClaim` | Relationship assertion/basis/period/provenance without application permission |
| `DelegationGrant` | Patient-approved allow/exclude scope, purpose, audience, period, status, relationship/approval bindings |

These seven contracts are `planned`; current `TraceEnvelope`, credential,
delegation, uploaded-care, clinical-edge, and projection schemas are experimental
profiles pending normalization. A profile may add fields but cannot change Core
meaning. Migration mappings must state represented, omitted, and extended
semantics before a current schema is called Core-compatible.

## Proposed repository layout

```text
src/caretrust/
  models.py
  delegation.py
  delegation_policy.py
  trace.py
  delegation_projections.py
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
../caretrust-spec/
  spec/
  profiles/
  schemas/
  examples/
  conformance/
  governance/
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

The published public-draft CareTrust Core 0.1 is exactly `MessageEnvelope`, `TrustArtifact`,
`AuthorizationRequest`, `AuthorizationDecision`, `StatusEvent`,
`CareRelationshipClaim`, and `DelegationGrant`. Current workflow contracts are
experimental profiles until normalization is complete. FHIR, W3C VC, OID4VC,
and OpenID Federation remain unchanged external standards used through mappings,
profiles, or validator-tested artifacts; CareTrust does not redefine them.

For v0.3, FHIR R4 `Consent` and `RelatedPerson` are complementary representations,
not substitutes: a relationship record is not an authorization grant. OAuth RAR
supplies the `authorization_details` transport grammar, but CareTrust must define
and govern its caregiver-delegation type. OpenID4VP/DCQL is a candidate future
presentation rail. OpenID Federation 1.0 is used only by the local
metadata-trust laboratory today and is the planned multi-hub topology. It does
not authorize a caregiver, carry patient consent, or override any
hub/application/data-holder local policy.

## Security and privacy boundary

- Only synthetic evidence is sent to Bedrock.
- Test signing keys are generated locally and excluded from Git.
- AWS credentials are resolved by the SDK and never written to logs.
- Estimated cumulative Bedrock spend is checked before batch execution.
- Logs redact secrets and avoid raw environment configuration.
- Error messages disclose no credential evidence beyond the synthetic test case.
- Model output is untrusted input and is schema-validated before persistence.
