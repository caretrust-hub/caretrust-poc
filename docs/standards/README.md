# CareTrust interoperability artifacts

This directory documents the bounded interoperability surface implemented by
the synthetic CareTrust proof of concept. It separates executable contracts
from design mappings so evaluators can see what runs today and what remains
future standards work.

All capability labels are defined once in the machine-readable
[evidence-status registry](evidence-status-registry.json):
`retained_aws`, `executed_local`, `contract_tested`, `local_simulation`,
`mapped_only`, and `planned`. The
[provenance-lineage registry](provenance-lineages.json) prevents matching
synthetic identifiers from being mistaken for proof that separate artifacts
came from one execution.

## Implemented boundary

- One **`retained_aws`** synthetic Textract-to-Bedrock record. It stops at an
  unverified draft and is not the deterministic activation trace.
- **`executed_local`** strict CareTrust JSON contracts for evidence, draft extraction, review,
  synthetic registry results, active professional-credential claims,
  authorization requests and decisions, and audit events.
- **`executed_local`** in-memory revocation enforcement and fresh-request
  denial. The exported revocation-record contract is checked separately; the
  runtime does not emit it through a durable status service.
- A **`contract_tested`** bounded
  [OpenAPI 3.1 contract](caretrust-openapi-3.1.json) for a possible
  Phase 2 HTTP surface. It reuses the published JSON contracts and stable
  reason/status vocabularies; Phase 1 does not deploy an HTTP server.
- **`executed_local`** deterministic, default-deny activation and
  authorization policy with stable
  machine-readable reason codes.
- **`executed_local`** short-lived JWTs signed and verified as EdDSA JSON Web
  Signatures (JWS), with
  audience, purpose, subject, claim, lifetime, status, and in-memory revocation
  checks.
- An **`executed_local`** deterministic FHIR R4-shaped projection with local
  tests, without an official validator, server, EHR, profile, or conformance
  claim.
- **`contract_tested`** OID4VCI/OID4VP-shaped artifacts, without endpoints,
  a wallet, a valid credential or presentation, or protocol conformance.
- A **`local_simulation`** OpenID Federation-shaped one-hop resolver, without
  discovery, network calls, or an operational federation.
- An **`executed_local`** synthetic
  [clinical-data holder edge](clinical-data-holder-edge.md) in which CareTrust
  supplies caregiver delegation/trust context to a participating-organization
  application while the synthetic data holder owns participant/client/user
  eligibility, patient matching, and the final disclosure policy. The
  caregiver never directly queries the holder. No live HIE or EHR is connected.
- Synthetic Hawaii CNA data, synthetic registry results, and no live
  integrations.

The checked-in schemas in [`../../schemas`](../../schemas) are generated from
the runtime Pydantic models by
[`../../scripts/export_interoperability_artifacts.py`](../../scripts/export_interoperability_artifacts.py).
The JSON examples in [`examples`](examples) validate against those models.

## Explicit boundary

CareTrust does **not** claim FHIR conformance, Verifiable Credential
conformance, deployed OID4VC support, SMART authorization, operational OpenID
Federation, identity proofing, live registry access, production security, or
an operational care network. The OpenAPI document is a contract-tested Phase 2
service design, not evidence of a deployed transport. The VC document remains
`mapped_only`; SMART integration remains `planned`.

See:

- [Lifecycle and reason codes](lifecycle-and-reason-codes.md)
- [OpenAPI 3.1 contract](caretrust-openapi-3.1.json)
- [Standards status](standards-status.md)
- [Evidence-status registry](evidence-status-registry.json)
- [Provenance and identifier lineages](provenance-lineages.json)
- [FHIR R4 mapping](fhir-r4-practitioner-qualification-mapping.md)
- [Executable local FHIR projection profile](fhir-r4-projection-profile.md)
- [W3C Verifiable Credentials 2.0 mapping](w3c-vc-2.0-mapping.md)
- [OID4VC exchange profile](oid4vc-exchange-profile.md)
- [Local federation simulation profile](openid-federation-trust-profile.md)
- [Synthetic HIE/EHR clinical-data holder edge](clinical-data-holder-edge.md)
- [Synthetic examples](examples/README.md)

## Official specifications

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [JSON Web Signature (RFC 7515)](https://www.rfc-editor.org/rfc/rfc7515)
- [JSON Web Token (RFC 7519)](https://www.rfc-editor.org/rfc/rfc7519)
- [FHIR R4 Practitioner](https://hl7.org/fhir/R4/practitioner.html)
- [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/)
