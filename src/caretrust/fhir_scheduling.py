"""Bounded FHIR R4 / SMART App Launch 2.2 scheduling projection.

This is a synthetic, local projection over already-issued CareTrust decisions.
SMART scopes are transport hints only: CareTrust RAR and the deterministic
decision remain the permission source, and no FHIR server is called.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from caretrust.case_bundle import build_synthetic_case_bundle


ROOT = Path(__file__).resolve().parents[2]
APP_COMPILATION = ROOT / "fixtures" / "compiler" / "application-compilation.json"
SCHEMA_VERSION = "caretrust.fhir-smart-scheduling-projection.v1"
FHIR_R4_URLS = {
    "appointment": "https://hl7.org/fhir/R4/appointment.html",
    "appointment_response": "https://hl7.org/fhir/R4/appointmentresponse.html",
    "encounter": "https://hl7.org/fhir/R4/encounter.html",
    "schedule": "https://hl7.org/fhir/R4/schedule.html",
    "slot": "https://hl7.org/fhir/R4/slot.html",
    "smart_scopes": "https://hl7.org/fhir/smart-app-launch/STU2.2/scopes-and-launch-context.html",
}
ACTION_SCOPE_MAP = {
    "view_appointments": "patient/Appointment.rs",
    "schedule_appointments": "patient/Appointment.cu",
}
FORBIDDEN_SCOPE_MARKERS = ("*", ".d", "user/")


class FHIRSchedulingProjectionError(ValueError):
    """Raised when this deliberately narrow scheduling projection is invalid."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: object) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _load_app_compilation() -> dict[str, Any]:
    return json.loads(APP_COMPILATION.read_text(encoding="utf-8"))


def _decision_by_request(bundle: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
    decision = next(
        (item for item in bundle["decisions"] if item["request_id"] == request_id),
        None,
    )
    if decision is None:
        raise FHIRSchedulingProjectionError(f"missing canonical decision {request_id}")
    return decision


def build_fhir_scheduling_projection() -> dict[str, object]:
    """Build a deterministic scheduling transport projection from canonical sources."""

    bundle = build_synthetic_case_bundle()
    app_compilation = _load_app_compilation()
    family_permit = _decision_by_request(bundle, "request:case:family-permit-001")
    family_revoked = _decision_by_request(bundle, "request:case:family-revoked-001")
    cna_permit = _decision_by_request(bundle, "request:case:cna-permit-001")
    patient_ref = bundle["patient"]["patient_ref"]
    family_ref = family_permit["caregiver_ref"]
    cna_ref = cna_permit["caregiver_ref"]
    app_draft = app_compilation["draft"]

    projection: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "case_id": bundle["case_id"],
        "synthetic": True,
        "evidence_status": "executed_local",
        "source_metadata": {
            "official_hl7_urls": FHIR_R4_URLS,
            "case_bundle_sha256": bundle["bundle_sha256"],
            "app_compilation_sha256": _hash(app_compilation),
            "external_fhir_server_executed": False,
            "external_smart_authorization_server_executed": False,
        },
        "business_action_mapping": [
            {
                "caretrust_action": action,
                "smart_scope": scope,
                "fhir_resource": "Appointment",
                "interactions": "read/search" if action == "view_appointments" else "create/update",
                "delete_allowed": False,
                "evidence_status": "contract_tested",
            }
            for action, scope in ACTION_SCOPE_MAP.items()
        ],
        "availability": {
            "fhir_resources": ["Schedule", "Slot"],
            "smart_scope": None,
            "gateway_filter": ["organization", "service", "location"],
            "warning": (
                "Patient-compartment scopes may not safely cover organization-level availability; "
                "user scopes are broader than this projection. Apply policy/gateway filtering by organization, service, and location."
            ),
            "evidence_status": "contract_tested",
        },
        "caretrust_permission_source": {
            "source": "CareTrust RAR-shaped authorization details plus fresh deterministic decision",
            "rar_type": app_draft["proposed_rar"][0]["type"],
            "rar_profile": app_draft["proposed_profile"],
            "rar_datatypes": app_draft["proposed_rar"][0]["datatypes"],
            "smart_models_underlying_permission": False,
            "non_claim": "SMART scopes do not encode CareTrust audience, purpose, grants, assignments, status, or revocation checks.",
        },
        "capability_matrix": [
            {
                "caregiver_ref": family_ref,
                "patient_ref": patient_ref,
                "caretrust_decision_id": family_permit["decision_id"],
                "caretrust_request_id": family_permit["request_id"],
                "caretrust_decision": family_permit["decision"],
                "caretrust_action": family_permit["action"],
                "smart_scopes": ["launch/patient", ACTION_SCOPE_MAP["schedule_appointments"]],
                "capability": "schedule_appointments",
                "evidence_status": family_permit["evidence_status"],
            },
            {
                "caregiver_ref": cna_ref,
                "patient_ref": patient_ref,
                "caretrust_decision_id": cna_permit["decision_id"],
                "caretrust_request_id": cna_permit["request_id"],
                "caretrust_decision": cna_permit["decision"],
                "caretrust_action": cna_permit["action"],
                "smart_scopes": [],
                "capability": "no_scheduling_capability",
                "reason": "CareTrust permit is bounded to assigned direct care, not appointment viewing or scheduling.",
                "evidence_status": cna_permit["evidence_status"],
            },
        ],
        "fresh_revocation_check": {
            "caregiver_ref": family_ref,
            "request_id": family_revoked["request_id"],
            "decision_id": family_revoked["decision_id"],
            "decision": family_revoked["decision"],
            "reason_code": family_revoked["reason_code"],
            "smart_scopes": [],
            "fresh_request_required": True,
            "evidence_status": family_revoked["evidence_status"],
            "non_claim": "This fresh denial does not terminate a real token or external session.",
        },
        "proposed_appointment_workflow": {
            "appointment": {
                "resourceType": "Appointment",
                "id": "synthetic-proposed-appointment-001",
                "status": "proposed",
                "participant": [
                    {"actor": {"reference": "Patient/synthetic-001"}, "status": "needs-action"},
                    {"actor": {"reference": "Practitioner/synthetic-scheduler"}, "status": "needs-action"},
                ],
            },
            "appointment_response": {
                "resourceType": "AppointmentResponse",
                "id": "synthetic-proposed-appointment-response-001",
                "appointment": {"reference": "Appointment/synthetic-proposed-appointment-001"},
                "actor": {"reference": "Patient/synthetic-001"},
                "participantStatus": "tentative",
            },
            "encounter_boundary": {
                "resourceType": "Encounter",
                "included": False,
                "reason": "Appointment is administrative planning; Encounter is a clinical event and is not created or read by this scheduling profile.",
            },
            "evidence_status": "contract_tested",
        },
        "non_claims": [
            "No external FHIR R4 server, SMART authorization server, or independent FHIR validator was executed.",
            "This projection does not claim SMART App Launch conformance or a live appointment workflow.",
            "No delete scope, wildcard scope, or user scope is requested or granted.",
        ],
    }
    projection["projection_sha256"] = _hash(projection)
    validate_fhir_scheduling_projection(projection)
    return projection


def validate_fhir_scheduling_projection(projection: Mapping[str, Any]) -> None:
    """Validate the bounded local profile without asserting HL7 conformance."""

    if projection.get("schema_version") != SCHEMA_VERSION or projection.get("synthetic") is not True:
        raise FHIRSchedulingProjectionError("unexpected scheduling projection identity")
    bound = dict(projection)
    digest = bound.pop("projection_sha256", None)
    if digest != _hash(bound):
        raise FHIRSchedulingProjectionError("projection hash does not bind payload")
    mapping = {item["caretrust_action"]: item for item in projection["business_action_mapping"]}
    for action, scope in ACTION_SCOPE_MAP.items():
        item = mapping.get(action)
        if item is None or item.get("smart_scope") != scope or item.get("delete_allowed") is not False:
            raise FHIRSchedulingProjectionError("business action mapping is not least-privilege")
    scopes = [
        scope
        for row in projection["capability_matrix"]
        for scope in row["smart_scopes"]
    ]
    if any(_forbidden_scope(scope) for scope in scopes):
        raise FHIRSchedulingProjectionError("wildcard, delete, or user SMART scope is forbidden")
    if projection["availability"].get("smart_scope") is not None or projection["availability"].get("gateway_filter") != ["organization", "service", "location"]:
        raise FHIRSchedulingProjectionError("availability must use explicit gateway filtering")
    if projection["caretrust_permission_source"].get("smart_models_underlying_permission") is not False:
        raise FHIRSchedulingProjectionError("SMART cannot be the underlying CareTrust permission source")
    matrix = projection["capability_matrix"]
    if len(matrix) != 2 or matrix[0]["smart_scopes"] == matrix[1]["smart_scopes"]:
        raise FHIRSchedulingProjectionError("two caregivers must have different scheduling capabilities")
    revoked = projection["fresh_revocation_check"]
    if revoked.get("decision") != "deny" or revoked.get("reason_code") != "GRANT_REVOKED" or revoked.get("smart_scopes"):
        raise FHIRSchedulingProjectionError("post-revocation fresh request must deny without scopes")
    workflow = projection["proposed_appointment_workflow"]
    if workflow["appointment"].get("status") != "proposed" or workflow["appointment_response"].get("participantStatus") != "tentative":
        raise FHIRSchedulingProjectionError("proposed appointment workflow is incomplete")
    if workflow["encounter_boundary"].get("included") is not False:
        raise FHIRSchedulingProjectionError("Encounter must remain outside scheduling projection")
    metadata = projection["source_metadata"]
    if metadata.get("external_fhir_server_executed") or metadata.get("external_smart_authorization_server_executed"):
        raise FHIRSchedulingProjectionError("external execution is not supported by this projection")
    if set(metadata["official_hl7_urls"]) != set(FHIR_R4_URLS) or any(not value.startswith("https://hl7.org/") for value in metadata["official_hl7_urls"].values()):
        raise FHIRSchedulingProjectionError("source metadata must cite official HL7 URLs only")


def _forbidden_scope(scope: str) -> bool:
    if any(marker in scope for marker in FORBIDDEN_SCOPE_MARKERS):
        return True
    if "." not in scope:
        return False
    interactions = scope.rsplit(".", 1)[1].split("?", 1)[0]
    return "d" in interactions
