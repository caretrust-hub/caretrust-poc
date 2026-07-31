# CareTrust

**Interoperable Care Trust Hub — open-source TRL 3 proof of concept**

CareTrust tests a bounded platform proposition: AI can help turn messy caregiver
intent and patient-provided documents into evidence-linked **drafts**, while
people, accountable organizations, and deterministic application policy retain
every authority-bearing decision.

The larger concept is a neutral, federated trust hub that care organizations,
nonprofits, and government programs could adopt without locking caregiver
relationships, delegations, credentials, and coordination items inside one
application. This repository demonstrates bounded pieces of that safety-critical
core; it does not claim that the larger ecosystem already exists.

The v0.5 operations prototype centers one synthetic provider activation:

```text
organization receives an incomplete synthetic referral
  -> AI proposes eight cited nonclinical facts and two focused gaps
  -> coordinator corrects one uncertainty instead of re-keying the referral
  -> patient separately approves three bounded sharing purposes
  -> deterministic qualification and availability gates filter the worker roster
  -> a supervisor assigns one eligible direct-care worker
  -> a scheduler and worker app receive different minimum-data projections
  -> workload counters show reviewed fields and app entries generated
  -> one revocation blocks fresh requests with zero case-data disclosure
```

CareTrust is a governed trust compiler, not a document summarizer or another
all-in-one care-management application. Its intent, evidence, and
application-requirements compilers produce reviewable drafts; humans approve
authority-bearing records; deterministic policy returns permit or deny.
Uploading a record establishes only who supplied that copy; it does not
establish authorship, clinical accuracy, currentness, patient matching, or legal
authority. Medication and warning-sign content cannot be promoted into orders
or clinical assertions by the model or a consumer reviewer.

Live HIE/EHR connectivity is a longer-term network seam. A local synthetic
data-holder adapter tests authority boundaries, but there is no connection,
agreement, patient match, data exchange, partnership, or endorsement involving
Hawaiʻi HIE or any production clinical system.

## Frozen v0.2 credential evidence lane

Two separately identified evidence traces demonstrate the boundaries:

```text
Retained AWS intake (`retained_aws`)
  synthetic Hawaii CNA image
    -> Amazon Textract OCR evidence
    -> Bedrock/Qwen unverified draft with blocking uncertainties
    -> STOP: no review, activation, token, or authorization

Deterministic trust lifecycle (`executed_local`)
  different retained clean model response
    -> authorized human review and correction
    -> synthetic source check
    -> active claim + short-lived Ed25519-signed token
    -> deterministic authorization
    -> in-memory revocation
    -> fresh request denied with TOKEN_REVOKED
```

OCR extracts evidence; it does not establish truth or authority. Only draft
structuring uses a language model. A model cannot create an active claim, sign
a token, override review, perform a source check, or return a permit. The
registry is a network-free simulator and all identities and evidence are
synthetic.

The traces share some synthetic fixture identifiers but are not one execution.
Their request IDs, response hashes, terminal states, and cross-artifact
identifier reuse are recorded in the machine-readable
[provenance-lineage registry](docs/standards/provenance-lineages.json).

The implementation is deliberately provider-neutral:

- `OcrAdapter` separates Textract from the evidence contract.
- `ModelAdapter` separates Bedrock/Qwen from the domain workflow.
- Pydantic contracts export implementation-neutral JSON Schemas.
- Stable reason codes make every deny inspectable.
- Standards mappings distinguish tested artifacts from proposed mappings.
- Raw, consecutive model outputs and failures are retained for audit.

## Run it locally

Prerequisites: Python 3.13 and Git. AWS access is needed only to repeat the
Textract and model calls; the demo, retained replay, and automated tests run
locally.

```powershell
git clone https://github.com/caretrust-hub/caretrust-spec.git
git clone https://github.com/caretrust-hub/caretrust-poc.git
cd caretrust-poc
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip==26.2
.\.venv\Scripts\python -m pip install -r requirements.lock
.\.venv\Scripts\python -m pip install -e . --no-deps
.\.venv\Scripts\python -m pytest -q
```

The repositories should remain siblings unless `CARETRUST_SPEC_ROOT` points to
the `caretrust-spec` checkout. The POC validates its Core 0.1 mappings against
the public draft schemas rather than maintaining a second private copy.

The tagged `trl3-poc-v0.4.1` release passed 331 tests. The v0.5 branch adds an
operational provider-workflow service and tests for stage ordering,
optimistic-version conflicts, patient approval, worker eligibility, disjoint app
projections, workload instrumentation, corrected AI citation protocols, and
fail-closed revocation. The current v0.5 branch passes **344 tests**.

### Interactive browser demonstrations

The dependency-free [landing and credential surface](demo/index.html) and
[v0.5 organization console](demo/network.html) are keyboard accessible. The
organization console connects to the local Python workflow API when served by
the command below and otherwise uses a browser-local reference adapter with the
same synthetic workflow contract.

```powershell
.\.venv\Scripts\python scripts\run_provider_console.py
```

Then open `http://127.0.0.1:8765/network.html`. A coordinator can compile an
incomplete referral, review evidence-linked fields, obtain a separate synthetic
patient approval, assign a policy-eligible worker, create different projections
for a scheduler and worker task app, revoke the assignment, and verify a fresh
deny. The console reports fields prefilled, exceptions, open follow-ups,
app-specific entries generated, and human approvals remaining. These are
prototype interaction measures, not validated time savings or field outcomes.

The static GitHub Pages build continues to work without a server through the
clearly labeled browser reference adapter. A login-free copy of the deployed
tagged release is available at **https://caretrust-hub.github.io/caretrust-poc/**;
the v0.5 branch is not a production deployment.

The separate frozen credential path visibly replays retained Textract evidence
and a retained Bedrock/Qwen draft, requires separate
human-review, source-check, and signing actions, then shows two applications
making distinct decisions from the same stable claim. Revocation preserves the
historical receipts and denies a fresh App B request. Human correction,
ambiguous-evidence deferral, registry mismatch, and prompt-injection containment
remain selectable scenarios. Status and reasons are communicated in text, not
color alone. This dependency-free browser is an interaction replay, not a
claim that its screens are one retained AWS-to-authorization execution. The
retained
[v0.2 browser QA manifest](artifacts/validation/screenshots-v0.2/manifest.json)
hashes four judge-readable screenshots from OCR evidence through a fresh
post-revocation denial.

### OCR-to-draft vertical slice

Credential bytes and normalized OCR output receive separate SHA-256 hashes.
Textract lines and words retain confidence, page, geometry, and offsets so a
reviewer can trace every proposed field to the extracted evidence. Invalid or
failed OCR stops the workflow before any model call.

Replay the retained provider response without AWS credentials:

```powershell
.\.venv\Scripts\python scripts\run_ocr_vertical_slice.py --offline
```

With configured AWS credentials, the same command without `--offline` calls
Amazon Textract and Bedrock/Qwen using only the visibly synthetic fixture:

```powershell
.\.venv\Scripts\python scripts\run_ocr_vertical_slice.py
```

The successful live synthetic run is retained at
[vertical-slice.json](artifacts/ocr/20260730T171807.004134Z/vertical-slice.json);
the credential-free replay is
[retained-offline-vertical-slice.json](artifacts/ocr/retained-offline-vertical-slice.json).
The live same-run artifact is `retained_aws` evidence and terminates at its
unverified draft with blocking uncertainties. It did not proceed through the
deterministic lifecycle. Repeating the live path may incur AWS charges.

### Deterministic command-line demonstration

```powershell
.\.venv\Scripts\python scripts\demo_vertical_slice.py
```

This replays the retained clean Bedrock result through evidence intake,
schema validation, authorized human correction, registry simulation,
activation, complete-claim signing, authorization, revocation, and the
subsequent denial. It does not make a new model call and does not use the live
AWS trace's model response. This behavior is `executed_local`. The current
machine-readable record is
[connected-vertical-slice.json](artifacts/validation/connected-vertical-slice.json);
the earlier milestone record remains
[vertical-slice.json](artifacts/validation/vertical-slice.json).

## Controlled Bedrock evaluation

The final synthetic evaluation used `qwen.qwen3-32b-v1:0` in `us-west-2`,
temperature `0`, a precommitted prompt/schema/policy/20-case fixture set, and a
hard $10 phase ceiling. The retained run cost estimate was **$0.010992**;
cumulative model inference for the prototype was **$0.0161976**.

| Observed measure | Result |
|---|---:|
| Retained / schema-valid cases | 20 / 20 |
| Field precision / recall / F1 | 0.904 / 0.920 / 0.912 |
| Exact match across nine normalized fields | 6 / 20 (30%) |
| Uncertainty precision / recall / F1 | 0.214 / 0.429 / 0.286 |
| Material-risk false clears | 0 / 7 |
| Review-routing agreement | 18 / 20 |
| Field corrections to reach gold | 19 across 14 cases |
| Activation proxy TP / TN / FP / FN | 4 / 10 / 0 / 6 |
| Mean model latency | 2,417.55 ms |

The [audited evaluation report](artifacts/evaluation/20260730T085655.959974Z/REPORT.md)
links these observations to retained case records and states metric limitations.
The freeze was committed before inference at
[`8fe3093`](https://github.com/caretrust-hub/caretrust-poc/commit/8fe3093),
and the untouched run was published at
[`19c37d3`](https://github.com/caretrust-hub/caretrust-poc/commit/19c37d3).

The 30% exact-record result and weak uncertainty F1 are important findings, not
hidden defects: the model output needs human correction and must not decide
activation. The run's authorization figure is only a Boolean scenario proxy;
separate deterministic tests provide the signed-token, tamper, and revocation
evidence.

Independent post-run review found that the frozen activation code did not
explicitly require the extracted credential status to be `active`. The affected
fixture still failed closed through another gate, so the frozen metrics did not
change. Commit
[`a38e295`](https://github.com/caretrust-hub/caretrust-poc/commit/a38e295)
adds the explicit status gate and regression test without replacing the run.

### Unknown-protocol safety case

A separately frozen one-call Bedrock test asked Qwen to apply the undefined
“Protocol 9-Delta.” The model identified it as unrecognized, stated that no
credential or authorization status changed, and required authorized human
direction. The [verbatim response and limitations](artifacts/safety/protocol-9-delta/REPORT.md)
are retained separately from the 20-case evaluation. The call used 204 tokens,
774 ms, and an estimated **$0.0000486**.

To create a separately labeled reproduction with configured AWS credentials:

```powershell
.\.venv\Scripts\python scripts\run_evaluation.py --freeze-only --prior-spend-usd 0.0052056
.\.venv\Scripts\python scripts\run_evaluation.py --prior-spend-usd 0.0052056
```

Do not overwrite the submitted run. A reproduction requires AWS access and may
incur model charges.

## Interoperability artifacts

- [Machine-readable evidence-status registry](docs/standards/evidence-status-registry.json)
- [Machine-readable provenance and identifier lineages](docs/standards/provenance-lineages.json)
- [Apache-2.0 CareTrust Core 0.1 standards repository](https://github.com/caretrust-hub/caretrust-spec)
- [Standards implementation status](docs/standards/standards-status.md)
- [Claim lifecycle and reason codes](docs/standards/lifecycle-and-reason-codes.md)
- [OpenAPI 3.1 contract-only Phase 2 surface](docs/standards/caretrust-openapi-3.1.json)
- [W3C Verifiable Credentials 2.0 mapping](docs/standards/w3c-vc-2.0-mapping.md)
- [FHIR R4 mapping](docs/standards/fhir-r4-practitioner-qualification-mapping.md)
- [Executable local FHIR R4 projection profile](docs/standards/fhir-r4-projection-profile.md)
- [OID4VC exchange profile and tested contract artifacts](docs/standards/oid4vc-exchange-profile.md)
- [Local synthetic federation trust-resolution profile](docs/standards/openid-federation-trust-profile.md)
- [Proof-of-concept evidence classification](docs/POC-EVIDENCE.md)
- [JSON Schemas](schemas/)
- [Example requests and decisions](docs/standards/examples/)

Mappings are design artifacts, not conformance claims. They expose what existing
standards can carry, what the prototype actually tests, and where governance or
future profiling is still required.

## Project controls and limitations

The repo-native [Specifica backlog](.specifica/trl3-poc/tasks.md) connects the
[principles](.specifica/principles.md),
[requirements](.specifica/trl3-poc/spec.md), and
[technical design](.specifica/trl3-poc/design.md) to implementation evidence.

CareTrust does **not** perform identity proofing, inspect real driver licenses,
contact Hawaii's live registry, process PHI, validate a medical power of
attorney, prove standards conformance, or demonstrate production federation.
Identity verification, document-authority policy, durable status, privacy and
security assessment, accessibility research with caregivers, and
cross-organization governance remain Phase 2 work.

Licensed under [Apache License 2.0](LICENSE).
