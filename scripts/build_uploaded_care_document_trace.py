"""Build the deterministic synthetic uploaded-care-document trace and examples."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from caretrust.trace import EvidenceStatus, TraceBundle, TraceRecorder
from caretrust.uploaded_care import (
    CandidateDocumentItem,
    CandidateItemKind,
    DocumentClassification,
    DocumentEvidenceSpan,
    DocumentExtractionDraft,
    DocumentFileValidation,
    DocumentIntakeStatus,
    DocumentItemCorrection,
    DocumentPageText,
    DocumentPrivacyMetadata,
    DocumentReviewCorrectionRecord,
    DocumentShareGrant,
    DocumentShareRequest,
    DocumentShareRevocationRecord,
    EvidenceRegion,
    ExtractionUncertainty,
    ExtractionUncertaintyCode,
    FileValidationStatus,
    MalwareScanStatus,
    ReviewDecision,
    SensitivityLevel,
    ShareAudience,
    ShareGrantStatus,
    SharePurpose,
    UploadedCareDocument,
    UploadedDocumentFhirProjection,
    canonical_sha256,
    decide_document_share,
    project_approved_document_items,
    project_uploaded_document_to_fhir,
    revoke_document_share_grant,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "documents" / "synthetic-discharge-instructions.txt"
EXAMPLES = ROOT / "docs" / "standards" / "examples" / "uploaded-care"
ARTIFACT = ROOT / "artifacts" / "validation" / "synthetic-uploaded-care-document-trace.json"
UTC = timezone.utc
BASE = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)


def _span(
    *,
    document_id: str,
    page_text: str,
    evidence_id: str,
    exact_text: str,
    y: float,
) -> DocumentEvidenceSpan:
    start = page_text.index(exact_text)
    return DocumentEvidenceSpan(
        evidence_id=evidence_id,
        document_id=document_id,
        page=1,
        region=EvidenceRegion(x=0.08, y=y, width=0.84, height=0.06),
        start_offset=start,
        end_offset=start + len(exact_text),
        exact_text=exact_text,
    )


def build_models() -> dict[str, object]:
    raw_source = FIXTURE.read_text(encoding="utf-8")
    source = raw_source.strip()
    document_id = "document:synthetic-discharge-001"
    document = UploadedCareDocument(
        document_id=document_id,
        patient_ref="patient:synthetic-001",
        uploader_account_ref="account:synthetic-leilani",
        uploader_role="invited_relative",
        invite_acceptance_id="invite-acceptance:synthetic-001",
        original_retained_ref="artifact:synthetic-upload-original-001",
        content_sha256=hashlib.sha256(raw_source.encode("utf-8")).hexdigest(),
        filename="synthetic-discharge-instructions.pdf",
        content_type="application/pdf",
        page_count=1,
        classification=DocumentClassification.DISCHARGE_INSTRUCTIONS,
        privacy=DocumentPrivacyMetadata(
            sensitivity=SensitivityLevel.RESTRICTED_HEALTH_INFORMATION
        ),
        file_validation=DocumentFileValidation(
            malware_scan_status=MalwareScanStatus.CLEAN,
            malware_scanner="scanner:synthetic-clamav-contract",
            file_validation_status=FileValidationStatus.VALID,
            validated_content_type="application/pdf",
            validated_size_bytes=len(raw_source.encode("utf-8")),
            active_content_detected=False,
            password_protected=False,
            reason_codes=("magic-bytes-contract-checked", "active-content-not-detected"),
            scanned_at=BASE,
        ),
        intake_status=DocumentIntakeStatus.ACCEPTED,
        uploaded_at=BASE + timedelta(seconds=1),
    )

    evidence = (
        _span(
            document_id=document_id,
            page_text=source,
            evidence_id="evidence:discharge-date",
            exact_text="Discharge date: 2026-07-29",
            y=0.25,
        ),
        _span(
            document_id=document_id,
            page_text=source,
            evidence_id="evidence:follow-up",
            exact_text="Instructions: Schedule a follow-up visit with primary care within 7 days.",
            y=0.36,
        ),
        _span(
            document_id=document_id,
            page_text=source,
            evidence_id="evidence:bring-documents",
            exact_text="Action item: Bring this discharge sheet and current medication list.",
            y=0.48,
        ),
        _span(
            document_id=document_id,
            page_text=source,
            evidence_id="evidence:medication-note",
            exact_text=(
                "Medication note: Continue home medicines as previously directed. "
                "Exact medicines and doses are not listed."
            ),
            y=0.60,
        ),
        _span(
            document_id=document_id,
            page_text=source,
            evidence_id="evidence:warning-signs",
            exact_text=(
                "Warning: Seek urgent care for new chest pain or severe shortness of breath."
            ),
            y=0.74,
        ),
    )
    draft = DocumentExtractionDraft(
        draft_id="extraction-draft:synthetic-discharge-001",
        document_id=document_id,
        extraction_run_id="extraction-run:synthetic-local-replay-001",
        extractor_ref="extractor:synthetic-ai-contract",
        source_pages=(
            DocumentPageText(
                page=1,
                text=source,
                text_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            ),
        ),
        evidence_spans=evidence,
        candidate_items=(
            CandidateDocumentItem(
                item_id="candidate:discharge-date",
                kind=CandidateItemKind.FACT,
                category="discharge-date",
                candidate_text="The document states a discharge date of 2026-07-29.",
                normalized_value="2026-07-29",
                evidence_refs=("evidence:discharge-date",),
                confidence=0.99,
                sensitivity=SensitivityLevel.RESTRICTED_HEALTH_INFORMATION,
            ),
            CandidateDocumentItem(
                item_id="candidate:follow-up",
                kind=CandidateItemKind.INSTRUCTION,
                category="follow-up-instruction",
                candidate_text="Schedule primary care follow-up within 7 days.",
                evidence_refs=("evidence:follow-up",),
                confidence=0.96,
                sensitivity=SensitivityLevel.RESTRICTED_HEALTH_INFORMATION,
            ),
            CandidateDocumentItem(
                item_id="candidate:bring-documents",
                kind=CandidateItemKind.ACTION_ITEM,
                category="visit-preparation",
                candidate_text="Bring the discharge sheet and current medication list.",
                evidence_refs=("evidence:bring-documents",),
                confidence=0.98,
                sensitivity=SensitivityLevel.RESTRICTED_HEALTH_INFORMATION,
            ),
            CandidateDocumentItem(
                item_id="candidate:medication",
                kind=CandidateItemKind.MEDICATION_CANDIDATE,
                category="medication-instruction",
                candidate_text="Continue home medicines as previously directed.",
                evidence_refs=("evidence:medication-note",),
                confidence=0.65,
                sensitivity=SensitivityLevel.HIGHLY_SENSITIVE_HEALTH_INFORMATION,
            ),
            CandidateDocumentItem(
                item_id="candidate:warning-signs",
                kind=CandidateItemKind.INSTRUCTION,
                category="warning-sign-instruction",
                candidate_text=(
                    "Seek urgent care for new chest pain or severe shortness of breath."
                ),
                evidence_refs=("evidence:warning-signs",),
                confidence=0.93,
                sensitivity=SensitivityLevel.HIGHLY_SENSITIVE_HEALTH_INFORMATION,
            ),
        ),
        uncertainties=(
            ExtractionUncertainty(
                uncertainty_id="uncertainty:medication-unspecified",
                item_id="candidate:medication",
                code=ExtractionUncertaintyCode.AMBIGUOUS_MEDICATION,
                detail="The document does not list medication names, doses, or a current regimen.",
                blocking=True,
                evidence_refs=("evidence:medication-note",),
            ),
            ExtractionUncertainty(
                uncertainty_id="uncertainty:warning-source-clarification",
                item_id="candidate:warning-signs",
                code=ExtractionUncertaintyCode.CLINICAL_INTERPRETATION_REQUIRED,
                detail=(
                    "The warning text must remain withheld from apps until an accountable "
                    "reviewer clarifies the originating clinical source and intended context."
                ),
                blocking=True,
                evidence_refs=("evidence:warning-signs",),
            ),
        ),
        blocking_issue_codes=(
            ExtractionUncertaintyCode.AMBIGUOUS_MEDICATION,
            ExtractionUncertaintyCode.CLINICAL_INTERPRETATION_REQUIRED,
        ),
        created_at=BASE + timedelta(seconds=2),
    )
    review = DocumentReviewCorrectionRecord(
        review_id="review:synthetic-discharge-001",
        document_id=document_id,
        draft_id=draft.draft_id,
        original_draft_sha256=canonical_sha256(draft),
        reviewer_account_ref="patient:synthetic-001",
        decision=ReviewDecision.CORRECTED,
        approved_item_ids=(
            "candidate:discharge-date",
            "candidate:follow-up",
            "candidate:bring-documents",
        ),
        rejected_item_ids=("candidate:medication",),
        deferred_item_ids=("candidate:warning-signs",),
        corrections=(
            DocumentItemCorrection(
                item_id="candidate:follow-up",
                previous_text="Schedule primary care follow-up within 7 days.",
                corrected_text="The uploaded document says to schedule primary care follow-up within 7 days.",
                reason="Preserve document-statement attribution; do not present as a current care-plan order.",
                evidence_refs=("evidence:follow-up",),
            ),
        ),
        reviewed_at=BASE + timedelta(seconds=3),
    )
    approved = project_approved_document_items(document, draft, review)
    approved_by_source = {item.source_item_id: item for item in approved}
    scheduling_grant = DocumentShareGrant(
        grant_id="document-share-grant:synthetic-scheduling-001",
        patient_ref=document.patient_ref,
        review_id=review.review_id,
        approved_item_ids=(
            approved_by_source["candidate:follow-up"].approved_item_id,
        ),
        allowed_audiences=(ShareAudience.SCHEDULING_APP,),
        allowed_purposes=(SharePurpose.DISCHARGE_FOLLOW_UP,),
        allowed_item_kinds=(CandidateItemKind.INSTRUCTION,),
        maximum_sensitivity=SensitivityLevel.RESTRICTED_HEALTH_INFORMATION,
        status=ShareGrantStatus.ACTIVE,
        valid_from=BASE + timedelta(seconds=4),
        valid_until=BASE + timedelta(days=7),
        issued_at=BASE + timedelta(seconds=4),
    )
    scheduling_request = DocumentShareRequest(
        request_id="document-share-request:synthetic-scheduling-permit-001",
        grant_id=scheduling_grant.grant_id,
        patient_ref=document.patient_ref,
        requester_ref="app:synthetic-scheduling",
        audience=ShareAudience.SCHEDULING_APP,
        purpose=SharePurpose.DISCHARGE_FOLLOW_UP,
        requested_approved_item_ids=(
            approved_by_source["candidate:follow-up"].approved_item_id,
        ),
        include_raw_document=False,
        requested_at=BASE + timedelta(seconds=5),
    )
    scheduling_decision = decide_document_share(
        scheduling_request,
        scheduling_grant,
        approved,
        decided_at=BASE + timedelta(seconds=6),
    )
    task_grant = DocumentShareGrant(
        grant_id="document-share-grant:synthetic-direct-care-task-001",
        patient_ref=document.patient_ref,
        review_id=review.review_id,
        approved_item_ids=(
            approved_by_source["candidate:bring-documents"].approved_item_id,
        ),
        allowed_audiences=(ShareAudience.DIRECT_CARE_TASK_APP,),
        allowed_purposes=(SharePurpose.VISIT_PREPARATION,),
        allowed_item_kinds=(CandidateItemKind.ACTION_ITEM,),
        maximum_sensitivity=SensitivityLevel.RESTRICTED_HEALTH_INFORMATION,
        status=ShareGrantStatus.ACTIVE,
        valid_from=BASE + timedelta(seconds=4),
        valid_until=BASE + timedelta(days=7),
        issued_at=BASE + timedelta(seconds=4),
    )
    task_request = DocumentShareRequest(
        request_id="document-share-request:synthetic-direct-care-task-permit-001",
        grant_id=task_grant.grant_id,
        patient_ref=document.patient_ref,
        requester_ref="app:synthetic-direct-care-tasks",
        audience=ShareAudience.DIRECT_CARE_TASK_APP,
        purpose=SharePurpose.VISIT_PREPARATION,
        requested_approved_item_ids=(
            approved_by_source["candidate:bring-documents"].approved_item_id,
        ),
        include_raw_document=False,
        requested_at=BASE + timedelta(seconds=7),
    )
    task_decision = decide_document_share(
        task_request,
        task_grant,
        approved,
        decided_at=BASE + timedelta(seconds=8),
    )
    fhir = project_uploaded_document_to_fhir(
        document,
        review,
        approved,
        recorded_at=BASE + timedelta(seconds=9),
    )
    revoked_grant, revocation = revoke_document_share_grant(
        scheduling_grant,
        revoked_by_account_ref=document.patient_ref,
        reason="Synthetic patient withdrew future scheduling-app sharing.",
        revoked_at=BASE + timedelta(seconds=10),
    )
    denied_request = scheduling_request.model_copy(
        update={
            "request_id": "document-share-request:synthetic-after-revocation-001",
            "requested_at": BASE + timedelta(seconds=11),
        }
    )
    denied_decision = decide_document_share(
        denied_request,
        revoked_grant,
        approved,
        decided_at=BASE + timedelta(seconds=12),
    )
    return {
        "uploaded-care-document": document,
        "document-extraction-draft": draft,
        "document-review-correction-record": review,
        "approved-document-items": approved,
        "document-share-grant": scheduling_grant,
        "document-share-request": scheduling_request,
        "document-share-decision": scheduling_decision,
        "direct-care-task-share-grant": task_grant,
        "direct-care-task-share-request": task_request,
        "direct-care-task-share-decision": task_decision,
        "uploaded-document-fhir-projection": fhir,
        "document-share-revocation-record": revocation,
        "revoked-document-share-grant": revoked_grant,
        "post-revocation-share-request": denied_request,
        "post-revocation-share-decision": denied_decision,
    }


def _payload(value: object) -> dict[str, object]:
    if hasattr(value, "model_dump"):
        # Normalize tuples and other JSON-mode containers before TraceEnvelope
        # computes its hash; the envelope's JsonValue validation does the same.
        return json.loads(json.dumps(value.model_dump(mode="json")))
    raise TypeError(f"trace payload must be a model, got {type(value)!r}")


def build_trace(models: dict[str, object]) -> TraceBundle:
    recorder = TraceRecorder("trace:synthetic-uploaded-care-document-001")
    steps = (
        (
            "event:upload-accepted",
            BASE + timedelta(seconds=1),
            "account:synthetic-leilani",
            "service:caretrust-document-intake",
            "device-to-intake",
            "UploadedCareDocument",
            EvidenceStatus.EXECUTED_LOCAL,
            models["uploaded-care-document"],
            (
                "CareTrust uploaded-care-document.v1",
                "CareTrust invite-acceptance.v1",
                "OWASP File Upload Cheat Sheet",
            ),
            (
                "The existing accepted invite is referenced by identifier; this trace does not re-adjudicate delegation authority.",
                "No production malware service or real patient content was used.",
            ),
        ),
        (
            "event:extraction-draft",
            BASE + timedelta(seconds=2),
            "service:synthetic-ai-extractor",
            "service:caretrust-review-queue",
            "untrusted-ai-to-accountable-review",
            "DocumentExtractionDraft",
            EvidenceStatus.CONTRACT_TESTED,
            models["document-extraction-draft"],
            ("CareTrust document-extraction-draft.v1",),
            ("This deterministic synthetic replay is not a retained Bedrock inference.",),
        ),
        (
            "event:review-correction",
            BASE + timedelta(seconds=3),
            "patient:synthetic-001",
            "service:caretrust-approved-item-projector",
            "accountable-review-to-approved-projection",
            "DocumentReviewCorrectionRecord",
            EvidenceStatus.EXECUTED_LOCAL,
            models["document-review-correction-record"],
            ("CareTrust document-review-correction-record.v1",),
            ("Review confirms document wording only, not current clinical truth.",),
        ),
        (
            "event:scheduling-share-grant",
            BASE + timedelta(seconds=4),
            "patient:synthetic-001",
            "service:caretrust-policy",
            "patient-to-policy",
            "DocumentShareGrant",
            EvidenceStatus.EXECUTED_LOCAL,
            models["document-share-grant"],
            ("CareTrust document-share-grant.v1", "NIST SP 800-162 ABAC"),
            ("No raw document sharing is authorized.",),
        ),
        (
            "event:direct-care-task-share-grant",
            BASE + timedelta(seconds=4),
            "patient:synthetic-001",
            "service:caretrust-policy",
            "patient-to-policy",
            "DocumentShareGrant",
            EvidenceStatus.EXECUTED_LOCAL,
            models["direct-care-task-share-grant"],
            ("CareTrust document-share-grant.v1", "NIST SP 800-162 ABAC"),
            (
                "Only the reviewed bring-documents reminder is in scope; raw and clinical content are withheld.",
            ),
        ),
        (
            "event:scheduling-share-request",
            BASE + timedelta(seconds=5),
            "app:synthetic-scheduling",
            "service:caretrust-policy",
            "application-to-policy",
            "DocumentShareRequest",
            EvidenceStatus.EXECUTED_LOCAL,
            models["document-share-request"],
            ("CareTrust document-share-request.v1",),
            (),
        ),
        (
            "event:scheduling-share-permit",
            BASE + timedelta(seconds=6),
            "service:caretrust-policy",
            "app:synthetic-scheduling",
            "policy-to-application",
            "DocumentShareDecision",
            EvidenceStatus.EXECUTED_LOCAL,
            models["document-share-decision"],
            ("CareTrust document-share-policy.v1", "NIST SP 800-162 ABAC"),
            (
                "The scheduling app receives only the reviewed follow-up/window statement, not the raw upload.",
            ),
        ),
        (
            "event:direct-care-task-share-request",
            BASE + timedelta(seconds=7),
            "app:synthetic-direct-care-tasks",
            "service:caretrust-policy",
            "application-to-policy",
            "DocumentShareRequest",
            EvidenceStatus.EXECUTED_LOCAL,
            models["direct-care-task-share-request"],
            ("CareTrust document-share-request.v1",),
            (),
        ),
        (
            "event:direct-care-task-share-permit",
            BASE + timedelta(seconds=8),
            "service:caretrust-policy",
            "app:synthetic-direct-care-tasks",
            "policy-to-application",
            "DocumentShareDecision",
            EvidenceStatus.EXECUTED_LOCAL,
            models["direct-care-task-share-decision"],
            ("CareTrust document-share-policy.v1", "NIST SP 800-162 ABAC"),
            (
                "The task app receives only the reviewed bring-documents reminder; medication and warning text remain withheld.",
            ),
        ),
        (
            "event:fhir-candidate-projection",
            BASE + timedelta(seconds=9),
            "service:caretrust-fhir-projector",
            "adapter:synthetic-fhir-boundary",
            "caretrust-to-fhir-r4-candidate",
            "UploadedDocumentFhirProjection",
            EvidenceStatus.MAPPED_ONLY,
            models["uploaded-document-fhir-projection"],
            ("HL7 FHIR R4 DocumentReference", "HL7 FHIR R4 Provenance"),
            (
                "No FHIR server exchange or official HL7 validator was executed.",
                "Task, CarePlan, and MedicationStatement resources are not emitted.",
            ),
        ),
        (
            "event:share-revocation",
            BASE + timedelta(seconds=10),
            "patient:synthetic-001",
            "service:caretrust-policy",
            "patient-to-policy",
            "DocumentShareRevocationRecord",
            EvidenceStatus.EXECUTED_LOCAL,
            models["document-share-revocation-record"],
            ("CareTrust document-share-revocation-record.v1",),
            ("Historical decisions remain append-only; future requests are reevaluated.",),
        ),
        (
            "event:post-revocation-request",
            BASE + timedelta(seconds=11),
            "app:synthetic-scheduling",
            "service:caretrust-policy",
            "application-to-policy",
            "DocumentShareRequest",
            EvidenceStatus.EXECUTED_LOCAL,
            models["post-revocation-share-request"],
            ("CareTrust document-share-request.v1",),
            (),
        ),
        (
            "event:post-revocation-deny",
            BASE + timedelta(seconds=12),
            "service:caretrust-policy",
            "app:synthetic-scheduling",
            "policy-to-application",
            "DocumentShareDecision",
            EvidenceStatus.EXECUTED_LOCAL,
            models["post-revocation-share-decision"],
            ("CareTrust document-share-policy.v1", "NIST SP 800-162 ABAC"),
            ("A prior permit is not replayed after revocation.",),
        ),
    )
    for (
        event_id,
        at,
        actor,
        receiver,
        boundary,
        message_type,
        evidence_status,
        value,
        standards,
        non_claims,
    ) in steps:
        payload = _payload(value)
        linked_ids = {
            key: str(payload[key])
            for key in (
                "document_id",
                "patient_ref",
                "uploader_account_ref",
                "invite_acceptance_id",
                "draft_id",
                "review_id",
                "grant_id",
                "request_id",
                "decision_id",
                "revocation_id",
                "source_document_id",
            )
            if key in payload
        }
        recorder.append(
            event_id=event_id,
            occurred_at=at,
            actor_ref=actor,
            receiver_ref=receiver,
            boundary=boundary,
            message_type=message_type,
            evidence_status=evidence_status,
            payload=payload,
            standard_refs=standards,
            linked_ids=linked_ids,
            non_claims=non_claims,
        )
    return recorder.bundle(
        title="Synthetic uploaded discharge document: evidence, review, bounded sharing, revocation",
        fixture_refs=(
            "fixtures/documents/synthetic-discharge-instructions.txt",
            "docs/standards/examples/delegation/invite-acceptance.json",
        ),
        limitations=(
            "Synthetic-only fixture: do not upload real PHI to this proof of concept.",
            "AI extraction is a deterministic contract replay, not a claim of clinical correctness.",
            "Review establishes document wording only; it does not establish current clinical truth.",
            "FHIR R4 DocumentReference and Provenance are candidate mappings with explicit semantic loss.",
            "HIE and EHR retrieval remain planned future integrations and are not dependencies of this trace.",
        ),
    )


def write_outputs() -> None:
    models = build_models()
    trace = build_trace(models)
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    for name, value in models.items():
        if isinstance(value, tuple):
            data = [item.model_dump(mode="json") for item in value]
        else:
            data = value.model_dump(mode="json")
        (EXAMPLES / f"{name}.json").write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(ARTIFACT.relative_to(ROOT))


if __name__ == "__main__":
    write_outputs()
