"""Strict domain contracts for the synthetic CareTrust proof of concept.

Model output is accepted only as :class:`DraftCredentialClaim`. The draft model
forbids unknown properties and admits no verified, active, registry-matched, or
authorized state.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

JsonScalar = str | int | float | bool | None


class StrictModel(BaseModel):
    """Immutable contract that rejects undeclared input."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


def _require_nonblank(value: str) -> str:
    if not value:
        raise ValueError("value must not be blank")
    return value


def _validate_sha256(value: str) -> str:
    normalized = value.lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError("value must be a 64-character SHA-256 hex digest")
    return normalized


class SourceRegion(StrictModel):
    """Optional document-space coordinates for an evidence span."""

    page: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None


class EvidenceSpan(StrictModel):
    """A synthetic source excerpt that supports one or more extracted values."""

    span_id: str
    artifact_id: str
    quote: str
    start_char: int | None = None
    end_char: int | None = None
    region: SourceRegion | None = None

    _span_id_nonblank = field_validator("span_id")(_require_nonblank)
    _artifact_id_nonblank = field_validator("artifact_id")(_require_nonblank)
    _quote_nonblank = field_validator("quote")(_require_nonblank)

    @model_validator(mode="after")
    def validate_offsets(self) -> EvidenceSpan:
        if (self.start_char is None) != (self.end_char is None):
            raise ValueError("start_char and end_char must be supplied together")
        if (
            self.start_char is not None
            and self.end_char is not None
            and (self.start_char < 0 or self.end_char <= self.start_char)
        ):
            raise ValueError("character offsets must form a positive ordered span")
        return self


class EvidenceArtifact(StrictModel):
    """Synthetic evidence accepted by the intake boundary."""

    artifact_id: str
    fixture_id: str
    synthetic: Literal[True]
    document_type: Literal["hawaii_cna_status_record"]
    content_type: Literal["text/plain", "application/pdf", "image/png"]
    source_filename: str
    content_sha256: str
    ocr_text: str
    spans: tuple[EvidenceSpan, ...]

    _artifact_id_nonblank = field_validator("artifact_id")(_require_nonblank)
    _fixture_id_nonblank = field_validator("fixture_id")(_require_nonblank)
    _source_filename_nonblank = field_validator("source_filename")(_require_nonblank)
    _ocr_text_nonblank = field_validator("ocr_text")(_require_nonblank)
    _content_hash = field_validator("content_sha256")(_validate_sha256)

    @model_validator(mode="after")
    def validate_span_ownership(self) -> EvidenceArtifact:
        if any(span.artifact_id != self.artifact_id for span in self.spans):
            raise ValueError("every evidence span must refer to this artifact")
        span_ids = [span.span_id for span in self.spans]
        if len(span_ids) != len(set(span_ids)):
            raise ValueError("evidence span identifiers must be unique")
        return self


class UncertaintyCode(StrEnum):
    AMBIGUOUS_DATE = "AMBIGUOUS_DATE"
    MISSING_IDENTIFIER = "MISSING_IDENTIFIER"
    CROPPED_RESTRICTION = "CROPPED_RESTRICTION"
    UNSUPPORTED_ISSUER = "UNSUPPORTED_ISSUER"
    UNREADABLE_EVIDENCE = "UNREADABLE_EVIDENCE"
    CONTRADICTORY_VALUE = "CONTRADICTORY_VALUE"


class DraftField(StrictModel):
    """One unverified extracted field with explicit evidence linkage."""

    value: str | None
    normalized_value: str | None = None
    confidence: float
    evidence_refs: tuple[str, ...]

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between zero and one")
        return value

    @model_validator(mode="after")
    def require_evidence_for_values(self) -> DraftField:
        if self.value is not None and not self.evidence_refs:
            raise ValueError("a populated draft field must cite source evidence")
        return self


class DraftCredentialFields(StrictModel):
    """Gold fields for the deliberately narrow Hawaii CNA smoke profile."""

    holder_name: DraftField
    registry_id: DraftField
    credential_type: DraftField
    jurisdiction: DraftField
    original_or_issue_date: DraftField
    expiration_date: DraftField
    credential_status: DraftField
    restrictions_or_notes: DraftField
    issuer_or_source: DraftField


class Uncertainty(StrictModel):
    code: UncertaintyCode
    field_paths: tuple[str, ...]
    message: str
    evidence_refs: tuple[str, ...]
    blocking: bool

    _message_nonblank = field_validator("message")(_require_nonblank)


class DraftCredentialClaim(StrictModel):
    """The only structured object that an extraction model may propose."""

    schema_version: Literal["caretrust.draft-credential-claim.v1"]
    draft_id: str
    evidence_id: str
    subject_ref: str
    claim_type: Literal["professional_credential"]
    credential_profile: Literal["hawaii_cna_smoke_v1"]
    status: Literal["draft"]
    fields: DraftCredentialFields
    uncertainties: tuple[Uncertainty, ...]
    blocking_issues: tuple[str, ...]

    _draft_id_nonblank = field_validator("draft_id")(_require_nonblank)
    _evidence_id_nonblank = field_validator("evidence_id")(_require_nonblank)
    _subject_ref_nonblank = field_validator("subject_ref")(_require_nonblank)


class ExtractionStatus(StrEnum):
    SUCCEEDED = "extraction_succeeded"
    FAILED = "extraction_failed"


class ExtractionRecord(StrictModel):
    """Immutable record of one schema-validation attempt."""

    extraction_id: str
    evidence_id: str
    status: ExtractionStatus
    model_id: str
    aws_region: str
    prompt_sha256: str
    schema_sha256: str
    raw_response_sha256: str
    started_at: AwareDatetime
    completed_at: AwareDatetime
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    draft: DraftCredentialClaim | None = None
    validation_errors: tuple[str, ...] = ()

    _prompt_hash = field_validator("prompt_sha256")(_validate_sha256)
    _schema_hash = field_validator("schema_sha256")(_validate_sha256)
    _response_hash = field_validator("raw_response_sha256")(_validate_sha256)

    @model_validator(mode="after")
    def validate_outcome(self) -> ExtractionRecord:
        if self.status is ExtractionStatus.SUCCEEDED and self.draft is None:
            raise ValueError("successful extraction requires a draft")
        if self.status is ExtractionStatus.FAILED and not self.validation_errors:
            raise ValueError("failed extraction requires visible validation errors")
        return self


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class FieldCorrection(StrictModel):
    field_path: str
    previous_value: str | None
    corrected_value: str | None
    reason: str
    evidence_refs: tuple[str, ...]


class ReviewRecord(StrictModel):
    review_id: str
    draft_id: str
    reviewer_ref: str
    reviewer_role: Literal["authorized_reviewer"]
    decision: ReviewDecision
    corrections: tuple[FieldCorrection, ...]
    reason: str
    reviewed_at: AwareDatetime
    original_draft_sha256: str

    _draft_hash = field_validator("original_draft_sha256")(_validate_sha256)


class RegistryStatus(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


class RegistryResult(StrictModel):
    registry_result_id: str
    draft_id: str
    simulator: Literal[True]
    source_name: Literal["Prometric CNA Registry simulator"]
    query_registry_id: str | None
    status: RegistryStatus
    checked_at: AwareDatetime
    reason_code: str
    response_sha256: str

    _response_hash = field_validator("response_sha256")(_validate_sha256)


class ClaimStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ActiveCredentialClaim(StrictModel):
    """A post-review, post-source-verification claim created outside the model."""

    schema_version: Literal["caretrust.active-credential-claim.v1"]
    claim_id: str
    claim_type: Literal["professional_credential"]
    credential_profile: Literal["hawaii_cna_smoke_v1"]
    subject_ref: str
    issuer_ref: str
    jurisdiction: Literal["HI"]
    registry_id: str
    credential_type: Literal["Certified Nurse Aide"]
    valid_from: str | None
    valid_until: str
    status: ClaimStatus
    allowed_audiences: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    review_id: str
    registry_result_id: str
    issued_at: AwareDatetime
    revoked_at: AwareDatetime | None = None


class AuthorizationRequest(StrictModel):
    request_id: str
    subject_ref: str
    claim_id: str
    requested_claim_type: Literal["professional_credential"]
    audience: str
    purpose: str
    requested_at: AwareDatetime


class DecisionValue(StrEnum):
    PERMIT = "permit"
    DENY = "deny"


class AuthorizationDecision(StrictModel):
    decision_id: str
    request_id: str
    decision: DecisionValue
    reason_codes: tuple[str, ...]
    supporting_claim_ids: tuple[str, ...]
    policy_version: str
    decided_at: AwareDatetime


class AuditEventType(StrEnum):
    EVIDENCE_RECEIVED = "evidence_received"
    EXTRACTION_COMPLETED = "extraction_completed"
    REVIEW_RECORDED = "review_recorded"
    REGISTRY_CHECKED = "registry_checked"
    ACTIVATION_DECIDED = "activation_decided"
    CLAIM_ISSUED = "claim_issued"
    AUTHORIZATION_DECIDED = "authorization_decided"
    CLAIM_REVOKED = "claim_revoked"


class AuditEvent(StrictModel):
    event_id: str
    event_type: AuditEventType
    actor_ref: str
    object_ref: str
    occurred_at: AwareDatetime
    trace_id: str
    details: dict[str, JsonScalar]
