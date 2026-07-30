from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from caretrust.models import (
    DraftCredentialClaim,
    FieldCorrection,
    RegistryStatus,
    ReviewDecision,
)
from caretrust.workflow import (
    JsonlAuditLog,
    SyntheticRegistrySimulator,
    decide_activation,
    intake_evidence,
    record_review,
    validate_and_record_extraction,
)


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def clean_fixture() -> dict:
    path = Path("fixtures/cna/smoke/clean.json")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def clean_draft(clean_fixture: dict) -> DraftCredentialClaim:
    return DraftCredentialClaim.model_validate(clean_fixture["expected"]["draft"])


@pytest.fixture
def audit_log(tmp_path: Path) -> JsonlAuditLog:
    return JsonlAuditLog(tmp_path / "audit" / "events.jsonl")


def evidence_payload(clean_fixture: dict) -> dict:
    source = clean_fixture["input"]
    ocr_bytes = source["ocr_text"].encode("utf-8")
    return {
        "artifact_id": source["artifact_id"],
        "fixture_id": clean_fixture["case_id"],
        "synthetic": True,
        "document_type": source["document_type"],
        "content_type": source["content_type"],
        "source_filename": source["source_filename"],
        "content_sha256": hashlib.sha256(ocr_bytes).hexdigest(),
        "ocr_text": source["ocr_text"],
        "spans": [
            {
                "span_id": span["span_id"],
                "artifact_id": source["artifact_id"],
                "quote": span["quote"],
            }
            for span in source["source_spans"]
        ],
    }


def approve(draft, audit_log):
    return record_review(
        draft,
        review_id="review:1",
        reviewer_ref="reviewer:synthetic",
        decision=ReviewDecision.APPROVED,
        reason="Synthetic evidence reviewed.",
        reviewed_at=NOW,
        audit_log=audit_log,
        actor_ref="reviewer:synthetic",
        trace_id="trace:1",
        event_id="event:review",
    )


def registry_check(draft, audit_log, result_id="registry:1"):
    return SyntheticRegistrySimulator().check(
        draft,
        registry_result_id=result_id,
        checked_at=NOW,
        audit_log=audit_log,
        actor_ref="system:registry-simulator",
        trace_id="trace:1",
        event_id=f"event:{result_id}",
    )


def activation(draft, audit_log, *, review=None, registry=None):
    return decide_activation(
        draft,
        review_bundle=review,
        registry_result=registry,
        claim_id="claim:1",
        issuer_ref="caretrust:synthetic-poc",
        allowed_audiences=("care-org:synthetic",),
        allowed_purposes=("caregiver-onboarding",),
        decided_at=NOW,
        audit_log=audit_log,
        actor_ref="system:activation-policy",
        trace_id="trace:1",
        event_id="event:activation",
    )


def draft_with(clean_draft: DraftCredentialClaim, **updates) -> DraftCredentialClaim:
    payload = clean_draft.model_dump(mode="json")
    for path, value in updates.items():
        cursor = payload
        parts = path.split(".")
        for part in parts[:-1]:
            cursor = cursor[part]
        cursor[parts[-1]] = value
    return DraftCredentialClaim.model_validate(payload)


def test_evidence_intake_validates_and_writes_jsonl(
    clean_fixture, audit_log
):
    artifact = intake_evidence(
        evidence_payload(clean_fixture),
        audit_log=audit_log,
        actor_ref="person:synthetic",
        trace_id="trace:1",
        occurred_at=NOW,
        event_id="event:intake",
    )

    assert artifact.synthetic is True
    events = audit_log.read()
    assert len(events) == 1
    assert events[0].event_type.value == "evidence_received"
    assert events[0].details["content_sha256"] == artifact.content_sha256
    raw_lines = audit_log.path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 1
    assert json.loads(raw_lines[0])["object_ref"] == artifact.artifact_id


@pytest.mark.parametrize("fixture_name", ["clean.json", "ambiguous-date.json"])
def test_clean_and_ambiguous_extractions_are_recorded_with_evidence_links(
    fixture_name, audit_log
):
    fixture = json.loads(
        (Path("fixtures/cna/smoke") / fixture_name).read_text(encoding="utf-8")
    )
    artifact = intake_evidence(
        evidence_payload(fixture),
        audit_log=audit_log,
        actor_ref="person:synthetic",
        trace_id="trace:extract",
        occurred_at=NOW,
        event_id=f"event:intake:{fixture['case_id']}",
    )
    raw = json.dumps(fixture["expected"]["draft"])

    record = validate_and_record_extraction(
        raw,
        artifact,
        extraction_id=f"extract:{fixture['case_id']}",
        model_id="synthetic-model",
        aws_region="us-west-2",
        prompt_sha256="0" * 64,
        schema_sha256="1" * 64,
        started_at=NOW,
        completed_at=NOW,
        latency_ms=1,
        audit_log=audit_log,
        actor_ref="system:extractor",
        trace_id="trace:extract",
        event_id=f"event:extract:{fixture['case_id']}",
    )

    assert record.status.value == "extraction_succeeded"
    assert record.draft == DraftCredentialClaim.model_validate(
        fixture["expected"]["draft"]
    )
    assert record.raw_response_sha256 == hashlib.sha256(raw.encode()).hexdigest()


@pytest.mark.parametrize(
    "raw",
    [
        "{not valid JSON",
        {"status": "verified", "unexpected": "model cannot assert trust"},
    ],
)
def test_malformed_and_forbidden_model_output_records_failure(
    clean_fixture, audit_log, raw
):
    artifact = intake_evidence(
        evidence_payload(clean_fixture),
        audit_log=audit_log,
        actor_ref="person:synthetic",
        trace_id="trace:extract",
        occurred_at=NOW,
        event_id="event:intake",
    )

    record = validate_and_record_extraction(
        raw,
        artifact,
        extraction_id="extract:failed",
        model_id="synthetic-model",
        aws_region="us-west-2",
        prompt_sha256="0" * 64,
        schema_sha256="1" * 64,
        started_at=NOW,
        completed_at=NOW,
        latency_ms=1,
        audit_log=audit_log,
        actor_ref="system:extractor",
        trace_id="trace:extract",
        event_id="event:extract",
    )

    assert record.status.value == "extraction_failed"
    assert record.draft is None
    assert record.validation_errors
    assert audit_log.read()[-1].details["validation_error_count"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(synthetic=False),
        lambda p: p.update(unexpected="forbidden"),
        lambda p: p["spans"][0].update(artifact_id="artifact:wrong"),
    ],
)
def test_malformed_evidence_fails_closed_without_accepted_event(
    clean_fixture, audit_log, mutation
):
    payload = evidence_payload(clean_fixture)
    mutation(payload)

    with pytest.raises(ValidationError):
        intake_evidence(
            payload,
            audit_log=audit_log,
            actor_ref="person:synthetic",
            trace_id="trace:1",
            occurred_at=NOW,
            event_id="event:intake",
        )
    assert audit_log.read() == ()


def test_correction_is_visible_and_original_model_output_is_unchanged(
    clean_draft, audit_log
):
    before = clean_draft.model_dump_json()
    correction = FieldCorrection(
        field_path="fields.expiration_date",
        previous_value="2028-04-15",
        corrected_value="2029-04-15",
        reason="Reviewer confirmed the synthetic date in cited evidence.",
        evidence_refs=("clean-expiration-date",),
    )

    bundle = record_review(
        clean_draft,
        review_id="review:corrected",
        reviewer_ref="reviewer:synthetic",
        decision=ReviewDecision.CORRECTED,
        corrections=(correction,),
        reason="One field corrected.",
        reviewed_at=NOW,
        audit_log=audit_log,
        actor_ref="reviewer:synthetic",
        trace_id="trace:1",
        event_id="event:review",
    )

    assert clean_draft.model_dump_json() == before
    assert bundle.original_draft is clean_draft
    event = audit_log.read()[0]
    assert event.details["correction_1_field_path"] == "fields.expiration_date"
    assert event.details["correction_1_previous_value"] == "2028-04-15"
    assert event.details["correction_1_corrected_value"] == "2029-04-15"


@pytest.mark.parametrize(
    ("decision", "corrections"),
    [
        (
            ReviewDecision.APPROVED,
            (
                FieldCorrection(
                    field_path="fields.expiration_date",
                    previous_value="2028-04-15",
                    corrected_value="2029-04-15",
                    reason="Not allowed with approve.",
                    evidence_refs=("clean-expiration-date",),
                ),
            ),
        ),
        (ReviewDecision.CORRECTED, ()),
    ],
)
def test_forbidden_review_states_are_rejected(
    clean_draft, audit_log, decision, corrections
):
    with pytest.raises(ValueError):
        record_review(
            clean_draft,
            review_id="review:bad",
            reviewer_ref="reviewer:synthetic",
            decision=decision,
            corrections=corrections,
            reason="Invalid combination.",
            reviewed_at=NOW,
            audit_log=audit_log,
            actor_ref="reviewer:synthetic",
            trace_id="trace:1",
            event_id="event:review",
        )


@pytest.mark.parametrize(
    ("registry_id", "expected"),
    [
        ("HI-CNA-SYN-1001", RegistryStatus.MATCH),
        ("HI-CNA-SYN-MISMATCH", RegistryStatus.MISMATCH),
        ("HI-CNA-SYN-NOT-FOUND", RegistryStatus.NOT_FOUND),
        ("HI-CNA-SYN-UNAVAILABLE", RegistryStatus.UNAVAILABLE),
    ],
)
def test_registry_simulator_has_four_deterministic_states(
    clean_draft, audit_log, registry_id, expected
):
    candidate = draft_with(
        clean_draft,
        **{
            "fields.registry_id.value": registry_id,
            "fields.registry_id.normalized_value": registry_id,
        },
    )
    result = registry_check(candidate, audit_log)

    assert result.simulator is True
    assert result.status is expected
    assert audit_log.read()[0].details["simulator"] is True


def test_approved_review_plus_registry_match_activates(
    clean_draft, audit_log
):
    review = approve(clean_draft, audit_log)
    registry = registry_check(clean_draft, audit_log)

    outcome = activation(
        clean_draft, audit_log, review=review, registry=registry
    )

    assert outcome.permitted is True
    assert outcome.reason_codes == ()
    assert outcome.claim is not None
    assert outcome.claim.status.value == "active"
    assert outcome.claim.registry_id == "HI-CNA-SYN-1001"
    assert [event.event_type.value for event in audit_log.read()][-2:] == [
        "activation_decided",
        "claim_issued",
    ]


def test_corrected_review_value_is_used_only_after_matching_registry(
    clean_draft, audit_log
):
    correction = FieldCorrection(
        field_path="fields.expiration_date",
        previous_value="2028-04-15",
        corrected_value="2029-04-15",
        reason="Synthetic correction.",
        evidence_refs=("clean-expiration-date",),
    )
    review = record_review(
        clean_draft,
        review_id="review:corrected",
        reviewer_ref="reviewer:synthetic",
        decision=ReviewDecision.CORRECTED,
        corrections=(correction,),
        reason="Corrected.",
        reviewed_at=NOW,
        audit_log=audit_log,
        actor_ref="reviewer:synthetic",
        trace_id="trace:1",
        event_id="event:review",
    )
    registry = registry_check(clean_draft, audit_log)

    outcome = activation(
        clean_draft, audit_log, review=review, registry=registry
    )

    assert outcome.permitted
    assert outcome.claim.valid_until == "2029-04-15"
    assert clean_draft.fields.expiration_date.normalized_value == "2028-04-15"


def test_missing_prerequisites_are_denied_with_reason_codes(
    clean_draft, audit_log
):
    incomplete = draft_with(
        clean_draft,
        **{
            "fields.registry_id.value": None,
            "fields.registry_id.normalized_value": None,
            "fields.credential_type.normalized_value": None,
            "fields.credential_type.value": "Home Health Aide",
            "fields.jurisdiction.normalized_value": None,
            "fields.jurisdiction.value": "CA",
            "fields.expiration_date.normalized_value": None,
            "fields.expiration_date.value": None,
        },
    )

    outcome = activation(incomplete, audit_log)

    assert outcome.permitted is False
    assert set(outcome.reason_codes) == {
        "REVIEW_REQUIRED",
        "REGISTRY_RESULT_REQUIRED",
        "REGISTRY_ID_REQUIRED",
        "CREDENTIAL_TYPE_UNSUPPORTED",
        "JURISDICTION_UNSUPPORTED",
        "EXPIRATION_DATE_REQUIRED",
    }
    assert outcome.claim is None


def test_expired_credential_is_denied_with_reason_code(
    clean_draft, audit_log
):
    expired = draft_with(
        clean_draft,
        **{
            "fields.expiration_date.value": "04/15/2020",
            "fields.expiration_date.normalized_value": "2020-04-15",
        },
    )
    review = approve(expired, audit_log)
    registry = registry_check(expired, audit_log)

    outcome = activation(
        expired, audit_log, review=review, registry=registry
    )

    assert outcome.permitted is False
    assert "CREDENTIAL_EXPIRED" in outcome.reason_codes


def test_non_active_credential_status_is_denied_with_reason_code(
    clean_draft, audit_log
):
    unreadable_status = draft_with(
        clean_draft,
        **{
            "fields.credential_status.value": "Unreadable",
            "fields.credential_status.normalized_value": None,
        },
    )
    review = approve(unreadable_status, audit_log)
    registry = registry_check(unreadable_status, audit_log)

    outcome = activation(
        unreadable_status, audit_log, review=review, registry=registry
    )

    assert outcome.permitted is False
    assert "CREDENTIAL_STATUS_NOT_ACTIVE" in outcome.reason_codes


def test_ambiguous_blocking_draft_is_denied_even_after_approval_and_match(
    clean_draft, audit_log
):
    ambiguous = draft_with(
        clean_draft,
        uncertainties=[
            {
                "code": "AMBIGUOUS_DATE",
                "field_paths": ["fields.expiration_date"],
                "message": "Two synthetic dates are plausible.",
                "evidence_refs": ["clean-expiration-date"],
                "blocking": True,
            }
        ],
        blocking_issues=["Resolve ambiguous expiration date."],
    )
    review = approve(ambiguous, audit_log)
    registry = registry_check(ambiguous, audit_log)

    outcome = activation(
        ambiguous, audit_log, review=review, registry=registry
    )

    assert outcome.permitted is False
    assert "BLOCKING_UNCERTAINTY" in outcome.reason_codes
    assert "UNRESOLVED_BLOCKING_ISSUE" in outcome.reason_codes


@pytest.mark.parametrize(
    "decision", [ReviewDecision.REJECTED, ReviewDecision.DEFERRED]
)
def test_non_accepting_review_denies_activation(
    clean_draft, audit_log, decision
):
    review = record_review(
        clean_draft,
        review_id=f"review:{decision.value}",
        reviewer_ref="reviewer:synthetic",
        decision=decision,
        reason="Not accepted.",
        reviewed_at=NOW,
        audit_log=audit_log,
        actor_ref="reviewer:synthetic",
        trace_id="trace:1",
        event_id="event:review",
    )
    registry = registry_check(clean_draft, audit_log)

    outcome = activation(
        clean_draft, audit_log, review=review, registry=registry
    )

    assert outcome.permitted is False
    expected = {
        ReviewDecision.REJECTED: "REVIEW_REJECTED",
        ReviewDecision.DEFERRED: "REVIEW_DEFERRED",
    }
    assert expected[decision] in outcome.reason_codes


@pytest.mark.parametrize(
    "status",
    [
        RegistryStatus.MISMATCH,
        RegistryStatus.NOT_FOUND,
        RegistryStatus.UNAVAILABLE,
    ],
)
def test_every_non_match_registry_state_denies(
    clean_draft, audit_log, status
):
    registry_ids = {
        RegistryStatus.MISMATCH: "HI-CNA-SYN-MISMATCH",
        RegistryStatus.NOT_FOUND: "HI-CNA-SYN-NOT-FOUND",
        RegistryStatus.UNAVAILABLE: "HI-CNA-SYN-UNAVAILABLE",
    }
    candidate = draft_with(
        clean_draft,
        **{
            "fields.registry_id.value": registry_ids[status],
            "fields.registry_id.normalized_value": registry_ids[status],
        },
    )
    review = approve(candidate, audit_log)
    registry = registry_check(candidate, audit_log)

    outcome = activation(
        candidate, audit_log, review=review, registry=registry
    )

    assert outcome.permitted is False
    expected = {
        RegistryStatus.MISMATCH: "SOURCE_MISMATCH",
        RegistryStatus.NOT_FOUND: "SOURCE_NOT_FOUND",
        RegistryStatus.UNAVAILABLE: "SOURCE_UNAVAILABLE",
    }
    assert expected[status] in outcome.reason_codes
