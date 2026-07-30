"""Deterministic, fail-closed workflow services for the CareTrust POC.

This module deliberately contains no network client.  The registry check is a
synthetic, in-memory simulator; model output remains an immutable draft and can
only become an active claim after a separately recorded human review and
matching simulated registry result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Mapping

from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.models import (
    ActiveCredentialClaim,
    AuditEvent,
    AuditEventType,
    ClaimStatus,
    DraftCredentialClaim,
    EvidenceArtifact,
    ExtractionRecord,
    ExtractionStatus,
    FieldCorrection,
    RegistryResult,
    RegistryStatus,
    ReviewDecision,
    ReviewRecord,
    StrictModel,
)


def _canonical_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class JsonlAuditLog:
    """Append validated audit events as one canonical JSON object per line."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: AuditEvent) -> None:
        validated = AuditEvent.model_validate(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical_json(validated))
            stream.write("\n")

    def read(self) -> tuple[AuditEvent, ...]:
        if not self.path.exists():
            return ()
        with self.path.open(encoding="utf-8") as stream:
            return tuple(
                AuditEvent.model_validate_json(line)
                for line in stream
                if line.strip()
            )


def intake_evidence(
    payload: EvidenceArtifact | Mapping[str, object],
    *,
    audit_log: JsonlAuditLog,
    actor_ref: str,
    trace_id: str,
    occurred_at: AwareDatetime,
    event_id: str,
) -> EvidenceArtifact:
    """Validate the evidence boundary before recording receipt.

    Invalid, non-synthetic, or extra-field payloads raise validation errors and
    are never appended to the accepted-evidence audit log.
    """

    artifact = EvidenceArtifact.model_validate(payload)
    audit_log.append(
        AuditEvent(
            event_id=event_id,
            event_type=AuditEventType.EVIDENCE_RECEIVED,
            actor_ref=actor_ref,
            object_ref=artifact.artifact_id,
            occurred_at=occurred_at,
            trace_id=trace_id,
            details={
                "fixture_id": artifact.fixture_id,
                "synthetic": True,
                "content_sha256": artifact.content_sha256,
                "document_type": artifact.document_type,
            },
        )
    )
    return artifact


def validate_and_record_extraction(
    raw_response: str | Mapping[str, object],
    artifact: EvidenceArtifact,
    *,
    extraction_id: str,
    model_id: str,
    aws_region: str,
    prompt_sha256: str,
    schema_sha256: str,
    started_at: AwareDatetime,
    completed_at: AwareDatetime,
    latency_ms: int,
    audit_log: JsonlAuditLog,
    actor_ref: str,
    trace_id: str,
    event_id: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
) -> ExtractionRecord:
    """Validate one immutable raw model response and record either outcome."""

    raw_text = (
        raw_response
        if isinstance(raw_response, str)
        else _canonical_json(raw_response)
    )
    draft: DraftCredentialClaim | None = None
    errors: list[str] = []
    try:
        draft = (
            DraftCredentialClaim.model_validate_json(raw_response)
            if isinstance(raw_response, str)
            else DraftCredentialClaim.model_validate(raw_response)
        )
        if draft.evidence_id != artifact.artifact_id:
            raise ValueError("draft evidence_id does not match the intake artifact")

        known_spans = {span.span_id for span in artifact.spans}
        for field_name in type(draft.fields).model_fields:
            field = getattr(draft.fields, field_name)
            unknown = set(field.evidence_refs) - known_spans
            if unknown:
                raise ValueError(
                    f"fields.{field_name} cites unknown evidence: {sorted(unknown)}"
                )
        for uncertainty in draft.uncertainties:
            unknown = set(uncertainty.evidence_refs) - known_spans
            if unknown:
                raise ValueError(
                    f"uncertainty {uncertainty.code.value} cites unknown evidence: "
                    f"{sorted(unknown)}"
                )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        draft = None

    status = (
        ExtractionStatus.SUCCEEDED
        if draft is not None
        else ExtractionStatus.FAILED
    )
    record = ExtractionRecord(
        extraction_id=extraction_id,
        evidence_id=artifact.artifact_id,
        status=status,
        model_id=model_id,
        aws_region=aws_region,
        prompt_sha256=prompt_sha256,
        schema_sha256=schema_sha256,
        raw_response_sha256=_sha256_text(raw_text),
        started_at=started_at,
        completed_at=completed_at,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        draft=draft,
        validation_errors=tuple(errors),
    )
    audit_log.append(
        AuditEvent(
            event_id=event_id,
            event_type=AuditEventType.EXTRACTION_COMPLETED,
            actor_ref=actor_ref,
            object_ref=record.extraction_id,
            occurred_at=completed_at,
            trace_id=trace_id,
            details={
                "status": record.status.value,
                "evidence_id": artifact.artifact_id,
                "raw_response_sha256": record.raw_response_sha256,
                "validation_error_count": len(record.validation_errors),
            },
        )
    )
    return record


class ReviewBundle(StrictModel):
    """A review tied to the exact immutable model output it considered."""

    original_draft: DraftCredentialClaim
    review: ReviewRecord

    @model_validator(mode="after")
    def validate_binding(self) -> "ReviewBundle":
        if self.review.draft_id != self.original_draft.draft_id:
            raise ValueError("review must refer to the supplied original draft")
        if self.review.original_draft_sha256 != _sha256(self.original_draft):
            raise ValueError("review hash must bind the immutable original draft")
        return self


_CORRECTABLE_FIELDS = frozenset(
    {
        "fields.holder_name",
        "fields.registry_id",
        "fields.credential_type",
        "fields.jurisdiction",
        "fields.original_or_issue_date",
        "fields.expiration_date",
        "fields.credential_status",
        "fields.restrictions_or_notes",
        "fields.issuer_or_source",
    }
)


@dataclass(frozen=True)
class ReviewerAuthorizationPolicy:
    """Deterministic synthetic reviewer allow-list for the Phase 1 boundary."""

    allowed_reviewer_refs: frozenset[str]
    policy_version: str = "caretrust.reviewer-authorization.v1"

    def require_authorized(self, reviewer_ref: str) -> None:
        if not reviewer_ref or reviewer_ref not in self.allowed_reviewer_refs:
            raise PermissionError(
                f"reviewer is not authorized by {self.policy_version}"
            )


def _draft_field_value(draft: DraftCredentialClaim, field_path: str) -> str | None:
    if field_path not in _CORRECTABLE_FIELDS:
        raise ValueError(f"field is not review-correctable: {field_path}")
    field_name = field_path.removeprefix("fields.")
    return getattr(draft.fields, field_name).normalized_value or getattr(
        draft.fields, field_name
    ).value


def record_review(
    draft: DraftCredentialClaim,
    *,
    review_id: str,
    reviewer_ref: str,
    decision: ReviewDecision,
    corrections: tuple[FieldCorrection, ...] = (),
    reason: str,
    reviewed_at: AwareDatetime,
    audit_log: JsonlAuditLog,
    actor_ref: str,
    trace_id: str,
    event_id: str,
    authorization_policy: ReviewerAuthorizationPolicy,
) -> ReviewBundle:
    """Record a constrained human decision without modifying model output."""

    authorization_policy.require_authorized(reviewer_ref)
    if actor_ref != reviewer_ref:
        raise PermissionError("review actor must match the authorized reviewer")
    if decision is ReviewDecision.APPROVED and corrections:
        raise ValueError("approved review cannot contain corrections")
    if decision is ReviewDecision.CORRECTED and not corrections:
        raise ValueError("corrected review requires at least one correction")
    if decision in {ReviewDecision.REJECTED, ReviewDecision.DEFERRED} and corrections:
        raise ValueError("rejected or deferred review cannot contain corrections")

    valid_evidence_refs = {
        ref
        for field_name in type(draft.fields).model_fields
        for ref in getattr(draft.fields, field_name).evidence_refs
    }
    valid_evidence_refs.update(
        ref for uncertainty in draft.uncertainties for ref in uncertainty.evidence_refs
    )
    seen_paths: set[str] = set()
    for correction in corrections:
        if correction.field_path in seen_paths:
            raise ValueError("a field may be corrected only once per review")
        seen_paths.add(correction.field_path)
        original_value = _draft_field_value(draft, correction.field_path)
        if correction.previous_value != original_value:
            raise ValueError(
                f"previous value for {correction.field_path} does not match the draft"
            )
        if not correction.reason:
            raise ValueError("correction reason must not be blank")
        if not correction.evidence_refs:
            raise ValueError("correction must retain visible evidence references")
        unknown_refs = set(correction.evidence_refs) - valid_evidence_refs
        if unknown_refs:
            raise ValueError(
                "correction cites evidence outside the reviewed draft: "
                f"{sorted(unknown_refs)}"
            )

    review = ReviewRecord(
        review_id=review_id,
        draft_id=draft.draft_id,
        reviewer_ref=reviewer_ref,
        reviewer_role="authorized_reviewer",
        decision=decision,
        corrections=corrections,
        reason=reason,
        reviewed_at=reviewed_at,
        original_draft_sha256=_sha256(draft),
    )
    details: dict[str, str | int | bool | None] = {
        "decision": review.decision.value,
        "correction_count": len(corrections),
        "original_draft_sha256": review.original_draft_sha256,
        "reviewer_authorization_policy": authorization_policy.policy_version,
    }
    for index, correction in enumerate(corrections, start=1):
        prefix = f"correction_{index}"
        details[f"{prefix}_field_path"] = correction.field_path
        details[f"{prefix}_previous_value"] = correction.previous_value
        details[f"{prefix}_corrected_value"] = correction.corrected_value
        details[f"{prefix}_reason"] = correction.reason

    audit_log.append(
        AuditEvent(
            event_id=event_id,
            event_type=AuditEventType.REVIEW_RECORDED,
            actor_ref=actor_ref,
            object_ref=review.review_id,
            occurred_at=reviewed_at,
            trace_id=trace_id,
            details=details,
        )
    )
    return ReviewBundle(original_draft=draft, review=review)


class SyntheticRegistrySimulator:
    """A deterministic registry double with no capability to make live calls."""

    DEFAULT_RESULTS: Mapping[str, RegistryStatus] = {
        "HI-CNA-SYN-1001": RegistryStatus.MATCH,
        "HI-CNA-SYN-MISMATCH": RegistryStatus.MISMATCH,
        "HI-CNA-SYN-NOT-FOUND": RegistryStatus.NOT_FOUND,
        "HI-CNA-SYN-UNAVAILABLE": RegistryStatus.UNAVAILABLE,
    }

    _REASONS: Mapping[RegistryStatus, str] = {
        RegistryStatus.MATCH: "SYNTHETIC_REGISTRY_MATCH",
        RegistryStatus.MISMATCH: "SYNTHETIC_REGISTRY_MISMATCH",
        RegistryStatus.NOT_FOUND: "SYNTHETIC_REGISTRY_NOT_FOUND",
        RegistryStatus.UNAVAILABLE: "SYNTHETIC_REGISTRY_UNAVAILABLE",
    }

    def __init__(
        self, results: Mapping[str, RegistryStatus] | None = None
    ) -> None:
        self._results = dict(results or self.DEFAULT_RESULTS)

    def check(
        self,
        draft: DraftCredentialClaim,
        *,
        registry_result_id: str,
        checked_at: AwareDatetime,
        audit_log: JsonlAuditLog,
        actor_ref: str,
        trace_id: str,
        event_id: str,
    ) -> RegistryResult:
        query_id = (
            draft.fields.registry_id.normalized_value
            or draft.fields.registry_id.value
        )
        status = (
            self._results.get(query_id, RegistryStatus.NOT_FOUND)
            if query_id
            else RegistryStatus.NOT_FOUND
        )
        reason_code = self._REASONS[status]
        response = {
            "simulator": True,
            "query_registry_id": query_id,
            "status": status.value,
            "reason_code": reason_code,
        }
        result = RegistryResult(
            registry_result_id=registry_result_id,
            draft_id=draft.draft_id,
            simulator=True,
            source_name="Prometric CNA Registry simulator",
            query_registry_id=query_id,
            status=status,
            checked_at=checked_at,
            reason_code=reason_code,
            response_sha256=_sha256(response),
        )
        audit_log.append(
            AuditEvent(
                event_id=event_id,
                event_type=AuditEventType.REGISTRY_CHECKED,
                actor_ref=actor_ref,
                object_ref=result.registry_result_id,
                occurred_at=checked_at,
                trace_id=trace_id,
                details={
                    "simulator": True,
                    "query_registry_id": query_id,
                    "status": status.value,
                    "reason_code": reason_code,
                },
            )
        )
        return result


class ActivationOutcome(StrictModel):
    """Deterministic activation result with machine-readable denial reasons."""

    permitted: bool
    reason_codes: tuple[str, ...]
    claim: ActiveCredentialClaim | None
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def validate_result(self) -> "ActivationOutcome":
        if self.permitted and (self.reason_codes or self.claim is None):
            raise ValueError("permitted activation requires a claim and no denials")
        if not self.permitted and (not self.reason_codes or self.claim is not None):
            raise ValueError("denied activation requires reasons and no claim")
        return self


def _reviewed_value(
    draft: DraftCredentialClaim,
    review: ReviewRecord | None,
    field_path: str,
) -> str | None:
    if review is not None:
        for correction in review.corrections:
            if correction.field_path == field_path:
                return correction.corrected_value
    return _draft_field_value(draft, field_path)


def decide_activation(
    draft: DraftCredentialClaim,
    *,
    review_bundle: ReviewBundle | None,
    registry_result: RegistryResult | None,
    claim_id: str,
    issuer_ref: str,
    allowed_audiences: tuple[str, ...],
    allowed_purposes: tuple[str, ...],
    decided_at: AwareDatetime,
    audit_log: JsonlAuditLog,
    actor_ref: str,
    trace_id: str,
    event_id: str,
) -> ActivationOutcome:
    """Issue only when every human, registry, and data prerequisite passes."""

    reasons: list[str] = []
    review = review_bundle.review if review_bundle is not None else None
    if review_bundle is None:
        reasons.append("REVIEW_REQUIRED")
    elif review_bundle.original_draft != draft or review.draft_id != draft.draft_id:
        reasons.append("REVIEW_DRAFT_MISMATCH")
    elif review.decision is ReviewDecision.REJECTED:
        reasons.append("REVIEW_REJECTED")
    elif review.decision is ReviewDecision.DEFERRED:
        reasons.append("REVIEW_DEFERRED")

    if registry_result is None:
        reasons.append("REGISTRY_RESULT_REQUIRED")
    else:
        if registry_result.draft_id != draft.draft_id:
            reasons.append("REGISTRY_DRAFT_MISMATCH")
        registry_denials = {
            RegistryStatus.MISMATCH: "SOURCE_MISMATCH",
            RegistryStatus.NOT_FOUND: "SOURCE_NOT_FOUND",
            RegistryStatus.UNAVAILABLE: "SOURCE_UNAVAILABLE",
        }
        if registry_result.status in registry_denials:
            reasons.append(registry_denials[registry_result.status])

    if any(uncertainty.blocking for uncertainty in draft.uncertainties):
        reasons.append("BLOCKING_UNCERTAINTY")
    if draft.blocking_issues:
        reasons.append("UNRESOLVED_BLOCKING_ISSUE")

    registry_id = _reviewed_value(draft, review, "fields.registry_id")
    credential_type = _reviewed_value(draft, review, "fields.credential_type")
    jurisdiction = _reviewed_value(draft, review, "fields.jurisdiction")
    credential_status = _reviewed_value(
        draft, review, "fields.credential_status"
    )
    valid_from = _reviewed_value(draft, review, "fields.original_or_issue_date")
    valid_until = _reviewed_value(draft, review, "fields.expiration_date")
    if not registry_id:
        reasons.append("REGISTRY_ID_REQUIRED")
    if credential_type != "Certified Nurse Aide":
        reasons.append("CREDENTIAL_TYPE_UNSUPPORTED")
    if jurisdiction != "HI":
        reasons.append("JURISDICTION_UNSUPPORTED")
    if credential_status != "active":
        reasons.append("CREDENTIAL_STATUS_NOT_ACTIVE")
    if not valid_until:
        reasons.append("EXPIRATION_DATE_REQUIRED")
    else:
        try:
            expiration = date.fromisoformat(valid_until)
        except ValueError:
            reasons.append("EXPIRATION_DATE_INVALID")
        else:
            if expiration < decided_at.date():
                reasons.append("CREDENTIAL_EXPIRED")
    if (
        registry_result is not None
        and registry_result.query_registry_id != registry_id
    ):
        reasons.append("REGISTRY_ID_MISMATCH")

    # Preserve declaration order while suppressing duplicate reasons.
    reason_codes = tuple(dict.fromkeys(reasons))
    claim: ActiveCredentialClaim | None = None
    if not reason_codes:
        all_evidence_refs = [
            reference
            for field_name in type(draft.fields).model_fields
            for reference in getattr(draft.fields, field_name).evidence_refs
        ]
        all_evidence_refs.extend(
            reference
            for correction in review.corrections
            for reference in correction.evidence_refs
        )
        evidence_refs = tuple(dict.fromkeys(all_evidence_refs))
        claim = ActiveCredentialClaim(
            schema_version="caretrust.active-credential-claim.v1",
            claim_id=claim_id,
            claim_type="professional_credential",
            credential_profile="hawaii_cna_smoke_v1",
            subject_ref=draft.subject_ref,
            issuer_ref=issuer_ref,
            jurisdiction="HI",
            registry_id=registry_id,
            credential_type="Certified Nurse Aide",
            valid_from=valid_from,
            valid_until=valid_until,
            status=ClaimStatus.ACTIVE,
            allowed_audiences=allowed_audiences,
            allowed_purposes=allowed_purposes,
            evidence_refs=evidence_refs,
            review_id=review.review_id,
            registry_result_id=registry_result.registry_result_id,
            issued_at=decided_at,
        )

    outcome = ActivationOutcome(
        permitted=claim is not None,
        reason_codes=reason_codes,
        claim=claim,
        decided_at=decided_at,
    )
    audit_log.append(
        AuditEvent(
            event_id=event_id,
            event_type=AuditEventType.ACTIVATION_DECIDED,
            actor_ref=actor_ref,
            object_ref=claim_id,
            occurred_at=decided_at,
            trace_id=trace_id,
            details={
                "permitted": outcome.permitted,
                "reason_codes": ",".join(outcome.reason_codes),
                "draft_id": draft.draft_id,
            },
        )
    )
    if claim is not None:
        audit_log.append(
            AuditEvent(
                event_id=f"{event_id}:issued",
                event_type=AuditEventType.CLAIM_ISSUED,
                actor_ref=actor_ref,
                object_ref=claim.claim_id,
                occurred_at=decided_at,
                trace_id=trace_id,
                details={
                    "draft_id": draft.draft_id,
                    "review_id": claim.review_id,
                    "registry_result_id": claim.registry_result_id,
                },
            )
        )
    return outcome
