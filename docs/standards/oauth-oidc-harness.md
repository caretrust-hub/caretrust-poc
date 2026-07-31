# Local OAuth/OIDC application and caregiver-auth harness

`scripts/build_auth_harness_trace.py` executes a provider-neutral local authorization-code flow over the canonical synthetic multi-caregiver case. It uses `state`, `nonce`, PKCE `S256`, a bounded RAR `authorization_details` object, and an RFC 8707-style `resource` identifier.

The harness locally verifies a signed synthetic OIDC ID token (issuer, audience, nonce, `iat`, `nbf`, `exp`, and signature) before creating an issuer/subject/assurance identity link. The upstream token terminates at CareTrust: the harness stores and publishes only its SHA-256 hash. It is never forwarded to the application. The retained `ApplicationOnboardingCompiler` produces the actual AI onboarding `draft`; separately supplied developer client metadata and accountable human review create a narrowed active registration. Registration constrains the compiler-proposed profile, locations/resource, purpose, actions, and datatypes.

Every authorization request is bound to the verified link, state, nonce, client, redirect URI, RAR type/actions/datatypes, resource, and purpose. Every code exchange is client, redirect URI, PKCE verifier, resource, resource-server audience, and purpose bound. Codes are one-time and short-lived. The resulting CareTrust-signed token is separately issued and introspected locally, and binds the caregiver, canonical case decision, client ID, resource-server audience/resource, and purpose.

Evidence status: the local harness is `executed_local`, using a deterministic synthetic signing key. It did not exercise external IdP metadata or identity proofing, Cognito/Login.gov, HTTP endpoints, or production deployment; those remain planned/not exercised. Public artifacts omit bearer tokens and private material.
