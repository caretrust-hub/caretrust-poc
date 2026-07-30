# Claim lifecycle and reason-code semantics

## Trust boundary and lifecycle

The extraction model may create only a `DraftCredentialClaim` whose status is
the literal `draft`. A draft is an unverified proposal linked to evidence; it
cannot be signed, activated, or used to permit access.

```text
synthetic evidence
  -> immutable draft (AI extraction; never trusted)
  -> authorized human review (approve, correct, reject, or defer)
  -> synthetic source check (match, mismatch, not found, or unavailable)
  -> deterministic activation decision
  -> active claim OR denial reasons
  -> short-lived signed token
  -> deterministic authorization decision
  -> permit OR denial reasons
```

The activation policy creates an `active` claim only after an accepting human
review, a matching synthetic registry result, no unresolved blocking issue,
an extracted or human-corrected credential status of `active`, and all bounded
Hawaii CNA data checks. There is no transition directly from `draft` to
`active` by the model.

An active claim can later be represented as `revoked` or `expired`. Only
`active` claims may be signed or produce a permit. The prototype has an
in-memory revocation seam; it does not implement a durable or federated status
service. A `caretrust.revocation-record.v1` JSON contract and synthetic example
make the proposed local revocation event portable, but the Phase 1 runtime does
not emit or distribute that record.

Status meanings:

| Status | Meaning in this prototype |
|---|---|
| `draft` | Unverified model proposal; human and source checks remain mandatory. |
| `active` | Bounded activation prerequisites passed at the recorded decision time. |
| `revoked` | Locally withdrawn; token issuance and authorization fail closed. |
| `expired` | Outside the claim validity period; authorization fails closed. |

Review states are `approved`, `corrected`, `rejected`, and `deferred`.
Synthetic registry states are `match`, `mismatch`, `not_found`, and
`unavailable`. Authorization decisions are `permit` and `deny`.

## Stable implemented reason-code catalog

These codes are executable prototype behavior. A deny may include several
codes, in deterministic evaluation order.

### Activation and review

| Code | Meaning |
|---|---|
| `REVIEW_REQUIRED` | No valid human review is bound to the draft. |
| `REVIEW_DRAFT_MISMATCH` | The review is not bound to the supplied immutable draft. |
| `REVIEW_REJECTED` | The reviewer rejected the draft. |
| `REVIEW_DEFERRED` | The reviewer deferred a decision. |
| `REGISTRY_RESULT_REQUIRED` | No synthetic source-check result was supplied. |
| `REGISTRY_DRAFT_MISMATCH` | The source-check result is bound to another draft. |
| `SOURCE_MISMATCH` | The synthetic registry returned a mismatch. |
| `SOURCE_NOT_FOUND` | The synthetic registry did not find the identifier. |
| `SOURCE_UNAVAILABLE` | The synthetic registry was unavailable. |
| `BLOCKING_UNCERTAINTY` | At least one extraction uncertainty is blocking. |
| `UNRESOLVED_BLOCKING_ISSUE` | The draft retains an unresolved blocking issue. |
| `REGISTRY_ID_REQUIRED` | A registry identifier is absent after review. |
| `CREDENTIAL_TYPE_UNSUPPORTED` | The reviewed credential is not the bounded CNA type. |
| `JURISDICTION_UNSUPPORTED` | The reviewed jurisdiction is outside the bounded Hawaii profile. |
| `CREDENTIAL_STATUS_NOT_ACTIVE` | The reviewed source credential status is absent or is not `active`. |
| `EXPIRATION_DATE_REQUIRED` | The reviewed expiration date is absent. |
| `EXPIRATION_DATE_INVALID` | The reviewed expiration date is not an ISO date. |
| `CREDENTIAL_EXPIRED` | The credential is past its validity boundary. |
| `REGISTRY_ID_MISMATCH` | The checked identifier differs from the reviewed identifier. |

The source simulator records one of:
`SYNTHETIC_REGISTRY_MATCH`, `SYNTHETIC_REGISTRY_MISMATCH`,
`SYNTHETIC_REGISTRY_NOT_FOUND`, or `SYNTHETIC_REGISTRY_UNAVAILABLE`.
These describe simulator output; they are not evidence of a live registry
query.

### Authorization policy

| Code | Meaning |
|---|---|
| `CLAIM_NOT_ACTIVE_TYPE` | The supplied object is not an active-claim contract. |
| `CLAIM_ID_MISMATCH` | Request and claim identifiers differ. |
| `SUBJECT_MISMATCH` | Request and claim subjects differ. |
| `CLAIM_TYPE_MISMATCH` | Request and claim types differ. |
| `CLAIM_REVOKED` | The claim status is revoked. |
| `CLAIM_EXPIRED` | The claim status or validity boundary is expired. |
| `CLAIM_STATUS_NOT_ACTIVE` | The claim is not active. |
| `AUDIENCE_NOT_ALLOWED` | The requesting audience is outside the claim allow-list. |
| `PURPOSE_NOT_ALLOWED` | The purpose is outside the claim allow-list. |
| `CLAIM_NOT_YET_VALID` | The claim validity period has not begun. |
| `TOKEN_CLAIM_TYPE_MISMATCH` | Signed-token and request claim types differ. |
| `TOKEN_ACTIVE_CLAIM_MISMATCH` | The complete signed active claim differs from the active claim supplied to policy. |
| `TOKEN_STATUS_NOT_ACTIVE` | The signed token does not carry active status. |
| `POLICY_REQUIREMENTS_SATISFIED` | All implemented checks passed; this is the permit reason. |

`REVIEW_REQUIRED` is also returned at the authorization boundary if a draft is
passed where an active claim is required.

### Signed-token verification

| Code | Meaning |
|---|---|
| `TOKEN_MALFORMED` | Compact token structure, encoding, or JSON is invalid. |
| `TOKEN_UNSUPPORTED_ALGORITHM` | The protected header is not the implemented EdDSA JWT profile. |
| `TOKEN_UNKNOWN_KEY` | The signing key identifier is not locally trusted. |
| `TOKEN_SIGNATURE_INVALID` | Signature verification failed. |
| `TOKEN_CLAIMS_INVALID` | Required token claims have invalid types or values. |
| `TOKEN_ISSUER_MISMATCH` | Token issuer differs from the configured issuer. |
| `TOKEN_NOT_YET_VALID` | Token issue/not-before time is in the future. |
| `TOKEN_EXPIRED` | Token lifetime has ended. |
| `TOKEN_REVOKED` | Token or supporting claim is in the in-memory revocation set. |
| `TOKEN_AUDIENCE_MISMATCH` | Expected audience is absent. |
| `TOKEN_PURPOSE_MISMATCH` | Expected purpose is absent. |
| `TOKEN_SUBJECT_MISMATCH` | Expected subject differs. |
| `TOKEN_CLAIM_MISMATCH` | Expected supporting claim identifier differs. |
| `TOKEN_STATUS_INVALID` | Token status is not active. |

Reason codes are CareTrust prototype codes, not codes assigned by HL7, W3C,
OpenID Foundation, or a government registry.
