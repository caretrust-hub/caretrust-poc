# CareTrust six-minute judge walkthrough contract

The machine-readable `judge-walkthrough-contract.json` is generated from
retained canonical artifacts, not from dashboard or browser state:

```powershell
.\.venv\Scripts\python.exe scripts\build_judge_walkthrough.py
.\.venv\Scripts\python.exe scripts\run_judge_walkthrough.py
```

The runner emits eight evidence-bound segments totaling 340 suggested seconds:

1. synthetic patient and three caregiver contexts;
2. AI intent candidate, exact evidence, and human-approval boundary;
3. AI app/OpenAPI candidate into RAR, profile, and minimum-data plan;
4. synthetic OIDC link, reviewed app registration, PKCE/RAR, fresh decision,
   and resource-token receipt;
5. FHIR Appointment/SMART least privilege and synthetic reference-app result;
6. revocation followed by a fresh deny;
7. MCP inspection with unchanged canonical state; and
8. a two-hub federation segment.

Every executed segment has retained artifact paths, SHA-256 bindings, canonical
IDs, evidence status, standards/message labels, and explicit non-claims. The
contract never treats a demo surface as authority.

The federation segment checks for a two-hub artifact at generation time. If none
is present, as in this bounded revision, it is visibly `planned`/`awaited` and
does not claim federation execution.

The CLI's `--json` option prints the same machine-readable contract. No live
model, FHIR, OAuth/OIDC, MCP HTTP, registry, EHR/HIE, or federation service is
invoked by this runner.
