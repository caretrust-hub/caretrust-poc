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

| Capability | Permitted description |
| --- | --- |
| CareTrust claim and policy | Implemented and locally tested |
| FHIR R4 qualification projection | Executable local projection with deterministic local tests |
| OID4VCI/OID4VP examples | Contract/artifact tested only |
| OpenID Federation-shaped trust seam | Local synthetic trust-resolution simulation only |
| OpenAPI 3.1 surface | Contract only; no HTTP server |

These classes must not be combined into a claim that CareTrust demonstrated a
production trust hub. The post-evaluation artifacts do not establish
cross-organization federation, FHIR conformance, OID4VC deployment, a wallet,
live-registry integration, EHR integration, or production readiness.

## Frozen evaluation separation

The manifest records hashes for the existing frozen evaluation configuration,
summary, and report as references. It labels the evaluation
`referenced_only_not_recomputed_or_replaced`, preserves its 20-case scope, and
does not derive new model-performance metrics from later code or standards work.
