"""Export deterministic interoperability-facing JSON Schema artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from caretrust.clinical_edge import (
    ClinicalDataAuthorizationDecision,
    ClinicalDataAuthorizationRequest,
    ClinicalDataExchangeRecord,
    PatientMatchResult,
)
from caretrust.delegation import (
    CareRelationshipClaim,
    ClarificationRequest,
    ClarificationResponse,
    DelegationAuthorizationDecision,
    DelegationAuthorizationRequest,
    DelegationDraft,
    DelegationGrant,
    DelegationRevocationRecord,
    IntentStatement,
    InviteAcceptance,
    PatientApprovalRecord,
    PatientInvite,
)
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
from caretrust.navigator import PatientNavigatorProjection
from caretrust.trace import TraceBundle, TraceEnvelope
from caretrust.uploaded_care import (
    DocumentExtractionDraft,
    DocumentReviewCorrectionRecord,
    DocumentShareDecision,
    DocumentShareGrant,
    DocumentShareRequest,
    DocumentShareRevocationRecord,
    UploadedCareDocument,
    UploadedDocumentFhirProjection,
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
    (
        TraceEnvelope,
        ROOT / "schemas" / "trace-envelope.schema.json",
    ),
    (
        TraceBundle,
        ROOT / "schemas" / "trace-bundle.schema.json",
    ),
    (
        IntentStatement,
        ROOT / "schemas" / "intent-statement.schema.json",
    ),
    (
        DelegationDraft,
        ROOT / "schemas" / "delegation-draft.schema.json",
    ),
    (
        ClarificationRequest,
        ROOT / "schemas" / "clarification-request.schema.json",
    ),
    (
        ClarificationResponse,
        ROOT / "schemas" / "clarification-response.schema.json",
    ),
    (
        PatientInvite,
        ROOT / "schemas" / "patient-invite.schema.json",
    ),
    (
        InviteAcceptance,
        ROOT / "schemas" / "invite-acceptance.schema.json",
    ),
    (
        PatientApprovalRecord,
        ROOT / "schemas" / "patient-approval-record.schema.json",
    ),
    (
        CareRelationshipClaim,
        ROOT / "schemas" / "care-relationship-claim.schema.json",
    ),
    (
        DelegationGrant,
        ROOT / "schemas" / "delegation-grant.schema.json",
    ),
    (
        DelegationAuthorizationRequest,
        ROOT / "schemas" / "delegation-authorization-request.schema.json",
    ),
    (
        DelegationAuthorizationDecision,
        ROOT / "schemas" / "delegation-authorization-decision.schema.json",
    ),
    (
        DelegationRevocationRecord,
        ROOT / "schemas" / "delegation-revocation-record.schema.json",
    ),
    (
        ClinicalDataAuthorizationRequest,
        ROOT / "schemas" / "clinical-data-authorization-request.schema.json",
    ),
    (
        PatientMatchResult,
        ROOT / "schemas" / "patient-match-result.schema.json",
    ),
    (
        ClinicalDataAuthorizationDecision,
        ROOT / "schemas" / "clinical-data-authorization-decision.schema.json",
    ),
    (
        ClinicalDataExchangeRecord,
        ROOT / "schemas" / "clinical-data-exchange-record.schema.json",
    ),
    (
        PatientNavigatorProjection,
        ROOT / "schemas" / "patient-navigator-projection.schema.json",
    ),
    (
        UploadedCareDocument,
        ROOT / "schemas" / "uploaded-care-document.schema.json",
    ),
    (
        DocumentExtractionDraft,
        ROOT / "schemas" / "document-extraction-draft.schema.json",
    ),
    (
        DocumentReviewCorrectionRecord,
        ROOT / "schemas" / "document-review-correction-record.schema.json",
    ),
    (
        DocumentShareGrant,
        ROOT / "schemas" / "document-share-grant.schema.json",
    ),
    (
        DocumentShareRequest,
        ROOT / "schemas" / "document-share-request.schema.json",
    ),
    (
        DocumentShareDecision,
        ROOT / "schemas" / "document-share-decision.schema.json",
    ),
    (
        DocumentShareRevocationRecord,
        ROOT / "schemas" / "document-share-revocation-record.schema.json",
    ),
    (
        UploadedDocumentFhirProjection,
        ROOT / "schemas" / "uploaded-document-fhir-projection.schema.json",
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
