# Uploaded care-document lane

Status: `executed_local` for deterministic intake, review, policy, revocation, and
trace code; `contract_tested` for the synthetic extraction replay; `mapped_only`
for FHIR R4 candidate projections. This lane uses synthetic content only.

## Demonstrated workflow

1. Invited caregiver `account:synthetic-leilani` uploads or phone-scans a
   one-page synthetic discharge packet for `patient:synthetic-001`.
   `UploadedCareDocument` binds the caregiver to
   `invite-acceptance:synthetic-001`, plus the SHA-256 digest, classification,
   opaque original-retained reference, privacy classification, and
   malware/file-validation result. An accepted upload must be clean, valid,
   non-password-protected, and free of detected active content.
2. An extractor produces `DocumentExtractionDraft`. Every candidate fact,
   instruction, action item, or medication statement cites exact normalized
   page text, character offsets, and a page region. Uncertainty is explicit.
   The draft is never verified, current, clinically authoritative, or shareable.
3. An accountable reviewer issues `DocumentReviewCorrectionRecord`, bound to
   the exact draft hash. The reviewer approves, rejects, or defers every
   candidate and can correct wording while retaining evidence. Review confirms
   what the uploaded document says; it does not establish legal authority,
   clinical validity, or a current care plan.
4. The discharge-date statement, seven-day primary-care follow-up statement,
   and bring-documents reminder pass administrative/document-statement review.
   The medication instruction is rejected, and the warning-sign instruction is
   deferred pending clinical-source clarification. Approved items become
   `ApprovedDocumentItem` projections. They remain
   document-stated assertions, carry evidence and sensitivity, and require
   clinical confirmation where applicable.
5. The patient issues `DocumentShareGrant` messages for named reviewed items, app
   audiences, purposes, item kinds, sensitivity ceiling, and time window.
   Apps submit a fresh `DocumentShareRequest`; the policy returns a
   `DocumentShareDecision`. Raw documents, unreviewed items, items outside the
   grant, wrong audience/purpose, excess sensitivity, expiration, and revocation
   default to deny. A prior permit is not replayed after revocation.
6. Two disjoint grants demonstrate purpose minimization:
   `app:synthetic-scheduling` receives only the reviewed primary-care
   follow-up/window statement for `discharge_follow_up`;
   `app:synthetic-direct-care-tasks` receives only the reviewed bring-documents
   reminder for `visit_preparation`. Neither app receives the discharge-date
   fact, raw packet, medication text, or warning-sign text.

The executable messages and hashes are in
`artifacts/validation/synthetic-uploaded-care-document-trace.json`. Linked,
standalone JSON examples are in `docs/standards/examples/uploaded-care/`, and
their exact validation contracts are exported under `schemas/`.

## Standards interaction

| Boundary | Standard or contract | Demonstrated status | Truth boundary |
|---|---|---|---|
| File intake | CareTrust uploaded-care-document.v1; OWASP file-upload controls | executed_local | Validation permits processing, not clinical trust |
| AI extraction | CareTrust document-extraction-draft.v1 | contract_tested synthetic replay | Candidate only; exact evidence and uncertainty required |
| Accountable review | CareTrust document-review-correction-record.v1 | executed_local | Confirms document wording only |
| App sharing | CareTrust grant/request/decision; NIST SP 800-162 ABAC concepts | executed_local | Minimum necessary, audience/purpose bounded, default deny |
| Clinical document projection | HL7 FHIR R4 `DocumentReference` + `Provenance` | mapped_only | Candidate mapping; no FHIR server or official validator claim |
| Derived workflow/clinical resources | FHIR R4 `Task`, `CarePlan`, `MedicationStatement` | planned/draft candidate | Not emitted; requires review and additional clinical governance |
| HIE/EHR retrieval | SMART App Launch, US Core/other network profiles | planned | Future adapter, not a dependency of the near-term prototype |

FHIR `DocumentReference.status = current` is the R4 status of the document
reference, not a claim that extracted clinical content is current. The candidate
projection reports semantic loss for exact evidence regions and CareTrust's
purpose/audience/revocation policy because base R4 does not carry those meanings
without profiles or extensions.

## Privacy and security limits

- Never use real PHI in this proof of concept.
- The original is represented by an opaque retained reference; raw content is
  not included in an app decision.
- Extraction text is untrusted input. Rendering must escape content and must not
  execute embedded markup, instructions, macros, or scripts.
- Highly sensitive content cannot cross a restricted-only grant.
- Production requires authenticated accounts, encrypted object storage,
  production malware scanning, retention/deletion policy, breach controls, and
  organization-specific privacy review.

## Likely extension work

CareTrust's item-level evidence, accountable review partition, purpose/audience
scope, and revocation semantics are preserved locally and explicitly identified
when base standards lose them. A future standards track can evaluate FHIR
extensions or profiles, UMA 2.0 authorization details, and verifiable
authorization/delegation representations without falsely claiming those
profiles exist or have been implemented here.
