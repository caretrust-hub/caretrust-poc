# CareTrust post-evaluation evidence manifest

The v0.2 evidence manifest is a deterministic inventory of the repository state,
artifact hashes, and bounded implementation statuses that exist after the frozen
20-case model evaluation. It does not change or enlarge the reported model
evaluation.

Generate it only after selecting the public repository and release identifiers
and retaining a test-result record:

```powershell
.\.venv\Scripts\python.exe scripts\build_poc_evidence_manifest.py `
  --test-result-reference <retained-test-result-path-or-public-reference> `
  --public-repository-url https://github.com/caretrust-hub/caretrust-poc `
  --release-tag <release-tag> `
  --release-commit <full-40-character-release-commit> `
  --output <manifest-output.json>
```

The release tag must exist locally and resolve to the supplied full commit. The
test-result reference is supplied by the caller; the generator records it but
does not execute tests or infer that they passed. The output contains no
generation timestamp, so identical repository bytes, git state, and caller
inputs produce identical JSON.

## Evidence classes

The authoritative values and definitions are in the machine-readable
[evidence-status registry](standards/evidence-status-registry.json). Unknown
values are rejected by automated tests.

| Capability | Evidence status | Bounded meaning |
| --- | --- | --- |
| AWS OCR-to-draft intake | `retained_aws` | One retained live synthetic AWS trace; it terminates at an unverified draft |
| CareTrust claim and policy | `executed_local` | Executed in the local runtime and covered by deterministic tests |
| FHIR R4 qualification projection | `executed_local` | Executable local projection with deterministic local tests |
| OID4VCI/OID4VP examples | `contract_tested` | Contract/artifact tested only |
| OpenID Federation-shaped trust seam | `local_simulation` | Local synthetic trust-resolution simulation only |
| Synthetic clinical-data holder edge | `executed_local` | Participant-app request; data-holder-owned participant/client/user eligibility, patient match, and final disclosure; no caregiver-direct or live HIE/EHR access |
| OpenAPI 3.1 surface | `contract_tested` | Contract tested; no HTTP server |
| W3C VC 2.0 projection | `mapped_only` | Design mapping only; no VC artifact or conformance |
| SMART App Launch | `planned` | Future integration direction with no implemented artifact |

These classes must not be combined into a claim that CareTrust demonstrated a
production trust hub. The post-evaluation artifacts do not establish
cross-organization federation, FHIR conformance, OID4VC deployment, a wallet,
live-registry integration, EHR integration, or production readiness.

## Trace separation

The retained AWS intake and deterministic trust lifecycle are different
provenance families. The live AWS record stops at an unverified draft with
blocking uncertainties. The deterministic lifecycle replays a different
retained model response through local review, source-check, activation,
authorization, and revocation behavior. The machine-readable
[lineage registry](standards/provenance-lineages.json) records their distinct
request IDs and response hashes, plus identifier reuse across standalone
standards examples. A matching synthetic ID alone is never treated as evidence
that two artifacts are one trace.

## Frozen evaluation separation

The manifest records hashes for the existing frozen evaluation configuration,
summary, and report as references. It labels the evaluation
`referenced_only_not_recomputed_or_replaced`, preserves its 20-case scope, and
does not derive new model-performance metrics from later code or standards work.
