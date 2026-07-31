# Standards implementation status

Every status in this table comes from the machine-readable
[evidence-status registry](evidence-status-registry.json). The six permitted
values are `retained_aws`, `executed_local`, `contract_tested`,
`local_simulation`, `mapped_only`, and `planned`. They classify evidence; none
is a production-readiness or conformance claim.

| Standard or capability | Status | Evidence and boundary |
|---|---|---|
| AWS OCR-to-draft intake | **`retained_aws` — Retained AWS trace** | One same-run synthetic record retains Textract and Bedrock request metadata, hashes, evidence spans, and the resulting draft. It terminates at an unverified draft with blocking uncertainties; it does not activate a claim. |
| CareTrust JSON contracts and JSON Schema | **`executed_local` — Executed local** | Strict Pydantic models and deterministic schema exports cover evidence, draft extraction, review, synthetic registry results, active claims, authorization requests/decisions, revocation records, and audit events. These are CareTrust application contracts, not an external standard or independent JSON Schema certification. |
| OpenAPI 3.1 HTTP surface | **`contract_tested` — Contract tested** | The machine-readable document defines a possible Phase 2 surface and is checked for internal contract consistency. No HTTP server or transport is deployed. |
| Revocation | **`executed_local` — Executed local** | The runtime enforces claim/token revocation in memory and tests fresh-request denial. The separately checked revocation-record contract is not emitted, persisted, or distributed by a durable status service. |
| CareTrust lifecycle and default-deny policy | **`executed_local` — Executed local** | Human review, synthetic source-check, activation, audience/purpose, validity, signature, status, and reason-code paths execute in local tests. |
| JWS/JWT security profile | **`executed_local` — Executed local** | Compact JWTs use EdDSA JWS, short lifetimes, local key trust, audience/purpose binding, and in-memory revocation. This bounded CareTrust profile is not a certification claim. See [RFC 7515](https://www.rfc-editor.org/rfc/rfc7515) and [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519). |
| FHIR R4 qualification projection | **`executed_local` — Executed local** | Code deterministically emits and locally validates a synthetic `Bundle` containing `Practitioner`, `Organization`, and `Provenance`. No official HL7 validator, StructureDefinition, FHIR server, EHR, implementation guide, or independent implementation is used. |
| W3C Verifiable Credentials Data Model 2.0 | **`mapped_only` — Mapped only** | A conceptual claim projection is documented, but no VC document, JSON-LD processing, VC securing mechanism, status method, or conformance suite is implemented. See [VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) and [VC JOSE/COSE](https://www.w3.org/TR/vc-jose-cose/). |
| OpenID4VCI and OpenID4VP exchange artifacts | **`contract_tested` — Contract tested** | Metadata, offer, authorization-detail, presentation-request, intentionally invalid placeholder response, and policy-linkage artifacts are cross-checked. There is no endpoint, wallet, issuance, valid presentation, proof verification, or interoperability test. |
| SMART App Launch | **`planned` — Planned** | Candidate future app authorization integration; no FHIR authorization server, scopes, launch context, EHR integration, or SMART test. See [SMART App Launch](https://hl7.org/fhir/smart-app-launch/). |
| OpenID Federation-shaped trust resolution | **`local_simulation` — Local simulation** | Signed synthetic entity statements for two organizations resolve against one locally pinned trust anchor. There is no discovery, network call, operational federation, or cross-organization test. |
| Synthetic HIE/EHR clinical-data holder edge | **`executed_local` — Executed local** | An authorized synthetic participating-organization user/client supplies CareTrust caregiver delegation/trust context. The caregiver does not query the holder. The holder independently gates participant/client/user eligibility, patient match, and final disclosure, returning a strict FHIR R4-shaped CarePlan bundle only on permit. No live HIE/EHR, MPI, SMART/OAuth, FHIR server, legal determination, or independent interoperability test is represented. |
| Identity proofing | **`planned` — Planned** | Synthetic subject references only; no driver-license, biometric, authoritative identity, NIST IAL, or vendor proofing integration. |
| Live Hawaii CNA registry | **`planned` — Planned** | Deterministic simulator only; no screen scraping, API, or authoritative source verification. |

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
prototype. The [provenance-lineage registry](provenance-lineages.json)
separately records which artifacts belong to the retained AWS intake,
deterministic lifecycle, contract-example, projection, and local-simulation
families.
