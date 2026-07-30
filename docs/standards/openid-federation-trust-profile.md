# CareTrust synthetic federation trust profile

## Status and boundary

This is an executable **local synthetic trust-resolution simulation only**. It
is not an OpenID Federation conformance claim and it is not an operational
federation. It uses only synthetic `.invalid` Entity Identifiers, ephemeral
in-memory Ed25519 private keys, caller-supplied statements, and a locally pinned
trust anchor. It performs no HTTP, discovery, registry, identity-proofing, or
other network call.

The implementation is in `src/caretrust/federation.py`; its machine-readable
example is
[`examples/federation/two-care-organizations.json`](examples/federation/two-care-organizations.json).
That example contains public JWKs and signed JWTs but no private key material.

## Standards vocabulary used

[OpenID Federation 1.0](https://openid.net/specs/openid-federation-1_0.html)
defines Entity Statements as signed JWTs and uses a trusted third party called
a Trust Anchor to establish trust between entities. The final specification
requires the `entity-statement+jwt` type and the `iss`, `sub`, `iat`, `exp`, and
`jwks` claims. When `iss` equals `sub`, the statement is an Entity
Configuration; a Trust Anchor uses a Subordinate Statement to describe an
immediate subordinate.

The local profile implements those bounded shapes:

| Element | Local behavior |
|---|---|
| JWS header | `typ=entity-statement+jwt`, `alg=EdDSA`, and a nonblank `kid` |
| Entity Configuration | Self-signed JWT with `iss=sub`, NumericDate validity, subject JWKS, metadata, and `authority_hints` for care organizations |
| Subordinate Statement | Trust-anchor-signed JWT with anchor `iss`, care-organization `sub`, and the organization JWKS and metadata |
| Public keys | Ed25519 `OKP` JWKs with `crv=Ed25519`, `use=sig`, and `alg=EdDSA` |
| Trust Anchor | Exact HTTPS Entity Identifier plus JWKS pinned in `LocalTrustStore` |
| Resolution | One deterministic, offline leaf-to-anchor path |

The custom `metadata.caretrust_care_organization` object is a CareTrust-local
extension. It is not registered OpenID Federation metadata.

## Executable trust decision

For one care organization, the resolver:

1. decodes the supplied Subordinate Statement only far enough to identify its
   claimed issuer;
2. requires an exact issuer match in the local trust store;
3. verifies the Subordinate Statement's Ed25519 signature with the pinned trust
   anchor JWK;
4. verifies `typ`, `alg`, `kid`, HTTPS `iss` and `sub`, `iat`, `exp`, `jwks`,
   and metadata shape;
5. verifies the care organization's self-signed Entity Configuration using the
   JWK carried in that configuration;
6. requires the Entity Configuration to be self-issued and to name the pinned
   anchor in `authority_hints`;
7. requires the organization JWKS bound by the anchor to equal the JWKS in the
   organization's Entity Configuration; and
8. returns a deterministic SHA-256 identifier over the two compact JWTs.

Any missing anchor, unknown key, malformed claim, invalid signature, future or
expired statement, authority-hint mismatch, or JWKS mismatch fails closed with
a stable `FEDERATION_*` error code.

## Synthetic topology

```text
https://trust.synthetic.invalid
  |-- signs statement about --> https://care-a.synthetic.invalid
  `-- signs statement about --> https://care-b.synthetic.invalid
```

Organization A is labeled as a synthetic credential issuer and Organization B
as a synthetic care application. Those role labels are illustrative metadata,
not authorization grants. Resolving both chains establishes only that the
locally configured anchor signed current key metadata for both entities. It
does not authorize an application request or prove a real organization. Running
two synthetic entity paths in one local process does not demonstrate
cross-organization federation.

## Rotation behavior

Leaf rotation is accepted only when:

- the leaf's new Entity Configuration is signed by a key included in its
  current JWKS; and
- a fresh anchor Subordinate Statement binds that same current JWKS.

A rotated leaf paired with a stale anchor statement fails with
`FEDERATION_JWKS_MISMATCH`.

Anchor rotation is accepted only after the local trust store is updated to pin
the new anchor public key. A statement signed by an unpinned anchor key fails
with `FEDERATION_UNKNOWN_KEY`. This overlap model is intentionally local; it
does not implement remote key discovery or historical key distribution.

## Explicit omissions

The final OpenID Federation specification defines substantially more than this
seam. The prototype does **not** implement:

- `/.well-known/openid-federation` publication or retrieval;
- Federation Entity Discovery, Fetch, List, or Resolve endpoints;
- intermediate authorities or multi-path trust-chain selection;
- metadata-policy operators, constraints, critical extensions, or policy
  application;
- trust marks, trust-mark issuers, or trust-mark status;
- automatic algorithm negotiation or algorithms other than EdDSA;
- TLS/Web PKI transport decisions, caching, refresh, replay storage, or
  distributed revocation;
- OpenID Connect, OAuth, SMART, OID4VC, FHIR, wallet, verifier, or credential
  issuance integration; or
- an OpenID Foundation conformance suite or interoperability test with another
  implementation.

Tests establish only the local implementation claims: two chains resolve,
resolution is deterministic, current rotation succeeds, stale rotation fails,
and missing trust, tampering, and expiry fail closed.
