"""Strict contracts for the synthetic uploaded-care-document demonstration.

This module deliberately separates document statements from current clinical
truth. AI extraction produces candidates with exact source evidence. A human
review can approve a document-stated item for bounded sharing, but it does not
make the item clinically authoritative or establish a current care plan.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


Identifier = Annotated[str, Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmptyText = Annotated[str, Field(min_length=1, max_length=4000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_sha256(value: BaseModel | dict[str, Any]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class UploaderRole(str, Enum):
    PATIENT = "patient"
    INVITED_RELATIVE = "invited_relative"


class DocumentClassification(str, Enum):
    DISCHARGE_INSTRUCTIONS = "discharge_instructions"
    AFTER_VISIT_SUMMARY = "after_visit_summary"
    MEDICATION_LIST = "medication_list"
    CARE_PLAN_EXCERPT = "care_plan_excerpt"
    OTHER_MEDICAL_RECORD = "other_medical_record"


class SensitivityLevel(str, Enum):
    RESTRICTED_HEALTH_INFORMATION = "restricted_health_information"
    HIGHLY_SENSITIVE_HEALTH_INFORMATION = "highly_sensitive_health_information"


class MalwareScanStatus(str, Enum):
    CLEAN = "clean"
    BLOCKED = "blocked"


class FileValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class DocumentIntakeStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DocumentPrivacyMetadata(StrictModel):
    sensitivity: SensitivityLevel
    contains_health_information: Literal[True] = True
    contains_real_phi: Literal[False] = False
    synthetic_only: Literal[True] = True
    minimum_necessary_required: Literal[True] = True
    redisclosure_requires_new_decision: Literal[True] = True


class DocumentFileValidation(StrictModel):
    malware_scan_status: MalwareScanStatus
    malware_scanner: Identifier
    file_validation_status: FileValidationStatus
    validated_content_type: Literal["application/pdf", "image/png", "image/jpeg"]
    validated_size_bytes: Annotated[int, Field(ge=1, le=25_000_000)]
    active_content_detected: bool
    password_protected: bool
    reason_codes: tuple[Identifier, ...]
    scanned_at: AwareDatetime


class UploadedCareDocument(StrictModel):
    schema_version: Literal["caretrust.uploaded-care-document.v1"] = (
        "caretrust.uploaded-care-document.v1"
    )
    document_id: Identifier
    patient_ref: Identifier
    uploader_account_ref: Identifier
    uploader_role: UploaderRole
    invite_acceptance_id: Identifier | None = None
    original_retained_ref: Identifier
    content_sha256: Sha256Hex
    filename: Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[^/\\]+$")]
    content_type: Literal["application/pdf", "image/png", "image/jpeg"]
    page_count: Annotated[int, Field(ge=1, le=500)]
    classification: DocumentClassification
    privacy: DocumentPrivacyMetadata
    file_validation: DocumentFileValidation
    intake_status: DocumentIntakeStatus
    uploaded_at: AwareDatetime
    clinically_authoritative: Literal[False] = False

    @model_validator(mode="after")
    def enforce_intake_and_invite(self) -> "UploadedCareDocument":
        if self.uploader_role == UploaderRole.INVITED_RELATIVE and not self.invite_acceptance_id:
            raise ValueError("invited-relative upload requires invite_acceptance_id")
        if self.uploader_role == UploaderRole.PATIENT and self.invite_acceptance_id is not None:
            raise ValueError("patient upload cannot assert invite_acceptance_id")
        accepted = (
            self.file_validation.malware_scan_status == MalwareScanStatus.CLEAN
            and self.file_validation.file_validation_status == FileValidationStatus.VALID
            and not self.file_validation.active_content_detected
            and not self.file_validation.password_protected
            and self.file_validation.validated_content_type == self.content_type
        )
        if (self.intake_status == DocumentIntakeStatus.ACCEPTED) != accepted:
            raise ValueError("intake_status must match malware and file-validation results")
        return self


class CandidateItemKind(str, Enum):
    FACT = "fact"
    INSTRUCTION = "instruction"
    ACTION_ITEM = "action_item"
    MEDICATION_CANDIDATE = "medication_candidate"


class ExtractionUncertaintyCode(str, Enum):
    AMBIGUOUS_DATE = "ambiguous_date"
    AMBIGUOUS_MEDICATION = "ambiguous_medication"
    MISSING_CONTEXT = "missing_context"
    UNREADABLE_TEXT = "unreadable_text"
    CONTRADICTORY_INSTRUCTION = "contradictory_instruction"
    CLINICAL_INTERPRETATION_REQUIRED = "clinical_interpretation_required"


class EvidenceRegion(StrictModel):
    x: Annotated[float, Field(ge=0, le=1)]
    y: Annotated[float, Field(ge=0, le=1)]
    width: Annotated[float, Field(gt=0, le=1)]
    height: Annotated[float, Field(gt=0, le=1)]

    @model_validator(mode="after")
    def stay_on_page(self) -> "EvidenceRegion":
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("evidence region must stay within normalized page bounds")
        return self


class DocumentPageText(StrictModel):
    page: Annotated[int, Field(ge=1)]
    text: Annotated[str, Field(min_length=1, max_length=100_000)]
    text_sha256: Sha256Hex

    @model_validator(mode="after")
    def verify_hash(self) -> "DocumentPageText":
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("page text hash does not match text")
        return self


class DocumentEvidenceSpan(StrictModel):
    evidence_id: Identifier
    document_id: Identifier
    page: Annotated[int, Field(ge=1)]
    region: EvidenceRegion
    start_offset: Annotated[int, Field(ge=0)]
    end_offset: Annotated[int, Field(gt=0)]
    exact_text: NonEmptyText

    @model_validator(mode="after")
    def verify_offsets(self) -> "DocumentEvidenceSpan":
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        if self.end_offset - self.start_offset != len(self.exact_text):
            raise ValueError("evidence offsets must exactly bound exact_text")
        return self


class CandidateDocumentItem(StrictModel):
    item_id: Identifier
    kind: CandidateItemKind
    category: Identifier
    candidate_text: NonEmptyText
    normalized_value: NonEmptyText | None = None
    evidence_refs: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    confidence: Annotated[float, Field(ge=0, le=1)]
    sensitivity: SensitivityLevel
    status: Literal["draft"] = "draft"
    clinically_verified: Literal[False] = False
    current_clinical_truth: Literal[False] = False
    clinically_authoritative: Literal[False] = False
    shareable: Literal[False] = False


class ExtractionUncertainty(StrictModel):
    uncertainty_id: Identifier
    item_id: Identifier
    code: ExtractionUncertaintyCode
    detail: NonEmptyText
    blocking: bool
    evidence_refs: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class DocumentExtractionDraft(StrictModel):
    schema_version: Literal["caretrust.document-extraction-draft.v1"] = (
        "caretrust.document-extraction-draft.v1"
    )
    draft_id: Identifier
    document_id: Identifier
    extraction_run_id: Identifier
    extractor_ref: Identifier
    source_pages: Annotated[tuple[DocumentPageText, ...], Field(min_length=1)]
    evidence_spans: Annotated[tuple[DocumentEvidenceSpan, ...], Field(min_length=1)]
    candidate_items: Annotated[tuple[CandidateDocumentItem, ...], Field(min_length=1)]
    uncertainties: tuple[ExtractionUncertainty, ...]
    blocking_issue_codes: tuple[ExtractionUncertaintyCode, ...]
    created_at: AwareDatetime
    status: Literal["draft"] = "draft"
    clinically_verified: Literal[False] = False
    current_clinical_truth: Literal[False] = False
    clinically_authoritative: Literal[False] = False
    shareable: Literal[False] = False
    synthetic_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_evidence_graph(self) -> "DocumentExtractionDraft":
        pages = {page.page: page for page in self.source_pages}
        if len(pages) != len(self.source_pages):
            raise ValueError("source page numbers must be unique")
        evidence = {span.evidence_id: span for span in self.evidence_spans}
        if len(evidence) != len(self.evidence_spans):
            raise ValueError("evidence IDs must be unique")
        for span in self.evidence_spans:
            if span.document_id != self.document_id:
                raise ValueError("evidence document_id must match draft")
            page = pages.get(span.page)
            if page is None or page.text[span.start_offset : span.end_offset] != span.exact_text:
                raise ValueError("evidence must exactly match retained normalized page text")
        items = {item.item_id: item for item in self.candidate_items}
        if len(items) != len(self.candidate_items):
            raise ValueError("candidate item IDs must be unique")
        for item in self.candidate_items:
            if not set(item.evidence_refs).issubset(evidence):
                raise ValueError("every candidate evidence reference must resolve")
        for uncertainty in self.uncertainties:
            if uncertainty.item_id not in items:
                raise ValueError("uncertainty item_id must resolve")
            if not set(uncertainty.evidence_refs).issubset(evidence):
                raise ValueError("uncertainty evidence reference must resolve")
        expected_blockers = {u.code for u in self.uncertainties if u.blocking}
        if set(self.blocking_issue_codes) != expected_blockers:
            raise ValueError("blocking_issue_codes must equal blocking uncertainties")
        return self


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class DocumentItemCorrection(StrictModel):
    item_id: Identifier
    previous_text: NonEmptyText
    corrected_text: NonEmptyText
    reason: NonEmptyText
    evidence_refs: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class DocumentReviewCorrectionRecord(StrictModel):
    schema_version: Literal["caretrust.document-review-correction-record.v1"] = (
        "caretrust.document-review-correction-record.v1"
    )
    review_id: Identifier
    document_id: Identifier
    draft_id: Identifier
    original_draft_sha256: Sha256Hex
    reviewer_account_ref: Identifier
    reviewer_role: Literal["accountable_reviewer"] = "accountable_reviewer"
    decision: ReviewDecision
    approved_item_ids: tuple[Identifier, ...]
    rejected_item_ids: tuple[Identifier, ...]
    deferred_item_ids: tuple[Identifier, ...]
    corrections: tuple[DocumentItemCorrection, ...]
    reviewed_at: AwareDatetime
    review_scope: Literal["document_statement_only"] = "document_statement_only"
    establishes_legal_authority: Literal[False] = False
    establishes_current_clinical_truth: Literal[False] = False

    @model_validator(mode="after")
    def verify_partition_shape(self) -> "DocumentReviewCorrectionRecord":
        groups = [
            set(self.approved_item_ids),
            set(self.rejected_item_ids),
            set(self.deferred_item_ids),
        ]
        if any(groups[i] & groups[j] for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("review item partitions must be disjoint")
        if len(self.corrections) != len({correction.item_id for correction in self.corrections}):
            raise ValueError("at most one correction is allowed per item")
        if any(c.item_id not in groups[0] for c in self.corrections):
            raise ValueError("corrected items must be in approved_item_ids")
        return self


class ApprovedDocumentItem(StrictModel):
    schema_version: Literal["caretrust.approved-document-item.v1"] = (
        "caretrust.approved-document-item.v1"
    )
    approved_item_id: Identifier
    patient_ref: Identifier
    document_id: Identifier
    draft_id: Identifier
    review_id: Identifier
    source_item_id: Identifier
    kind: CandidateItemKind
    category: Identifier
    reviewed_text: NonEmptyText
    evidence_refs: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    sensitivity: SensitivityLevel
    approval_status: Literal["approved_for_bounded_sharing"] = "approved_for_bounded_sharing"
    source_assertion: Literal["uploaded_document_statement"] = "uploaded_document_statement"
    clinically_authoritative: Literal[False] = False
    current_clinical_truth: Literal[False] = False
    requires_clinical_confirmation: bool


def project_approved_document_items(
    document: UploadedCareDocument,
    draft: DocumentExtractionDraft,
    review: DocumentReviewCorrectionRecord,
) -> tuple[ApprovedDocumentItem, ...]:
    if document.document_id != draft.document_id or review.document_id != draft.document_id:
        raise ValueError("document, draft, and review document IDs must match")
    if review.draft_id != draft.draft_id:
        raise ValueError("review draft_id must match draft")
    if review.original_draft_sha256 != canonical_sha256(draft):
        raise ValueError("review must bind the exact original draft")
    all_ids = {item.item_id for item in draft.candidate_items}
    partition = set(review.approved_item_ids) | set(review.rejected_item_ids) | set(
        review.deferred_item_ids
    )
    if partition != all_ids:
        raise ValueError("review must account for every candidate item exactly once")
    evidence_ids = {span.evidence_id for span in draft.evidence_spans}
    corrections = {correction.item_id: correction for correction in review.corrections}
    result: list[ApprovedDocumentItem] = []
    for item in draft.candidate_items:
        if item.item_id not in review.approved_item_ids:
            continue
        correction = corrections.get(item.item_id)
        if correction:
            if correction.previous_text != item.candidate_text:
                raise ValueError("correction previous_text must match candidate_text")
            if not set(correction.evidence_refs).issubset(evidence_ids):
                raise ValueError("correction evidence references must resolve")
        reviewed_text = correction.corrected_text if correction else item.candidate_text
        result.append(
            ApprovedDocumentItem(
                approved_item_id=f"approved:{review.review_id}:{item.item_id}",
                patient_ref=document.patient_ref,
                document_id=document.document_id,
                draft_id=draft.draft_id,
                review_id=review.review_id,
                source_item_id=item.item_id,
                kind=item.kind,
                category=item.category,
                reviewed_text=reviewed_text,
                evidence_refs=item.evidence_refs,
                sensitivity=item.sensitivity,
                requires_clinical_confirmation=item.kind
                in {CandidateItemKind.MEDICATION_CANDIDATE, CandidateItemKind.ACTION_ITEM},
            )
        )
    return tuple(result)


class SharePurpose(str, Enum):
    CARE_COORDINATION = "care_coordination"
    DISCHARGE_FOLLOW_UP = "discharge_follow_up"
    VISIT_PREPARATION = "visit_preparation"


class ShareAudience(str, Enum):
    CARE_COORDINATION_APP = "app:synthetic-care-coordination"
    SCHEDULING_APP = "app:synthetic-scheduling"
    DIRECT_CARE_TASK_APP = "app:synthetic-direct-care-tasks"


class ShareGrantStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class DocumentShareGrant(StrictModel):
    schema_version: Literal["caretrust.document-share-grant.v1"] = (
        "caretrust.document-share-grant.v1"
    )
    grant_id: Identifier
    patient_ref: Identifier
    review_id: Identifier
    approved_item_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    allowed_audiences: Annotated[tuple[ShareAudience, ...], Field(min_length=1)]
    allowed_purposes: Annotated[tuple[SharePurpose, ...], Field(min_length=1)]
    allowed_item_kinds: Annotated[tuple[CandidateItemKind, ...], Field(min_length=1)]
    maximum_sensitivity: SensitivityLevel
    status: ShareGrantStatus
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    issued_at: AwareDatetime
    revoked_at: AwareDatetime | None = None
    raw_document_sharing_allowed: Literal[False] = False
    unapproved_items_allowed: Literal[False] = False
    overbroad_requests_allowed: Literal[False] = False
    fresh_decision_required: Literal[True] = True
    synthetic_only: Literal[True] = True

    @model_validator(mode="after")
    def verify_lifecycle(self) -> "DocumentShareGrant":
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must follow valid_from")
        if self.status == ShareGrantStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked grant requires revoked_at")
        if self.status != ShareGrantStatus.REVOKED and self.revoked_at is not None:
            raise ValueError("only revoked grant may include revoked_at")
        return self


class DocumentShareRequest(StrictModel):
    schema_version: Literal["caretrust.document-share-request.v1"] = (
        "caretrust.document-share-request.v1"
    )
    request_id: Identifier
    grant_id: Identifier
    patient_ref: Identifier
    requester_ref: Identifier
    audience: ShareAudience
    purpose: SharePurpose
    requested_approved_item_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    include_raw_document: bool
    requested_at: AwareDatetime
    synthetic_only: Literal[True] = True


class DocumentShareReason(str, Enum):
    POLICY_SATISFIED = "policy_satisfied"
    RAW_DOCUMENT_PROHIBITED = "raw_document_prohibited"
    GRANT_MISMATCH = "grant_mismatch"
    PATIENT_MISMATCH = "patient_mismatch"
    GRANT_REVOKED = "grant_revoked"
    GRANT_EXPIRED = "grant_expired"
    OUTSIDE_VALIDITY_WINDOW = "outside_validity_window"
    AUDIENCE_NOT_ALLOWED = "audience_not_allowed"
    PURPOSE_NOT_ALLOWED = "purpose_not_allowed"
    ITEM_NOT_APPROVED = "item_not_approved"
    ITEM_OUTSIDE_GRANT = "item_outside_grant"
    ITEM_KIND_NOT_ALLOWED = "item_kind_not_allowed"
    SENSITIVITY_EXCEEDS_GRANT = "sensitivity_exceeds_grant"


class DocumentShareDecision(StrictModel):
    schema_version: Literal["caretrust.document-share-decision.v1"] = (
        "caretrust.document-share-decision.v1"
    )
    decision_id: Identifier
    request_id: Identifier
    outcome: Literal["permit", "deny"]
    reason_codes: Annotated[tuple[DocumentShareReason, ...], Field(min_length=1)]
    granted_approved_item_ids: tuple[Identifier, ...]
    supporting_grant_id: Identifier | None
    policy_version: Literal["caretrust.document-share-policy.v1"] = (
        "caretrust.document-share-policy.v1"
    )
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def enforce_default_deny_shape(self) -> "DocumentShareDecision":
        if self.outcome == "permit":
            if self.reason_codes != (DocumentShareReason.POLICY_SATISFIED,):
                raise ValueError("permit must use only policy_satisfied")
            if not self.granted_approved_item_ids or self.supporting_grant_id is None:
                raise ValueError("permit requires granted items and supporting grant")
        elif self.granted_approved_item_ids or self.supporting_grant_id is not None:
            raise ValueError("deny cannot disclose items or cite a supporting grant")
        return self


_SENSITIVITY_RANK = {
    SensitivityLevel.RESTRICTED_HEALTH_INFORMATION: 1,
    SensitivityLevel.HIGHLY_SENSITIVE_HEALTH_INFORMATION: 2,
}


def decide_document_share(
    request: DocumentShareRequest,
    grant: DocumentShareGrant,
    approved_items: tuple[ApprovedDocumentItem, ...],
    *,
    decided_at: datetime,
) -> DocumentShareDecision:
    reasons: list[DocumentShareReason] = []
    if request.include_raw_document:
        reasons.append(DocumentShareReason.RAW_DOCUMENT_PROHIBITED)
    if request.grant_id != grant.grant_id:
        reasons.append(DocumentShareReason.GRANT_MISMATCH)
    if request.patient_ref != grant.patient_ref:
        reasons.append(DocumentShareReason.PATIENT_MISMATCH)
    if grant.status == ShareGrantStatus.REVOKED:
        reasons.append(DocumentShareReason.GRANT_REVOKED)
    elif grant.status == ShareGrantStatus.EXPIRED:
        reasons.append(DocumentShareReason.GRANT_EXPIRED)
    if decided_at < grant.valid_from or decided_at >= grant.valid_until:
        reasons.append(DocumentShareReason.OUTSIDE_VALIDITY_WINDOW)
    if request.audience not in grant.allowed_audiences:
        reasons.append(DocumentShareReason.AUDIENCE_NOT_ALLOWED)
    if request.purpose not in grant.allowed_purposes:
        reasons.append(DocumentShareReason.PURPOSE_NOT_ALLOWED)

    approved_by_id = {item.approved_item_id: item for item in approved_items}
    requested_ids = set(request.requested_approved_item_ids)
    unknown_ids = requested_ids - set(approved_by_id)
    if unknown_ids:
        reasons.append(DocumentShareReason.ITEM_NOT_APPROVED)
    if requested_ids - set(grant.approved_item_ids):
        reasons.append(DocumentShareReason.ITEM_OUTSIDE_GRANT)
    known_items = [approved_by_id[item_id] for item_id in requested_ids if item_id in approved_by_id]
    if any(item.patient_ref != grant.patient_ref for item in known_items):
        reasons.append(DocumentShareReason.PATIENT_MISMATCH)
    if any(item.kind not in grant.allowed_item_kinds for item in known_items):
        reasons.append(DocumentShareReason.ITEM_KIND_NOT_ALLOWED)
    if any(
        _SENSITIVITY_RANK[item.sensitivity] > _SENSITIVITY_RANK[grant.maximum_sensitivity]
        for item in known_items
    ):
        reasons.append(DocumentShareReason.SENSITIVITY_EXCEEDS_GRANT)

    unique_reasons = tuple(dict.fromkeys(reasons))
    if unique_reasons:
        return DocumentShareDecision(
            decision_id=f"decision:{request.request_id}",
            request_id=request.request_id,
            outcome="deny",
            reason_codes=unique_reasons,
            granted_approved_item_ids=(),
            supporting_grant_id=None,
            decided_at=decided_at,
        )
    return DocumentShareDecision(
        decision_id=f"decision:{request.request_id}",
        request_id=request.request_id,
        outcome="permit",
        reason_codes=(DocumentShareReason.POLICY_SATISFIED,),
        granted_approved_item_ids=request.requested_approved_item_ids,
        supporting_grant_id=grant.grant_id,
        decided_at=decided_at,
    )


class DocumentShareRevocationRecord(StrictModel):
    schema_version: Literal["caretrust.document-share-revocation-record.v1"] = (
        "caretrust.document-share-revocation-record.v1"
    )
    revocation_id: Identifier
    grant_id: Identifier
    patient_ref: Identifier
    revoked_by_account_ref: Identifier
    reason: NonEmptyText
    revoked_at: AwareDatetime
    historical_decisions_retained: Literal[True] = True
    future_requests_require_fresh_denial: Literal[True] = True


def revoke_document_share_grant(
    grant: DocumentShareGrant,
    *,
    revoked_by_account_ref: str,
    reason: str,
    revoked_at: datetime,
) -> tuple[DocumentShareGrant, DocumentShareRevocationRecord]:
    if grant.status != ShareGrantStatus.ACTIVE:
        raise ValueError("only an active grant can be revoked")
    revoked = grant.model_copy(update={"status": ShareGrantStatus.REVOKED, "revoked_at": revoked_at})
    return revoked, DocumentShareRevocationRecord(
        revocation_id=f"revocation:{grant.grant_id}",
        grant_id=grant.grant_id,
        patient_ref=grant.patient_ref,
        revoked_by_account_ref=revoked_by_account_ref,
        reason=reason,
        revoked_at=revoked_at,
    )


class FhirReference(StrictModel):
    reference: Identifier
    display: NonEmptyText | None = None


class FhirCoding(StrictModel):
    system: Annotated[str, Field(min_length=1, max_length=500)]
    code: NonEmptyText
    display: NonEmptyText | None = None


class FhirCodeableConcept(StrictModel):
    coding: Annotated[tuple[FhirCoding, ...], Field(min_length=1)]
    text: NonEmptyText | None = None


class FhirIdentifier(StrictModel):
    system: Annotated[str, Field(min_length=1, max_length=500)]
    value: NonEmptyText


class FhirAttachment(StrictModel):
    contentType: Literal["application/pdf", "image/png", "image/jpeg"]
    url: Annotated[str, Field(min_length=1, max_length=1000)]
    title: NonEmptyText


class FhirDocumentReferenceContent(StrictModel):
    attachment: FhirAttachment


class FhirDocumentReferenceCandidate(StrictModel):
    resourceType: Literal["DocumentReference"] = "DocumentReference"
    id: Identifier
    status: Literal["current"] = "current"
    type: FhirCodeableConcept
    subject: FhirReference
    date: AwareDatetime
    author: Annotated[tuple[FhirReference, ...], Field(min_length=1)]
    securityLabel: Annotated[tuple[FhirCodeableConcept, ...], Field(min_length=1)]
    identifier: Annotated[tuple[FhirIdentifier, ...], Field(min_length=1)]
    content: Annotated[tuple[FhirDocumentReferenceContent, ...], Field(min_length=1)]


class FhirProvenanceAgent(StrictModel):
    type: FhirCodeableConcept
    who: FhirReference


class FhirProvenanceEntity(StrictModel):
    role: Literal["source"] = "source"
    what: FhirReference


class FhirProvenanceCandidate(StrictModel):
    resourceType: Literal["Provenance"] = "Provenance"
    id: Identifier
    target: Annotated[tuple[FhirReference, ...], Field(min_length=1)]
    recorded: AwareDatetime
    agent: Annotated[tuple[FhirProvenanceAgent, ...], Field(min_length=1)]
    entity: Annotated[tuple[FhirProvenanceEntity, ...], Field(min_length=1)]


class SemanticLossDisposition(str, Enum):
    REPRESENTED = "represented"
    LOCAL_ONLY = "local_only"
    OMITTED = "omitted"


class FhirSemanticLoss(StrictModel):
    source_field: Identifier
    fhir_target: NonEmptyText
    disposition: SemanticLossDisposition
    detail: NonEmptyText


class DownstreamResourceFamily(str, Enum):
    TASK = "Task"
    CARE_PLAN = "CarePlan"
    MEDICATION_STATEMENT = "MedicationStatement"


class DownstreamCandidateStatus(StrictModel):
    resource_family: DownstreamResourceFamily
    source_item_ids: tuple[Identifier, ...]
    projection_status: Literal["planned", "draft_candidate"]
    emitted: Literal[False] = False
    clinically_authoritative: Literal[False] = False
    current_clinical_truth: Literal[False] = False


class UploadedDocumentFhirProjection(StrictModel):
    schema_version: Literal["caretrust.uploaded-document-fhir-r4-candidate-projection.v1"] = (
        "caretrust.uploaded-document-fhir-r4-candidate-projection.v1"
    )
    source_document_id: Identifier
    source_review_id: Identifier
    source_approved_item_ids: tuple[Identifier, ...]
    document_reference: FhirDocumentReferenceCandidate
    provenance: FhirProvenanceCandidate
    semantic_loss: Annotated[tuple[FhirSemanticLoss, ...], Field(min_length=1)]
    downstream_candidates: Annotated[tuple[DownstreamCandidateStatus, ...], Field(min_length=3)]
    candidate_only: Literal[True] = True
    fhir_server_exchange_executed: Literal[False] = False
    official_hl7_validation_executed: Literal[False] = False
    clinically_authoritative: Literal[False] = False

    @model_validator(mode="after")
    def enforce_candidate_bundle(self) -> "UploadedDocumentFhirProjection":
        if self.provenance.target != (
            FhirReference(reference=f"DocumentReference/{self.document_reference.id}"),
        ):
            raise ValueError("Provenance target must be the candidate DocumentReference")
        families = {item.resource_family for item in self.downstream_candidates}
        if families != set(DownstreamResourceFamily):
            raise ValueError("downstream candidate status must cover Task, CarePlan, and Medication")
        if not any(item.disposition == SemanticLossDisposition.OMITTED for item in self.semantic_loss):
            raise ValueError("projection must explicitly identify at least one omitted semantic")
        return self


def project_uploaded_document_to_fhir(
    document: UploadedCareDocument,
    review: DocumentReviewCorrectionRecord,
    approved_items: tuple[ApprovedDocumentItem, ...],
    *,
    recorded_at: datetime,
) -> UploadedDocumentFhirProjection:
    if review.document_id != document.document_id:
        raise ValueError("review must reference uploaded document")
    if any(item.document_id != document.document_id or item.review_id != review.review_id for item in approved_items):
        raise ValueError("approved items must originate from document and review")

    action_ids = tuple(
        item.approved_item_id
        for item in approved_items
        if item.kind == CandidateItemKind.ACTION_ITEM
    )
    medication_ids = tuple(
        item.approved_item_id
        for item in approved_items
        if item.kind == CandidateItemKind.MEDICATION_CANDIDATE
    )
    care_plan_ids = tuple(
        item.approved_item_id
        for item in approved_items
        if item.kind == CandidateItemKind.INSTRUCTION
    )
    doc_ref_id = f"docref-{document.document_id.replace(':', '-')}"
    type_codes = {
        DocumentClassification.DISCHARGE_INSTRUCTIONS: ("18842-5", "Discharge summary"),
        DocumentClassification.AFTER_VISIT_SUMMARY: ("34133-9", "Summarization of episode note"),
        DocumentClassification.MEDICATION_LIST: ("56445-0", "Medication summary"),
        DocumentClassification.CARE_PLAN_EXCERPT: ("18776-5", "Plan of care note"),
        DocumentClassification.OTHER_MEDICAL_RECORD: ("34109-9", "Note"),
    }
    loinc_code, loinc_display = type_codes[document.classification]
    security_code = (
        "R"
        if document.privacy.sensitivity == SensitivityLevel.RESTRICTED_HEALTH_INFORMATION
        else "V"
    )
    return UploadedDocumentFhirProjection(
        source_document_id=document.document_id,
        source_review_id=review.review_id,
        source_approved_item_ids=tuple(item.approved_item_id for item in approved_items),
        document_reference=FhirDocumentReferenceCandidate(
            id=doc_ref_id,
            type=FhirCodeableConcept(
                coding=(
                    FhirCoding(
                        system="http://loinc.org",
                        code=loinc_code,
                        display=loinc_display,
                    ),
                ),
                text=document.classification.value,
            ),
            subject=FhirReference(reference=f"Patient/{document.patient_ref}"),
            date=document.uploaded_at,
            author=(
                FhirReference(
                    reference=f"RelatedPerson/{document.uploader_account_ref}",
                    display="Synthetic document uploader",
                ),
            ),
            securityLabel=(
                FhirCodeableConcept(
                    coding=(
                        FhirCoding(
                            system="http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                            code=security_code,
                            display="restricted" if security_code == "R" else "very restricted",
                        ),
                    )
                ),
            ),
            identifier=(
                FhirIdentifier(
                    system="https://caretrust.example/synthetic/document-sha256",
                    value=document.content_sha256,
                ),
            ),
            content=(
                FhirDocumentReferenceContent(
                    attachment=FhirAttachment(
                        contentType=document.content_type,
                        url=f"https://storage.synthetic.invalid/documents/{document.document_id}",
                        title=document.filename,
                    )
                ),
            ),
        ),
        provenance=FhirProvenanceCandidate(
            id=f"provenance-{review.review_id.replace(':', '-')}",
            target=(FhirReference(reference=f"DocumentReference/{doc_ref_id}"),),
            recorded=recorded_at,
            agent=(
                FhirProvenanceAgent(
                    type=FhirCodeableConcept(
                        coding=(
                            FhirCoding(
                                system="http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                                code="assembler",
                                display="Assembler",
                            ),
                        )
                    ),
                    who=FhirReference(reference=f"Practitioner/{review.reviewer_account_ref}"),
                ),
            ),
            entity=(
                FhirProvenanceEntity(
                    what=FhirReference(reference=f"DocumentReference/source-{document.document_id}")
                ),
                FhirProvenanceEntity(
                    what=FhirReference(reference=f"Basic/{review.review_id}")
                ),
            ),
        ),
        semantic_loss=(
            FhirSemanticLoss(
                source_field="privacy.sensitivity",
                fhir_target="DocumentReference.securityLabel",
                disposition=SemanticLossDisposition.REPRESENTED,
                detail="Mapped to v3 Confidentiality; CareTrust policy detail remains local.",
            ),
            FhirSemanticLoss(
                source_field="original_retained_ref",
                fhir_target="DocumentReference.content.attachment.url",
                disposition=SemanticLossDisposition.LOCAL_ONLY,
                detail="FHIR URL is a synthetic locator; the opaque retained-reference contract remains local.",
            ),
            FhirSemanticLoss(
                source_field="evidence_spans",
                fhir_target="none",
                disposition=SemanticLossDisposition.OMITTED,
                detail="Exact page, region, and text offsets are retained in CareTrust and not emitted in base R4.",
            ),
            FhirSemanticLoss(
                source_field="document_share_grant",
                fhir_target="none",
                disposition=SemanticLossDisposition.OMITTED,
                detail="Purpose, audience, approved-item scope, and revocation require the CareTrust policy contract.",
            ),
        ),
        downstream_candidates=(
            DownstreamCandidateStatus(
                resource_family=DownstreamResourceFamily.TASK,
                source_item_ids=action_ids,
                projection_status="draft_candidate" if action_ids else "planned",
            ),
            DownstreamCandidateStatus(
                resource_family=DownstreamResourceFamily.CARE_PLAN,
                source_item_ids=care_plan_ids,
                projection_status="draft_candidate" if care_plan_ids else "planned",
            ),
            DownstreamCandidateStatus(
                resource_family=DownstreamResourceFamily.MEDICATION_STATEMENT,
                source_item_ids=medication_ids,
                projection_status="draft_candidate" if medication_ids else "planned",
            ),
        ),
    )
