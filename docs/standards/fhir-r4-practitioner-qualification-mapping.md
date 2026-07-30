# Design mapping to FHIR R4 `Practitioner.qualification`

Status: **Mapped only — not implemented**.

The target is the `Practitioner.qualification` backbone element in
[FHIR R4 Practitioner](https://hl7.org/fhir/R4/practitioner.html). The table is
a proposed projection of a CareTrust active claim, not a serialized FHIR
resource or an HL7 profile.

| CareTrust field | Candidate FHIR R4 location | Transformation or gap |
|---|---|---|
| `subject_ref` | containing `Practitioner.id` or an external `Practitioner.identifier` | Requires identity resolution and an identifier system; copying the opaque CareTrust reference is not sufficient. |
| `claim_id` | `Practitioner.qualification.identifier` | Candidate qualification-instance identifier. A stable `Identifier.system` URI is required and is not defined by the prototype. |
| `registry_id` | `Practitioner.qualification.identifier.value` | Candidate authoritative credential number. `Identifier.system`, type, assigner, and provenance require governance. |
| `credential_type` | `Practitioner.qualification.code` | “Certified Nurse Aide” can be carried as `CodeableConcept.text`; interoperable coding requires an agreed code system and terminology binding. |
| `valid_from` | `Practitioner.qualification.period.start` | ISO date can project to FHIR `dateTime`; precision and timezone policy must be retained. |
| `valid_until` | `Practitioner.qualification.period.end` | The prototype treats a date-only end as inclusive through the end of that UTC date. FHIR `Period.end` is an upper boundary, so a profile must define an exact conversion. |
| `issuer_ref` | `Practitioner.qualification.issuer` | Candidate `Reference(Organization)`. Requires a resolvable Organization identity; a CareTrust string is not automatically a FHIR reference. |
| `jurisdiction` | no direct R4 qualification child | Requires a governed extension, coding convention, or adjacent resource/profile decision. |
| `status`, `revoked_at` | no direct R4 qualification child | Requires an extension or a separate status artifact; a missing status must never be interpreted as active. |
| `evidence_refs` | no direct R4 qualification child | Candidate linkage through `Provenance`, `DocumentReference`, or governed extensions; none is implemented. |
| `review_id`, `registry_result_id` | no direct R4 qualification child | Candidate provenance/entity references. Review and source-check semantics need a profile or implementation guide. |
| `issued_at` | no direct R4 qualification child | Candidate `Provenance.recorded` for the projection event, not necessarily the credential’s original issue date. |
| `allowed_audiences`, `allowed_purposes` | no direct R4 qualification child | Authorization policy belongs outside the qualification unless a governed security-label or consent approach is selected. |
| `schema_version`, `credential_profile`, `claim_type` | FHIR `meta.profile`, coding, or out-of-band contract | A real canonical profile URL and terminology are not defined. |

## Non-conformance boundary

The proof of concept does not:

- emit a FHIR `Practitioner`;
- expose a FHIR REST endpoint;
- define a StructureDefinition, extension, search parameter, capability
  statement, terminology binding, or implementation guide;
- run an HL7 FHIR validator; or
- claim that a mapped CareTrust claim is interchangeable with a FHIR resource.

FHIR JSON has rules beyond generic JSON Schema. See
[FHIR R4 JSON representation](https://hl7.org/fhir/R4/json.html). A later
implementation should define and validate a constrained projection, preserve
the original CareTrust audit binding, and test round trips for loss and
semantic drift.
