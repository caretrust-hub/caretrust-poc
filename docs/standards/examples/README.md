# Synthetic interoperability examples

All examples are fictional and validate against the checked-in CareTrust JSON
schemas. They demonstrate the application contract, not FHIR or W3C
Verifiable Credential conformance.

- `active-credential-claim.json`: a post-review, post-simulator active claim.
- `authorization-request.json`: a synthetic app request that can be permitted.
- `authorization-request-deny.json`: a request with an unapproved audience and
  purpose.
- `authorization-decision-permit.json`: the default-deny policy’s permit shape.
- `authorization-decision-deny.json`: the corresponding deny shape with
  audience and purpose failures and no supporting claim.

No token is checked in because private signing keys are generated only in
memory by tests and demos.
