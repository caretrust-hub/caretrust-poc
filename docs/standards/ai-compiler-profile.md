# CareTrust AI compiler profile v1

**Evidence status:** `executed_local` for deterministic fixtures and tests;
`contract_tested` for the optional Bedrock structured-output seam. No live AWS
invocation is required or implied.

The compiler plane accepts synthetic, untrusted patient language or application
description/OpenAPI material and returns only reviewable drafts. It cannot
approve, permit, register, activate, authorize, sign, issue, or revoke anything.
Those operations remain outside this profile and must be performed by
deterministic, accountable services after human review.

## Intent compilation

`CompilerService` compiles an `IntentStatement` into the existing
`caretrust.delegation-draft.v1` contract. Every proposed non-empty field has an
`evidence_binding` referencing an exact input span. Missing or ambiguous
delegate, action, audience, purpose, or bounded duration produces a required
clarification and a blocking issue. Prompt-injection wording is recorded as a
blocking safety flag and never followed.

Each `CompilationRun` binds the compiler version, provider/model identifier,
prompt, input, and response with SHA-256 hashes, as well as latency and an
estimated cost. The normal provider is a `deterministic_fallback` replay engine.
Its replay compares the draft, clarifications, and safety flags byte-for-byte in
canonical JSON.

The optional Bedrock seam requests an `IntentModelCandidate`: bounded actions,
resources, exclusions, audience, purpose, relationship, delegate, and end date;
every value carries an exact retained `span_id` and quote. The deterministic
validator rejects candidates with unknown vocabulary, unsupported phrases,
hallucinated span/quote references, conflicting exclusions, or action/resource
mismatches before it builds the draft. A valid candidate is causally material:
only its selected validated values become the draft and the result is labeled
`model_candidate_validated`. A rejected candidate is explicitly labeled
`deterministic_fallback_after_model_rejection`. A validated candidate is
retained alongside the draft so a reviewer can inspect the exact proposed
values and quotes; rejected output is not retained as trusted data, but its
response hash and validation error remain visible.

## Application onboarding compilation

`ApplicationOnboardingCompiler` converts synthetic description/OpenAPI material
into a draft application authorization profile, a RAR-shaped detail proposal,
and a minimum-data plan. The model candidate can select the bounded capability,
data fields, and HTTPS location, each with an exact retained source citation.
Description and canonical OpenAPI inputs are separate retained citation sources,
so a location or operation inferred from OpenAPI remains inspectable.
The validator accepts only allow-listed minimum-data fields for that capability.
Each item links to exact source material. Broad data
requests (`all records`, full chart, raw documents) are flagged as excessive.
Requests to diagnose, prescribe, alter medication, or make clinical decisions
are flagged as clinical-authority requests and require accountable review.

The RAR shape uses proposed HTTPS identifiers under the CareTrust Hub GitHub
Pages namespace: `https://caretrust-hub.github.io/caretrust-spec/rar/care-data/v1`
and a capability-specific `/profiles/<capability>/v1` identifier. Their
vocabulary is a draft extension and publication at those URLs is a standards
work item, not a claim of a deployed authorization server or application
registry. The proposal is deliberately resource-, action-, and purpose-bounded;
it does not expose raw evidence packets.

## Output safety boundary

Provider output is rejected when it asserts approval, a permit, activation,
revocation, or authorization. This safety check applies to provider output, not
to patient text: harmful text in an input is retained as evidence and marked as
an injection attempt. Both compiler outputs have `status: "draft"` and false
permission/activation fields by contract.

Reproducible synthetic fixtures are generated with:

```powershell
.\.venv\Scripts\python.exe scripts\build_compiler_fixtures.py
```

The generated fixture set exercises recorded structured-output candidates and
is labeled `recorded_contract_fixture` / `contract_tested`. It is local synthetic
evidence only; it does not claim a live Bedrock call, deployed model endpoint,
OAuth server, app registry, or patient authorization.
