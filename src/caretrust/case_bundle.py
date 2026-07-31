"""Deterministic canonical multi-caregiver case bundle.

The module is deliberately a projection/evaluation seam.  It calls existing
POC builders read-only and derives local case decisions from request bindings,
claims, relationships, delegations, assignments, service grants, and time.
It never turns a display row into authority.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.build_credential_walkthrough_trace import build_credential_walkthrough_trace
from scripts.build_synthetic_patient_navigator import build_trace as build_delegation_trace
from scripts.build_uploaded_care_document_trace import (
    build_models as build_uploaded_models,
    build_trace as build_uploaded_trace,
)
from scripts.export_clinical_edge_examples import build_examples as build_clinical_examples


AS_OF = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
PATIENT = "patient:synthetic-001"
POLICY_ID = "https://caretrust-hub.github.io/caretrust-spec/policies/case-access/v1"
POLICY_VERSION = "case-access.v1"
AUTHORITY_PATH_REQUIREMENTS = {
    "family_delegation_v1": frozenset({"relationship", "delegation"}),
    "workforce_assignment_v1": frozenset(
        {"credential", "assignment", "service_grant"}
    ),
    "community_respite_v1": frozenset({"assignment", "service_grant"}),
}


def canonical_sha256(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _event(trace: Any, message_type: str, *, last: bool = False) -> Any:
    events = [event for event in trace.events if event.message_type == message_type]
    if not events:
        raise ValueError(f"trace contains no {message_type}")
    return events[-1] if last else events[0]


def _json(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    assert isinstance(value, dict)
    return value


def _at(value: str | None, *, inclusive_date_end: bool = False) -> datetime | None:
    if value is None:
        return None
    if len(value) == 10:
        parsed_date = date.fromisoformat(value)
        if inclusive_date_end:
            parsed_date += timedelta(days=1)
        return datetime.combine(parsed_date, time.min, tzinfo=UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _active(value: Mapping[str, Any], as_of: datetime, *, status_key: str = "status") -> str | None:
    """Return the deterministic failing reason, if the bounded object is inactive."""
    status = value.get(status_key)
    if status == "revoked":
        revoked_at = _at(value.get("revoked_at"))
        if revoked_at is None or as_of >= revoked_at:
            return "GRANT_REVOKED"
    if status == "expired":
        return "ASSIGNMENT_EXPIRED"
    if status not in {"active", "revoked"}:
        return "STATUS_NOT_ACTIVE"
    start = _at(value.get("valid_from"))
    end = _at(value.get("valid_until"), inclusive_date_end=True)
    if start is not None and as_of < start:
        return "NOT_YET_VALID"
    if end is not None and as_of >= end:
        return "ASSIGNMENT_EXPIRED"
    return None


def _decision_id(
    request: Mapping[str, Any], as_of: datetime, outcome: str, reason: str
) -> str:
    material = (
        f"{canonical_sha256(request)}|{as_of.isoformat()}|{outcome}|{reason}"
    )
    return "decision:case:" + sha256(material.encode("utf-8")).hexdigest()[:20]


def evaluate_case_permission(
    request: Mapping[str, Any],
    *,
    credential_claim: Mapping[str, Any] | None = None,
    relationship_claim: Mapping[str, Any] | None = None,
    delegation_grant: Mapping[str, Any] | None = None,
    assignment: Mapping[str, Any] | None = None,
    service_grant: Mapping[str, Any] | None = None,
    approved_items: Mapping[str, Mapping[str, Any]] | None = None,
    as_of: datetime,
) -> dict[str, object]:
    """Evaluate one case request with default-deny, source-bound local policy.

    The request declares which bases are required.  A permit requires every
    required base to bind the same patient/caregiver/audience/purpose/action and
    to be active at ``as_of``.  Only reviewed approved-item text may be emitted.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    approved_items = approved_items or {}
    authority_path = request.get("authority_path")
    required = AUTHORITY_PATH_REQUIREMENTS.get(str(authority_path))
    patient = str(request.get("patient_ref", ""))
    caregiver = str(request.get("caregiver_ref", ""))
    application = str(request.get("application_id", ""))
    audience = str(request.get("audience", ""))
    purpose = str(request.get("purpose", ""))
    action = str(request.get("action", ""))
    request_id = str(request.get("request_id", "request:invalid"))

    def deny(reason: str) -> dict[str, object]:
        return {
            "decision_id": _decision_id(request, as_of, "deny", reason),
            "request_id": request_id, "caregiver_ref": caregiver,
            "request_sha256": canonical_sha256(request),
            "application_id": application, "audience": audience,
            "action": action, "purpose": purpose, "as_of": as_of.isoformat().replace("+00:00", "Z"),
            "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
            "decision": "deny", "reason_code": reason,
            "supporting_canonical_ids": [], "minimum_data": [],
            "evidence_status": request.get("evidence_status", "executed_local"),
        }

    expected_request_fields = {
        "request_id",
        "patient_ref",
        "caregiver_ref",
        "application_id",
        "audience",
        "action",
        "purpose",
        "authority_path",
        "requested_approved_item_ids",
        "clinical_clarification_required",
        "evidence_status",
    }
    if set(request) != expected_request_fields or not all(
        (request_id, patient, caregiver, application, audience, action, purpose)
    ):
        return deny("REQUEST_SHAPE_INVALID")

    # An unresolved clinical interpretation blocks before any document data is projected.
    if request.get("clinical_clarification_required"):
        return deny("CLINICAL_CLARIFICATION_REQUIRED")
    if required is None:
        return deny("UNKNOWN_AUTHORITY_PATH")
    if application != audience:
        return deny("APPLICATION_AUDIENCE_MISMATCH")

    supporting: list[str] = []
    if "relationship" in required:
        if relationship_claim is None:
            return deny("RELATIONSHIP_REQUIRED")
        if relationship_claim.get("patient_ref") != patient or relationship_claim.get("caregiver_ref") != caregiver:
            return deny("RELATIONSHIP_SUBJECT_MISMATCH")
        reason = _active(relationship_claim, as_of)
        if reason:
            return deny(reason)
        supporting.append(relationship_claim["relationship_claim_id"])

    if "delegation" in required:
        if delegation_grant is None:
            return deny("GRANT_REQUIRED")
        if delegation_grant.get("patient_ref") != patient or delegation_grant.get("delegate_ref") != caregiver:
            return deny("GRANT_SUBJECT_MISMATCH")
        reason = _active(delegation_grant, as_of)
        if reason:
            return deny(reason)
        if audience not in delegation_grant.get("allowed_audiences", ()):
            return deny("AUDIENCE_NOT_ALLOWED")
        if purpose not in delegation_grant.get("allowed_purposes", ()):
            return deny("PURPOSE_NOT_ALLOWED")
        if action not in delegation_grant.get("allowed_actions", ()):
            return deny("ACTION_NOT_ALLOWED")
        supporting.append(delegation_grant["grant_id"])

    if "credential" in required:
        if credential_claim is None:
            return deny("CLAIM_REQUIRED")
        if credential_claim.get("subject_ref") != caregiver:
            return deny("CLAIM_SUBJECT_MISMATCH")
        status = credential_claim.get("status")
        if status == "revoked":
            revoked_at = _at(credential_claim.get("revoked_at"))
            if revoked_at is None or as_of >= revoked_at:
                return deny("CLAIM_REVOKED")
        if status == "expired":
            return deny("CLAIM_EXPIRED")
        if status not in {"active", "revoked"}:
            return deny("CLAIM_NOT_ACTIVE")
        if audience not in credential_claim.get("allowed_audiences", ()):
            return deny("AUDIENCE_NOT_ALLOWED")
        if purpose not in credential_claim.get("allowed_purposes", ()):
            return deny("PURPOSE_NOT_ALLOWED")
        if _at(credential_claim.get("valid_from")) and as_of < _at(credential_claim["valid_from"]):
            return deny("CLAIM_NOT_YET_VALID")
        if as_of >= _at(credential_claim["valid_until"]):
            return deny("CLAIM_EXPIRED")
        supporting.append(credential_claim["claim_id"])

    if "assignment" in required:
        if assignment is None:
            return deny("ASSIGNMENT_REQUIRED")
        if assignment.get("patient_ref") != patient or assignment.get("caregiver_ref") != caregiver:
            return deny("ASSIGNMENT_SUBJECT_MISMATCH")
        reason = _active(assignment, as_of)
        if reason:
            return deny(reason)
        if action not in assignment.get("allowed_actions", ()):
            return deny("ACTION_NOT_ALLOWED")
        supporting.append(assignment["assignment_id"])

    requested_item_ids = tuple(request.get("requested_approved_item_ids", ()))
    if "service_grant" in required:
        if service_grant is None:
            return deny("SERVICE_GRANT_REQUIRED")
        if service_grant.get("patient_ref") != patient or service_grant.get("caregiver_ref") != caregiver:
            return deny("SERVICE_GRANT_SUBJECT_MISMATCH")
        reason = _active(service_grant, as_of)
        if reason:
            return deny(reason)
        if audience not in service_grant.get("allowed_audiences", ()):
            return deny("AUDIENCE_NOT_ALLOWED")
        if purpose not in service_grant.get("allowed_purposes", ()):
            return deny("PURPOSE_NOT_ALLOWED")
        if action not in service_grant.get("allowed_actions", ()):
            return deny("ACTION_NOT_ALLOWED")
        if not set(requested_item_ids) <= set(service_grant.get("approved_item_ids", ())):
            return deny("ITEM_NOT_ALLOWED")
        supporting.append(service_grant["grant_id"])

    if requested_item_ids and "service_grant" not in required:
        return deny("DOCUMENT_GRANT_REQUIRED")
    minimum_data: list[dict[str, object]] = []
    for item_id in requested_item_ids:
        item = approved_items.get(item_id)
        if item is None or item.get("approval_status") != "approved_for_bounded_sharing":
            return deny("ITEM_NOT_APPROVED")
        if item.get("patient_ref") != patient:
            return deny("ITEM_SUBJECT_MISMATCH")
        minimum_data.append(
            {
                "approved_item_id": item_id,
                "kind": item["kind"],
                "category": item["category"],
                "reviewed_text": item["reviewed_text"],
                "source_assertion": item["source_assertion"],
                "clinically_authoritative": item["clinically_authoritative"],
                "requires_clinical_confirmation": item[
                    "requires_clinical_confirmation"
                ],
            }
        )
    if not supporting:
        return deny("AUTHORITY_REQUIRED")
    return {
        "decision_id": _decision_id(
            request, as_of, "permit", "POLICY_REQUIREMENTS_SATISFIED"
        ),
        "request_id": request_id, "caregiver_ref": caregiver,
        "request_sha256": canonical_sha256(request),
        "application_id": application, "audience": audience,
        "action": action, "purpose": purpose, "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
        "decision": "permit", "reason_code": "POLICY_REQUIREMENTS_SATISFIED",
        "supporting_canonical_ids": supporting, "minimum_data": minimum_data,
        "evidence_status": request.get("evidence_status", "executed_local"),
    }


def _application_projection(decisions: list[dict[str, object]]) -> list[dict[str, object]]:
    """Receipts are a strict allowlist, excluding canonical source packets."""
    fields = ("decision_id", "request_id", "request_sha256", "caregiver_ref", "application_id", "audience", "action", "purpose", "policy_id", "policy_version", "decision", "reason_code", "minimum_data", "evidence_status")
    return [{field: decision[field] for field in fields} for decision in decisions]


def _request(request_id: str, caregiver_ref: str, application_id: str, action: str, purpose: str, authority_path: str, *, item_ids: tuple[str, ...] = (), clinical_block: bool = False, evidence_status: str = "executed_local") -> dict[str, object]:
    return {
        "request_id": request_id, "patient_ref": PATIENT, "caregiver_ref": caregiver_ref,
        "application_id": application_id, "audience": application_id, "action": action,
        "purpose": purpose, "authority_path": authority_path,
        "requested_approved_item_ids": list(item_ids), "clinical_clarification_required": clinical_block,
        "evidence_status": evidence_status,
    }


def build_synthetic_case_bundle() -> dict[str, object]:
    delegation_trace = build_delegation_trace()
    credential_trace = build_credential_walkthrough_trace()
    uploaded = build_uploaded_models()
    uploaded_trace = build_uploaded_trace(uploaded)
    clinical = build_clinical_examples()

    relationship = _event(delegation_trace, "CareRelationshipClaim").payload
    delegation_grant = _event(delegation_trace, "DelegationGrant").payload
    delegation_revocation = _event(delegation_trace, "DelegationRevocationRecord").payload
    credential_claim = _event(credential_trace, "ActiveCredentialClaim").payload
    credential_revocation = _event(credential_trace, "RevocationRecord").payload
    document = uploaded["uploaded-care-document"]
    extraction = uploaded["document-extraction-draft"]
    review = uploaded["document-review-correction-record"]
    approved = uploaded["approved-document-items"]
    approved_by_id = {item.approved_item_id: _json(item) for item in approved}
    document_share_grant = uploaded["document-share-grant"]
    document_share_request = uploaded["document-share-request"]
    document_share_decision = uploaded["document-share-decision"]
    direct_share_grant = uploaded["direct-care-task-share-grant"]
    direct_share_request = uploaded["direct-care-task-share-request"]
    direct_share_decision = uploaded["direct-care-task-share-decision"]
    document_revocation = uploaded["document-share-revocation-record"]
    post_revocation_share_request = uploaded["post-revocation-share-request"]
    post_revocation_share_decision = uploaded["post-revocation-share-decision"]

    family = delegation_grant["delegate_ref"]
    cna = credential_claim["subject_ref"]
    respite = "caregiver:synthetic-respite-001"
    direct_app = "urn:caretrust:app:scheduling"  # Existing active CNA claim audience.
    approved_task = direct_share_grant.approved_item_ids[0]
    agency_assignment = {
        "assignment_id": "assignment:synthetic-cna-direct-care-001", "caregiver_ref": cna,
        "patient_ref": PATIENT, "organization_ref": "org:synthetic-home-care-001", "role": "agency_cna",
        "status": "active", "valid_from": "2026-07-30T17:00:00Z", "valid_until": "2026-07-31T01:00:00Z",
        "allowed_actions": ["perform_assigned_direct_care"], "evidence_status": "executed_local",
    }
    agency_service_grant = {
        "grant_id": "grant:synthetic-cna-direct-care-001", "patient_ref": PATIENT, "caregiver_ref": cna,
        "status": "active", "valid_from": "2026-07-30T17:00:00Z", "valid_until": "2026-07-31T01:00:00Z",
        "allowed_audiences": [direct_app], "allowed_purposes": ["shift-assignment"],
        "allowed_actions": ["perform_assigned_direct_care"], "approved_item_ids": [approved_task],
        "source_document_share_grant_id": direct_share_grant.grant_id, "evidence_status": "executed_local",
    }
    respite_assignment = {
        "assignment_id": "assignment:synthetic-respite-community-001", "caregiver_ref": respite,
        "patient_ref": PATIENT, "organization_ref": "org:synthetic-community-respite-001", "role": "respite_community_caregiver",
        "status": "active", "valid_from": "2026-07-30T16:00:00Z", "valid_until": "2026-07-30T17:00:00Z",
        "allowed_actions": ["respite_visit_support"], "evidence_status": "contract_tested",
    }
    respite_service_grant = {
        "grant_id": "grant:synthetic-respite-community-001", "patient_ref": PATIENT, "caregiver_ref": respite,
        "status": "active", "valid_from": "2026-07-30T16:00:00Z", "valid_until": "2026-07-30T17:00:00Z",
        "allowed_audiences": ["app:synthetic-respite-community"], "allowed_purposes": ["respite_visit_support"],
        "allowed_actions": ["respite_visit_support"], "approved_item_ids": [approved_task], "evidence_status": "contract_tested",
    }
    revoked_respite_service_grant = {**respite_service_grant, "status": "revoked", "revoked_at": "2026-07-30T16:45:00Z"}
    revoked_delegation = {**delegation_grant, "status": "revoked", "revoked_at": delegation_revocation["revoked_at"]}
    revoked_credential = {**credential_claim, "status": "revoked", "revoked_at": credential_revocation["revoked_at"]}

    requests = [
        _request("request:case:family-permit-001", family, "app:synthetic-scheduling", "schedule_appointments", "appointment_management", "family_delegation_v1"),
        _request("request:case:family-wrong-purpose-001", family, "app:synthetic-scheduling", "schedule_appointments", "discharge_follow_up", "family_delegation_v1"),
        _request("request:case:cna-permit-001", cna, direct_app, "perform_assigned_direct_care", "shift-assignment", "workforce_assignment_v1", item_ids=(approved_task,)),
        _request("request:case:cna-missing-claim-001", cna, direct_app, "perform_assigned_direct_care", "shift-assignment", "workforce_assignment_v1", item_ids=(approved_task,)),
        _request("request:case:respite-historical-001", respite, "app:synthetic-respite-community", "respite_visit_support", "respite_visit_support", "community_respite_v1", item_ids=(approved_task,), evidence_status="contract_tested"),
        _request("request:case:respite-expired-001", respite, "app:synthetic-respite-community", "respite_visit_support", "respite_visit_support", "community_respite_v1", item_ids=(approved_task,), evidence_status="contract_tested"),
        _request("request:case:respite-clinical-block-001", respite, "app:synthetic-respite-community", "view_warning_instruction", "respite_visit_support", "community_respite_v1", clinical_block=True, evidence_status="contract_tested"),
        _request("request:case:family-revoked-001", family, "app:synthetic-scheduling", "schedule_appointments", "appointment_management", "family_delegation_v1"),
        _request("request:case:cna-revoked-001", cna, direct_app, "perform_assigned_direct_care", "shift-assignment", "workforce_assignment_v1", item_ids=(approved_task,)),
        _request("request:case:respite-revoked-001", respite, "app:synthetic-respite-community", "respite_visit_support", "respite_visit_support", "community_respite_v1", item_ids=(approved_task,), evidence_status="contract_tested"),
    ]
    by_request = {request["request_id"]: request for request in requests}
    decisions = [
        evaluate_case_permission(by_request["request:case:family-permit-001"], relationship_claim=relationship, delegation_grant=delegation_grant, approved_items=approved_by_id, as_of=datetime(2026, 7, 30, 10, 0, tzinfo=UTC)),
        evaluate_case_permission(by_request["request:case:family-wrong-purpose-001"], relationship_claim=relationship, delegation_grant=delegation_grant, approved_items=approved_by_id, as_of=datetime(2026, 7, 30, 10, 0, tzinfo=UTC)),
        evaluate_case_permission(by_request["request:case:cna-permit-001"], credential_claim=credential_claim, assignment=agency_assignment, service_grant=agency_service_grant, approved_items=approved_by_id, as_of=AS_OF),
        evaluate_case_permission(by_request["request:case:cna-missing-claim-001"], assignment=agency_assignment, service_grant=agency_service_grant, approved_items=approved_by_id, as_of=AS_OF),
        evaluate_case_permission(by_request["request:case:respite-historical-001"], assignment=respite_assignment, service_grant=respite_service_grant, approved_items=approved_by_id, as_of=datetime(2026, 7, 30, 16, 30, tzinfo=UTC)),
        evaluate_case_permission(by_request["request:case:respite-expired-001"], assignment=respite_assignment, service_grant=respite_service_grant, approved_items=approved_by_id, as_of=AS_OF),
        evaluate_case_permission(by_request["request:case:respite-clinical-block-001"], assignment=respite_assignment, service_grant=respite_service_grant, approved_items=approved_by_id, as_of=datetime(2026, 7, 30, 16, 30, tzinfo=UTC)),
        evaluate_case_permission(by_request["request:case:family-revoked-001"], relationship_claim=relationship, delegation_grant=revoked_delegation, approved_items=approved_by_id, as_of=datetime(2026, 7, 30, 10, 6, tzinfo=UTC)),
        evaluate_case_permission(by_request["request:case:cna-revoked-001"], credential_claim=revoked_credential, assignment=agency_assignment, service_grant=agency_service_grant, approved_items=approved_by_id, as_of=datetime(2026, 7, 30, 18, 0, 11, tzinfo=UTC)),
        evaluate_case_permission(by_request["request:case:respite-revoked-001"], assignment=respite_assignment, service_grant=revoked_respite_service_grant, approved_items=approved_by_id, as_of=datetime(2026, 7, 30, 16, 46, tzinfo=UTC)),
    ]

    canonical_objects = {
        "relationship_claim": relationship, "delegation_grant": delegation_grant, "delegation_revocation": delegation_revocation,
        "credential_claim": credential_claim, "credential_revocation": credential_revocation,
        "agency_assignment": agency_assignment, "agency_service_grant": agency_service_grant,
        "respite_assignment": respite_assignment, "respite_service_grant": respite_service_grant,
        "respite_service_grant_revocation": revoked_respite_service_grant,
        "uploaded_document": _json(document), "uploaded_extraction_draft": _json(extraction),
        "uploaded_review_correction": _json(review), "approved_document_items": [_json(item) for item in approved],
        "document_share_grant": _json(document_share_grant),
        "document_share_request": _json(document_share_request),
        "document_share_decision": _json(document_share_decision),
        "direct_care_document_share_grant": _json(direct_share_grant), "direct_care_document_share_request": _json(direct_share_request),
        "direct_care_document_share_decision": _json(direct_share_decision), "document_share_revocation": _json(document_revocation),
        "post_revocation_document_share_request": _json(post_revocation_share_request),
        "post_revocation_document_share_decision": _json(post_revocation_share_decision),
        "permission_requests": requests,
        "clinical_holder_revocation_deny": _json(clinical["deny-revoked-fresh-request.json"]),
    }
    care_team = [
        {"caregiver_ref": family, "role": "patient_invited_family_caregiver", "basis_ids": [relationship["relationship_claim_id"], delegation_grant["grant_id"]], "status": "revoked_for_future_access"},
        {"caregiver_ref": cna, "role": "agency_cna", "basis_ids": [credential_claim["claim_id"], agency_assignment["assignment_id"], agency_service_grant["grant_id"]], "status": "revoked_claim"},
        {"caregiver_ref": respite, "role": "respite_community_caregiver", "basis_ids": [respite_assignment["assignment_id"], respite_service_grant["grant_id"]], "status": "expired_then_revoked"},
    ]
    history = [
        {"event_id": event.event_id, "message_type": event.message_type, "canonical_hash": event.payload_sha256, "canonical_ids": event.linked_ids, "evidence_status": event.evidence_status.value}
        for trace in (delegation_trace, credential_trace, uploaded_trace)
        for event in trace.events
    ]
    clinical_record = clinical["deny-revoked-fresh-request.json"]
    standards = [
        {"canonical_id": delegation_grant["grant_id"], "standard": "CareTrust delegation v1", "evidence_status": "executed_local"},
        {"canonical_id": credential_claim["claim_id"], "standard": "CareTrust active credential claim v1", "evidence_status": "executed_local"},
        {"canonical_id": direct_share_grant.grant_id, "standard": "CareTrust document share v1", "evidence_status": "executed_local"},
        {"canonical_id": clinical_record.decision.decision_id, "standard": "FHIR R4-shaped local holder exchange", "evidence_status": "executed_local", "non_claim": "No live EHR, HIE, or network edge was used."},
    ]
    bundle: dict[str, object] = {
        "schema_version": "caretrust.synthetic-case-bundle.v1", "case_id": "case:synthetic-multi-caregiver-001",
        "generated_at": AS_OF.isoformat().replace("+00:00", "Z"), "synthetic": True,
        "patient": {"patient_ref": PATIENT, "not_clinical_chart": True}, "caregivers": care_team,
        "policy": {
            "policy_id": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "default": "deny",
            "authority_path_requirements": {
                key: sorted(value)
                for key, value in AUTHORITY_PATH_REQUIREMENTS.items()
            },
            "temporal_semantics": {
                "valid_from": "inclusive",
                "valid_until": "exclusive; a bare date means the first instant of the following UTC day",
                "revoked_at": "effective at the stated instant",
            },
            "document_projection_rule": "approved items require a service_grant and are projected as minimum-data source assertions, never clinical truth",
            "clinical_uncertainty_rule": "unresolved clinical interpretation denies before projection",
        },
        "canonical_objects": canonical_objects,
        "applications": [
            {"application_id": "app:synthetic-scheduling", "supported_actions": ["schedule_appointments"]},
            {"application_id": direct_app, "supported_actions": ["perform_assigned_direct_care"]},
            {"application_id": "app:synthetic-respite-community", "supported_actions": ["respite_visit_support", "view_warning_instruction"]},
        ],
        "decisions": decisions,
        "projections": {
            "care_team": care_team, "permissions": decisions, "history": history,
            "applications": _application_projection(decisions),
            "evidence": [
                {"canonical_id": document.document_id, "class": "restricted_health_information", "status": "executed_local", "application_disclosure": False},
                {"canonical_id": review.review_id, "class": "accountable_review_correction", "status": "executed_local", "application_disclosure": False},
                {"canonical_id": extraction.draft_id, "class": "ai_draft_with_clinical_uncertainty", "status": "contract_tested", "application_disclosure": False},
            ],
            "standards": standards,
        },
        "limitations": [
            "Synthetic local fixtures only; no live applications, EHR, registry, or identity proofing.",
            "Application projections omit raw packets, extraction text, unrelated claims, and clinical-holder payloads.",
            "Clinical clarification is a block, not a clinical determination or authorization.",
        ],
    }
    bundle["bundle_sha256"] = canonical_sha256(bundle)
    validate_case_bundle(bundle)
    return bundle


def validate_case_bundle(bundle: dict[str, object]) -> None:
    if bundle.get("schema_version") != "caretrust.synthetic-case-bundle.v1":
        raise ValueError("unexpected case bundle schema")
    projections = bundle["projections"]
    assert isinstance(projections, dict)
    decisions = bundle["decisions"]
    canonical_objects = bundle["canonical_objects"]
    assert isinstance(decisions, list) and isinstance(canonical_objects, dict)
    requests = canonical_objects["permission_requests"]
    assert isinstance(requests, list)
    request_ids = {item["request_id"] for item in requests}
    requests_by_id = {item["request_id"]: item for item in requests}
    decision_ids = {item["decision_id"] for item in decisions}
    if len(decision_ids) != len(decisions) or {item["request_id"] for item in decisions} != request_ids:
        raise ValueError("each request must resolve to exactly one canonical decision")
    for decision in decisions:
        if decision["request_sha256"] != canonical_sha256(
            requests_by_id[decision["request_id"]]
        ):
            raise ValueError("decision request hash must bind its canonical request")
        if (
            decision["policy_id"] != POLICY_ID
            or decision["policy_version"] != POLICY_VERSION
        ):
            raise ValueError("decision must identify the executed policy")
    for app_row in projections["applications"]:
        if app_row["decision_id"] not in decision_ids or app_row["request_id"] not in request_ids:
            raise ValueError("application row must resolve to canonical request and decision")
        forbidden = {"raw_document", "raw_packet", "uploaded_extraction_draft", "supporting_canonical_ids", "clinical_holder_revocation_deny"}
        if forbidden & set(app_row):
            raise ValueError("application projection exposed a prohibited field")
    reasons = {item["reason_code"] for item in decisions}
    required = {"PURPOSE_NOT_ALLOWED", "CLAIM_REQUIRED", "CLINICAL_CLARIFICATION_REQUIRED", "ASSIGNMENT_EXPIRED", "GRANT_REVOKED", "CLAIM_REVOKED"}
    if not required <= reasons:
        raise ValueError("case lacks a required negative outcome")
    roles = {item["role"] for item in bundle["caregivers"]}
    if roles != {"patient_invited_family_caregiver", "agency_cna", "respite_community_caregiver"}:
        raise ValueError("case must have exactly the three required caregiver bases")
