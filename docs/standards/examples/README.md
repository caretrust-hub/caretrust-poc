# Synthetic interoperability examples

All examples are fictional and validate against the runtime CareTrust
contracts. Tests separately require every checked-in generated schema to equal
its runtime contract. These examples do not establish independent JSON Schema,
FHIR, or W3C Verifiable Credential conformance.

- `evidence-artifact.json`: synthetic evidence metadata and one source span.
- `extraction-record.json`: a retained, failed synthetic extraction attempt.
- `review-record.json`: an authorized correction bound to an immutable draft.
- `registry-result.json`: one deterministic synthetic source-match result.
- `active-credential-claim.json`: a post-review, post-simulator active claim.
- `authorization-request.json`: a synthetic app request that can be permitted.
- `authorization-request-deny.json`: a request with an unapproved audience and
  purpose.
- `authorization-decision-permit.json`: the default-deny policy’s permit shape.
- `authorization-decision-deny.json`: the corresponding deny shape with
  audience and purpose failures and no supporting claim.
- `revocation-record.json`: a machine-readable synthetic claim-revocation
  record shape.
- `audit-event.json`: the corresponding synthetic revocation audit-event shape.
- `clinical-edge/`: five executed-local synthetic participating-organization
  and data-holder exchange records covering permit, unregistered client,
  patient no-match, insufficient delegated scope, and a fresh request after
  revocation. The caregiver is delegation context, not the HIE requester or
  recipient. The data holder owns participant/client/user eligibility,
  patient matching, and final disclosure policy; no live HIE or EHR is
  connected.
- `delegation/`: a linked patient-intent, clarification, hashed invite,
  explicit approval, relationship, least-privilege grant, application decision,
  and revocation example chain. These artifacts do not establish identity or
  legal authority.

No token is checked in because private signing keys are generated only in
memory by tests and demos.

The revocation-record contract is exported and validated as an interoperability
artifact. The Phase 1 runtime still uses in-memory revocation state and does not
emit this record through a durable or federated status service.
