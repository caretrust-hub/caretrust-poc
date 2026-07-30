"""Export deterministic interoperability-facing JSON Schema artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from caretrust.models import (
    ActiveCredentialClaim,
    AuditEvent,
    AuthorizationDecision,
    AuthorizationRequest,
    DraftCredentialClaim,
    EvidenceArtifact,
    ExtractionRecord,
    RegistryResult,
    ReviewRecord,
    RevocationRecord,
)

ROOT = Path(__file__).resolve().parents[1]
EXPORTS: tuple[tuple[type[BaseModel], Path], ...] = (
    (
        EvidenceArtifact,
        ROOT / "schemas" / "evidence-artifact.schema.json",
    ),
    (
        DraftCredentialClaim,
        ROOT / "schemas" / "draft-credential-claim.schema.json",
    ),
    (
        ExtractionRecord,
        ROOT / "schemas" / "extraction-record.schema.json",
    ),
    (
        ReviewRecord,
        ROOT / "schemas" / "review-record.schema.json",
    ),
    (
        RegistryResult,
        ROOT / "schemas" / "registry-result.schema.json",
    ),
    (
        ActiveCredentialClaim,
        ROOT / "schemas" / "active-credential-claim.schema.json",
    ),
    (
        AuthorizationRequest,
        ROOT / "schemas" / "authorization-request.schema.json",
    ),
    (
        AuthorizationDecision,
        ROOT / "schemas" / "authorization-decision.schema.json",
    ),
    (
        RevocationRecord,
        ROOT / "schemas" / "revocation-record.schema.json",
    ),
    (
        AuditEvent,
        ROOT / "schemas" / "audit-event.schema.json",
    ),
)


def schema_for(model: type[BaseModel]) -> dict[str, object]:
    """Return the exact validation schema used for checked-in exports."""

    return model.model_json_schema(
        mode="validation",
        ref_template="#/$defs/{model}",
    )


def main() -> None:
    for model, output in EXPORTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(schema_for(model), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
