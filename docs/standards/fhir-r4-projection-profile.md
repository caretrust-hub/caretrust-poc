# CareTrust bounded FHIR R4 projection profile

Evidence status: **`executed_local` — Executed local**. This means an
executable local projection with deterministic local tests; it is not an
official FHIR conformance claim.

This prototype projects one active, synthetic Hawaii Certified Nurse Aide
CareTrust claim into a FHIR R4 `Bundle` of type `collection`. The bundle carries
exactly:

1. one `Practitioner` with one `qualification`;
2. one issuer `Organization`; and
3. one `Provenance` record identifying the practitioner as the generated target,
   the organization as the participating agent, and the CareTrust claim and
   evidence references as source entities.

The structure follows the published R4 resource definitions:

- [`Practitioner.qualification`](https://hl7.org/fhir/R4/practitioner.html)
  permits qualification identifiers, a required `CodeableConcept`, a validity
  `Period`, and an issuer `Reference(Organization)`.
- [`Organization`](https://hl7.org/fhir/R4/organization.html) requires at least
  a name or identifier.
- [`Provenance`](https://hl7.org/fhir/R4/provenance.html) requires one or more
  targets, a recorded instant, and one or more agents; source entities use the
  required R4 `source` role.
- [`Bundle`](https://hl7.org/fhir/R4/bundle.html) supports `collection` and
  requires unique `fullUrl` values when supplied.
- R4 [`Period`](https://hl7.org/fhir/R4/datatypes.html#Period) uses inclusive
  start and end boundaries.

## Executable boundary

`caretrust.fhir_projection.project_active_claim_to_fhir_r4()` accepts only an
active, unrevoked claim with full valid-from and valid-until dates, at least one
evidence reference, and identifiers explicitly marked synthetic. It emits
deterministic resource IDs and references.

`caretrust.fhir_projection.validate_fhir_r4_projection()` checks the local
contract without network calls. It enforces:

- `Bundle`, `Practitioner`, `Organization`, and `Provenance` resource types;
- FHIR `id` lexical form and unique, ID-bound `fullUrl` values;
- exactly one qualification with a synthetic registry identifier;
- the local Hawaii CNA coding, human-readable display, and text;
- ordered, valid dates in the qualification `Period`;
- an issuer reference to the bundled `Organization`;
- local status `active` and jurisdiction `HI` qualification extensions;
- the `Provenance` target, issuer agent, activity, recorded time, and source
  claim/evidence identifiers; and
- optional exact equality with the deterministic projection of an expected
  `ActiveCredentialClaim`.

CareTrust treats a credential `valid_until` date as inclusive, matching R4
`Period.end`, so the date projects without adjustment. For example,
`valid_until = 2028-04-15` becomes `Period.end = 2028-04-15`.

## Local terminology and extensions

All identifier systems, code systems, and extension URLs under
`https://caretrust.example/fhir/` are local prototype identifiers. In
particular, `hawaii-cna` is not asserted to be an official HL7, state, or
national terminology code. The two qualification extension URLs carry
CareTrust status and jurisdiction because R4
`Practitioner.qualification` has no direct children for those semantics.

No `StructureDefinition`, official terminology publication, CapabilityStatement,
FHIR REST endpoint, or implementation guide is supplied in Phase 1.

## Deliberate omissions

The source active claim does not contain a reviewed human name, so the projection
does not invent a `Practitioner.name`. It does not emit `PractitionerRole`,
`DocumentReference`, or a live-registry resource. Audience and purpose policy
remain in the CareTrust authorization layer rather than being represented as
qualification data.

The checked-in
[`synthetic-hawaii-cna-bundle.json`](examples/fhir/synthetic-hawaii-cna-bundle.json)
is generated from a synthetic claim and is asserted byte-for-structure against
the projection in automated tests.

No EHR or FHIR server is contacted. The projection and its local validator run
in the same test environment; no exchange with an independent implementation
is represented.

## Validation limitation

The automated tests execute CareTrust's deterministic local validator. They do
not run the official HL7 FHIR validator, validate extension definitions, or
establish interoperability with an independent FHIR implementation. The result
should therefore be described as an executable R4-shaped projection, not as a
conformant FHIR profile or certified FHIR resource.
