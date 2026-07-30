# CareTrust Principles

These principles govern the CareTrust proof of concept and any later implementation.
When requirements conflict, apply the principles in this order.

## 1. Care work comes first

CareTrust must reduce repeated administrative work for direct care workers and care
organizations. It must not create a second proprietary record system that workers
must maintain.

## 2. AI proposes; accountable parties decide

AI may extract, normalize, cite, compare, and flag uncertainty. AI may not establish
identity, verify a credential, interpret legal authority, activate a claim, or grant
access. Those outcomes require explicit human, source-system, and deterministic
policy decisions.

## 3. Every material value is evidence-linked

An extracted value must retain a reference to its source text or source region.
Unsupported, missing, conflicting, or ambiguous values must remain visibly
unresolved.

## 4. Draft and verified state are different objects

Model output is always a draft. Only the activation service can create an active
claim, and only after schema validation, authorized review, source verification,
and validity checks succeed.

## 5. Authorization is deterministic

The model never decides whether an application receives access. Inspectable policy
code evaluates active status, scope, audience, purpose, time bounds, recipient
permission when access concerns a care recipient, and revocation state. The
Phase 1 credentialing profile does not access a care recipient's data, so it
tests audience, purpose, validity, claim binding, and revocation rather than a
recipient-consent grant.

## 6. Interoperability is a contract, not a vendor

Public schemas, APIs, reason codes, evidence contracts, status semantics, and test
fixtures form the interoperability boundary. Model providers, hosting platforms,
identity-verification vendors, and user interfaces must be replaceable.

## 7. Standards claims are precise

CareTrust distinguishes among:

- implemented and tested;
- validator-tested artifact;
- mapped or standards-shaped;
- planned for a later phase.

The proof of concept does not claim protocol conformance merely because a field
mapping or illustrative artifact exists.

## 8. Minimize data and preserve choice

The Phase 1 proof of concept uses only synthetic identities, credentials, registry
responses, and care relationships. No real credential, protected health
information, biometric, or government identifier may enter the repository or
model prompts.

## 9. Failure must be safe and understandable

Low confidence, missing evidence, registry unavailability, signature failure,
expiration, mismatch, and revocation must result in review or denial with a stable
reason code. Silence and fabricated completion are not acceptable fallbacks.

## 10. Evidence outranks polish

Reproducible outputs, frozen fixtures, honest failures, configuration hashes, and
measured results take priority over animation, broad feature coverage, or a
production-looking interface.

## 11. Open source must be reproducible

The repository must include an open license, pinned dependencies, setup
instructions, synthetic fixtures, schemas, tests, and an evaluation command.
Secrets, local configuration, and generated private submission materials stay out
of the public repository.

## 12. Accessibility and affordability are architectural

Critical workflows must remain understandable with plain language, keyboard
navigation, visible status, and non-color-only cues. The implementation must
measure model usage, latency, and estimated cost and must retain a provider-neutral
model adapter.
