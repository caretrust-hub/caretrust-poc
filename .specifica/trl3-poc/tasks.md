# TRL 3 Proof of Concept - Tasks

This is the authoritative technical backlog. Tasks are ordered by dependency.
Check a task only when its stated evidence exists in the repository or saved
validation record.

## Current architecture checkpoint — 2026-07-30

This checkpoint controls later backlog interpretation:

- Primary Track 2 surface: care-organization dashboard.
- Synthetic mobile reference client: tests/demo only.
- Current executable case: one patient with family, agency-CNA, and
  community-respite caregiver contexts, ten fresh policy decisions, and
  separate credential/assignment/delegation/revocation lifecycles.
- AI compiler plane: retained credential and Smart40 Bedrock evidence plus
  integrated intent, document, and app-onboarding compiler contracts with
  deterministic fallbacks and draft-only authority boundaries.
- Deterministic authority and policy plane: local credential, delegation,
  uploaded-care, status, authorization, and revocation behavior exists.
- `caretrust-spec`: Apache-2.0 public draft published at
  `https://github.com/caretrust-hub/caretrust-spec`, initial commit `56ff896`;
  112 JSON and 25 Markdown files plus Core schemas/examples validate.
- CareTrust Core 0.1 POC runtime mapping, local MCP adapter contract,
  synthetic OIDC/PKCE/RAR harness, FHIR/SMART scheduling projection, and
  two-hub OpenID Federation 1.0 laboratory are integrated locally. Production
  servers, live IdPs, and operational federation remain planned.
- Standards/auth appendix, exact-message inspector, provider-operations
  dashboard, and executable judge walkthrough are integrated locally.

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
- [x] **T027 [Codex]** Tag the exact submission code and evidence state.
  **Done when:** an immutable version tag resolves to the commit referenced in the
  application.

## v0.3 — Inspectable care-trust network prototype

The v0.2 release remains the frozen baseline. v0.3 is a separate 1–2 week
enhancement whose thesis is: **one inspectable trust lifecycle, two claim
types, and one honest standards/network horizon**. The professional-credential
and patient-invited-caregiver lanes share a trace grammar, but never collapse
credential, relationship, consent, delegation, identity, or legal authority
into the same claim.

### Epic 0 — Provenance and truth vocabulary

- [x] **T028 [Agent: provenance]** Define one machine-readable evidence-status
  registry: `retained_aws`, `executed_local`, `contract_tested`,
  `local_simulation`, `mapped_only`, and `planned`. **Done when:** UI, docs, and
  manifest labels are asserted against the registry and unknown labels fail
  tests. **Evidence status:** `executed_local`;
  `docs/standards/evidence-status-registry.json` and
  `tests/test_evidence_status_registry.py`.
- [x] **T029 [Agent: provenance]** Inventory and reconcile the synthetic
  identity and identifier lineages. **Done when:** the browser, core runtime,
  FHIR projection, OID4VC artifacts, and decisions either use one canonical
  lineage or display an explicit cross-artifact mapping; no implied linkage is
  unsupported. **Evidence status:** `contract_tested`;
  `docs/standards/provenance-lineages.json`.
- [x] **T030 [Agent: provenance]** Separate the retained AWS intake trace from
  the deterministic trust-lifecycle trace. **Done when:** the actual blocking
  Qwen result visibly terminates without activation and the clean lifecycle has
  its own trace ID and provenance. **Evidence status:** `executed_local` plus
  separate `retained_aws` source evidence;
  `artifacts/validation/credential-walkthrough-trace.json`.
- [x] **T031 [Agent: standards]** Reconcile capability status everywhere.
  **Done when:** README, demo, standards tables, FHIR docs, OID4VC docs,
  federation docs, and submission use the same bounded evidence classes, with
  no contradictory implementation claims. **Evidence:** the shared registry,
  standards-status table, generated dashboard contract, application, appendix,
  and browser inspector use the same six evidence classes.

### Epic 1 — Canonical trace runtime and exact messages

- [x] **T032 [Agent: trace]** Define and export a strict `TraceEnvelope`
  contract containing sequence, actor, receiver, trust boundary, message type,
  evidence status, standard references, payload, hashes, and linked IDs.
  **Done when:** schema, examples, order validation, and malformed-trace tests
  pass. **Evidence status:** `executed_local`; `src/caretrust/trace.py`,
  `schemas/trace-envelope.schema.json`, and `tests/test_trace.py`.
- [x] **T033 [Agent: trace]** Generate an append-only professional-credential
  trace from runtime objects rather than handwritten browser prose. **Done
  when:** evidence, OCR, draft, review, source result, active claim, decoded JWS,
  two app requests/decisions, revocation, and fresh denial form one
  referentially intact downloadable artifact. **Evidence status:**
  `executed_local`; `scripts/build_credential_walkthrough_trace.py` and
  `artifacts/validation/credential-walkthrough-trace.json`.
- [x] **T034 [Agent: policy]** Execute App A and App B through the real
  authorization policy with distinct audience, purpose, request ID, decision
  ID, and policy version but the same claim ID. **Done when:** mutation tests
  prove wrong audience, purpose, status, or signature fails closed.
  **Evidence:** canonical multi-caregiver case, dashboard contract, judge
  walkthrough, and policy mutation tests.
- [x] **T035 [Agent: policy]** Make authorization and revocation history
  append-only. **Done when:** both earlier permit receipts remain available,
  revocation appends a status event, and a fresh App B request appends a
  `TOKEN_REVOKED` denial rather than overwriting history. **Evidence:**
  credential/delegation traces, case history, and revocation regression tests.
- [x] **T036 [Agent: evidence]** Generate a trace pack and integrity manifest.
  **Done when:** displayed/downloaded JSON, source artifacts, SHA-256 values,
  release commit, and screenshots cross-verify with no private key or secret.
  **Evidence:** deterministic
  `artifacts/validation/poc-evidence-manifest-v0.4.1.json` binds the v0.4.1
  release, readiness record, frozen evaluation references, and 287 tracked
  public artifacts with SHA-256 hashes.

### Epic 2 — Stage-linked technical walkthrough

- [x] **T037 [Agent: demo]** Add a synchronized message inspector to the human
  walkthrough. **Done when:** every state transition exposes `Input`, `Request`,
  `Response`, `Contract`, `Standard`, and `Verification` views plus a concise
  actor-to-receiver boundary and exact JSON. **Evidence:** the v0.4 console
  exposes exact local messages, actor/receiver, contract/profile, evidence
  status, JSON, and non-claim boundaries through native dialogs.
- [ ] **T038 [Agent: demo]** Add a persistent linked-ID rail from artifact to
  draft, review/source records, claim, token, requests, decisions, and
  revocation. **Done when:** selecting an ID highlights every event that
  consumes or produces it.
- [ ] **T039 [Agent: demo]** Add a same-claim standards view. **Done when:** the
  native CareTrust claim, executable local FHIR projection, W3C VC mapping,
  OID4VC contract artifacts, and federation seam each show their exact evidence
  class and explicit non-claim.
- [x] **T040 [Agent: demo]** Add a “Why it stopped” view for fail-closed paths.
  **Done when:** the last accepted message, reason code, suppressed downstream
  call, and absence of activation/permit are visible and browser-tested.
  **Evidence:** credential failure scenarios, clinical block, access-decision
  reason codes, and fresh-revocation denial are inspectable in the browser.

### Epic 3 — AI-assisted patient invite and bounded delegation

- [x] **T041 [Agent: delegation]** Define separate `PatientInvite`,
  `InviteAcceptance`, `IntentDraft`, `ClarificationRequest`,
  `CareRelationshipClaim`, and `DelegationGrant` contracts. **Done when:**
  schemas keep relationship, authority basis, delegated actions, data classes,
  audience, purpose, period, and status semantically distinct and contain no
  plaintext recipient contact value. **Evidence status:** `contract_tested`;
  `src/caretrust/delegation.py`, delegation schemas/examples, and tests.
- [x] **T042 [Agent: AI]** Implement a provider-neutral intent-to-delegation AI
  adapter. **Done when:** natural-language patient intent produces a draft only,
  every field cites the source utterance, ambiguities become clarification
  questions, and the model cannot approve, activate, widen, or infer legal
  authority. **Evidence:** `src/caretrust/compiler.py`, compiler fixtures,
  frozen Smart 40 records, dashboard proposal, and compiler safety tests.
- [ ] **T043 [Agent: AI]** Freeze a delegation evaluation set covering clear,
  ambiguous, contradictory, overbroad, multilingual, prompt-injected,
  incapacity, MPOA, and emergency-language cases. **Done when:** the run reports
  exact structured match, scope precision/recall, ambiguity recall, correction
  count, and material-risk false clears without replacing the original
  credential evaluation.
- [x] **T044 [Agent: delegation]** Execute the patient-invite lifecycle:
  create → accept → clarify → patient confirm → activate relationship/grant →
  two local app decisions → revoke → fresh deny. **Done when:** one deterministic
  success trace and expired, replayed, wrong-recipient, escalation,
  wrong-audience/purpose, withdrawn-consent, and revoked-grant tests pass with
  zero false permits. **Evidence status:** `executed_local`; delegation examples,
  `fixtures/delegation/synthetic-patient-navigator-trace.json`, and tests.
- [x] **T045 [Agent: standards]** Implement tested local FHIR R4 projections to
  `RelatedPerson`, `Consent`, and `Provenance` and a CareTrust OAuth RAR
  `authorization_details` profile. **Done when:** deterministic projections and
  validated examples preserve actor, action, purpose, period, data class, and
  provenance; no FHIR server, official validator, access token, or enforcement
  claim is made. **Evidence:** delegation/FHIR examples, local auth harness, RAR
  profile, scheduling projection, and negative projection tests.
- [ ] **T046 [Agent: authority]** Add document-authority hooks for MPOA,
  guardianship, and licenses. **Done when:** such evidence can create only a
  draft evidence package pending governed legal/source review; no document or
  AI output alone activates authority.

### Epic 4 — Aspirational network explorer and standards gaps

- [ ] **T047 [Agent: network]** Build synchronized `Now`, `Phase 2`, and
  `Network` explorer modes. **Done when:** the default view contains only
  executed components and every future node/edge uses a distinct textual
  evidence label.
- [x] **T047A [Agent: operator-console]** Model one accountable caregiver-support
  organization console and a diverse application registry. **Done when:** the
  console exposes referrals/invites, evidence readiness, separate trust records,
  app metadata/purpose, exact receipts, and revocation, while at least three
  synthetic apps request different minimum claim sets without receiving raw
  evidence. Use the ALU LIKE public program only as an explicitly non-endorsed
  reference scenario. **Evidence:** v0.4 organization console, generated
  dashboard contract, three-app registry, and synthetic ALU LIKE reference
  scenario.
- [x] **T047B [Agent: operator-console]** Implement a synthetic patient/case
  navigator derived from the append-only trace. **Done when:** an authorized
  operator can browse care-team, permission-matrix, and case-history views;
  inspect exact claims/requests/decisions and reason codes; see corrections as
  appended events and revoked grants as history; and see an explicit statement
  that this is not a complete clinical chart. **Evidence status:**
  `executed_local`; `src/caretrust/navigator.py`,
  `artifacts/validation/synthetic-patient-navigator.json`, and tests.
- [x] **T047C [Agent: standards]** Add bounded case-view standards projections.
  **Done when:** the demo exposes a local FHIR R4 `CareTeam` and linked
  `RelatedPerson`/`Consent`/`Provenance` candidates, while `AuditEvent`, `Task`,
  `ServiceRequest`, and `EpisodeOfCare` are labeled according to their actual
  evidence status and semantic-loss notes. **Evidence:** patient navigator,
  dashboard standards inspector, FHIR profiles/examples, and semantic-loss
  assertions.
- [x] **T047D [Agent: hie-edge]** Retain the synthetic HIE/EHR holder adapter as
  long-term technical evidence. **Done when:** its participant/app/authorized-user,
  patient-match, disclosure, and revocation boundaries are executable locally,
  while the main walkthrough labels Hawaiʻi HIE connectivity as planned—not a
  live connection, partner, or endorsement. **Evidence status:** holder adapter
  `executed_local`; live HIE/EHR `planned`.
- [x] **T047E [Agent: document-onramp]** Implement the patient-provided care-packet
  lane. **Done when:** a built-in synthetic relative upload/phone scan produces a
  hashed original, uploader provenance, evidence-linked AI draft, accountable
  item-by-item review/correction, minimum-disclosure app projections, exact
  receipts, and fresh denial after revocation. The workflow never claims uploader
  identity proves document authorship, clinical accuracy, or currentness.
  **Evidence status:** policy/review `executed_local`, extraction replay
  `contract_tested`, FHIR candidate projection `mapped_only`;
  `artifacts/validation/synthetic-uploaded-care-document-trace.json`.
- [x] **T048 [Agent: network]** Expose the local OpenID Federation laboratory.
  **Done when:** decoded trust anchor, entity configuration, subordinate
  statement, JWKS, chain hash, and tamper/expiry/key-mismatch failures are
  inspectable and explicitly described as one-process synthetic simulation.
  **Evidence status:** `local_simulation`; `src/caretrust/federation.py` and
  tests.
- [x] **T049 [Agent: network]** Expose concrete OID4VCI/OID4VP/DCQL candidate
  messages. **Done when:** metadata, offer, authorization detail, presentation
  request, intentionally invalid placeholder response, and policy linkage are
  viewable as contract-tested artifacts with no wallet/endpoint claim.
  **Evidence status:** `contract_tested`; OID4VC examples and
  `tests/test_oid4vc_artifacts.py`.
- [ ] **T050 [Agent: standards]** Create a machine-readable standards-gap
  registry. **Done when:** each workflow edge identifies what an existing
  standard supplies, missing caregiver semantics/governance, a proposed
  CareTrust profile or extension, privacy/safety risks, owner/phase, and the
  evidence required to graduate its status.

### Epic 5 — Verification, judge evidence, and release

- [x] **T051 [Agent: safety]** Expand the failure matrix across OCR, model,
  evidence references, review, source status, credential validity, token
  security, app policy, delegation, revocation, and federation. **Done when:**
  each scenario asserts its terminal state, stable reason code, and omitted
  downstream messages. **Evidence:** the 331-test suite covers each named
  boundary, including negative Core, auth, clinical-edge, MCP, and federation
  paths.
- [x] **T052 [Agent: UX]** Complete desktop/mobile, keyboard, reduced-motion,
  and code-inspector accessibility QA. **Done when:** critical flows work at
  390px and desktop, status is not color-only, focus is coherent, JSON is
  readable, and there are no console/page errors. **Evidence:** browser-tested
  desktop and 390px console, keyboard skip link, native exact-message dialogs,
  color-independent status text, and repaired zero-error revocation path.
- [x] **T053 [Agent: security]** Complete a synthetic-data, secret, key-material,
  dependency, and static-host review. **Done when:** no PII/PHI, credential,
  plaintext invite target, or private signing material is publishable.
  **Evidence:** v0.4.1 tracked-content scan found no applicant contact value,
  AWS access-key identifier, private-key block, or likely literal secret; all
  public demonstrations remain explicitly synthetic.
- [x] **T054 [Agent: release]** Run clean-clone unit/schema/referential/policy/
  browser tests and build the evidence bundle. **Done when:** the exact release
  commit is clean and all commands, artifacts, hashes, screenshots, statuses,
  and limitations are retained. **Evidence:** POC `82c3d4f` plus standards
  `cbef37a` passed 331 tests in a fresh paired clone; the standards repository
  separately validated 113 JSON and 29 Markdown files.
- [x] **T055 [Agent: submission]** Synchronize the 15-page submission and demo
  script with the v0.3 evidence. **Done when:** the north-star network,
  demonstrated lanes, AI value, partner path, standards gaps, measured results,
  and non-claims match the public artifacts. **Evidence:** 13-page application,
  10-page appendix, Smart 40 attachment, support letter, v0.4 README, and
  provider-first browser walkthrough.
- [x] **T056 [Codex]** Tag and deploy `trl3-poc-v0.3.0` or its superseding
  release. **Done when:** the tag
  resolves to the tested commit, GitHub Pages serves the same files, release
  assets are downloadable, and v0.2 remains recoverable. **Evidence:** the
  superseding `trl3-poc-v0.4.1` tag resolves to tested commit `82c3d4f`;
  successful Pages run `30601907087` deployed source `dc7981b`, and the landing,
  provider-console, and reference-client URLs each returned HTTP 200.

### Epic 6 — Track 2 dashboard, Core 0.1, and public profile

- [x] **T057 [Surface: dashboard]** Make the care-organization dashboard the
  primary Track 2 and judging surface. **Acceptance:** one operator can inspect
  patient case, caregivers, review queues, claim-derived permissions,
  application registrations, exact decisions, and revocations without implying
  a clinical chart. **Evidence status:** browser-tested static provider console
  over generated `dashboard-contract.json`, multi-caregiver, compiler, auth,
  FHIR, and federation artifacts; no deployment or field-outcome claim.
- [x] **T058 [Surface: reference-client]** Define the synthetic mobile reference
  client. **Acceptance:** it exercises invite, acceptance, patient approval,
  upload, status, and revocation against canonical APIs/messages, stores no
  independent authority state, and is labeled test/demo only. **Evidence
  status:** `executed_local` as a browser-testable, phone-sized reference client
  over the same retained canonical records as the provider console; no
  production mobile product, identity proofing, or live API claim.
- [x] **T059 [Case: multi-caregiver]** Add one-patient/multiple-caregiver fixtures
  and projections. **Acceptance:** at least two caregivers have independent
  relationship/grant IDs, scopes, exclusions, periods, statuses, and app
  decisions; conflict, expiry, and revocation tests prove dashboard permissions
  are claim-derived. **Evidence status:** `executed_local` and
  `contract_tested` per decision in
  `artifacts/validation/synthetic-multi-caregiver-case.json`; covered by the
  case, dashboard, FHIR scheduling, and judge-walkthrough tests.
- [x] **T060 [Plane: AI compiler]** Define purpose-specific intent, evidence, and
  app-onboarding compiler contracts. **Acceptance:** every output is draft-only,
  source/evidence-linked, uncertain where appropriate, versioned, and rejected
  if it asserts approval, activation, permit, status, or revocation. **Evidence
  status:** `executed_local` for deterministic compiler fixtures and safety
  enforcement, `retained_aws` for selected model/OCR evidence; no AI authority.
- [x] **T061 [Plane: authority-policy]** Bind all authority-bearing transitions
  behind deterministic versioned services. **Acceptance:** review, activation,
  signing, request/decision, status, and revocation run without an LLM and
  reject compiler/MCP attempts to mutate authority. **Evidence status:**
  `executed_local`; policy, Core mapping, MCP mutation-denial, auth, and
  revocation tests.
- [x] **T062 [Core: contracts]** Define CareTrust Core 0.1 schemas/examples for
  exactly `MessageEnvelope`, `TrustArtifact`, `AuthorizationRequest`,
  `AuthorizationDecision`, `StatusEvent`, `CareRelationshipClaim`, and
  `DelegationGrant`. **Acceptance:** stable IDs/versions, linkage, provenance,
  status, semantic invariants, validation, and no workflow-specific leakage.
  **Evidence status:** `executed_local`; published schemas, examples, canonical
  hashes, and validator at `caretrust-spec` commit `56ff896`. POC runtime mapping
  remains T063/Wave 1 work.
- [x] **T063 [Core: profile-normalization]** Reclassify current credential,
  delegation, uploaded-care, clinical-edge, trace, and projection contracts as
  experimental profiles and map them to Core 0.1. **Acceptance:** every schema
  field is represented, intentionally omitted, or assigned a versioned
  extension with migration tests. **Evidence status:** `executed_local` and
  `contract_tested`; Core runtime bridge validation, profile manifests,
  semantic-loss records, and mapping tests.
- [x] **T064 [Standards: local-repository]** Create the separate Apache-2.0
  `caretrust-spec` public draft working tree. **Acceptance:** README, LICENSE,
  CHANGELOG, CONTRIBUTING, SECURITY, `spec/`, `profiles/`, `schemas/`,
  `examples/`, `conformance/`, `governance/`, and gap register exist; copied
  JSON and links validate. **Evidence status:** `executed_local` and published
  from `C:\Users\mike\Documents\caretrust-spec` at commit `56ff896`.
- [x] **T065 [Standards: publication]** Review, commit, and intentionally publish
  `caretrust-spec`. **Acceptance:** provenance records source commits, public
  language has legal/standards review, CI validates JSON/links, and a selected
  remote is created only with explicit approval. **Evidence status:**
  `executed_local` and public at `https://github.com/caretrust-hub/caretrust-spec`,
  commit `56ff896`; no adoption, endorsement, certification, external review,
  or independent conformance claim.
- [x] **T066 [Federation]** Specify and test the future OpenID Federation 1.0
  multi-hub topology. **Acceptance:** entity configurations/statements, anchors,
  trust marks, key rotation, expiry, discovery, tamper failures, and two
  independently operated hubs are demonstrated while every hub/app/data holder
  retains local policy. **Evidence status:** existing laboratory
  `local_simulation`; two independently configured synthetic hubs, metadata
  policy, expiry/tamper/key-rollover failures, and separate local caregiver
  policy are retained. Operational federation remains `planned`.
- [ ] **T067 [Identity]** Integrate an external standards-based OIDC/OAuth
  authorization server and IdP for Phase 2. **Acceptance:** documented client,
  user, token, key, logout/revocation, audit, and service-account flows wrap
  CareTrust APIs without replacing CareTrust policy. **Evidence status:**
  `planned`; Phase 1 has no external server or production IdP.
- [x] **T068 [Adapter: MCP]** Implement an optional MCP adapter over CareTrust
  APIs. **Acceptance:** only `draft`, `read`, `validate`, and `simulate` tools
  exist initially; scopes, schemas, audit, rate limits, prompt-injection tests,
  and tests proving zero authority-bearing mutations pass. **Evidence status:**
  local stdio JSON-RPC adapter contract in `src/caretrust/mcp_adapter.py`,
  `artifacts/validation/mcp-adapter-contract.json`, and
  `tests/test_mcp_adapter.py`; no remote deployment or core-protocol claim.
- [x] **T069 [Submission: appendix]** Generate the standards/auth messaging
  appendix. **Acceptance:** Markdown and DOCX expose exact message sequence,
  standards roles, local-policy boundaries, evidence classes, and non-claims.
  **Evidence status:** `executed_local`; evidence is
  `submission/CareTrust_Appendix_A_Standards_Messaging_Auth.*` and
  `scripts/build_auth_messaging_appendix.py`.
- [x] **T070 [Submission: standards-inspector]** Integrate the standards inspector
  with the dashboard/walkthrough. **Acceptance:** each selected stage exposes
  exact message, contract, IDs/hashes, actor/receiver, evidence status, unchanged
  base standard, CareTrust profile constraint, candidate gap, semantic loss, and
  non-claim from repository artifacts. **Evidence status:** `executed_local` for
  the browser inspector and generated dashboard contract; individual standards
  projections retain their own bounded evidence labels.
- [x] **T071 [Planning: coherence]** Reconcile `spec.md`, `design.md`, and
  `tasks.md` around this architecture. **Acceptance:** a cross-file grep finds
  the dashboard, reference client, multi-caregiver model, compiler/policy planes,
  seven Core contracts, experimental profiles, `caretrust-spec`, OpenID
  Federation 1.0, MCP tool boundary, external OIDC/OAuth boundary, appendix,
  inspector, and honest statuses in all controlling documents. **Evidence
  status:** `executed_local`; documentation-only evidence, no implementation
  upgrade.

## Track 2 architecture acceptance matrix

- [x] Dashboard is the primary surface and mobile is explicitly test/demo only.
- [x] One patient/two-caregiver case derives all permissions from canonical
  claims, grants, status events, and fresh decisions.
- [x] AI compiler outputs cannot create any authority-bearing mutation.
- [x] The seven Core 0.1 contracts and experimental-profile migrations validate.
- [x] OpenID Federation 1.0 multi-hub exchange preserves each local-policy
  boundary.
- [x] Optional MCP tools are API adapters with no authority mutation.
- [x] External OIDC/OAuth is integrated or remains explicitly `planned`.
- [x] Appendix and standards inspector expose exact messages, standards,
  profiles, gaps, evidence classes, and non-claims.
- [x] `caretrust-spec` is public at commit `56ff896` and its local validator passes.

## Epic 7 — Aggressive v0.4 integrated proof

Controlling execution design:
[`execution-v0.4.md`](execution-v0.4.md). Terra ownership and launch briefs:
[`terra-waves-v0.4.md`](terra-waves-v0.4.md).

- [x] **T072 [Wave 1: Core runtime]** Execute Terra A and pass Gate 1 Core
  review. **Acceptance:** POC Core models/mappings, canonical artifacts,
  negative tests, and full regression suite pass without changing published
  schemas or hiding semantic loss.
- [x] **T073 [Wave 1: AI compiler]** Execute Terra B and pass Gate 1 AI
  review. **Acceptance:** intent and app-onboarding compilers emit only
  evidence-linked drafts, produce clarification/minimum-data proposals, reject
  authority-bearing output, support deterministic replay, and pass injection
  tests.
- [x] **T074 [Wave 1: case bundle]** Execute Terra C and pass Gate 1 case
  review. **Acceptance:** one patient/three caregivers, disjoint claim-derived
  permissions, exact decisions, clinical block, expiry, correction, and
  revocation share canonical IDs across all projections.
- [x] **T075 [Gate 1: integration]** Root integrates Wave 1. **Acceptance:**
  canonical `SyntheticCaseBundle` validates against Core/profile contracts; AI
  creates no authority; no UI-only permission state exists; focused and full
  suites pass. **Evidence:** published-schema validation at `56ff896`, retained
  AI/OpenAPI candidates, policy-owned authority paths, hash-bound requests,
  temporal/revocation mutation tests, and `283 passed`.
- [x] **T076 [Wave 2: dashboard contract]** Generate dashboard and standards-
  inspector data from the canonical bundle without overwriting user-authored UI
  design. **Acceptance:** care team, permissions, history, applications,
  evidence, AI review, messages, mappings, gaps, and receipts resolve to the
  same IDs/hashes.
- [x] **T077 [Wave 2: MCP]** Implement the optional MCP adapter. **Acceptance:**
  draft/read/validate/explain/simulate tools use canonical services; tests prove
  no approval, activation, authority issuance, or revocation mutation.
- [x] **T078 [Wave 2: OAuth/OIDC]** Implement the application/identity harness.
  **Acceptance:** external identity link, app registration, PKCE/RAR-shaped
  flow, resource-bound CareTrust token, upstream-token termination, negative
  client/audience/purpose tests, and honest live-versus-harness evidence.
- [x] **T079 [Gate 2: integration]** Root integrates Wave 2. **Acceptance:**
  dashboard, reference client, MCP, and auth harness call the same services;
  minimum disclosure and structured denials are consistent; all tests pass.
  **Evidence:** canonical dashboard contract, negotiated MCP 2025-11-25
  transcript, locally verified synthetic OIDC/PKCE/RAR flow, FHIR R4/SMART 2.2
  least-privilege scheduling projection, exact action-to-decision binding, and
  `316 passed`.
- [x] **T080 [Wave 3: federation]** Extend to two independently configured hub
  fixtures. **Acceptance:** entity statements, trust chain, metadata policy,
  expiry/tamper/key-rollover cases, followed by a separate local caregiver
  decision; no federation-equals-permission claim. **Evidence:**
  `federation-two-hub-lab.json`, federation lab/profile code, and negative
  tests.
- [ ] **T081 [Wave 3: conformance/security]** Add CI, negative fixtures,
  sensitive-pattern scans, and an integrated public conformance report across
  both repositories. Prepare the ACL-recommended 40-cycle software/logic stress
  log only as one frozen, consecutive, fully retained run; include at least two
  correctly routed HITL cases and the exact Protocol 9-Delta response. Never
  assemble or relabel unrelated runs as a consecutive Smart 40.
- [x] **T082 [Wave 3: judge trace]** Build the executable six-minute trace and
  synchronize submission, appendix, README, evidence manifest, and UI claims.
  **Evidence:** generated judge-walkthrough contract, provider-first console,
  application, appendix, README, and 331-test result.
- [x] **T083 [Gate 3: final audit]** Root performs architecture, security,
  accessibility, interoperability, judge, evidence-boundary, and requirement-
  by-requirement completion audits before any completion claim. **Evidence:**
  v0.4.1 release-readiness record, browser walkthrough, public URL checks,
  paired clean-clone suite, standards validation, security scan, and explicit
  retained backlog for incomplete production/future work.

## Epic 8 — v0.5 provider operations workflow

- [x] **T084 [Product]** Recenter the executable story on Track 2 workforce
  activation. **Acceptance:** one incomplete referral proceeds through cited AI
  intake, coordinator review, separate patient approval, deterministic worker
  eligibility, supervisor assignment, two app projections, revocation, and a
  fresh deny. Document/OCR, federation, and HIE remain supporting paths.
- [x] **T085 [Backend]** Implement a stateful provider-workflow service.
  **Acceptance:** typed domain state, explicit stage guards, optimistic versions,
  append-only events, workload counters, disjoint app projections, and
  fail-closed revocation pass focused and regression tests.
- [x] **T086 [HTTP adapter]** Serve the provider console and synthetic workflow
  API from one origin. **Acceptance:** health, session creation, session read,
  and versioned command endpoints pass loopback integration tests without a web
  framework dependency.
- [x] **T087 [Organization console]** Replace the evaluator slideshow with an
  operational work queue and editable case flow. **Acceptance:** the next human
  task dominates; AI evidence, uncertainty, patient scope, roster gates,
  per-app disclosure, workload counters, care team, and history are interactive;
  standards remain in a secondary evidence drawer.
- [x] **T088 [Independent client]** Reduce the caregiver mobile surface to one
  minimum-data test consumer. **Acceptance:** Care Tasks Mobile reads the same
  synthetic session, shows only its permitted shift/task projection, and shows
  no case fields on deny.
- [x] **T089 [AI protocol correction]** Expose frozen canonical evidence-span
  IDs, delegate identity mappings, and bounded vocabularies to the intent model;
  require an ontology-complete output contract. Preserve the defective v1/v2
  runs and publish the frozen v3 run with the exact executed request, candidate
  acceptance, grounding, semantic accuracy, HITL routing, safety, and
  deterministic fallback reported separately. **Evidence:** 40/40 schema-valid,
  39/40 citation-valid, 22/40 accepted and semantically exact candidates, 18
  fail-closed fallbacks, 40/40 HITL routing, and 40/40 no-authority enforcement.
- [x] **T090 [Design/submission]** Rewrite the UI handoff and application’s
  primary workflow around explicit provider workload reduction. **Acceptance:**
  use case, actors, screen hierarchy, workload measures, AI boundaries,
  standards path, architecture, truthfulness rules, and executable acceptance
  criteria agree with the v0.5 implementation.
- [ ] **T091 [User evidence]** Run and document at least three structured
  prototype reviews: provider coordinator/supervisor, direct-care worker, and
  care recipient/family caregiver. **Acceptance:** raw consented notes or
  de-identified summaries, role and date, task results, direct quotations within
  permission, issue severity, and requirement/change traceability are retained.

## Original v0.2 deadline rule

If timing slips, omit optional OCR, general UI polish, full FHIR validation,
OID4VC runtime, federation runtime, wallets, and production identity proofing.
Never omit real model output, frozen gold labels, human/source gates,
deterministic safety tests, actual metrics, or honest limitations.

## v0.3 cut rule

If the enhancement window compresses, ship Epics 0–2, professional-credential
failure paths, the patient-provided document on-ramp, and the standards-gap
registry skeleton. Do not rush federation or live HIE behavior into misleading
mock execution. Planned interactive models remain visibly `planned` until exact
messages and tests exist.
