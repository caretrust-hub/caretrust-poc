from __future__ import annotations

from copy import deepcopy
import json
from datetime import UTC, datetime
from pathlib import Path

from caretrust.case_bundle import (
    build_synthetic_case_bundle,
    canonical_sha256,
    evaluate_case_permission,
    validate_case_bundle,
)
from scripts.build_case_bundle import main

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "validation" / "synthetic-multi-caregiver-case.json"


def _cna_inputs(bundle: dict[str, object]) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    objects = bundle["canonical_objects"]
    assert isinstance(objects, dict)
    request = next(item for item in objects["permission_requests"] if item["request_id"] == "request:case:cna-permit-001")
    return request, objects["credential_claim"], objects["agency_assignment"], objects["agency_service_grant"]


def test_case_bundle_is_one_canonical_three_caregiver_projection() -> None:
    bundle = build_synthetic_case_bundle()
    assert bundle["patient"]["patient_ref"] == "patient:synthetic-001"
    assert {row["role"] for row in bundle["caregivers"]} == {
        "patient_invited_family_caregiver", "agency_cna", "respite_community_caregiver",
    }
    assert bundle["bundle_sha256"] == canonical_sha256({key: value for key, value in bundle.items() if key != "bundle_sha256"})


def test_evaluator_mutations_change_purpose_audience_action_status_and_validity_outcomes() -> None:
    bundle = build_synthetic_case_bundle()
    request, claim, assignment, service_grant = _cna_inputs(bundle)
    items = {item["approved_item_id"]: item for item in bundle["canonical_objects"]["approved_document_items"]}
    now = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)

    def decide(candidate: dict[str, object], **overrides: object) -> dict[str, object]:
        return evaluate_case_permission(
            candidate, credential_claim=overrides.get("claim", claim),
            assignment=overrides.get("assignment", assignment), service_grant=overrides.get("service_grant", service_grant),
            approved_items=items, as_of=overrides.get("as_of", now),
        )

    assert decide(request)["decision"] == "permit"
    wrong_purpose = deepcopy(request); wrong_purpose["purpose"] = "wrong-purpose"
    assert decide(wrong_purpose)["reason_code"] == "PURPOSE_NOT_ALLOWED"
    wrong_audience = deepcopy(request); wrong_audience["application_id"] = wrong_audience["audience"] = "app:wrong"
    assert decide(wrong_audience)["reason_code"] == "AUDIENCE_NOT_ALLOWED"
    mismatched_audience = deepcopy(request); mismatched_audience["audience"] = "app:wrong"
    assert decide(mismatched_audience)["reason_code"] == "APPLICATION_AUDIENCE_MISMATCH"
    wrong_action = deepcopy(request); wrong_action["action"] = "delete_record"
    assert decide(wrong_action)["reason_code"] == "ACTION_NOT_ALLOWED"
    unknown_path = deepcopy(request); unknown_path["authority_path"] = "caller_selected_empty_path"
    assert decide(unknown_path)["reason_code"] == "UNKNOWN_AUTHORITY_PATH"
    injected_requirements = deepcopy(request); injected_requirements["required_bases"] = []
    assert decide(injected_requirements)["reason_code"] == "REQUEST_SHAPE_INVALID"
    revoked_claim = deepcopy(claim); revoked_claim["status"] = "revoked"
    assert decide(request, claim=revoked_claim)["reason_code"] == "CLAIM_REVOKED"
    expired_assignment = deepcopy(assignment); expired_assignment["valid_until"] = "2026-07-30T17:00:00Z"
    assert decide(request, assignment=expired_assignment)["reason_code"] == "ASSIGNMENT_EXPIRED"
    exact_boundary = deepcopy(assignment); exact_boundary["valid_until"] = "2026-07-30T18:00:00Z"
    assert decide(request, assignment=exact_boundary)["reason_code"] == "ASSIGNMENT_EXPIRED"


def test_required_outcomes_and_real_correction_lineage_are_projected() -> None:
    bundle = build_synthetic_case_bundle()
    decisions = bundle["projections"]["permissions"]
    reasons = {row["reason_code"] for row in decisions}
    assert any(row["decision"] == "permit" for row in decisions)
    assert {"PURPOSE_NOT_ALLOWED", "CLAIM_REQUIRED", "CLINICAL_CLARIFICATION_REQUIRED", "ASSIGNMENT_EXPIRED", "GRANT_REVOKED", "CLAIM_REVOKED"} <= reasons
    objects = bundle["canonical_objects"]
    review = objects["uploaded_review_correction"]
    approved = objects["approved_document_items"]
    assert review["decision"] == "corrected"
    assert review["review_id"] == approved[0]["review_id"]
    assert review["draft_id"] == approved[0]["draft_id"]
    correction_events = [row for row in bundle["projections"]["history"] if row["message_type"] == "DocumentReviewCorrectionRecord"]
    assert correction_events and correction_events[0]["canonical_ids"]["review_id"] == review["review_id"]
    assert objects["document_share_decision"]["outcome"] == "permit"
    assert objects["post_revocation_document_share_decision"]["outcome"] == "deny"
    assert objects["post_revocation_document_share_decision"]["request_id"] == (
        objects["post_revocation_document_share_request"]["request_id"]
    )
    assert bundle["policy"]["default"] == "deny"
    assert bundle["policy"]["authority_path_requirements"]["workforce_assignment_v1"] == [
        "assignment", "credential", "service_grant"
    ]


def test_app_rows_resolve_canonical_requests_decisions_and_leak_no_source_content() -> None:
    bundle = build_synthetic_case_bundle()
    app_rows = bundle["projections"]["applications"]
    requests = {item["request_id"] for item in bundle["canonical_objects"]["permission_requests"]}
    decisions = {item["decision_id"] for item in bundle["decisions"]}
    assert {row["request_id"] for row in app_rows} == requests
    assert {row["decision_id"] for row in app_rows} == decisions
    serialized = json.dumps(app_rows)
    for forbidden in ("raw_document", "uploaded_extraction_draft", "claim:synthetic-hi-cna-1001", "CarePlan", "synthetic caregiver visit instructions"):
        assert forbidden not in serialized
    assert all("supporting_canonical_ids" not in row for row in app_rows)
    cna_permit = next(
        row for row in app_rows if row["request_id"] == "request:case:cna-permit-001"
    )
    assert cna_permit["minimum_data"][0]["source_assertion"] == "uploaded_document_statement"
    assert cna_permit["minimum_data"][0]["clinically_authoritative"] is False


def test_generator_writes_validated_artifact() -> None:
    main()
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    validate_case_bundle(data)
