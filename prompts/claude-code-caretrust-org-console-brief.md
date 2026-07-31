# Claude Code brief: CareTrust organization console

**Revision:** July 30, 2026 — provider-first workflow, independent-app
authorization, Core 0.1 messaging, and federation-aware network story.

## Your assignment

Redesign and implement the CareTrust organization console so a reviewer can
understand the product, the operational workflow, and the larger platform in one
coherent walkthrough.

This is not a generic case-management dashboard and not a document-summary
demo. CareTrust is the neutral trust and coordination layer between:

- a care recipient;
- family and direct-care caregivers;
- a caregiver-support organization;
- independently operated caregiving applications; and
- eventually, governed clinical-data holders such as an EHR or HIE.

The organization uses one console to coordinate a case. Multiple mobile or web
applications reuse CareTrust claims, permissions, provenance, and policy
decisions without sharing a proprietary identity database or receiving the
entire case record.

Work primarily in:

- `demo/network.html`
- `demo/network.css`
- `demo/network.js`
- `demo/network-data.js` is generated; do not hand-edit it.

Preserve the existing Python contracts, generated JSON fixtures, and automated
tests. Do not invent live integrations, partners, users, or production
capabilities.

## What this revision must make clearer

The first screen must communicate the complete product boundary:

- the **organization console** is the operational surface used by a
  caregiver-support organization to turn a referral into an access-ready care
  team;
- the **caregiver mobile client** is only a reference consumer that demonstrates
  what one independent app receives;
- **CareTrust Core** is the shared trust layer that compiles drafts, stores
  approved authority, evaluates fresh requests, and emits minimum-necessary
  decisions and receipts; and
- the **network/federation view** is the long-term open ecosystem, not a claim
  that the current prototype is deployed across organizations.

The primary story is not “upload a document and summarize it.” It is:

```text
organization receives referral
  -> patient and caregivers establish bounded trust
  -> organization assembles an access-ready care team
  -> independent apps request different capabilities
  -> CareTrust evaluates fresh, deterministic policy
  -> case events and receipts remain inspectable and revocable
```

Patient-provided documents are one valuable evidence on-ramp within that larger
workflow. They help an organization convert information already in the family’s
hands into reviewable coordination work without treating AI output as truth.

Three AI-assisted compiler lanes should appear as a coherent system:

1. **Intent compiler:** ordinary-language caregiver intent becomes a
   source-linked, bounded delegation draft and focused clarification questions.
2. **Evidence compiler:** OCR/document evidence becomes source-linked
   coordination candidates with safety classes and uncertainty.
3. **Application-requirements compiler:** app descriptions or OpenAPI metadata
   become a proposed RAR/minimum-data profile and standards-gap report.

All three stop at drafts. Humans approve authority-bearing records; deterministic
CareTrust policy alone returns permit or deny.

## Market-informed interaction references

Use these as workflow references, not as visual clones and not as claimed
partners:

- **Birdie / ShiftCare:** one agency hub, a worker app, and a family view;
  invitation, configurable visibility, schedules, care logs, and revocation.
- **Unite Us / Findhelp:** organization caseload, longitudinal case/referral
  history, cross-organization exchange, and standards-aware integration.
- **ianacare / Cariloop:** low-friction family invitation, explicit care-team
  roles, shared updates, and document/case collaboration.
- **HHAeXchange / CareBridge:** many provider applications connecting to a
  state-scale aggregation layer.

CareTrust must visibly differ from all-in-one platforms: it does not own
scheduling, EVV, billing, clinical records, or the caregiver’s preferred app.
It supplies reusable evidence-linked authority context to those systems through
open contracts.

## Product thesis

> CareTrust turns human intent, messy evidence, and application requirements
> into governed, reusable coordination across independent caregiving
> applications.

AI is used to draft, classify, locate evidence, explain, ask clarification, and
propose an application's standards-based authorization/minimum-data profile. AI
never creates authority. Care recipients, authorized organization staff, data
holders, and deterministic application policy make the decisions.

The interface must make that separation obvious without requiring the user to
read architecture documentation.

## Primary users and their intent

### 1. Organization program coordinator

The primary console user.

They need to:

- understand what is happening with a case in under 30 seconds;
- see the care recipient’s support team without mistaking team membership for
  permission;
- see who may do what, through which application, for which purpose, and until
  when;
- identify what needs human review and why;
- turn approved information into assignable work;
- know exactly what each application received;
- correct or revoke trust state without erasing history; and
- inspect the exact request, decision, evidence, provenance, standard mapping,
  and reason code behind any important UI state.

They do not want to:

- read raw JSON during normal work;
- manually re-key the same facts into several applications;
- interpret an entire discharge packet to create a routine scheduling task;
- become responsible for clinical validation they are not authorized to
  perform; or
- trust an unexplained AI output.

### 2. Care recipient

They need to:

- invite a caregiver;
- state permission in ordinary words;
- answer focused clarification questions;
- approve the exact final scope, applications, exclusions, and expiration;
- approve administrative coordination items derived from a document; and
- revoke future use.

Patient invitation is an access workflow. It does not prove identity,
relationship, capacity, legal authority, document authenticity, licensure, or
clinical correctness.

### 3. Family caregiver

They need to:

- accept an invitation;
- upload or scan a document the family already has;
- understand what the upload does and does not establish;
- correct OCR transcription when permitted;
- see what was shared and with which application; and
- avoid completing the same onboarding process separately in every app.

### 4. Direct care worker

They need to receive a bounded, shift-relevant task in the application they
already use. They should not have to read an entire discharge packet or infer a
clinical instruction from an AI summary.

### 5. Application integrator

They need an open, stable request/decision contract, minimum necessary payloads,
reason codes, receipts, and standards projections. They must not have to adopt
the console’s internal database or proprietary identity model.

## The six-minute primary walkthrough

Design the interface around this sequence. It should feel like one unfolding
case, not five unrelated feature tabs.

### Step 1 — Accept the referral and orient to the case

Open synthetic case `CT-SYN-0042`, Malia K.

Immediately show:

- a synthetic referral/transition reason and referring context;
- the state change from referral received to organization case accepted;
- why the case is open;
- the next decision requiring attention;
- current delegation status;
- assigned organization coordinator;
- latest material event;
- number of apps using the trust context;
- three independently scoped caregivers (family, agency CNA, and
  respite/community), without implying that care-team membership grants access;
  and
- an explicit “synthetic, no PHI, not a clinical chart” label.

The visual hierarchy should make the next action more prominent than metadata.
The organization’s work queue should make clear which cases are waiting for
patient action, caregiver evidence, staff review, app routing, or revocation
follow-up.

### Step 2 — Assemble the access-ready care team

Show Malia’s statement:

> Let my daughter Leilani schedule appointments and see visit instructions
> through 2026-12-31, but not billing or mental health records.

Show the actual transition:

1. patient intent;
2. AI-created bounded draft;
3. clarification about permitted applications;
4. caregiver invite acceptance;
5. patient approval of the exact final scope;
6. separate relationship and delegation records; and
7. independent local decisions by two applications.

The user must understand:

- relationship is not permission;
- invitation acceptance is not patient approval;
- patient approval is version-bound;
- the grant is limited by action, application, purpose, exclusions, and time;
  and
- each application still decides locally.

Then compare the same patient across three caregivers:

- **Leilani, family caregiver:** patient-delegated scheduling and approved visit
  instructions;
- **Jonah, agency CNA:** reviewed credential plus active organization assignment
  and patient-specific direct-care task scope; and
- **Pua, respite/community caregiver:** time-bounded service assignment and
  minimum-data respite scope.

Show at least one permitted and denied request for each. The differences must
resolve to visible claims, grants, assignments, purpose, audience, validity, and
status—not hard-coded persona rules.

Also show the caregiver authentication boundary:

1. an independent app redirects the caregiver to CareTrust;
2. CareTrust uses an external OIDC identity provider and links the verified
   issuer/subject to a CareTrust participant;
3. the app sends a bounded OAuth authorization request with PKCE, state, nonce,
   resource indicator, and RAR `authorization_details`;
4. CareTrust evaluates relationship, delegation, assignment, app registration,
   purpose, audience, validity, and revocation;
5. the caregiver sees the exact requested capability;
6. the app receives a one-time authorization code and exchanges it with the PKCE
   verifier; and
7. CareTrust issues its own short-lived app/audience-bound token and receipt.

The upstream identity token terminates at CareTrust and is not forwarded to the
application. In this prototype, the identity provider is synthetic and local.
Login.gov or another production identity provider is a planned adapter, not an
executed integration.

### Step 3 — Upload the family’s discharge packet

The family caregiver supplies a visibly synthetic discharge scan.

Show:

- uploader account and capacity;
- file type and safety checks;
- original artifact hash;
- document classification;
- authorship/currentness/clinical-authority status as unknown or unverified;
- exact OCR text regions; and
- the status of the OCR/model execution.

Do not present upload as proof that the source is authentic or clinically
current.

### Step 4 — AI proposes evidence-linked coordination candidates

Display the document and candidate items side by side.

Required candidates:

1. follow-up appointment within seven days;
2. bring or maintain a daily weight log;
3. medication-list change evidence; and
4. warning-sign evidence.

Each candidate must open the exact page, quotation, line or OCR region, and
provenance record. Show confidence and why the candidate was classified.

The safety boundary must be visual, not buried:

- follow-up and weight-log items can enter administrative review;
- medication content cannot become a medication order or statement;
- warning-sign text is preserved but cannot be interpreted or triaged by the
  model; and
- conflicting or incomplete clinical content stops for an accountable clinical
  source.

### Step 5 — Separate patient approval from organization routing

Do not use one button that says the patient approved and the coordinator
confirmed routing.

Implement two visibly separate gates:

1. **Patient review**
   - approve, correct, or reject each administrative candidate;
   - defer clinical candidates;
   - preview the exact text being approved;
   - bind the decision to the draft version.

2. **Organization routing review**
   - confirm which approved item is appropriate for which registered app;
   - inspect the minimum-necessary projection;
   - see excluded fields before routing;
   - confirm the accountable operator and policy version.

Neither gate clinically validates the packet.

### Step 6 — Route to independent apps and revoke

Use at least two visibly distinct receiving applications:

- **Kākou Scheduling**
  - receives only the approved follow-up statement/window and necessary source
    reference;
  - does not receive the raw document, medication evidence, warning signs,
    diagnosis, or unrelated case history.

- **Direct Care Tasks**
  - receives only the reviewed, shift-relevant reminder;
  - does not receive the follow-up scheduling data or clinical content.

Also show a Medication Support request denied before disclosure.

For every app, provide:

- app identity and registration/trust status;
- declared purpose;
- exact requested fields;
- exact included and excluded fields;
- policy decision and reason codes;
- local receipt; and
- the app’s independent status after receipt.

Then revoke the scheduling share or delegation and run a fresh request. Show:

- historical receipt remains;
- current grant is revoked;
- fresh request is denied;
- no new data is released; and
- no claim is made that previously delivered data was erased or an existing
  session was terminated.

## Information architecture

The current top-level case views may be retained, reorganized, or combined, but
the resulting product must support these jobs:

### Overview / care journey

- case state and next action;
- concise workflow timeline;
- current trust summary;
- current risk or review blockers;
- app participation summary.

### Support team

Show the patient, family caregiver, direct-care worker if assigned, coordinator,
and participating organization.

For each member, distinguish:

- contextual role;
- relationship basis and assertor;
- identity assurance;
- professional qualification if relevant;
- delegation status;
- legal-authority status;
- validity;
- provenance.

Never imply that appearing on the care team grants access.

### Permissions

Use a matrix answering:

> Who may request what, through which application, for which purpose, about
> which data or service, until when, and with what exclusions?

Show current and historical state. Support exact request/decision drill-down.

### Case history

Use an append-only event sequence:

- intent;
- AI draft;
- clarification;
- invite;
- invite acceptance;
- patient approval;
- claim issuance;
- document upload;
- OCR/model draft;
- corrections;
- patient item review;
- organization routing review;
- app requests and receipts;
- revocation;
- fresh denial.

Corrections append new events. Do not rewrite prior events.

### Shared care packet

This is the primary working surface for the document-to-coordination workflow,
not merely a document preview.

### Application registry / network

Make the larger platform visible without distracting from the current case.
Show registered apps as independent consumers with:

- application identifier;
- operator;
- purpose;
- permitted contract/profile;
- requested claim or item types;
- public-key or metadata status where applicable;
- trust status;
- last receipt;
- evidence classification.

Include a long-term network view showing multiple care organizations and
government/community adopters federating through open standards. Label this
`planned` or `local simulation` as appropriate. Do not imply that ALU LIKE,
Hawaiʻi HIE, VA, or any government body is a partner or production connection.

Include one AI-assisted application-onboarding proposal. Given a synthetic
respite application's description or OpenAPI metadata, show:

- proposed required claims and RAR authorization details;
- proposed purpose, actions, resource/data types, and minimum-data response;
- excessive or clinically inappropriate requested fields visibly flagged;
- human organization approval still required; and
- a conformance preview against the Apache-2.0 CareTrust public draft.

The approved registration view should show the resulting client identifier,
redirect URI, authentication method, key/metadata status, allowed resource
server, permitted purposes/actions/datatypes, evidence classification, and
policy profile. Do not imply that an AI draft registers the app.

Distinguish three onboarding/authentication concerns:

- **human identity:** external OIDC authentication linked to a CareTrust
  participant;
- **interactive app authorization:** authorization code + PKCE + RAR for the
  caregiver-facing client; and
- **service authentication:** separately registered organizational clients and
  keys for machine-to-machine exchanges.

An authenticated caregiver is not automatically authorized for a patient.
An approved application is not automatically entitled to case data.

## Exact-message and standards inspector

Every important state must have a progressive-disclosure inspector. The normal
workflow uses plain language; the inspector gives a technical reviewer the
exact evidence.

The inspector must show:

- display title;
- evidence status: `executed_local`, `retained_aws`, `contract_tested`,
  `local_simulation`, `mapped_only`, or `planned`;
- sender and receiver;
- native CareTrust contract;
- exact retained/generated JSON;
- linked source IDs and hashes;
- policy/version and reason codes;
- standards projection;
- semantic loss or missing standard;
- explicit non-claims.

Relevant standards:

- OpenID Connect Core;
- OAuth 2.0 authorization code flow and PKCE;
- OAuth 2.0 Rich Authorization Requests / `authorization_details`;
- OAuth 2.0 Resource Indicators;
- SMART App Launch 2.2 resource scopes;
- HL7 FHIR R4 `DocumentReference`, `Task`, `CareTeam`, `RelatedPerson`,
  `Consent`, `Provenance`, `AuditEvent`, `Appointment`,
  `AppointmentResponse`, `Schedule`, and `Slot`;
- W3C Verifiable Credentials Data Model 2.0;
- OpenID for Verifiable Presentations;
- OpenID for Verifiable Credential Issuance;
- OpenID Federation 1.0;
- OAuth authorization-details / rich-authorization-request patterns;
- OpenAPI 3.1 and JSON Schema.

Do not claim full conformance when only a mapping or contract example exists.
Base FHIR does not fully carry OCR regions, model confidence, CareTrust review
authority, or minimum-disclosure receipts; keep those semantics in the native
message and state the gap.

For scheduling, show that the approved family-caregiver action can project to
bounded SMART scopes and FHIR R4 `Appointment` / `AppointmentResponse`
artifacts. Do not use `Encounter` as a substitute for an administrative
appointment. `Schedule` and `Slot` availability require additional
organization/service/location policy and must not be exposed through a broad
wildcard scope.

For federation, show two synthetic hubs resolving participant and client
metadata through OpenID Federation-shaped trust chains. Federation establishes
metadata trust only. Local patient permission, organization policy, purpose,
audience, status, and revocation must still pass before disclosure.

Link technical inspectors to the public Apache-2.0 `caretrust-spec` Core 0.1
contracts and conformance examples. When existing standards cannot carry a
CareTrust semantic cleanly, label the gap and the proposed extension instead of
hiding it in proprietary application state.

## Visual and interaction direction

Aim for a credible modern public-interest operations product, not a hackathon
landing page.

- Calm, trustworthy, information-dense, and humane.
- Hawaii context may appear through names and restrained warmth, not tourism
  imagery or decorative clichés.
- The organization’s work queue and next actions should feel operational.
- Use status text plus icon/shape; never rely on color alone.
- Keep technical detail one click away.
- Make the AI boundary visually consistent wherever AI appears.
- Use compact tables only when comparison is the user’s job.
- Prefer a timeline or stepper when sequence and authority change are the job.
- Avoid large decorative hero sections inside the authenticated console.
- Avoid excessive cards, repeated badges, and repeated boundary disclaimers.
  Consolidate them into contextual explanations.
- Support keyboard navigation, visible focus, screen readers, reduced motion,
  200% zoom, and a 390-pixel mobile layout.

## Non-negotiable truth and safety rules

- All people, organizations, documents, and records in the public demo are
  synthetic.
- No real PHI.
- Upload does not establish document authenticity, authorship, accuracy,
  currentness, patient matching, relationship, licensure, or legal authority.
- AI creates only unverified drafts.
- AI cannot approve, activate, sign, authorize, widen scope, or return a permit.
- Patient and organization decisions are separate.
- Clinical conflicts require an accountable source.
- Never generate `MedicationRequest` or `MedicationStatement` from extracted
  discharge text.
- Raw documents are not included in routine app projections.
- Revocation affects fresh decisions and preserves history.
- HIE/EHR exchange is planned unless an actual tested edge is explicitly shown.
- ALU LIKE and Hawaiʻi HIE are reference contexts only, not partners or
  endorsers.

## Implementation requirements

1. Use `window.CARETRUST_DEMO_DATA` from generated `demo/network-data.js` as the
   source of inspector objects and visible state wherever possible. Remove
   duplicated hard-coded JSON from `demo/network.js`.
2. Keep the demo dependency-free and suitable for GitHub Pages.
3. Do not call live services from the browser.
4. Preserve stable IDs or add `data-testid` attributes for critical controls.
5. Model the workflow as an explicit state machine. At minimum:
   - `packet_received`
   - `draft_ready`
   - `patient_review_in_progress`
   - `patient_reviewed`
   - `organization_review_in_progress`
   - `ready_to_route`
   - `routed`
   - `revoked`
   - `fresh_request_denied`
6. A stale draft or correction must invalidate later approval/routing state.
7. The two app projections must be visibly and structurally disjoint.
8. All important interactive transitions must update the append-only case
   history.
9. Refresh existing automated tests and add tests for the new state transitions
   and critical text/controls.

## Acceptance criteria

The work is complete when:

- A first-time reviewer can state what CareTrust is and who operates the console
  after the first screen.
- The main six-minute walkthrough can be completed without opening raw JSON.
- Patient approval and organization routing are distinct actions with distinct
  records.
- Each extracted item opens its exact source evidence.
- Medication and warning-sign content cannot be routed as ordinary tasks.
- The scheduling and direct-care apps receive different minimum payloads.
- The family, agency CNA, and respite caregivers receive different
  claim-derived capabilities for the same patient.
- The AI-assisted app-onboarding proposal is visibly a draft and cannot register
  or authorize the application without organization approval.
- The intent, evidence, and application-requirements compiler lanes all produce
  inspectable drafts with human gates and never produce a permit.
- A reviewer can follow the caregiver’s OIDC/PKCE/RAR authorization exchange
  from app redirect through token receipt without confusing authentication with
  patient-specific authorization.
- The family caregiver receives a bounded scheduling projection while the CNA
  receives no scheduling scope.
- The raw packet is absent from both payloads.
- Every app decision has an exact request, policy result, reason code, and
  receipt.
- Revocation followed by a fresh request visibly produces a deny while retaining
  the earlier receipt.
- Support-team membership is not visually confused with access permission.
- The long-term neutral/federated platform is understandable and visibly
  separated from current executable evidence.
- Federation metadata trust never bypasses local patient permission or policy.
- Desktop and 390-pixel mobile layouts work with keyboard-only navigation.
- There are no console errors.
- The full Python and static-demo test suite passes.

## Deliverable

Return:

1. implemented changes in the existing demo files;
2. a short summary of the UX decisions;
3. screenshots of the primary desktop workflow and mobile state;
4. the exact commands and test results used for verification; and
5. a list of any remaining product questions that require Michael’s decision.
