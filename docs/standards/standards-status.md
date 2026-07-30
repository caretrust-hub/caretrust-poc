# Standards implementation status

The labels below deliberately distinguish executable prototype behavior from
design intent. “Mapped” means that a documented field correspondence exists;
it does not mean the prototype emits or accepts a conformant artifact.

| Standard or capability | Status | Evidence and boundary |
|---|---|---|
| CareTrust JSON contracts and JSON Schema | **Implemented and tested** | Strict Pydantic models and deterministic schema exports cover evidence, draft extraction, extraction records, human review, synthetic registry results, active claims, authorization requests/decisions, revocation records, and audit events. Tests compare every checked-in schema with its runtime contract and validate synthetic JSON examples. These are CareTrust application contracts, not an external standard or an independent JSON Schema conformance result. |
| OpenAPI 3.1 HTTP surface | **Contract only — no Phase 1 server** | A machine-readable OpenAPI 3.1 document defines a bounded possible Phase 2 surface for evidence, review, synthetic registry checks, activation, claim retrieval/revocation, authorization, and read-only evaluation records. Tests check its version, unique operation identifiers, local schema references, and explicit implementation-status labels. No HTTP transport is deployed in Phase 1. |
| Revocation-record contract | **Contract implemented and tested; runtime emission not implemented** | A machine-readable claim/token revocation record schema and synthetic example are exported and runtime-model validated. The current revocation seam remains in memory and does not persist or distribute this record. |
| CareTrust lifecycle and default-deny policy | **Implemented and tested** | Human review, synthetic source-check, activation, audience/purpose, validity, and reason-code paths execute in local tests. |
| JWS/JWT security profile | **Implemented and tested** | Compact JWTs use EdDSA JWS, short lifetimes, local key trust, audience/purpose binding, and in-memory revocation. This is a bounded prototype profile, not a certification claim. See [RFC 7515](https://www.rfc-editor.org/rfc/rfc7515) and [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519). |
| FHIR R4 `Practitioner.qualification` | **Mapped only — not implemented** | A field projection is documented, but no FHIR resource, profile, terminology binding, validator result, FHIR API, or conformance statement is implemented. See [FHIR R4 Practitioner](https://hl7.org/fhir/R4/practitioner.html). |
| W3C Verifiable Credentials Data Model 2.0 | **Mapped only — not implemented** | A conceptual claim projection is documented, but no VC document, JSON-LD processing, VC securing mechanism, status method, or conformance suite is implemented. See [VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) and [VC JOSE/COSE](https://www.w3.org/TR/vc-jose-cose/). |
| OpenID for Verifiable Credential Issuance | **Planned / not implemented** | Candidate future issuance transport; no endpoint, metadata, authorization flow, proof, or interoperability test. See [OpenID4VCI 1.0](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html). |
| OpenID for Verifiable Presentations | **Planned / not implemented** | Candidate future presentation transport; no verifier/wallet flow or interoperability test. See [OpenID4VP 1.0](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html). |
| SMART App Launch | **Planned / not implemented** | Candidate future app authorization integration; no FHIR authorization server, scopes, launch context, or EHR integration. See [SMART App Launch](https://hl7.org/fhir/smart-app-launch/). |
| OpenID Federation 1.0 | **Planned / not implemented** | Candidate future trust-chain mechanism; no entity statements, trust anchors, subordinate statements, resolution, or operational federation. See [OpenID Federation 1.0](https://openid.net/specs/openid-federation-1_0.html). |
| Identity proofing | **Out of scope / not implemented** | Synthetic subject references only; no driver-license, biometric, authoritative identity, NIST IAL, or vendor proofing integration. |
| Live Hawaii CNA registry | **Out of scope / not implemented** | Deterministic simulator only; no screen scraping, API, or claim of source verification. |

## Where standards work is still needed

The prototype makes gaps observable instead of hiding them behind a
proprietary claim:

1. A governed vocabulary and profile for caregiver authority, relationship,
   professional credential, delegation, scope, jurisdiction, and expiration.
2. A FHIR profile or implementation guide defining how trust provenance,
   source-check results, restrictions, and lifecycle status travel with (or
   alongside) `Practitioner.qualification`.
3. A VC credential type, context/terms, credential status method, evidence
   conventions, and securing/enveloping profile.
4. Cross-organization issuer/verifier metadata, trust-list governance,
   revocation/status distribution, audit semantics, and federation policy.
5. Privacy-preserving presentation and purpose/audience semantics that can be
   tested across apps without disclosing unrelated claims.

Those are proposed collaboration areas, not capabilities of this TRL 3
prototype.
