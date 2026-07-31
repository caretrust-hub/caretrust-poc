# TRL 3 Proof of Concept - Specification

## Intent

Demonstrate in a controlled environment that AI can translate messy caregiver
intent and legacy evidence into interoperable, evidence-linked **draft trust
artifacts** without allowing AI output to become identity, relationship, legal
authority, consent, a delegation grant, a verified credential, or application
access.

The Track 2 product hero is a **care-organization dashboard**, not a consumer
mobile application. An accountable organization uses one patient-centered case
view to coordinate multiple caregivers, inspect claim-derived permissions,
review AI-compiled intent/evidence, register applications, and see exact
authorization receipts. A synthetic mobile reference client may exercise patient
invite, approval, and revocation messages for test/demo purposes only; it is not
the primary product surface or a production patient app.

AI is a compiler plane: it converts natural-language intent, legacy evidence,
and future application-onboarding descriptions into evidence-linked drafts.
Only deterministic authority and policy services may approve, activate, sign,
authorize, revoke, or emit authority-bearing status. The Hawaii CNA credential
workflow remains a secondary legacy-credential lane and the v0.2 release remains
frozen evidence.

## Primary outcome

One synthetic patient utterance is converted into a phrase-linked delegation
draft by an Amazon Bedrock model. Material ambiguity blocks progress until a
bounded clarification is answered. A single-use synthetic invite is accepted,
the patient explicitly approves the final draft, and deterministic policy creates
separate relationship and delegation artifacts. One application may permit an
allowed action while another denies an excluded action. Revocation preserves
historical receipts and denies a fresh request.

The same dashboard case then receives a synthetic caregiver-uploaded discharge
packet. The
original hash and uploader provenance are retained. AI proposes only source-
linked coordination candidates; administrative items require patient approval
and organization routing, while medication and warning-sign content remains
blocked for accountable clinical-source review. Two apps receive disjoint
purpose-minimized projections and never receive the raw packet by default.

A second, visibly separate outcome retains the actual Textract-to-Qwen CNA intake
trace and correctly stops at its blocking draft. A deterministic credential
lifecycle demonstrates the later human/source/signature/policy mechanics without
claiming it is the same live AWS trace.

## Controlling architecture and current status — 2026-07-30

The following table reconciles product intent with current repository evidence.
Static browser surfaces remain presentation layers over retained artifacts; they
do not upgrade any underlying capability beyond its recorded evidence status.

| Capability | Controlling decision | Current evidence status and exact boundary |
|---|---|---|
| Track 2 surface | Care-organization dashboard is primary | Static provider-operations console is integrated and browser-tested; its generated dashboard and multi-caregiver inputs are `executed_local`, while measured organizational outcomes remain `planned` |
| Mobile | Synthetic reference client for tests and demos only | `planned`; no production mobile client or distribution claim |
| Case model | One patient may have multiple caregivers; dashboard permissions are derived from claims/grants and fresh app decisions | Three-context synthetic case, exact permit/deny decisions, assignment/credential/delegation status, and revocation tests are `executed_local` or explicitly `contract_tested` per row |
| AI compiler plane | Compile intent, evidence, and app-onboarding descriptions into draft artifacts with evidence/uncertainty | Credential OCR/Bedrock evidence and the frozen Smart40 are `retained_aws`; intent, app-onboarding, and uploaded-care compiler contracts and deterministic fallbacks are integrated and tested; all authority effects remain false |
| Deterministic authority and policy plane | Review, activation, authorization, status, and revocation only | Credential, delegation, uploaded-care policy, and fresh-denial paths are `executed_local`; no LLM authority decision |
| Core 0.1 | Normalize seven minimal contracts: `MessageEnvelope`, `TrustArtifact`, `AuthorizationRequest`, `AuthorizationDecision`, `StatusEvent`, `CareRelationshipClaim`, `DelegationGrant` | Schemas, examples, canonical hashes, and validator are `executed_local` in published `caretrust-spec` commit `56ff896`; POC runtime mappings are in progress |
| Existing workflow schemas | Preserve as experimental profiles until Core normalization and migration mappings exist | Mixed `executed_local`/`contract_tested`; presence does not make them stable Core contracts |
| Public standards draft | Separate Apache-2.0 `caretrust-spec` repository | Public at `https://github.com/caretrust-hub/caretrust-spec`, commit `56ff896`; 112 JSON and 25 Markdown files validate; no adoption, endorsement, certification, or external conformance claim |
| Federation | OpenID Federation 1.0 is the future multi-hub trust topology; each hub/application retains local policy | Two-entity, one-process laboratory is `local_simulation`; multi-hub network is `planned` |
| CareTrust MCP adapter | Optional adapter over the same APIs, not a core protocol | Local stdio JSON-RPC adapter contract, immutable inspection/simulation tools, and retained artifact are `executed_local`; no deployed remote MCP service |
| External authentication | Standards-based OIDC/OAuth server in deployment architecture | Synthetic OIDC-link, reviewed-registration, PKCE/RAR, fresh-decision, and token-receipt harness is `executed_local`; no production IdP or authorization server |
| Submission evidence | Standards/auth appendix plus judge-facing standards inspector | Appendix generation, provider dashboard, exact-message inspector, and eight-segment executable walkthrough are integrated; live deployment and field outcomes remain `planned` |

## Actors

- **Care recipient / patient account:** states intent, answers clarification,
  creates an invite, reviews the interpretation, approves or revokes a grant.
- **Invited caregiver account:** accepts a single-use synthetic invite; acceptance
  proves only control of the synthetic account, not identity or authority; may
  supply a patient-provided record when the active delegation allows it.
- **Program coordinator:** reviews transcription/routing readiness and routes
  approved administrative work; cannot clinically validate medication or
  warning-sign instructions.
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

### v0.3 functional requirements

- [ ] **REQ-017 - Intent evidence:** Preserve the exact synthetic patient
  utterance, character spans, content hash, language, and version history.
- [ ] **REQ-018 - Draft-only intent AI:** Translate only explicit actions,
  exclusions, purposes, audiences, data categories, actors, and periods into a
  strict draft; unknown or inferred authority is prohibited.
- [ ] **REQ-019 - Clarification gate:** Represent material ambiguity as bounded
  machine-readable questions and prevent invite/approval/activation until every
  blocking question is resolved.
- [ ] **REQ-020 - Patient invite:** Create an expiring, single-use invite with a
  nonce and hashed recipient hint; do not retain plaintext email or phone data.
- [ ] **REQ-021 - Explicit patient approval:** Bind approval to the exact intent,
  final draft, clarification, invite acceptance, patient account, and timestamp.
  Any later mutation invalidates approval.
- [ ] **REQ-022 - Separate trust artifacts:** Maintain distinct relationship,
  consent/approval, delegation, professional credential, and legal-document
  evidence semantics and lifecycles.
- [ ] **REQ-023 - Least-privilege delegation:** Activate only allowlisted actions,
  resource/data categories, audiences, purposes, and periods; explicit exclusions
  always win.
- [ ] **REQ-024 - Independent apps:** Execute distinct local request/decision
  policies against the same grant and retain complete append-only receipts.
- [ ] **REQ-025 - Exact technical trace:** Drive the walkthrough from the same
  messages used by domain state and expose actor, receiver, trust boundary,
  contract, standard/profile, hashes, IDs, verification, and exact JSON.
- [ ] **REQ-026 - Standards projections:** Deterministically project an approved
  delegation into locally profiled FHIR R4 `RelatedPerson`, `Consent`, and
  `Provenance`, plus a contract-tested OAuth RAR `authorization_details` object,
  with a machine-readable semantic-loss report.
- [ ] **REQ-027 - Network explorer:** Show executed-local, contract-tested,
  local-simulation, mapped-only, and planned seams without presenting candidate
  OID4VC, FHIR, and federation artifacts as one executed distributed transaction.
- [ ] **REQ-028 - Standards gaps:** Publish a machine-readable registry of the
  caregiver semantics, profiles, extensions, governance, privacy controls, and
  conformance evidence still required.
- [ ] **REQ-029 - Patient/case navigator:** An authorized organization operator
  can browse a synthetic patient's care team, current and historical permissions,
  and append-only case history, then inspect the exact claims, requests,
  decisions, reason codes, and provenance behind each projection.
- [ ] **REQ-030 - Case data minimization:** Case views are purpose- and
  role-bounded; revoked records remain historical, corrections append rather
  than overwrite, and the UI states that CareTrust history is not a complete
  clinical chart.
- [ ] **REQ-031 - Patient-provided care packet:** An invited relative or patient
  can load a built-in synthetic discharge/medical-record scan; the system retains
  the original hash and uploader provenance, and AI produces only evidence-linked
  candidate coordination items with uncertainty and sensitivity labels.
- [ ] **REQ-032 - Reviewed item sharing:** An accountable reviewer can confirm,
  correct, defer, or reject each candidate item; independent applications receive
  only explicitly approved, purpose/audience-bounded items or decisions, not the
  complete packet by default. Revocation makes fresh requests deny without
  deleting historical receipts.
- [ ] **REQ-033 - Long-term clinical exchange seam:** Keep HIE/EHR connectivity in
  the planned network view. A retained local adapter may prove the authority
  boundary, but the primary walkthrough must state there is no live Hawaiʻi HIE
  connection and must not depict an informal caregiver directly querying an HIE.
- [ ] **REQ-034 - Organization-first Track 2 dashboard:** Make an accountable
  care-organization dashboard the primary product and demo surface. It must
  expose case roster, caregiver relationships, claim-derived permissions,
  review queues, application registry, exact receipts, revocation, and standards
  evidence without becoming a clinical chart.
- [ ] **REQ-035 - One patient/multiple caregivers:** Support at least two
  caregivers with independent relationship claims, delegation grants,
  exclusions, validity, and app decisions for one synthetic patient. Dashboard
  permissions must be derived from retained claims and fresh decisions, never
  hand-maintained UI flags.
- [ ] **REQ-036 - Synthetic mobile reference client:** Define a minimal reference
  client that emits/consumes the same invite, approval, status, and revocation
  messages as the APIs. It is test/demo infrastructure only and cannot be
  described as a production mobile product.
- [ ] **REQ-037 - AI compiler plane:** Define draft-only compilers for patient
  intent, document evidence, and application-onboarding descriptions. Compiler
  output must retain source evidence and uncertainty and cannot create or mutate
  authority-bearing state.
- [ ] **REQ-038 - Deterministic authority/policy plane:** All approval,
  activation, signing, authorization, status, and revocation transitions must
  be deterministic, versioned, fail closed, and independently testable without
  an LLM.
- [x] **REQ-039 - CareTrust Core 0.1:** Publish schemas and examples for exactly
  `MessageEnvelope`, `TrustArtifact`, `AuthorizationRequest`,
  `AuthorizationDecision`, `StatusEvent`, `CareRelationshipClaim`, and
  `DelegationGrant`, including stable IDs, versions, provenance, status, and
  referential-integrity rules.
- [ ] **REQ-040 - Experimental profile normalization:** Keep current credential,
  delegation, uploaded-care, clinical-edge, trace, and projection schemas as
  experimental workflow profiles until each maps to Core 0.1 with documented
  semantic loss and migration.
- [x] **REQ-041 - Separate public-draft repository:** Create and publish Apache-2.0
  `caretrust-spec` with specification, profiles, schemas, examples,
  conformance, governance, and gap register. Current evidence is public commit
  `56ff896` at `https://github.com/caretrust-hub/caretrust-spec`; publication
  does not imply adoption, endorsement, certification, or independent conformance.
- [ ] **REQ-042 - OpenID Federation 1.0 topology:** Specify future hub metadata,
  trust anchors, entity statements, trust marks, key rotation, expiry, and
  discovery while preserving the rule that federation establishes metadata
  trust only; every hub/data holder/application makes its own policy decision.
- [ ] **REQ-043 - Optional CareTrust MCP adapter:** Expose `draft`, `read`,
  `validate`, and `simulate` tools over the normal CareTrust APIs. MCP is not the
  core protocol. Initial tools are read/draft/simulation only and must not
  approve, activate, authorize, revoke, or otherwise mutate authority state.
- [ ] **REQ-044 - Standards inspector and submission appendix:** Link each
  walkthrough stage to exact messages, contracts, evidence status, unchanged
  base standards, CareTrust profile constraints, candidate gaps, and non-claims.
  The generated appendix exists locally; the integrated inspector remains
  planned/in progress.
- [ ] **REQ-045 - External auth boundary:** Treat a standards-based external
  OIDC/OAuth authorization server and IdP as planned deployment dependencies,
  not Phase 1 implemented components.

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
- [ ] **SAFE-008:** AI cannot approve intent, resolve material ambiguity, create or
  widen a relationship/delegation, or return an application permit.
- [ ] **SAFE-009:** Invite acceptance alone cannot prove identity, relationship,
  consent, MPOA, guardianship, or legal authority.
- [ ] **SAFE-010:** Unknown actions, resources, audiences, purposes, or RAR types
  fail closed; an explicit exclusion cannot be overridden by a broader allow.
- [ ] **SAFE-011:** Patient approval is necessary but not sufficient for an
  application permit; application-local policy remains independent.
- [ ] **SAFE-012:** Revoking a delegation denies fresh requests without silently
  erasing the separate relationship record or claiming existing-session
  termination.
- [ ] **SAFE-013:** AI compiler output and MCP tools cannot perform
  authority-bearing mutations; approval, activation, authorization, status, and
  revocation require deterministic core APIs and accountable actors.
- [ ] **SAFE-014:** Federation metadata trust cannot override patient intent,
  grant scope, application-local policy, data-holder policy, or revocation.

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
- [ ] **NFR-007 - Referential integrity:** Every displayed fact and linked ID must
  resolve to an authoritative retained or generated artifact; tests fail on
  browser/runtime/artifact drift.
- [ ] **NFR-008 - Evidence classification:** Every artifact uses exactly one of
  `retained_aws`, `executed_local`, `contract_tested`, `local_simulation`,
  `mapped_only`, or `planned` and states the associated non-claim.
- [ ] **NFR-009 - Semantic-loss visibility:** Standards projections must report
  each native field as represented, intentionally omitted, or requiring a
  governed extension/profile.
- [ ] **NFR-010 - Core/profile separation:** Core 0.1 contracts, experimental
  workflow profiles, and unchanged external standards must have distinct
  namespaces, versions, compatibility rules, and evidence labels.
- [ ] **NFR-011 - Surface parity:** Dashboard, synthetic mobile client,
  submission appendix, standards inspector, optional MCP adapter, and future
  APIs must show or carry the same canonical IDs and decisions rather than
  maintaining independent authorization state.

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

## v0.3 enhancement acceptance criteria

- [ ] The landing walkthrough starts with natural-language patient intent rather
  than OCR.
- [ ] Every AI-produced delegation field cites an exact phrase span and remains a
  draft.
- [ ] At least one material ambiguity visibly requires clarification before an
  invite or approval can continue.
- [ ] Patient approval is hash-bound to the final reviewed draft.
- [ ] Relationship and delegation are separate runtime artifacts with independent
  lifecycle behavior.
- [ ] One app permits an allowed action and another denies an excluded action from
  the same grant using executable policy messages.
- [ ] A fresh post-revocation request is denied while historical receipts remain.
- [ ] A patient or invited-relative synthetic upload retains uploader context,
  file-validation state, restricted artifact reference, and exact content hash
  without claiming document authorship or clinical currentness.
- [ ] Every document-derived candidate cites exact page, region, quote, and
  extraction record; medication and warning-sign content remains blocked from
  structured clinical assertions or app routing.
- [ ] Reviewed administrative document statements are version-bound and two apps
  receive disjoint, purpose-minimized projections while raw/unapproved/overbroad
  requests deny.
- [ ] The upload lane projects a candidate FHIR R4 `DocumentReference` and
  `Provenance` with semantic-loss notes; `Task`, `CarePlan`, medication resources,
  and live HIE/EHR exchange retain their actual planned/mapped status.
- [ ] The same grant is deterministically projected into native CareTrust, FHIR,
  and RAR views with explicit semantic-loss accounting.
- [ ] The actual AWS credential trace is shown with exact values and its blocking
  outcome; it is never blended into the deterministic success trace.
- [ ] Every walkthrough step exposes its exact message and evidence class.
- [ ] Network views distinguish local execution, contract artifacts, simulation,
  mappings, and planned deployment in text, not color alone.
- [ ] The primary Track 2 walkthrough is the care-organization dashboard; any
  mobile view is labeled synthetic test/demo reference client.
- [ ] One synthetic patient has at least two independently scoped caregivers,
  and every dashboard permission resolves to claims/grants and fresh app
  decisions.
- [ ] Core 0.1 exports exactly the seven minimal contracts and maps each retained
  experimental workflow schema to Core or an explicit extension.
- [ ] The AI compiler plane demonstrates draft-only intent, evidence, and app
  onboarding outputs; deterministic tests prove it cannot mutate authority.
- [ ] OpenID Federation 1.0 multi-hub diagrams/messages remain `planned` until an
  independent network exchange exists and clearly show each local-policy
  boundary.
- [ ] Optional MCP `draft/read/validate/simulate` tools, if implemented, call the
  same APIs and have no authority-bearing mutation capability.
- [ ] The submission appendix and standards inspector distinguish unchanged
  standards, CareTrust profiles, candidate gaps, evidence classes, and
  non-claims.

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
| Patient-provided document intake, review, sharing, FHIR projection, and revocation | `src/caretrust/uploaded_care.py`, `tests/test_uploaded_care.py`, `artifacts/validation/synthetic-uploaded-care-document-trace.json` |
| Patient/case navigator derived from claims and trace | `src/caretrust/navigator.py`, `tests/test_navigator.py`, `artifacts/validation/synthetic-patient-navigator.json` |
| Public-draft standards repository | `C:\Users\mike\Documents\caretrust-spec\`; `https://github.com/caretrust-hub/caretrust-spec` at initial commit `56ff896` |
| Generated submission appendix | `submission/CareTrust_Appendix_A_Standards_Messaging_Auth.md`, `.docx`, `scripts/build_auth_messaging_appendix.py` |
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

CareTrust Core 0.1 is a published public-draft grammar with seven minimal contracts:
`MessageEnvelope`, `TrustArtifact`, `AuthorizationRequest`,
`AuthorizationDecision`, `StatusEvent`, `CareRelationshipClaim`, and
`DelegationGrant`. Its schemas, examples, canonical hashes, and local validator
are published at commit `56ff896`. Current workflow schemas remain experimental
profiles until their Core mappings, compatibility rules, and semantic loss are
tested. The separate `caretrust-spec` repository is an Apache-2.0 public draft,
not an adopted standard, certification, or independent conformance program.

## Explicitly out of scope

- Real identity proofing, biometrics, or driver-license verification.
- Live Hawaii registry automation, scraping, or CAPTCHA bypass.
- Real PHI, production credentials, or care-recipient data.
- Medical power-of-attorney interpretation or activation.
- Production wallet, OID4VC issuance/presentation, UMA, SMART, or Shared Signals.
- Two-hub federation runtime.
- Production CareTrust MCP server or authority-bearing MCP mutations.
- Implemented external OIDC/OAuth authorization server or production IdP.
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
