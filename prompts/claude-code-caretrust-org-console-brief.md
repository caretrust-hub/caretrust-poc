# CareTrust provider operations console — workflow and UI handoff

**Revision:** July 30, 2026

**Prototype target:** Track 2 direct-care workforce activation

**Primary files:** `demo/network.html`, `demo/network.css`,
`demo/network.js`, `demo/reference-client.*`

**Executable backend:** `src/caretrust/provider_operations.py`,
`scripts/run_provider_console.py`

## Product in one sentence

CareTrust helps a care organization turn a fragmented referral into a
reviewed, patient-approved, qualified-worker assignment, then gives each
independent app only the minimum information it needs.

The product is the neutral trust and coordination layer. It is not a new
scheduler, EVV product, clinical chart, family organizer, or document-summary
app.

## Primary outcome

A coordinator should complete this synthetic workflow in under six minutes:

```text
incomplete referral
  → cited AI intake draft and focused exceptions
  → coordinator review
  → separate patient sharing approval
  → policy-filtered direct-care worker roster
  → supervisor assignment
  → two app-specific minimum-data packages
  → one revocation
  → fresh requests deny with zero disclosure
```

The interface should feel like a working operations console. Standards,
messages, and architecture are inspectable evidence behind the workflow—not
the main navigation.

## Why an organization adopts this

Care coordinators currently repeat the same work across referral inboxes,
spreadsheets, rosters, scheduling systems, worker apps, and reporting tools.
CareTrust reduces that workload in five explicit ways:

1. **Review instead of re-key.** AI proposes cited nonclinical intake fields.
   Staff focus on uncertainty and missing information.
2. **Ask once for what is missing.** The hub produces a focused follow-up list
   and a separate patient confirmation rather than leaving staff to discover
   gaps downstream.
3. **Filter before browsing a roster.** Deterministic qualification,
   availability, service-area, assignment, and status checks remove ineligible
   workers. AI explains fit but does not rank around failed gates.
4. **Approve once, project many times.** One reviewed case produces different
   minimum-data packages for independent scheduler, task, and future EVV apps.
5. **Change once, enforce everywhere.** Reassignment or revocation affects
   every fresh application request while historical receipts remain.

Do not claim validated time savings in Phase 1. Display measured prototype
counters:

- source fields detected;
- fields prefilled;
- fields requiring correction;
- fields corrected;
- follow-up items open;
- purpose-limited app entries generated;
- application packages generated; and
- human approvals remaining.

Phase 2 should compare time-on-task, correction rate, follow-up contacts,
duplicate data entry, onboarding completion, and user confidence with and
without CareTrust.

## Primary user

### Provider organization coordinator

They need to:

- see which cases need human action;
- accept an incomplete referral without losing provenance;
- review AI suggestions without reading raw JSON;
- correct only uncertain or missing items;
- send a bounded scope to the patient for approval;
- understand which workers are eligible and why;
- hand reviewed context to the organization’s existing applications;
- see exactly what each app received and what was excluded;
- revoke or reassign once; and
- inspect the evidence, decision, reason code, and standards projection when
  something is questioned.

They must never have to decide clinical truth from AI output or treat a family
relationship as permission.

## Other actors

### Care recipient

Reviews an exact, plain-language sharing scope in a separate surface. Can
approve, decline, or later revoke. An invite or account login does not establish
legal authority, capacity, relationship, document authenticity, or consent.

### Direct-care supervisor

Assigns an eligible worker. The roster is filtered by deterministic gates.
An AI explanation may summarize the fit but cannot change credential status,
availability, service requirements, or the final assignment.

### Direct-care worker

Uses an existing or independent app. Receives only the approved shift facts and
tasks needed for that service. Does not receive the referral, full case, family
details, credential evidence, or clinical record.

### Application integrator

Registers an application and requests a bounded capability using open
contracts. Receives an audience-bound decision, minimum-data projection, reason
codes, and receipt. Does not adopt CareTrust’s internal database or proprietary
identity model.

## Executable synthetic case

**Case:** `CT-SYN-0042` / `case:synthetic-malia-k`

**Care recipient:** Malia K.

**Organization:** Kūpuna Care Coordination Network (synthetic)

**Requested service:** in-home respite support

**Coordinator:** Michael M. (synthetic demo role)

Referral text:

> Malia K. needs in-home respite support beginning August 5, 2026,
> preferably Wednesday afternoons in East Honolulu. Her daughter Leilani is
> helping coordinate. English is spoken; a caregiver with local cultural
> knowledge is preferred. Please bring the printed transition packet to the
> first visit. The note does not state the visit end time or include Malia's
> approval to share.

This is a service coordination record, not a clinical chart.

## Screen hierarchy

### Global header

- CareTrust / Provider operations
- prominent `Synthetic data · no PHI` marker
- backend state:
  - `Python API · local`, or
  - `Browser reference adapter`
- links to organization console, test worker app, and technical proof

### Organization work queue

Show realistic statuses such as:

- new referral;
- waiting for patient;
- credential exception;
- ready to assign;
- app routing; and
- revocation follow-up.

Only Malia’s row is executable in the Phase 1 public demo. Clearly label the
other rows as illustrative rather than presenting inert controls as complete
features.

### Case header

Immediately answer:

- who is this;
- why is the case open;
- who owns the next action;
- what stage is it in; and
- what type of record is this.

### Workload strip

Keep the workload counters visible across the workflow. Add a short
“How measured” explanation that distinguishes engineering counters from
validated field outcomes.

### Case views

Use four operational views:

1. **Work** — the primary unfolding workflow;
2. **Care team** — relationships, approval, eligibility, assignment, and
   permission shown separately;
3. **Applications** — app-by-app request, decision, disclosed fields, and
   exclusions; and
4. **Case history** — automatically generated AI, human, patient, policy, and
   revocation events.

Do not make “standards,” “federation,” or “architecture” top-level case tabs.

## Workflow interaction specification

### 1. Intake

Show the referral beside one primary action: **Compile referral draft**.

Explain that AI may:

- locate names, requested service, date, schedule, area, preferences, and
  preparation text;
- link each proposed value to an exact quote;
- score uncertainty; and
- identify missing information.

Explain that AI may not:

- record consent;
- verify credentials;
- create an assignment;
- infer clinical instructions; or
- grant app access.

### 2. Coordinator review

Render eight editable field rows. Each row includes:

- label;
- proposed value;
- confidence;
- exact-source link; and
- a visible exception treatment when uncertain.

The schedule proposal should remain “Wednesday afternoons” because the source
does not establish exact hours. The coordinator corrects it to
“Wednesdays, 1:00–5:00 PM” and resolves the missing visit end time.

The patient-approval gap must remain unresolved and move to its own gate.

### 3. Patient approval

Show two side-by-side contexts:

- the coordinator’s prepared scope; and
- a visibly separate patient-facing confirmation preview.

The approved purposes are:

- coordinate one respite service;
- share the approved schedule with the assigned worker; and
- share approved first-visit preparation with the worker task app.

Explicit exclusions:

- source document;
- clinical record;
- credential evidence;
- billing;
- mental-health information; and
- unrelated case history.

### 4. Worker assignment

Show three candidates:

- **Kai N.** — eligible; simulated active Hawaiʻi CNA, current simulated CPR,
  schedule and area match;
- **Noa P.** — blocked; role and duration do not satisfy requirements; and
- **Liko R.** — blocked; qualified but unavailable during the approved window.

For each candidate, distinguish:

- deterministic checks;
- AI explanation; and
- supervisor action.

There must be no control that assigns an ineligible worker.

### 5. Independent application routing

Use two test consumers:

#### OpenShift Scheduler

Receives:

- case identifier;
- care-recipient display name;
- assigned worker;
- approved service;
- start date;
- visit window; and
- service area.

Does not receive:

- source document;
- family relationship details;
- clinical record; or
- credential evidence.

#### Care Tasks Mobile

Receives:

- case identifier;
- care-recipient display name;
- assigned worker;
- visit window; and
- first-visit preparation task.

Does not receive:

- source document;
- family relationship details;
- exact home address;
- clinical record; or
- credential evidence.

Every card must show:

- independent app and purpose;
- `NOT REQUESTED`, `ALLOW`, or `DENY`;
- current reason;
- disclosed fields;
- excluded categories; and
- a way to inspect the standards-shaped message.

### 6. Revocation proof

One supervisor action revokes the assignment for the hub.

After revocation:

- clear previously displayed current projections;
- retain historical permit events;
- allow a fresh request from either app;
- return `DENY`;
- disclose zero case fields; and
- show an assignment-revoked reason.

Do not claim existing-session termination. The prototype demonstrates fresh
decision enforcement.

## Test worker reference client

`reference-client.html` is a deliberately small consumer, not another product
pitch.

It should:

- identify itself as `TEST / DEMO ONLY`;
- show the synthetic worker identity;
- read the Care Tasks Mobile projection from the same browser-local synthetic
  session;
- display only the approved visit window and preparation task on permit;
- display no case data on deny;
- display the excluded categories and a compact receipt; and
- explain the standards-shaped OAuth authorization request.

The worker client is evidence that many apps can consume the trust layer.
CareTrust does not require organizations to replace their preferred workforce
apps.

## Technical architecture

```text
provider console / patient confirmation / independent app
                         │
                         ▼
             Provider Workflow API (commands)
                         │
             optimistic version + event log
                         │
       ┌─────────────────┼──────────────────┐
       ▼                 ▼                  ▼
 AI draft boundary   human records   deterministic policy
       │                 │                  │
 citations + gaps   approval/assignment   app projections
       └─────────────────┼──────────────────┘
                         ▼
           Core 0.1 receipts and projections
```

Phase 1 executable implementation:

- Pydantic domain objects and state transitions;
- in-memory local service;
- standard-library HTTP JSON adapter;
- static browser reference adapter with the same command contract;
- synthetic data only; and
- automated lifecycle tests.

Phase 2 deployment path:

- API Gateway / Lambda or container service;
- DynamoDB or PostgreSQL event/state store;
- KMS signing and secrets management;
- organization and app registration;
- external OIDC identity provider adapter;
- durable consent, assignment, and revocation records;
- FHIR gateway projections;
- operational telemetry and alerting; and
- multi-organization conformance and federation pilots.

## Open standards workflow

Use existing standards where they fit:

- **OpenID Connect** for upstream authentication;
- **OAuth 2.0 Authorization Code + PKCE** for interactive app authorization;
- **RFC 8707 resource indicators** for intended resource/audience;
- **RFC 9396 Rich Authorization Requests** for bounded capability details;
- **FHIR R4** RelatedPerson, Consent, CareTeam, Task, Appointment, Provenance,
  and AuditEvent as downstream projections;
- **SMART App Launch concepts** when the relying application is FHIR-aware;
- **W3C Verifiable Credentials / OpenID4VC** for portable evidence where an
  issuer is authoritative; and
- **OpenID Federation 1.0** as a future trust-establishment substrate between
  governed hubs.

CareTrust Core 0.1 fills care-coordination gaps:

- explicit separation of relationship, legal authority, patient delegation,
  workforce eligibility, organization assignment, and app authorization;
- evidence-linked AI draft records;
- patient- and case-bound caregiver capability requests;
- minimum-data projection manifests;
- stable reason codes and receipts; and
- revocation/lifecycle semantics across independent applications.

Treat Core 0.1 as an open Apache-2.0 experimental profile. Do not claim it is an
adopted standard.

## AI prominence and safety

AI has visible work in three bounded compiler lanes:

1. **Referral/evidence compiler** — extracts cited nonclinical facts, detects
   missing information, classifies risk, and routes exceptions.
2. **Workforce explanation assistant** — summarizes why reviewed facts and
   deterministic gates make a worker eligible or ineligible. It cannot override
   a failed gate or assign a worker.
3. **App requirements compiler** — converts app metadata or an OpenAPI
   description into a proposed RAR request, minimum-data profile, and
   standards-gap report for human registration review.

Only the first two need to appear in the primary six-minute workflow. Keep the
third in technical proof or app onboarding so it does not distract from provider
operations.

All model output is:

- non-authoritative;
- source-linked;
- schema-constrained;
- uncertainty-aware;
- reviewable;
- replaceable with a provider-neutral adapter; and
- prohibited from approving, activating, assigning, widening, revoking, or
  granting access.

## Truthfulness rules

Always label:

- synthetic versus live data;
- browser reference adapter versus Python API;
- deterministic local output versus retained model run;
- simulated registry status;
- contract-tested standards projection;
- local federation laboratory; and
- planned identity, HIE, EHR, or production integration.

Never imply:

- real PHI is loaded;
- a named organization is a partner without evidence;
- Login.gov integration is executed;
- AI verified a license, legal document, relationship, consent, or clinical
  fact;
- CareTrust owns scheduling, billing, EVV, or the clinical record;
- federation is operational; or
- prototype interaction counters are field outcomes.

## Accessibility and responsive behavior

- logical heading order and one page-level `h1`;
- keyboard-visible focus;
- explicit labels for inputs;
- status and error announcements;
- no color-only status distinctions;
- touch targets at least 40px high for primary controls;
- reduced-motion support;
- no horizontal scrolling at 320px;
- queue may collapse below tablet width; and
- the current action must remain above secondary evidence on mobile.

## Acceptance criteria

The implementation is ready when:

1. A fresh case can traverse every state through visible user actions.
2. Eight cited fields and two missing items appear after compilation.
3. The coordinator corrects one uncertain field and resolves one missing detail.
4. Patient approval is a separate action and screen context.
5. Two ineligible workers cannot be assigned.
6. A supervisor assigns the one eligible worker.
7. Both apps return different minimum-data projections.
8. The workload strip reports 12 generated app entries for the completed run.
9. Revocation clears current projections.
10. A fresh post-revocation request denies with zero disclosed fields.
11. Care team and history views distinguish relationship, approval, assignment,
    and access.
12. The worker reference client shows only its projection.
13. Standards and raw messages remain secondary but inspectable.
14. The local Python API and browser reference adapter implement the same user
    workflow.
15. Automated tests cover stage ordering, version conflicts, ineligible-worker
    blocking, disjoint projections, and revocation denial.
