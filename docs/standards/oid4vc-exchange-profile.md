# CareTrust illustrative OID4VC exchange profile

## Status and boundary

This profile is an **illustrative, contract-tested exchange sketch** for a
future CareTrust credential flow. Its implementation status is
**`contract_tested` — Contract tested**. It is not runtime behavior, not an
interoperability certification, and not a conformance claim.

The examples show how a future credential issuer, wallet, verifier, and the
existing CareTrust authorization decision contract could be joined using:

- [OpenID for Verifiable Credential Issuance 1.0 Final](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0-final.html);
- [OpenID for Verifiable Presentations 1.0 Final](https://openid.net/specs/openid-4-verifiable-presentations-1_0-final.html); and
- CareTrust's current claim identifiers, credential profile, audience,
  purpose, authorization schemas, and reason-code vocabulary.

No HTTP endpoints are deployed by this artifact. No credential is signed,
issued, stored in a wallet, or cryptographically verified. In particular, the
current CareTrust signed authorization token is not asserted to be a
`jwt_vc_json` Verifiable Credential. The `jwt_vc_json` selection and
presentation placeholder below are candidate integration contracts only; a
real implementation still requires the vocabulary, issuer identity, securing
mechanism, credential status method, wallet privacy model, and conformance
testing listed in the existing
[W3C VC 2.0 mapping](w3c-vc-2.0-mapping.md).
No wallet is implemented or connected, and no independent issuer or verifier
participates in these tests.

## Contract-tested files

| Artifact | Bounded purpose |
| --- | --- |
| `examples/oid4vc/credential-issuer-metadata.json` | Candidate OID4VCI credential issuer metadata for one Hawaii CNA configuration |
| `examples/oid4vc/oauth-authorization-server-metadata.json` | Candidate OAuth authorization server metadata used by that issuer |
| `examples/oid4vc/credential-offer.json` | Authorization Code flow offer for the one credential configuration |
| `examples/oid4vc/authorization-details.json` | `openid_credential` authorization detail requested by a wallet |
| `examples/oid4vc/presentation-request.json` | Direct-post OID4VP request containing one DCQL credential query |
| `examples/oid4vc/presentation-response.json` | Response envelope with an intentionally invalid synthetic presentation placeholder |
| `examples/oid4vc/response-decision-linkage.json` | Local linkage from the protocol exchange to existing CareTrust authorization request and decision contracts |

The test suite checks JSON validity, fixed synthetic URLs and identifiers,
cross-file consistency, required bounded fields, reuse of the current
CareTrust Pydantic contracts, and the absence of obvious secrets or personal
data. Those checks do not substitute for protocol conformance tests.

## Stable synthetic namespace

Every service URL is under the IANA-reserved `.example` namespace:

- Credential Issuer: `https://issuer.caretrust.example`
- Authorization Server: `https://as.caretrust.example`
- Verifier: `https://verifier.caretrust.example`

Every person, claim, request, decision, state, nonce, and presentation value is
explicitly synthetic. The examples contain no driver-license image, medical
record, license-holder data, access token, signing key, or production
endpoint.

## Issuance path

1. A wallet discovers the credential issuer metadata at the OID4VCI
   well-known location for `https://issuer.caretrust.example`.
2. The issuer metadata points to the separate synthetic authorization server
   and advertises exactly one configuration:
   `caretrust_hawaii_cna_v1`.
3. The credential offer selects the Authorization Code grant and carries an
   opaque synthetic `issuer_state`.
4. The wallet sends the `openid_credential` authorization detail. Its
   `locations` member binds the request to the advertised credential issuer,
   and its `credential_configuration_id` matches both the offer and issuer
   metadata.
5. This profile stops before an authorization response, token response,
   credential request, or credential response. Those messages would require
   deployed endpoints, authenticated user interaction, key binding, and a
   genuinely secured credential.

The candidate credential subject vocabulary projects these CareTrust
concepts:

| CareTrust concept | Candidate credential-subject member |
| --- | --- |
| `claim_id` | `claimId` |
| `credential_profile` | `credentialProfile` |
| `credential_type` | `credentialType` |
| `jurisdiction` | `jurisdiction` |
| `registry_id` | `registryId` |
| `valid_until` | `validUntil` |
| lifecycle status | `status` |

This is a minimal exchange vocabulary, not a normative CareTrust ontology.
Evidence references, reviewer identity, full registry results, provenance, and
policy evaluation records remain outside the presented credential.

## Presentation and policy-decision path

1. The verifier creates a direct-post OID4VP request with `response_type`
   `vp_token`, a synthetic `nonce` and `state`, and one DCQL query named
   `caretrust_cna`.
2. The DCQL query selects the candidate professional credential type and asks
   for the stable CareTrust claim identifier, `hawaii_cna_smoke_v1` profile,
   `Certified Nurse Aide` type, `HI` jurisdiction, and `active` status.
3. A future wallet would obtain holder consent and return a secured
   presentation. The checked-in response contains
   `SYNTHETIC_PRESENTATION_PLACEHOLDER_NOT_A_CREDENTIAL`, which preserves the
   response envelope and DCQL result-key linkage without pretending to be a
   valid token.
4. The local linkage record converts the verifier's business context into the
   existing CareTrust `AuthorizationRequest` contract. It then records the
   existing `AuthorizationDecision` contract with:
   `permit`, `POLICY_REQUIREMENTS_SATISFIED`, the supporting claim ID, and
   policy version `caretrust.authorization.v1`.

`caretrust_request_context` in the presentation request is a namespaced
CareTrust extension, not an OID4VP standard parameter. The separate linkage
record is also a local audit/integration artifact, not part of the OID4VP
authorization response. Keeping policy output outside `vp_token` avoids
misrepresenting a CareTrust decision as wallet-supplied credential evidence.

## Implementation and standards work still required

Before any production or conformance claim, a later phase must:

- define and publish stable JSON-LD terms or another normative vocabulary for
  the candidate credential subject;
- select and implement an OID4VCI/OID4VP security profile, issuer/verifier
  client identification, key management, replay protection, and holder
  binding;
- define status, suspension, revocation, expiration, and registry-refresh
  semantics that align with CareTrust lifecycle reason codes;
- minimize disclosure and define wallet consent, correlation resistance,
  retention, and audit policies;
- implement credential and presentation endpoints, wallet behavior, error
  paths, and authorization server controls;
- test against the final specifications and applicable ecosystem profiles;
  and
- decide whether CareTrust-specific request context belongs in a future
  registered extension, an external transaction API, or a trust-framework
  profile.

The useful TRL 3 result is therefore not a claim that the standards problem is
finished. The artifacts illustrate a concrete seam where future standardized
issuance and presentation messages could connect a narrowly defined
professional-credential projection to CareTrust's open, deterministic policy
contract.
