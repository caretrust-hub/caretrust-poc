# Terra Agent Launch Plan — CareTrust v0.4

## Operating model

Three Terra agents execute in parallel. The root agent owns architecture,
integration, evidence claims, commits, pushes, and final review. Work is split
by file ownership to minimize merge conflicts.

## Wave 1 launch briefs

### Terra A — Core runtime bridge

**Goal:** Make the published CareTrust Core 0.1 contracts executable inside the
POC and map existing authorization families to them.

**Allowed files**

- `src/caretrust/core_protocol.py`
- `src/caretrust/core_mappings.py`
- `scripts/export_core_case_contracts.py`
- `tests/test_core_protocol.py`
- `tests/test_core_mappings.py`
- generated artifacts under `artifacts/validation/core-v0.1/`

**Read-only dependencies**

- `C:\Users\mike\Documents\caretrust-spec\schemas\core\v0.1\`
- `C:\Users\mike\Documents\caretrust-spec\schemas\profiles\v0.1\`
- existing POC delegation, uploaded-care, and clinical-edge modules

**Acceptance**

- strict models reject unknown fields;
- canonical hashes and RFC 3339 times match the specification;
- delegation and document-share permits/denies map without semantic loss being
  hidden;
- status/revocation maps to `StatusEvent`;
- negative tests cover stale hash, wrong artifact, expiry, and malformed reason
  namespace; and
- full existing tests remain green.

### Terra B — AI compiler plane

**Goal:** Make AI prominent through evidence-linked intent and application
onboarding compilers while proving it cannot create authority.

**Allowed files**

- `src/caretrust/compiler.py`
- `src/caretrust/app_onboarding.py`
- `scripts/build_compiler_fixtures.py`
- `fixtures/compiler/`
- `tests/test_compiler.py`
- `tests/test_app_onboarding.py`
- `docs/standards/ai-compiler-profile.md`

**Read-only dependencies**

- existing model adapters, delegation vocabulary, OpenAPI, RAR examples, and
  evidence contracts

**Acceptance**

- intent output cites exact source phrases and remains `draft`;
- ambiguous action/purpose/audience produces clarification;
- application description produces a proposed RAR/profile/minimum-data plan;
- excessive data and clinical authority requests are flagged;
- output containing approval/permit/activation/revocation is rejected;
- deterministic replay is available without AWS;
- optional Bedrock path retains model/prompt/response hashes, latency, and cost;
- prompt-injection tests pass; and
- full existing tests remain green.

### Terra C — Multi-caregiver case bundle

**Goal:** Produce the canonical one-patient/three-caregiver case and all
dashboard/reference-client projections from executable artifacts.

**Allowed files**

- `src/caretrust/case_bundle.py`
- `scripts/build_case_bundle.py`
- `fixtures/cases/`
- `artifacts/validation/synthetic-multi-caregiver-case.json`
- `tests/test_case_bundle.py`
- `docs/use-cases/multi-caregiver-reference-case.md`

**Read-only dependencies**

- existing delegation, navigator, credential, uploaded-care, trace, and
  clinical-edge modules

**Acceptance**

- three caregivers have distinct evidence/claim/grant/assignment bases;
- scheduling, direct-care, and respite actions produce disjoint outcomes;
- views for care team, permissions, history, applications, evidence, and
  standards share canonical IDs;
- raw packets and unrelated claims are absent from app projections;
- correction, expiry, clinical block, and revocation are represented;
- no permissions are hard-coded in display fixtures; and
- full existing tests remain green.

## Wave 2 launch briefs

Wave 2 starts only after Gate 1 review.

### Terra D — Dashboard integration and standards inspector

Consume the canonical case bundle and expose stable UI data contracts. Do not
redesign user-authored mockups. Supply event drill-down data, standards
projection, semantic-loss, evidence-status, and non-claim fields.

### Terra E — MCP adapter

Implement only `draft`, `read`, `validate`, `explain`, and `simulate` tools over
the same services. Add tests proving that no tool can mutate authority.

### Terra F — OAuth/OIDC application harness

Implement external identity linkage, application registration, PKCE/RAR-shaped
authorization artifacts, resource-bound CareTrust tokens, and negative tests.
Use live Cognito only if configuration is available and can remain synthetic.

## Wave 3 launch briefs

Wave 3 starts only after Gate 2 review.

### Terra G — Federation laboratory

Extend federation fixtures to two hubs while preserving separate entity-trust
and patient-authorization decisions.

### Terra H — Conformance/security/CI

Build validators, negative fixtures, sensitive-pattern scans, and reproducible
reports across both repositories.

### Terra I — Judge trace and final evidence synchronization

Generate the end-to-end walkthrough artifacts and reconcile every public claim
with actual evidence. Do not polish over missing behavior.

## Integration rejection criteria

Root rejects a handoff if it:

- creates authority from AI output;
- hard-codes permissions in UI/demo data;
- changes an existing schema without migration evidence;
- introduces a second case/permission truth source;
- presents a mapping as conformance;
- implies a live HIE, Login.gov, registry, or federation connection;
- exposes raw evidence where a minimum-data projection is required;
- modifies another agent's allowed files;
- lacks negative tests; or
- breaks existing tests.
