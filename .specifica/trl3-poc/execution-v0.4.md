# CareTrust v0.4 — Aggressive 24-Hour Execution Design

## Mission

Produce a judge-ready, technically inspectable proof that CareTrust is:

1. an AI-assisted operational tool for caregiver organizations;
2. a deterministic trust and authorization service;
3. an Apache-2.0 interoperability profile that independent applications can implement; and
4. a credible path to federated, independently operated trust hubs.

The 24-hour objective is not a collection of screens or standards artifacts. It
is one integrated synthetic case in which AI compiles messy inputs, accountable
people approve bounded drafts, deterministic services authorize different
caregivers and applications, and every result is exposed through portable
messages and conformance evidence.

## Judge-facing integrated result

One synthetic patient has three caregivers:

- a patient-invited family caregiver;
- an agency CNA with a reviewed credential and active assignment; and
- a time-bounded respite/community caregiver.

The care-organization dashboard is the primary Track 2 surface. It shows the
care team, evidence/review queues, claim-derived permissions, application
registry, case history, exact decisions, and revocation impact.

A synthetic reference client is used only to prove that an independent
application can authenticate, request a purpose-bound decision, receive a
minimum-data projection, render a structured denial, and observe revocation.

## Target architecture

```text
UNSTRUCTURED INPUTS
patient language | documents/scans | application/OpenAPI description
                         |
                         v
AI COMPILER PLANE
intent compiler | evidence compiler | application-onboarding compiler
drafts + source spans + uncertainty + clarification + proposed mappings
                         |
                         v
ACCOUNTABLE REVIEW GATES
patient approval | organization review | credential/source review
                         |
                         v
DETERMINISTIC TRUST PLANE
Core 0.1 envelope/artifact/request/decision/status contracts
relationship | delegation | assignment | policy | receipt | revocation
                         |
             +-----------+------------+
             |                        |
CARE-ORG DASHBOARD              OPEN ADAPTER PLANE
primary Track 2 surface         REST/OpenAPI, FHIR, RAR,
                               OID4VC, OpenID Federation,
                               optional MCP
             |                        |
             +-----------+------------+
                         v
INDEPENDENT APPLICATIONS
scheduling | direct care | respite | transportation | training | government
```

## Non-negotiable architecture rules

1. AI never approves, activates, signs, authorizes, or revokes.
2. Every material AI value is linked to input evidence or exact human language.
3. All authority-bearing transitions operate without an LLM.
4. The dashboard and reference client consume the same canonical case bundle and
   decisions; neither contains hidden permission logic.
5. CareTrust Core 0.1 is the stable grammar. Workflow-specific payloads are
   versioned profiles.
6. MCP is an optional AI adapter over CareTrust APIs, never the core protocol.
7. OpenID Federation establishes entity/metadata trust, never patient access.
8. No real PHI, production credential, government identifier, or private key is
   used.
9. Every screen and claim carries an evidence class and non-claim boundary.

## Canonical integration object

All experiences consume one generated `SyntheticCaseBundle` containing:

- patient reference and case metadata;
- caregiver identities and identity-link provenance;
- relationship, credential, assignment, delegation, and service artifacts;
- application registrations and supported authorization-detail types;
- evidence, AI drafts, review/correction records, and approved items;
- fresh authorization requests and decisions;
- minimum-data projections and disclosure receipts;
- status events, replacement links, expiry, and revocation;
- standards projections and semantic-loss statements; and
- evidence-status labels.

The bundle is generated from executable domain objects and validated fixtures.
It is not maintained manually in HTML.

## Wave 1 — Foundations and AI (hours 0–8)

### Workstream A: Core 0.1 runtime bridge

- Consume the published `caretrust-spec` Core 0.1 schemas.
- Add deterministic POC models/builders for envelope, artifact, request,
  decision, and status event.
- Map current delegation and document-sharing decisions into the canonical
  request/decision shape.
- Preserve legacy artifacts as experimental profiles.
- Add positive, negative, temporal, hash-binding, and revocation tests.

### Workstream B: AI compiler plane

- Implement a provider-neutral `CompilerService`.
- Implement intent-to-delegation draft compilation with phrase citations.
- Implement app-description/OpenAPI-to-authorization-profile compilation.
- Retain evidence, uncertainty, clarification questions, model/prompt hashes,
  latency, cost, and explicit prohibited outputs.
- Provide deterministic replay fixtures and optional Bedrock execution.
- Add prompt-injection and authority-escalation tests.

### Workstream C: Multi-caregiver case bundle

- Build the one-patient/three-caregiver synthetic case.
- Generate disjoint permissions from actual claims, grants, assignments,
  audience, purpose, status, and policy.
- Generate care-team, permissions, history, application, evidence, and standards
  projections from the same bundle.
- Include at least one permit, wrong-purpose deny, missing-claim deny, clinical
  clarification block, expiry, and post-revocation deny.

### Gate 1

Root review must prove:

- no UI-only authority state;
- AI outputs are draft-only;
- all case projections resolve to canonical IDs/hashes;
- Core 0.1 validation passes; and
- a complete machine-readable case bundle exists.

## Wave 2 — Integrations and visible proof (hours 8–16)

### Workstream D: Dashboard integration contract

- Expose the canonical case bundle through static generated data or a bounded API.
- Supply dashboard-ready views without coupling to a particular UI framework.
- Add a standards inspector payload for every material event.
- Add before/after correction and revocation projections.

### Workstream E: CareTrust MCP

- Implement read, draft, validate, explain, and simulate tools only.
- Add tools for delegation drafting, app-profile proposal, permission matrix,
  decision explanation, standards projection, and conformance validation.
- Prove that MCP cannot approve, activate, issue authority, or revoke.
- Support local demo transport; document the OAuth protected-resource target.

### Workstream F: OAuth/OIDC and application onboarding

- Add a provider-neutral external identity-link contract.
- Implement a developer-controlled OIDC/Cognito test path if credentials and
  environment permit; otherwise ship an executable local OIDC contract harness.
- Implement application registration metadata, authorization-code/PKCE/RAR
  request artifacts, and resource-specific tokens/receipts.
- Never forward an upstream IdP token to an application.

### Gate 2

Root review must prove:

- the dashboard data and MCP tools use the same services;
- app requests are resource/audience/purpose bound;
- upstream and CareTrust tokens are separated;
- the reference client has no privileged back door; and
- all new capabilities have honest evidence labels.

## Wave 3 — Federation, conformance, and submission proof (hours 16–24)

### Workstream G: Federation laboratory

- Extend the current local simulation to two independently configured hubs.
- Exercise entity configuration, subordinate statements, trust-chain
  resolution, metadata policy, expiry/tamper denial, and key rollover fixtures.
- Demonstrate cross-hub entity trust followed by a separate local caregiver
  authorization decision.
- Keep network deployment and independent interoperability claims explicit.

### Workstream H: Conformance and security

- Add CI for JSON, links, schema/example validation, and sensitive-pattern scans.
- Add negative fixtures for unknown profiles, stale hashes, expired grants,
  wrong clients, excessive data, prompt injection, clinical escalation, and
  revocation.
- Produce a public conformance report for the integrated case bundle.
- Run full POC and standards validators.

### Workstream I: Judge trace and submission

- Build the six-minute walkthrough from executable evidence.
- Make AI activity, human review, permission differences, standards projection,
  independent-app portability, and revocation visually explicit.
- Update the application, appendix, evidence manifest, public README, and demo
  claims to the final evidence state.
- Run adversarial judging, security, accessibility, and claim-boundary reviews.

### Gate 3

Root final review must prove:

- one coherent walkthrough runs from source input to app receipt/revocation;
- the AI does material visible work;
- the organization workflow remains primary;
- open standards are shown through executable artifacts, not logos;
- all planned/executed boundaries are accurate; and
- both repositories are reproducible from clean instructions.

## Scope ladder

### Must ship

- Core 0.1 runtime bridge
- one-patient/three-caregiver case bundle
- AI intent compiler and evidence-linked document compiler
- app-specific permissions and minimum-data projection
- dashboard integration payload and standards inspector
- structured denial and revocation trace
- validators, tests, and submission synchronization

### Aggressive ship

- application-onboarding AI compiler
- MCP adapter
- executable OAuth/OIDC test harness
- second-hub federation laboratory
- public conformance report

### Stretch

- live Cognito configuration
- FHIR validator/IG tooling
- deployed MCP HTTP authorization
- independent second implementation
- automated accessibility browser run

## Root-agent review protocol

Every Terra handoff must include:

1. exact files changed;
2. commands and results;
3. evidence status for each capability;
4. known limitations and unimplemented paths;
5. claim-boundary assertions;
6. prohibited files left untouched; and
7. a proposed integration commit message.

Root reviews architecture, contract compatibility, tests, security/privacy,
evidence claims, and judge coherence before accepting or requesting another
agent turn. Agents do not commit, push, deploy, or modify another workstream's
files unless explicitly authorized.
