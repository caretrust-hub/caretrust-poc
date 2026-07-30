# CareTrust interoperability artifacts

This directory documents the bounded interoperability surface implemented by
the synthetic CareTrust proof of concept. It separates executable contracts
from design mappings so evaluators can see what runs today and what remains
future standards work.

## Implemented boundary

- Strict CareTrust JSON contracts for an active professional-credential claim,
  an authorization request, and an authorization decision.
- Deterministic, default-deny activation and authorization policy with stable
  machine-readable reason codes.
- Short-lived JWTs signed and verified as EdDSA JSON Web Signatures (JWS), with
  audience, purpose, subject, claim, lifetime, status, and in-memory revocation
  checks.
- Synthetic Hawaii CNA data, synthetic registry results, and no live
  integrations.

The checked-in schemas in [`../../schemas`](../../schemas) are generated from
the runtime Pydantic models by
[`../../scripts/export_interoperability_artifacts.py`](../../scripts/export_interoperability_artifacts.py).
The JSON examples in [`examples`](examples) validate against those models.

## Explicit boundary

CareTrust does **not** claim FHIR conformance, Verifiable Credential
conformance, OID4VC support, SMART authorization, OpenID Federation,
identity proofing, live registry access, production security, or an operational
federation. The FHIR and VC documents are field-level design mappings only.

See:

- [Lifecycle and reason codes](lifecycle-and-reason-codes.md)
- [Standards status](standards-status.md)
- [FHIR R4 mapping](fhir-r4-practitioner-qualification-mapping.md)
- [W3C Verifiable Credentials 2.0 mapping](w3c-vc-2.0-mapping.md)
- [Synthetic examples](examples/README.md)

## Official specifications

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [JSON Web Signature (RFC 7515)](https://www.rfc-editor.org/rfc/rfc7515)
- [JSON Web Token (RFC 7519)](https://www.rfc-editor.org/rfc/rfc7519)
- [FHIR R4 Practitioner](https://hl7.org/fhir/R4/practitioner.html)
- [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/)
