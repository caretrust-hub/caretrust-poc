# CareTrust

**Interoperable Care Trust Hub — open-source TRL 3 proof of concept**

CareTrust tests one bounded proposition: AI can help turn synthetic caregiver
credential evidence into a structured **draft**, while people and deterministic
policy retain every authority-bearing decision. The Phase 1 profile is a
synthetic Hawaii Certified Nurse Aide (CNA) workflow.

The larger concept is a neutral, federated trust hub that care organizations,
nonprofits, and government programs could adopt without locking caregiver claims
inside one application. This repository demonstrates the safety-critical core;
it does not claim that the larger ecosystem already exists.

## What the prototype demonstrates

```text
synthetic evidence
  -> AI-extracted draft with evidence links and uncertainty
  -> authorized human approve / correct / reject / defer
  -> synthetic registry match / mismatch / not-found / unavailable
  -> deterministic activation gate
  -> short-lived Ed25519-signed claim token
  -> deterministic audience + purpose authorization
  -> revocation and subsequent denial
```

Only draft extraction uses a language model. A model cannot create an active
claim, sign a token, override review, perform a source check, or return a permit.
The registry is a network-free simulator and all identities and evidence are
synthetic.

The implementation is deliberately provider-neutral:

- `ModelAdapter` separates Bedrock/Qwen from the domain workflow.
- Pydantic contracts export implementation-neutral JSON Schemas.
- Stable reason codes make every deny inspectable.
- Standards mappings distinguish tested artifacts from proposed mappings.
- Raw, consecutive model outputs and failures are retained for audit.

## Run it locally

Prerequisites: Python 3.13 and Git. AWS access is needed only to repeat a model
run; the demo and automated tests run locally.

```powershell
git clone https://github.com/caretrust-hub/caretrust-poc.git
cd caretrust-poc
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip==26.2
.\.venv\Scripts\python -m pip install -e ".[aws,dev]"
.\.venv\Scripts\python -m pytest -q
```

The current post-evaluation code state passes **69 tests**.

### Interactive browser demonstration

The dependency-free [demonstration surface](demo/index.html) is keyboard
accessible and does not call a live service:

```powershell
.\.venv\Scripts\python -m http.server 8000
```

Then open `http://localhost:8000/demo/`. It presents clean permit and revocation,
human correction with the original draft preserved, ambiguous-evidence
deferral, registry-mismatch denial, and prompt-injection containment. Status
and reasons are communicated in text, not color alone. The retained
[browser QA record](artifacts/validation/demo-browser-qa-screenshots.json)
links to judge-readable screenshots of each key state.

### Deterministic command-line demonstration

```powershell
.\.venv\Scripts\python scripts\demo_vertical_slice.py
```

This exercises review, registry simulation, activation, signing, authorization,
and revocation. The recorded validation artifact is
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

To create a separately labeled reproduction with configured AWS credentials:

```powershell
.\.venv\Scripts\python scripts\run_evaluation.py --freeze-only --prior-spend-usd 0.0052056
.\.venv\Scripts\python scripts\run_evaluation.py --prior-spend-usd 0.0052056
```

Do not overwrite the submitted run. A reproduction requires AWS access and may
incur model charges.

## Interoperability artifacts

- [Standards implementation status](docs/standards/standards-status.md)
- [Claim lifecycle and reason codes](docs/standards/lifecycle-and-reason-codes.md)
- [W3C Verifiable Credentials 2.0 mapping](docs/standards/w3c-vc-2.0-mapping.md)
- [FHIR R4 mapping](docs/standards/fhir-r4-practitioner-qualification-mapping.md)
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
