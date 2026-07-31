"""Tests for the bounded synthetic FHIR R4 / SMART scheduling projection."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from caretrust.fhir_scheduling import (
    FHIRSchedulingProjectionError,
    build_fhir_scheduling_projection,
    validate_fhir_scheduling_projection,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "validation" / "fhir-smart-scheduling-projection.json"


def _rehash(projection: dict[str, object]) -> None:
    from caretrust.fhir_scheduling import _hash

    source = dict(projection)
    source.pop("projection_sha256")
    projection["projection_sha256"] = _hash(source)


def test_artifact_reproduces_and_uses_only_official_hl7_metadata() -> None:
    built = build_fhir_scheduling_projection()
    assert json.loads(ARTIFACT.read_text(encoding="utf-8")) == built
    assert all(url.startswith("https://hl7.org/") for url in built["source_metadata"]["official_hl7_urls"].values())


def test_business_actions_and_scopes_are_least_privilege() -> None:
    projection = build_fhir_scheduling_projection()
    mappings = {row["caretrust_action"]: row["smart_scope"] for row in projection["business_action_mapping"]}
    assert mappings == {
        "view_appointments": "patient/Appointment.rs",
        "schedule_appointments": "patient/Appointment.cu",
    }
    scopes = [scope for row in projection["capability_matrix"] for scope in row["smart_scopes"]]
    assert all("*" not in scope and ".d" not in scope and not scope.startswith("user/") for scope in scopes)
    assert projection["availability"]["smart_scope"] is None
    assert projection["availability"]["gateway_filter"] == ["organization", "service", "location"]


def test_caregivers_differ_and_revoked_fresh_request_has_no_scope() -> None:
    projection = build_fhir_scheduling_projection()
    family, cna = projection["capability_matrix"]
    assert family["capability"] == "schedule_appointments"
    assert family["smart_scopes"] == ["launch/patient", "patient/Appointment.cu"]
    assert cna["capability"] == "no_scheduling_capability"
    assert cna["smart_scopes"] == []
    assert projection["fresh_revocation_check"]["decision"] == "deny"
    assert projection["fresh_revocation_check"]["reason_code"] == "GRANT_REVOKED"
    assert projection["fresh_revocation_check"]["smart_scopes"] == []


def test_caretrust_rar_remains_underlying_permission_source() -> None:
    projection = build_fhir_scheduling_projection()
    source = projection["caretrust_permission_source"]
    assert source["smart_models_underlying_permission"] is False
    assert source["rar_type"]
    assert source["rar_profile"]


def test_validator_rejects_delete_wildcard_user_scope_and_encounter() -> None:
    for invalid_scope in ("patient/Appointment.cud", "patient/*.rs", "user/Appointment.cruds"):
        projection = copy.deepcopy(build_fhir_scheduling_projection())
        projection["capability_matrix"][0]["smart_scopes"] = [invalid_scope]
        _rehash(projection)
        with pytest.raises(FHIRSchedulingProjectionError):
            validate_fhir_scheduling_projection(projection)
    projection = copy.deepcopy(build_fhir_scheduling_projection())
    projection["proposed_appointment_workflow"]["encounter_boundary"]["included"] = True
    _rehash(projection)
    with pytest.raises(FHIRSchedulingProjectionError):
        validate_fhir_scheduling_projection(projection)
