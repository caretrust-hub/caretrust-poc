# Design mapping to FHIR R4 `Practitioner.qualification`

Document evidence status: **`mapped_only` — Mapped only**.

The target is the `Practitioner.qualification` backbone element in
[FHIR R4 Practitioner](https://hl7.org/fhir/R4/practitioner.html). The table is
a design-level field analysis. Separately, the repository now contains an
**`executed_local` — Executed local** bounded projection that emits a synthetic
FHIR R4-shaped `Bundle`; see the
[projection profile](fhir-r4-projection-profile.md) and its
[generated example](examples/fhir/synthetic-hawaii-cna-bundle.json). Neither
document is an HL7 profile or conformance claim.

| CareTrust field | Candidate FHIR R4 location | Transformation or gap |
|---|---|---|
| `subject_ref` | containing `Practitioner.identifier` | The local projection uses a synthetic identifier system; production identity resolution and governance remain undefined. |
| `claim_id` | `Bundle.identifier` and `Provenance.entity.what.identifier` | The local projection preserves the opaque CareTrust claim identifier under a prototype URI system. A governed production URI strategy remains undefined. |
| `registry_id` | `Practitioner.qualification.identifier.value` | The local projection uses a visibly synthetic registry identifier system. Authoritative system, type, assigner, and provenance governance remain open. |
| `credential_type` | `Practitioner.qualification.code` | The local projection uses a CareTrust-local `hawaii-cna` code and text. It is not an official terminology binding. |
| `valid_from` | `Practitioner.qualification.period.start` | ISO date can project to FHIR `dateTime`; precision and timezone policy must be retained. |
| `valid_until` | `Practitioner.qualification.period.end` | The local profile treats the source date and R4 `Period.end` as inclusive and preserves the date without adjustment. Production precision and timezone policy still require governance. |
| `issuer_ref` | `Practitioner.qualification.issuer` | The local projection bundles a synthetic `Organization` and uses an internal reference. Production Organization identity and resolution remain undefined. |
| `jurisdiction` | no direct R4 qualification child | The local projection uses a CareTrust-local extension; a governed canonical extension is still needed. |
| `status`, `revoked_at` | no direct R4 qualification child | The local projection carries active status in a CareTrust-local extension and rejects revoked source claims. A distributed status design remains unimplemented. |
| `evidence_refs` | `Provenance.entity` | The local projection retains source identifiers in `Provenance`; dereferencing, privacy, and authoritative semantics remain undefined. |
| `review_id`, `registry_result_id` | no direct R4 qualification child | These are not projected. Review and source-check semantics need a profile or implementation guide. |
| `issued_at` | no direct R4 qualification child | Candidate `Provenance.recorded` for the projection event, not necessarily the credential’s original issue date. |
| `allowed_audiences`, `allowed_purposes` | no direct R4 qualification child | Authorization policy belongs outside the qualification unless a governed security-label or consent approach is selected. |
| `schema_version`, `credential_profile`, `claim_type` | FHIR `meta.profile`, coding, or out-of-band contract | A real canonical profile URL and terminology are not defined. |

## Non-conformance boundary

The proof of concept does:

- deterministically emit a local FHIR R4-shaped `Bundle` containing a
  `Practitioner`, `Organization`, and `Provenance`; and
- validate that bounded output with CareTrust's local validator and tests.

It does **not**:

- expose a FHIR REST endpoint;
- define a StructureDefinition, extension, search parameter, capability
  statement, terminology binding, or implementation guide;
- run an HL7 FHIR validator; or
- claim that a mapped CareTrust claim is interchangeable with a FHIR resource.

FHIR JSON has rules beyond the local checks. See
[FHIR R4 JSON representation](https://hl7.org/fhir/R4/json.html). A later
implementation should publish and validate a governed profile, preserve the
original CareTrust audit binding, and test round trips with an independent
implementation for loss and semantic drift.
