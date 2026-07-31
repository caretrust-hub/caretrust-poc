from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from caretrust.trace import TraceBundle
from caretrust.uploaded_care import (
    DocumentExtractionDraft,
    DocumentReviewCorrectionRecord,
    DocumentShareDecision,
    DocumentShareGrant,
    DocumentShareReason,
    DocumentShareRequest,
    DocumentShareRevocationRecord,
    UploadedCareDocument,
    UploadedDocumentFhirProjection,
    decide_document_share,
    project_approved_document_items,
)
from scripts.build_uploaded_care_document_trace import BASE, build_models, build_trace


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "standards" / "examples" / "uploaded-care"
ARTIFACT = ROOT / "artifacts" / "validation" / "synthetic-uploaded-care-document-trace.json"
SCHEMAS = ROOT / "schemas"


SCHEMA_MODELS = {
    "uploaded-care-document.schema.json": UploadedCareDocument,
    "document-extraction-draft.schema.json": DocumentExtractionDraft,
    "document-review-correction-record.schema.json": DocumentReviewCorrectionRecord,
    "document-share-grant.schema.json": DocumentShareGrant,
    "document-share-request.schema.json": DocumentShareRequest,
    "document-share-decision.schema.json": DocumentShareDecision,
    "document-share-revocation-record.schema.json": DocumentShareRevocationRecord,
    "uploaded-document-fhir-projection.schema.json": UploadedDocumentFhirProjection,
}


def _dump(value: object) -> dict[str, object]:
    assert hasattr(value, "model_dump")
    return value.model_dump(mode="json")


def test_valid_synthetic_chain_has_exact_evidence_and_accountable_review() -> None:
    models = build_models()
    document = models["uploaded-care-document"]
    draft = models["document-extraction-draft"]
    review = models["document-review-correction-record"]
    approved = models["approved-document-items"]
    assert isinstance(document, UploadedCareDocument)
    assert isinstance(draft, DocumentExtractionDraft)
    assert isinstance(review, DocumentReviewCorrectionRecord)
    assert document.patient_ref == "patient:synthetic-001"
    assert document.uploader_account_ref == "account:synthetic-leilani"
    assert document.uploader_role == "invited_relative"
    assert document.invite_acceptance_id == "invite-acceptance:synthetic-001"
    assert document.privacy.contains_real_phi is False
    assert document.clinically_authoritative is False
    assert draft.shareable is False
    assert draft.clinically_verified is False
    assert all(
        draft.source_pages[span.page - 1].text[span.start_offset : span.end_offset]
        == span.exact_text
        for span in draft.evidence_spans
    )
    assert {item.source_item_id for item in approved} == set(review.approved_item_ids)
    assert review.rejected_item_ids == ("candidate:medication",)
    assert review.deferred_item_ids == ("candidate:warning-signs",)
    assert {
        uncertainty.code.value
        for uncertainty in draft.uncertainties
        if uncertainty.blocking
    } == {"ambiguous_medication", "clinical_interpretation_required"}
    assert all(item.current_clinical_truth is False for item in approved)
    assert all(item.source_assertion == "uploaded_document_statement" for item in approved)


def test_tampered_evidence_and_invalid_file_intake_are_rejected() -> None:
    models = build_models()
    draft_payload = _dump(models["document-extraction-draft"])
    draft_payload["evidence_spans"][0]["exact_text"] = "Discharge date: 2026-07-28"
    with pytest.raises(ValidationError, match="offsets|exactly match"):
        DocumentExtractionDraft.model_validate(draft_payload)

    document_payload = _dump(models["uploaded-care-document"])
    document_payload["file_validation"]["malware_scan_status"] = "blocked"
    with pytest.raises(ValidationError, match="intake_status"):
        UploadedCareDocument.model_validate(document_payload)


def test_review_binds_exact_draft_and_accounts_for_every_candidate() -> None:
    models = build_models()
    review_payload = _dump(models["document-review-correction-record"])
    review_payload["original_draft_sha256"] = "0" * 64
    tampered_review = DocumentReviewCorrectionRecord.model_validate(review_payload)
    with pytest.raises(ValueError, match="exact original draft"):
        project_approved_document_items(
            models["uploaded-care-document"],
            models["document-extraction-draft"],
            tampered_review,
        )

    review_payload = _dump(models["document-review-correction-record"])
    review_payload["rejected_item_ids"] = []
    incomplete_review = DocumentReviewCorrectionRecord.model_validate(review_payload)
    with pytest.raises(ValueError, match="account for every"):
        project_approved_document_items(
            models["uploaded-care-document"],
            models["document-extraction-draft"],
            incomplete_review,
        )


def test_share_policy_denies_raw_unapproved_overbroad_and_wrong_purpose() -> None:
    models = build_models()
    grant = models["document-share-grant"]
    approved = models["approved-document-items"]
    base_request = models["document-share-request"]
    approved_by_source = {item.source_item_id: item for item in approved}

    cases = (
        (
            {"request_id": "request:raw", "include_raw_document": True},
            DocumentShareReason.RAW_DOCUMENT_PROHIBITED,
        ),
        (
            {
                "request_id": "request:unknown-item",
                "requested_approved_item_ids": ("approved:not-reviewed",),
            },
            DocumentShareReason.ITEM_NOT_APPROVED,
        ),
        (
            {
                "request_id": "request:approved-but-overbroad",
                "requested_approved_item_ids": (
                    approved_by_source["candidate:discharge-date"].approved_item_id,
                ),
            },
            DocumentShareReason.ITEM_OUTSIDE_GRANT,
        ),
        (
            {
                "request_id": "request:wrong-purpose",
                "purpose": "care_coordination",
            },
            DocumentShareReason.PURPOSE_NOT_ALLOWED,
        ),
    )
    for update, expected in cases:
        request = DocumentShareRequest.model_validate(
            {**_dump(base_request), **update}
        )
        decision = decide_document_share(
            request,
            grant,
            approved,
            decided_at=BASE + timedelta(seconds=6),
        )
        assert decision.outcome == "deny"
        assert expected in decision.reason_codes
        assert decision.granted_approved_item_ids == ()
        assert decision.supporting_grant_id is None


def test_two_apps_receive_disjoint_purpose_minimized_administrative_items() -> None:
    models = build_models()
    approved = {
        item.approved_item_id: item for item in models["approved-document-items"]
    }
    scheduling_grant = models["document-share-grant"]
    scheduling_decision = models["document-share-decision"]
    task_grant = models["direct-care-task-share-grant"]
    task_decision = models["direct-care-task-share-decision"]

    assert scheduling_decision.outcome == task_decision.outcome == "permit"
    assert set(scheduling_decision.granted_approved_item_ids) == set(
        scheduling_grant.approved_item_ids
    )
    assert set(task_decision.granted_approved_item_ids) == set(task_grant.approved_item_ids)
    assert set(scheduling_grant.approved_item_ids).isdisjoint(task_grant.approved_item_ids)
    assert {
        approved[item_id].source_item_id for item_id in scheduling_grant.approved_item_ids
    } == {"candidate:follow-up"}
    assert {
        approved[item_id].source_item_id for item_id in task_grant.approved_item_ids
    } == {"candidate:bring-documents"}
    disclosed_source_ids = {
        approved[item_id].source_item_id
        for item_id in (
            *scheduling_decision.granted_approved_item_ids,
            *task_decision.granted_approved_item_ids,
        )
    }
    assert "candidate:medication" not in disclosed_source_ids
    assert "candidate:warning-signs" not in disclosed_source_ids
    assert "candidate:discharge-date" not in disclosed_source_ids
    assert scheduling_grant.raw_document_sharing_allowed is False
    assert task_grant.raw_document_sharing_allowed is False


def test_revocation_forces_a_fresh_denial_without_erasing_prior_permit() -> None:
    models = build_models()
    permit = models["document-share-decision"]
    denial = models["post-revocation-share-decision"]
    revocation = models["document-share-revocation-record"]
    assert permit.outcome == "permit"
    assert denial.outcome == "deny"
    assert denial.reason_codes == (DocumentShareReason.GRANT_REVOKED,)
    assert revocation.historical_decisions_retained is True
    trace = build_trace(models)
    assert [
        event.event_id
        for event in trace.events
        if event.message_type == "DocumentShareDecision"
    ] == [
        "event:scheduling-share-permit",
        "event:direct-care-task-share-permit",
        "event:post-revocation-deny",
    ]
    assert [event.message_type for event in trace.events][-3:] == [
        "DocumentShareRevocationRecord",
        "DocumentShareRequest",
        "DocumentShareDecision",
    ]
    assert trace.events[-1].payload["outcome"] == "deny"


def test_fhir_projection_is_candidate_only_and_names_semantic_loss() -> None:
    projection = build_models()["uploaded-document-fhir-projection"]
    assert isinstance(projection, UploadedDocumentFhirProjection)
    assert projection.document_reference.resourceType == "DocumentReference"
    assert projection.provenance.resourceType == "Provenance"
    assert projection.fhir_server_exchange_executed is False
    assert projection.official_hl7_validation_executed is False
    assert any(loss.disposition == "omitted" for loss in projection.semantic_loss)
    assert {candidate.resource_family.value for candidate in projection.downstream_candidates} == {
        "Task",
        "CarePlan",
        "MedicationStatement",
    }
    assert all(candidate.emitted is False for candidate in projection.downstream_candidates)
    serialized = json.dumps(projection.model_dump(mode="json"))
    assert '"resourceType": "Task"' not in serialized
    assert '"resourceType": "CarePlan"' not in serialized
    assert '"resourceType": "MedicationStatement"' not in serialized


def test_checked_in_examples_artifact_and_schemas_equal_runtime() -> None:
    models = build_models()
    for name, value in models.items():
        expected = (
            [item.model_dump(mode="json") for item in value]
            if isinstance(value, tuple)
            else value.model_dump(mode="json")
        )
        actual = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
        assert actual == expected

    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert TraceBundle.model_validate(artifact) == build_trace(models)
    for filename, model in SCHEMA_MODELS.items():
        exported = json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))
        assert exported == model.model_json_schema(
            mode="validation",
            ref_template="#/$defs/{model}",
        )


def test_public_uploaded_care_artifacts_are_synthetic_and_contain_no_contacts_or_secrets() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [ARTIFACT, *EXAMPLES.glob("*.json")]
    )
    assert "SYNTHETIC" in text.upper()
    for pattern in (
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"AKIA[0-9A-Z]{16}",
    ):
        assert re.search(pattern, text) is None
