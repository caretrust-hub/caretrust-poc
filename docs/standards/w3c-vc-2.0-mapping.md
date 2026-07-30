# Design mapping to W3C Verifiable Credentials Data Model 2.0

Status: **Mapped only — not implemented**.

The target is the
[W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/).
This table describes a possible future credential representation. The
prototype currently uses a CareTrust JSON claim and a compact EdDSA JWS/JWT;
that token is not presented as a conforming Verifiable Credential.

| CareTrust field | Candidate VC 2.0 location | Transformation or gap |
|---|---|---|
| `claim_id` | credential `id` | Requires a globally unambiguous URI strategy. Current opaque IDs are synthetic application identifiers. |
| `issuer_ref` | `issuer` | Requires an issuer identifier and metadata that verifiers can resolve and trust. |
| `issued_at` | `validFrom` | Can project from the activation timestamp; policy must distinguish activation from an original professional-license issue date. |
| `valid_until` | `validUntil` | Date-only inclusive semantics require conversion to a precise VC date-time boundary. |
| `subject_ref` | `credentialSubject.id` | Requires a privacy-aware subject identifier strategy and correlation policy. |
| `claim_type`, `credential_profile` | credential `type` | Requires a governed CareTrust credential type and, for JSON-LD use, defined vocabulary terms/context. |
| `credential_type` | `credentialSubject.credentialType` (proposed) | `credentialType` is not defined here as a standard VC property; a vocabulary term and code system are needed. |
| `registry_id` | `credentialSubject.registryId` (proposed) | Custom term; identifier system, disclosure policy, and namespace governance are needed. |
| `jurisdiction` | `credentialSubject.jurisdiction` (proposed) | Custom term; governed code/value definition is needed. |
| `valid_from` | `credentialSubject.credentialValidFrom` (proposed) | Distinct from VC-envelope `validFrom`; custom semantics are needed for the underlying credential. |
| `status`, `revoked_at` | `credentialStatus` | Requires selection and implementation of a credential-status method. The in-memory prototype revocation seam is not one. |
| `evidence_refs` | `evidence` or linked provenance (candidate) | Requires an evidence vocabulary, privacy controls, integrity binding, and dereference policy. |
| `review_id`, `registry_result_id` | custom evidence/provenance terms | No standard CareTrust vocabulary or interoperable proof of these events exists. |
| `allowed_audiences`, `allowed_purposes` | presentation/authorization policy, not ordinary subject claims | Selective disclosure and verifier purpose binding need protocol and governance decisions. |
| `schema_version` | `credentialSchema` (candidate) | The CareTrust JSON Schema could be referenced only after defining a stable URI, schema type, and verification semantics. |

## Security-format boundary

The implemented compact token follows the basic JWS and JWT structures in
[RFC 7515](https://www.rfc-editor.org/rfc/rfc7515) and
[RFC 7519](https://www.rfc-editor.org/rfc/rfc7519). It has CareTrust-specific
claims and policy checks. It does not implement the
[W3C Securing Verifiable Credentials using JOSE and COSE](https://www.w3.org/TR/vc-jose-cose/)
recommendation, a Data Integrity proof, JSON-LD processing, a VC media type,
or a VC conformance test suite.

## Non-conformance boundary

No JSON artifact in this repository should be labeled a Verifiable Credential.
Future work must define the credential vocabulary/context, issuer identity,
status method, securing or enveloping mechanism, holder/presentation flow,
privacy model, and conformance tests before making that claim.
