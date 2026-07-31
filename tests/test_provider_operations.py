from datetime import UTC, datetime

import pytest

from caretrust.provider_operations import (
    AppDecision,
    ApprovalStatus,
    ProviderStage,
    ProviderWorkflow,
    WorkflowConflict,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


@pytest.fixture
def workflow() -> ProviderWorkflow:
    return ProviderWorkflow(clock=lambda: NOW)


def _reviewed(workflow: ProviderWorkflow):
    session = workflow.create_demo_session()
    session = workflow.compile_referral(
        session.session_id, expected_version=session.version
    )
    return workflow.review_draft(
        session.session_id,
        reviewer_ref="user:coordinator",
        corrections={"service.schedule": "Wednesdays, 1:00–5:00 PM"},
        resolved_items={"visit_end": "5:00 PM"},
        expected_version=session.version,
    )


def _assigned(workflow: ProviderWorkflow):
    session = _reviewed(workflow)
    session = workflow.record_patient_approval(
        session.session_id,
        patient_ref="patient:malia",
        approved=True,
        expected_version=session.version,
    )
    return workflow.assign_worker(
        session.session_id,
        worker_id="worker:synthetic-kai-n",
        supervisor_ref="user:supervisor",
        expected_version=session.version,
    )


def test_ai_draft_is_cited_and_requires_human_review(workflow: ProviderWorkflow):
    session = workflow.create_demo_session()
    session = workflow.compile_referral(session.session_id)

    assert session.stage is ProviderStage.REVIEW_DRAFT
    assert len(session.facts) == 8
    assert all(fact.quote and fact.source_ref for fact in session.facts)
    assert any(fact.needs_review for fact in session.facts)
    assert session.metrics.fields_prefilled == 8
    assert session.metrics.human_approvals_remaining == 3


def test_review_resolves_exception_without_granting_access(workflow: ProviderWorkflow):
    session = _reviewed(workflow)

    assert session.stage is ProviderStage.PATIENT_APPROVAL
    assert session.patient_approval is ApprovalStatus.PENDING
    assert session.metrics.fields_corrected == 1
    assert all(
        app.decision is AppDecision.NOT_REQUESTED
        for app in session.app_projections
    )


def test_ineligible_worker_cannot_be_assigned(workflow: ProviderWorkflow):
    session = _reviewed(workflow)
    session = workflow.record_patient_approval(
        session.session_id, patient_ref="patient:malia", approved=True
    )

    with pytest.raises(WorkflowConflict, match="eligibility"):
        workflow.assign_worker(
            session.session_id,
            worker_id="worker:synthetic-noa-p",
            supervisor_ref="user:supervisor",
        )


def test_two_apps_receive_disjoint_minimum_projections(workflow: ProviderWorkflow):
    session = _assigned(workflow)
    for app_id in ("app:synthetic-scheduler", "app:synthetic-field-client"):
        session = workflow.request_app_access(
            session.session_id,
            app_id=app_id,
            expected_version=session.version,
        )

    scheduler, field_client = session.app_projections
    assert session.stage is ProviderStage.ACTIVE
    assert scheduler.decision is AppDecision.ALLOW
    assert field_client.decision is AppDecision.ALLOW
    assert "start_date" in scheduler.data
    assert "start_date" not in field_client.data
    assert "first_visit_task" in field_client.data
    assert "first_visit_task" not in scheduler.data
    assert "source document" in scheduler.excluded
    assert session.metrics.duplicate_app_entries_avoided == (
        len(scheduler.data) + len(field_client.data)
    )


def test_revocation_denies_every_fresh_app_request(workflow: ProviderWorkflow):
    session = _assigned(workflow)
    session = workflow.request_app_access(
        session.session_id, app_id="app:synthetic-scheduler"
    )
    session = workflow.revoke_assignment(
        session.session_id,
        actor_ref="user:supervisor",
        reason="Worker is no longer assigned",
    )
    session = workflow.request_app_access(
        session.session_id, app_id="app:synthetic-scheduler"
    )

    assert session.stage is ProviderStage.REVOKED
    assert session.app_projections[0].decision is AppDecision.DENY
    assert session.app_projections[0].data == {}


def test_expected_version_prevents_lost_updates(workflow: ProviderWorkflow):
    session = workflow.create_demo_session()
    with pytest.raises(WorkflowConflict, match="version conflict"):
        workflow.compile_referral(
            session.session_id, expected_version=session.version + 1
        )
