from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from caretrust.navigator import (
    HistoryRecordState,
    NavigatorGrantState,
    NavigatorProjectionError,
    PatientNavigatorProjection,
    PermissionEffect,
    project_patient_navigator,
)
from caretrust.trace import TraceBundle, sha256_json
from scripts.build_synthetic_patient_navigator import build_trace

ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = (
    ROOT / "fixtures" / "delegation" / "synthetic-patient-navigator-trace.json"
)
PROJECTION_PATH = (
    ROOT / "artifacts" / "validation" / "synthetic-patient-navigator.json"
)
SCHEMA_PATH = ROOT / "schemas" / "patient-navigator-projection.schema.json"
PATIENT_REF = "patient:synthetic-001"


def load_trace() -> TraceBundle:
    return TraceBundle.model_validate_json(TRACE_PATH.read_text(encoding="utf-8"))


def load_projection() -> PatientNavigatorProjection:
    return PatientNavigatorProjection.model_validate_json(
        PROJECTION_PATH.read_text(encoding="utf-8")
    )


def test_generated_fixture_and_projection_are_deterministic() -> None:
    built_trace = build_trace()
    retained_trace = load_trace()
    assert built_trace == retained_trace

    projected = project_patient_navigator(
        retained_trace,
        patient_ref=PATIENT_REF,
    )
    assert projected == load_projection()
    assert projected.metadata.source_trace_sha256 == sha256_json(retained_trace)


def test_projection_is_explicitly_not_a_clinical_chart() -> None:
    projection = load_projection()
    assert projection.metadata.not_clinical_chart is True
    assert projection.metadata.clinical_chart_status == "not_a_clinical_chart"
    assert projection.metadata.synthetic_only is True
    limitations = " ".join(projection.metadata.limitations).lower()
    assert "not a clinical chart" in limitations
    assert "not authoritative" in limitations

    schema_text = SCHEMA_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (
        '"diagnosis"',
        '"medication"',
        '"observation"',
        '"clinical_note"',
    ):
        assert forbidden not in schema_text


def test_care_team_preserves_relationship_and_revoked_grant_separately() -> None:
    projection = load_projection()
    assert len(projection.care_team_rows) == 1
    row = projection.care_team_rows[0]
    assert row.patient_ref == PATIENT_REF
    assert row.caregiver_ref == "account:synthetic-leilani"
    assert row.relationship_claim_id == "relationship:synthetic-001"
    assert row.relationship_status.value == "active"
    assert row.relationship_code == "child"
    assert row.legal_authority_status == "not_established"

    assert len(row.grant_history) == 1
    grant = row.grant_history[0]
    assert grant.grant_id == "grant:synthetic-001"
    assert grant.state is NavigatorGrantState.REVOKED
    assert grant.was_ever_active is True
    assert grant.revocation_id == "delegation-revocation:synthetic-001"
    assert grant.revocation_event_id == "event:navigator:revocation:001"


def test_permission_matrix_shows_roles_purposes_exclusions_and_revocation() -> None:
    projection = load_projection()
    rows = projection.permission_matrix_rows
    assert len(rows) == 4

    allowed = [row for row in rows if row.effect is PermissionEffect.ALLOW]
    excluded = [row for row in rows if row.effect is PermissionEffect.EXCLUDE]
    assert {(row.action, row.resource.value) for row in allowed} == {
        ("schedule_appointments", "appointments"),
        ("view_visit_instructions", "visit_instructions"),
    }
    assert {row.resource.value for row in excluded} == {
        "billing",
        "mental_health_records",
    }
    assert all(row.action is None for row in excluded)
    assert all(row.grant_state is NavigatorGrantState.REVOKED for row in rows)
    assert all(row.currently_effective is False for row in rows)

    for row in rows:
        assert row.audiences == (
            "app:synthetic-scheduling",
            "app:synthetic-care-portal",
        )
        assert row.purposes == (
            "appointment_management",
            "care_coordination",
        )
        assert {item.kind.value for item in row.role_evidence} == {
            "role",
            "approval",
        }
        assert {item.value for item in row.purpose_evidence} == {
            "appointment_management",
            "care_coordination",
        }
        assert "event:navigator:relationship:001" in row.source_event_ids
        assert "event:navigator:approval:001" in row.source_event_ids
        assert "event:navigator:grant:001" in row.source_event_ids
        assert "event:navigator:revocation:001" in row.source_event_ids


def test_case_history_is_ordered_append_only_and_preserves_supersession() -> None:
    projection = load_projection()
    history = projection.case_history_rows
    assert [row.trace_sequence for row in history] == list(range(1, 16))
    assert tuple(row.source_event_id for row in history) == (
        projection.metadata.source_event_ids
    )

    original = next(
        row
        for row in history
        if row.source_event_id == "event:navigator:draft:001"
    )
    correction = next(
        row
        for row in history
        if row.source_event_id == "event:navigator:draft:002"
    )
    assert original.record_state is HistoryRecordState.SUPERSEDED
    assert original.superseded_by_event_id == correction.source_event_id
    assert correction.record_state is HistoryRecordState.CURRENT
    assert correction.supersedes_event_id == original.source_event_id
    assert original.source_payload_sha256 != correction.source_payload_sha256
    assert original.summary_code == "delegation_draft_blocked"
    assert correction.summary_code == "delegation_draft_ready_for_review"

    assert history[-3].summary_code == "delegation_revoked"
    assert history[-1].summary_code == "authorization_deny"


def test_row_ids_and_source_hashes_are_stable_and_trace_bound() -> None:
    trace = load_trace()
    first = project_patient_navigator(trace, patient_ref=PATIENT_REF)
    second = project_patient_navigator(trace, patient_ref=PATIENT_REF)
    assert first == second

    events = {event.event_id: event for event in trace.events}
    for row in first.case_history_rows:
        assert row.source_payload_sha256 == events[row.source_event_id].payload_sha256
    for row in first.care_team_rows:
        assert set(row.source_payload_sha256s) == {
            events[event_id].payload_sha256
            for event_id in row.source_event_ids
        }
    for row in first.permission_matrix_rows:
        assert set(row.source_payload_sha256s) == {
            events[event_id].payload_sha256
            for event_id in row.source_event_ids
        }


def test_as_of_projection_uses_only_then_visible_events() -> None:
    trace = load_trace()
    before_revocation = project_patient_navigator(
        trace,
        patient_ref=PATIENT_REF,
        as_of=datetime(2026, 7, 30, 10, 4, 1, tzinfo=UTC),
    )
    assert len(before_revocation.case_history_rows) == 12
    assert all(
        row.grant_state is NavigatorGrantState.ACTIVE
        for row in before_revocation.permission_matrix_rows
    )
    assert all(
        row.currently_effective
        for row in before_revocation.permission_matrix_rows
        if row.effect is PermissionEffect.ALLOW
    )
    assert all(
        not row.currently_effective
        for row in before_revocation.permission_matrix_rows
        if row.effect is PermissionEffect.EXCLUDE
    )

    care_row = before_revocation.care_team_rows[0]
    assert care_row.relationship_status.value == "active"
    assert care_row.grant_history[0].state is NavigatorGrantState.ACTIVE
    assert care_row.grant_history[0].revocation_event_id is None


def test_projection_rejects_invalid_recognized_domain_payload() -> None:
    trace_data = load_trace().model_dump(mode="json")
    draft = next(
        event
        for event in trace_data["events"]
        if event["event_id"] == "event:navigator:draft:002"
    )
    draft["payload"]["status"] = "active"
    draft["payload_sha256"] = sha256_json(draft["payload"])
    trace = TraceBundle.model_validate(trace_data)
    with pytest.raises(NavigatorProjectionError, match="invalid DelegationDraft"):
        project_patient_navigator(trace, patient_ref=PATIENT_REF)


def test_projection_rejects_broken_supersession_links() -> None:
    trace_data = load_trace().model_dump(mode="json")
    correction = next(
        event
        for event in trace_data["events"]
        if event["event_id"] == "event:navigator:draft:002"
    )
    correction["linked_ids"]["supersedes_event_id"] = "event:missing"
    trace = TraceBundle.model_validate(trace_data)
    with pytest.raises(NavigatorProjectionError, match="supersedes missing event"):
        project_patient_navigator(trace, patient_ref=PATIENT_REF)


def test_projection_rejects_cross_patient_trace_mixing() -> None:
    trace_data = load_trace().model_dump(mode="json")
    request = next(
        event
        for event in trace_data["events"]
        if event["event_id"] == "event:navigator:request:002"
    )
    request["payload"]["patient_ref"] = "patient:synthetic-other"
    request["payload_sha256"] = sha256_json(request["payload"])
    trace = TraceBundle.model_validate(trace_data)
    with pytest.raises(NavigatorProjectionError, match="must not mix"):
        project_patient_navigator(trace, patient_ref=PATIENT_REF)


def test_projection_schema_equals_exported_runtime_contract() -> None:
    exported = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    runtime = PatientNavigatorProjection.model_json_schema(
        mode="validation",
        ref_template="#/$defs/{model}",
    )
    assert exported == runtime


def test_projection_contains_pointers_not_authoritative_payload_copies() -> None:
    schema = PatientNavigatorProjection.model_json_schema(mode="validation")
    serialized = json.dumps(schema)
    assert '"source_event_id"' in serialized
    assert '"source_payload_sha256"' in serialized
    assert '"payload"' not in serialized
    assert '"not_clinical_chart"' in serialized
