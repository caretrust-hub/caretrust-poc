# ALU LIKE caregiver-support reference scenario

> **Illustrative design scenario only.** ALU LIKE has not endorsed CareTrust and
> is not represented as a project partner. The program facts below come from
> ALU LIKE's public Native Hawaiian Caregiver Support Program page, reviewed
> 2026-07-30.

## Why this is a useful reference

ALU LIKE describes a program for families caring for an older Native Hawaiian
relative with a chronic condition or disability and for some grandparents or
older relatives caring for children. The public program page states that the
care recipient's age and ethnicity must be evidenced for the elder-care pathway,
while the caregiver does not need to provide that proof. It lists caregiver
information, access assistance, counseling/support-group/training referrals,
respite support, and limited supplemental services.

Source: [ALU LIKE Native Hawaiian Caregiver Support Program](https://www.alulike.org/services/kumu-kahi/caregiver-support/).

These facts expose three different concerns that proprietary applications often
collapse:

1. **Evidence and program eligibility** — an accountable program operator applies
   a governed policy to evidence.
2. **Caregiver relationship and bounded delegation** — a care recipient or other
   accountable authority establishes who may do what, for which purpose and
   period.
3. **Application authorization** — each service application independently decides
   whether a particular request is allowed.

CareTrust does not decide Native Hawaiian identity, disability, capacity, legal
authority, or program eligibility with AI. AI may organize submitted information,
identify missing evidence, draft bounded intent, and produce clarification
questions. An authorized program worker or governed source makes every
authority-bearing decision.

## Target operating model

```text
Care recipient + family caregiver
       | intent, invite, evidence status
       v
ALU LIKE-like operator console
  - intake and referral queue
  - human evidence/program-policy review
  - relationship and delegation review
  - service authorization and exception handling
  - status, revocation, and audit
       |
       v
Neutral CareTrust trust core
  - source/evidence references and hashes
  - relationship, eligibility, participation, and delegation claims
  - signed short-lived presentations and status
  - purpose/audience policy receipts
  - FHIR/RAR/OID4VC projection seams
       |
       +----------------+------------------+------------------+
       v                v                  v                  v
Service navigator   Training/support   Respite scheduler   Supplemental-service app
local policy        local policy       local policy        local policy
```

The operator console is the main organization's workspace. It is not the only
caregiving application. Mobile and web applications remain independently owned,
independently governed, and free to evolve. They integrate with the trust core
through open request, claim, status, and decision contracts.

## Candidate claim families

| Claim | Accountable issuer | What it establishes | What it does not establish |
|---|---|---|---|
| `CareRelationshipClaim` | Care recipient or governed operator | A stated or reviewed relationship and period | Identity, capacity, legal proxy authority, or app access |
| `DelegationGrant` | Care recipient or governed authority | Specific actions, resources, exclusions, audience, purpose, and period | Universal access or an app permit |
| `ProgramEligibilityClaim` | Program operator | The operator applied a named policy version and found the synthetic participant eligible | The raw basis, ethnicity, disability, or legal status for unrelated uses |
| `ProgramParticipationClaim` | Program operator | Active enrollment/participation and status | Entitlement to every service |
| `ServiceAuthorizationClaim` | Program operator | A bounded service approval such as respite units and validity | Scheduling availability, payment, or downstream fulfillment |
| `ProfessionalCredentialClaim` | Credential/source workflow | A reviewed caregiver professional credential | Patient delegation or program eligibility |

The current repository executes only the professional-credential claim and is
building the patient-invited relationship/delegation lane. Eligibility,
participation, and service-authorization claims are target claim-model work until
their contracts, policies, exact messages, and tests exist.

## Minimum-disclosure application requests

Applications request a purpose-bound decision rather than the operator's source
documents.

### Service navigation

```json
{
  "audience": "urn:caretrust:app:service-navigation",
  "purpose": "caregiver-service-navigation",
  "requested_claims": [
    "program_participation",
    "care_relationship"
  ]
}
```

### Training and peer support

```json
{
  "audience": "urn:caretrust:app:caregiver-learning",
  "purpose": "caregiver-training-and-support",
  "requested_claims": [
    "program_participation"
  ]
}
```

### Respite scheduling

```json
{
  "audience": "urn:caretrust:app:respite-scheduling",
  "purpose": "respite-service-scheduling",
  "requested_claims": [
    "program_eligibility",
    "care_relationship",
    "service_authorization"
  ]
}
```

The respite application can receive a permit tied to an active eligibility and
service-authorization claim without receiving a birth certificate, ethnicity
evidence, clinical record, or unrelated program history. The application still
checks its own service capacity, scheduling, safety, and operational policy.

## Organization console capabilities

The v0.3 Network Explorer should model an operator console with these bounded
work queues and views:

- **Referrals and invitations** — who initiated the workflow, which relationship
  or service is requested, invitation expiry/replay state, and required next step.
- **Evidence readiness** — evidence received, missing, ambiguous, or needing
  accountable review; AI suggestions remain visibly unverified.
- **Trust records** — relationship, delegation, program, and service claims with
  distinct issuer, policy, validity, status, and provenance.
- **Application registry** — approved application identifier, declared purpose,
  supported request contract, public keys/metadata, and current trust status.
- **Decision receipts** — exact app requests, local policy versions, permit/deny
  results, reasons, supporting claim IDs, and disclosure summary.
- **Status and revocation** — append-only status history and fresh-request effects;
  no claim of terminating established sessions.
- **Standards/gap view** — native messages, FHIR/RAR/OID4VC/federation seams, their
  evidence classes, missing semantics, and governance owner.

### Patient/case workspace

An authorized organization user should be able to open one synthetic case and
browse three synchronized views derived from the same append-only CareTrust
trace:

1. **Care team** — the patient/care recipient, family and community caregivers,
   professionals, service coordinators, and participating organizations, with
   each member's role, relationship basis, issuer, validity, status, and
   provenance.
2. **Permissions** — a matrix of who may request which action, through which
   application, for which purpose and data/service category, until when, with
   explicit exclusions and current/revoked/expired state.
3. **Case history** — referrals, patient intent, AI draft and clarification,
   invitation and acceptance, evidence review, approvals, claim issuance,
   application decisions, corrections, expiration, and revocation in immutable
   event order.

Each row must drill into the exact source claim, authorization request, local
policy decision, reason codes, and provenance available to that operator's role.
Historical entries remain visible after revocation; a correction appends a new
event and never rewrites prior history. This is a trust and service-coordination
case record, not a complete clinical chart.

FHIR R4 `CareTeam` is a candidate projection for participating people and
organizations. `RelatedPerson`, `Consent`, and `Provenance` carry narrower
relationship, delegation-choice, and derivation semantics. `AuditEvent` is a
candidate representation for security-relevant access activity. `Task`,
`ServiceRequest`, and `EpisodeOfCare` require future workflow profiling; the
native CareTrust trace remains authoritative in v0.3.

### Patient- or relative-provided care packet

The more realistic near-term information handoff is a patient or invited family
caregiver uploading or phone-scanning a synthetic discharge packet, visit
instructions, or medical-record excerpt. CareTrust can preserve the original
hash and uploader provenance, let AI draft evidence-linked coordination items,
route ambiguous or sensitive content to accountable review, and disclose only
approved items to the applications that need them.

For example, a scheduling app may receive a reviewed follow-up date and a
transportation app may receive the time and location, while neither receives the
complete discharge packet, diagnosis, medication list, or unrelated case
history. A care portal may receive a separately approved instruction excerpt.
Every disclosure has a purpose, audience, source item, policy decision, and
receipt.

Uploading proves only which synthetic account supplied the file. It does not
prove hospital authorship, legal authority, clinical accuracy, or currentness.
Human review can confirm transcription and intended sharing; it is not a medical
validation. The original remains restricted and revocation blocks fresh app
requests without deleting historical receipts.

### Long-term clinical-data exchange edge

A future organization deployment may connect the patient/case workspace to a
health information exchange such as Hawaiʻi HIE or to an EHR. CareTrust supplies
the governed trust context and authorization request; the clinical-data holder
performs patient matching, applies its own legal and organizational policy, and
returns only the permitted data through its supported exchange interface.

The v0.3 repository may retain this edge as secondary executable technical
evidence with synthetic FHIR R4 resources and an explicit holder-local policy
decision. The main walkthrough labels Hawaiʻi HIE connectivity as `planned`:
there is no live connection, data-sharing agreement, patient match, or production
clinical-data exchange in the prototype.

## Diverse application integration

The neutral layer is useful only if applications do not have to adopt the
operator console's internal database or proprietary identity model. Candidate
integration surfaces are:

1. CareTrust JSON Schemas and OpenAPI request/decision contracts.
2. Short-lived, audience/purpose-bound signed CareTrust JWTs for the local
   reference implementation.
3. FHIR projections when a healthcare system needs `Consent`, `RelatedPerson`,
   `Practitioner.qualification`, or `Provenance` representations.
4. An OAuth RAR caregiver-delegation type for fine-grained authorization details.
5. OID4VCI/OID4VP/DCQL candidate issuance/presentation artifacts for future wallet
   or credential exchange.
6. OpenID Federation-shaped metadata trust and distributed status as future
   network-governance work.

These are concrete candidate seams, not one executed distributed transaction.

## Phase 2 hypotheses to test with an operator

- Staff re-key fewer repeated participant, relationship, and status facts.
- Caregivers complete fewer duplicate onboarding steps across service apps.
- Downstream applications receive less raw eligibility evidence.
- Staff can see exactly which app requested which claim for which purpose.
- Revocation and expiration produce consistent fresh-request denials.
- Community organizations can add or replace applications without migrating a
  proprietary caregiver identity/claim database.

These are hypotheses, not demonstrated workforce outcomes. Phase 2 requires
workflow co-design with caregivers and staff, privacy/security review, governed
eligibility and authority policies, accessibility research, and at least two real
application integrations.
