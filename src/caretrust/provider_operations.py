"""Operational provider workflow for the CareTrust Track 2 prototype.

The module is deliberately domain-first: a UI, an HTTP adapter, or a future
durable store can drive the same deterministic transitions.  AI may propose
evidence-linked facts and worker explanations, but only people approve facts,
consent, and assignments.  App projections are produced by deterministic
minimum-necessary policy.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import Field, model_validator

from caretrust.models import StrictModel


class WorkflowConflict(ValueError):
    """Raised when a command is invalid for the current workflow state."""


class ProviderStage(StrEnum):
    INTAKE = "intake"
    REVIEW_DRAFT = "review_draft"
    PATIENT_APPROVAL = "patient_approval"
    WORKER_ASSIGNMENT = "worker_assignment"
    APP_ROUTING = "app_routing"
    ACTIVE = "active"
    REVOKED = "revoked"


class ApprovalStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


class AppDecision(StrEnum):
    NOT_REQUESTED = "not_requested"
    ALLOW = "allow"
    DENY = "deny"


class EvidenceFact(StrictModel):
    field_path: str
    label: str
    proposed_value: str
    confidence: float = Field(ge=0, le=1)
    source_ref: str
    quote: str
    needs_review: bool = False
    reviewed_value: str | None = None
    reviewed_by: str | None = None


class MissingItem(StrictModel):
    item_id: str
    label: str
    resolution: str | None = None
    resolved_by: str | None = None


class WorkerCandidate(StrictModel):
    worker_id: str
    display_name: str
    role: str
    qualifications: tuple[str, ...]
    availability: str
    eligible: bool
    deterministic_checks: tuple[str, ...]
    ai_explanation: str


class Assignment(StrictModel):
    worker_id: str
    worker_name: str
    assigned_by: str
    assigned_at: datetime
    status: str = "active"


class AppProjection(StrictModel):
    app_id: str
    app_name: str
    purpose: str
    decision: AppDecision = AppDecision.NOT_REQUESTED
    reason: str = "Awaiting a fresh access request."
    data: dict[str, Any] = Field(default_factory=dict)
    excluded: tuple[str, ...] = ()
    decided_at: datetime | None = None


class WorkflowEvent(StrictModel):
    event_id: str
    occurred_at: datetime
    actor_type: str
    actor_ref: str
    action: str
    summary: str
    stage: ProviderStage


class WorkloadMetrics(StrictModel):
    source_fields_detected: int = 0
    fields_prefilled: int = 0
    fields_requiring_correction: int = 0
    fields_corrected: int = 0
    follow_up_items_open: int = 0
    duplicate_app_entries_avoided: int = 0
    app_packages_generated: int = 0
    human_approvals_remaining: int = 3


class ProviderSession(StrictModel):
    session_id: str
    version: int = 1
    stage: ProviderStage = ProviderStage.INTAKE
    case_id: str
    case_display: str
    organization: str
    referral_text: str
    referral_source: str
    facts: tuple[EvidenceFact, ...] = ()
    missing_items: tuple[MissingItem, ...] = ()
    patient_approval: ApprovalStatus = ApprovalStatus.NOT_REQUESTED
    patient_approval_scope: tuple[str, ...] = ()
    worker_candidates: tuple[WorkerCandidate, ...] = ()
    assignment: Assignment | None = None
    app_projections: tuple[AppProjection, ...] = ()
    events: tuple[WorkflowEvent, ...] = ()
    metrics: WorkloadMetrics = Field(default_factory=WorkloadMetrics)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_stage_dependencies(self) -> "ProviderSession":
        if self.stage in {
            ProviderStage.WORKER_ASSIGNMENT,
            ProviderStage.APP_ROUTING,
            ProviderStage.ACTIVE,
        } and self.patient_approval is not ApprovalStatus.APPROVED:
            raise ValueError("patient approval is required before worker assignment")
        if self.stage in {ProviderStage.APP_ROUTING, ProviderStage.ACTIVE} and not self.assignment:
            raise ValueError("an assignment is required before app routing")
        return self


class ProviderWorkflow:
    """In-memory command service with optimistic-version checks."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sessions: dict[str, ProviderSession] = {}

    def create_demo_session(self) -> ProviderSession:
        now = self._now()
        session_id = f"provider-session:{uuid4()}"
        session = ProviderSession(
            session_id=session_id,
            case_id="case:synthetic-malia-k",
            case_display="Malia K. · respite support referral",
            organization="Kūpuna Care Coordination Network (synthetic)",
            referral_source="Synthetic hospital transition note",
            referral_text=(
                "Malia K. needs in-home respite support beginning August 5, 2026, "
                "preferably Wednesday afternoons in East Honolulu. Her daughter "
                "Leilani is helping coordinate. English is spoken; a caregiver "
                "with local cultural knowledge is preferred. Please bring the "
                "printed transition packet to the first visit. The note does not "
                "state the visit end time or include Malia's approval to share."
            ),
            app_projections=_initial_app_projections(),
            events=(
                self._event(
                    now,
                    actor_type="system",
                    actor_ref="caretrust",
                    action="referral_received",
                    summary="Synthetic referral entered the provider work queue.",
                    stage=ProviderStage.INTAKE,
                ),
            ),
            metrics=WorkloadMetrics(human_approvals_remaining=3),
            created_at=now,
            updated_at=now,
        )
        self._sessions[session_id] = session
        return deepcopy(session)

    def get(self, session_id: str) -> ProviderSession:
        try:
            return deepcopy(self._sessions[session_id])
        except KeyError as exc:
            raise KeyError(f"unknown provider session: {session_id}") from exc

    def compile_referral(
        self, session_id: str, *, expected_version: int | None = None
    ) -> ProviderSession:
        session = self._require(session_id, ProviderStage.INTAKE, expected_version)
        now = self._now()
        facts = _reference_ai_facts()
        missing = (
            MissingItem(item_id="visit_end", label="Confirm requested visit end time"),
            MissingItem(
                item_id="patient_approval",
                label="Obtain Malia's approval for the proposed sharing scope",
            ),
        )
        metrics = session.metrics.model_copy(
            update={
                "source_fields_detected": len(facts),
                "fields_prefilled": len(facts),
                "fields_requiring_correction": sum(fact.needs_review for fact in facts),
                "follow_up_items_open": len(missing),
                "human_approvals_remaining": 3,
            }
        )
        updated = session.model_copy(
            update={
                "version": session.version + 1,
                "stage": ProviderStage.REVIEW_DRAFT,
                "facts": facts,
                "missing_items": missing,
                "metrics": metrics,
                "updated_at": now,
                "events": session.events
                + (
                    self._event(
                        now,
                        actor_type="ai",
                        actor_ref="caretrust-intake-compiler",
                        action="draft_compiled",
                        summary=(
                            f"Proposed {len(facts)} cited fields and routed "
                            f"{len(missing)} exceptions to a person."
                        ),
                        stage=ProviderStage.REVIEW_DRAFT,
                    ),
                ),
            }
        )
        return self._save(updated)

    def review_draft(
        self,
        session_id: str,
        *,
        reviewer_ref: str,
        corrections: Mapping[str, str] | None = None,
        resolved_items: Mapping[str, str] | None = None,
        expected_version: int | None = None,
    ) -> ProviderSession:
        session = self._require(
            session_id, ProviderStage.REVIEW_DRAFT, expected_version
        )
        corrections = corrections or {}
        resolved_items = resolved_items or {}
        known_fields = {fact.field_path for fact in session.facts}
        unknown = set(corrections) - known_fields
        if unknown:
            raise WorkflowConflict(f"unknown correction fields: {sorted(unknown)}")

        reviewed_facts = tuple(
            fact.model_copy(
                update={
                    "reviewed_value": corrections.get(
                        fact.field_path, fact.proposed_value
                    ),
                    "reviewed_by": reviewer_ref,
                }
            )
            for fact in session.facts
        )
        reviewed_missing = tuple(
            item.model_copy(
                update={
                    "resolution": resolved_items.get(item.item_id),
                    "resolved_by": (
                        reviewer_ref if item.item_id in resolved_items else None
                    ),
                }
            )
            for item in session.missing_items
        )
        unresolved_nonapproval = [
            item
            for item in reviewed_missing
            if item.item_id != "patient_approval" and not item.resolution
        ]
        if unresolved_nonapproval:
            raise WorkflowConflict(
                "resolve required referral details before requesting approval"
            )

        now = self._now()
        corrected_count = sum(
            fact.field_path in corrections
            and corrections[fact.field_path] != fact.proposed_value
            for fact in session.facts
        )
        metrics = session.metrics.model_copy(
            update={
                "fields_corrected": corrected_count,
                "follow_up_items_open": sum(
                    item.resolution is None for item in reviewed_missing
                ),
                "human_approvals_remaining": 2,
            }
        )
        updated = session.model_copy(
            update={
                "version": session.version + 1,
                "stage": ProviderStage.PATIENT_APPROVAL,
                "facts": reviewed_facts,
                "missing_items": reviewed_missing,
                "patient_approval": ApprovalStatus.PENDING,
                "metrics": metrics,
                "updated_at": now,
                "events": session.events
                + (
                    self._event(
                        now,
                        actor_type="human",
                        actor_ref=reviewer_ref,
                        action="draft_reviewed",
                        summary=(
                            f"Coordinator reviewed {len(reviewed_facts)} fields, "
                            f"changed {corrected_count}, and requested patient approval."
                        ),
                        stage=ProviderStage.PATIENT_APPROVAL,
                    ),
                ),
            }
        )
        return self._save(updated)

    def record_patient_approval(
        self,
        session_id: str,
        *,
        patient_ref: str,
        approved: bool,
        expected_version: int | None = None,
    ) -> ProviderSession:
        session = self._require(
            session_id, ProviderStage.PATIENT_APPROVAL, expected_version
        )
        now = self._now()
        if not approved:
            updated = session.model_copy(
                update={
                    "version": session.version + 1,
                    "patient_approval": ApprovalStatus.DECLINED,
                    "updated_at": now,
                    "events": session.events
                    + (
                        self._event(
                            now,
                            actor_type="patient",
                            actor_ref=patient_ref,
                            action="sharing_declined",
                            summary="Patient declined the proposed sharing scope.",
                            stage=ProviderStage.PATIENT_APPROVAL,
                        ),
                    ),
                }
            )
            return self._save(updated)

        approval_scope = (
            "coordinate-respite-visit",
            "share-schedule-with-assigned-worker",
            "share-approved-preparation-tasks",
        )
        missing = tuple(
            item.model_copy(
                update={
                    "resolution": (
                        "Approved in patient confirmation flow"
                        if item.item_id == "patient_approval"
                        else item.resolution
                    ),
                    "resolved_by": (
                        patient_ref
                        if item.item_id == "patient_approval"
                        else item.resolved_by
                    ),
                }
            )
            for item in session.missing_items
        )
        metrics = session.metrics.model_copy(
            update={
                "follow_up_items_open": 0,
                "human_approvals_remaining": 1,
            }
        )
        updated = session.model_copy(
            update={
                "version": session.version + 1,
                "stage": ProviderStage.WORKER_ASSIGNMENT,
                "patient_approval": ApprovalStatus.APPROVED,
                "patient_approval_scope": approval_scope,
                "worker_candidates": _worker_candidates(),
                "missing_items": missing,
                "metrics": metrics,
                "updated_at": now,
                "events": session.events
                + (
                    self._event(
                        now,
                        actor_type="patient",
                        actor_ref=patient_ref,
                        action="sharing_approved",
                        summary=(
                            "Patient approved three bounded purposes; policy generated "
                            "an eligible worker shortlist."
                        ),
                        stage=ProviderStage.WORKER_ASSIGNMENT,
                    ),
                ),
            }
        )
        return self._save(updated)

    def assign_worker(
        self,
        session_id: str,
        *,
        worker_id: str,
        supervisor_ref: str,
        expected_version: int | None = None,
    ) -> ProviderSession:
        session = self._require(
            session_id, ProviderStage.WORKER_ASSIGNMENT, expected_version
        )
        candidate = next(
            (item for item in session.worker_candidates if item.worker_id == worker_id),
            None,
        )
        if candidate is None:
            raise WorkflowConflict("worker is not in the reviewed candidate set")
        if not candidate.eligible:
            raise WorkflowConflict("worker failed deterministic eligibility checks")

        now = self._now()
        assignment = Assignment(
            worker_id=candidate.worker_id,
            worker_name=candidate.display_name,
            assigned_by=supervisor_ref,
            assigned_at=now,
        )
        metrics = session.metrics.model_copy(
            update={"human_approvals_remaining": 0}
        )
        updated = session.model_copy(
            update={
                "version": session.version + 1,
                "stage": ProviderStage.APP_ROUTING,
                "assignment": assignment,
                "metrics": metrics,
                "updated_at": now,
                "events": session.events
                + (
                    self._event(
                        now,
                        actor_type="human",
                        actor_ref=supervisor_ref,
                        action="worker_assigned",
                        summary=(
                            f"Supervisor assigned {candidate.display_name}; AI explanation "
                            "did not control eligibility or assignment."
                        ),
                        stage=ProviderStage.APP_ROUTING,
                    ),
                ),
            }
        )
        return self._save(updated)

    def request_app_access(
        self,
        session_id: str,
        *,
        app_id: str,
        expected_version: int | None = None,
    ) -> ProviderSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"unknown provider session: {session_id}")
        self._check_version(session, expected_version)
        if session.stage not in {
            ProviderStage.APP_ROUTING,
            ProviderStage.ACTIVE,
            ProviderStage.REVOKED,
        }:
            raise WorkflowConflict("app access requires an approved assignment")
        app = next(
            (item for item in session.app_projections if item.app_id == app_id), None
        )
        if app is None:
            raise WorkflowConflict("unknown application")

        now = self._now()
        if session.stage is ProviderStage.REVOKED or not session.assignment:
            decided = app.model_copy(
                update={
                    "decision": AppDecision.DENY,
                    "reason": "Fresh request denied: the assignment is revoked.",
                    "data": {},
                    "decided_at": now,
                }
            )
            action = "app_access_denied"
            summary = f"{app.app_name} received deny after revocation."
        else:
            decided = _allow_projection(app, session, now)
            action = "app_access_allowed"
            summary = (
                f"{app.app_name} received {len(decided.data)} purpose-limited fields; "
                f"{len(decided.excluded)} sensitive categories were excluded."
            )

        projections = tuple(
            decided if item.app_id == app_id else item
            for item in session.app_projections
        )
        allowed_count = sum(
            item.decision is AppDecision.ALLOW for item in projections
        )
        metrics = session.metrics.model_copy(
            update={
                "app_packages_generated": allowed_count,
                # Each package contains independently mapped values that the
                # reference benchmark would otherwise re-enter by hand.
                "duplicate_app_entries_avoided": sum(
                    len(item.data)
                    for item in projections
                    if item.decision is AppDecision.ALLOW
                ),
            }
        )
        updated = session.model_copy(
            update={
                "version": session.version + 1,
                "stage": (
                    ProviderStage.ACTIVE
                    if allowed_count == len(projections)
                    else session.stage
                ),
                "app_projections": projections,
                "metrics": metrics,
                "updated_at": now,
                "events": session.events
                + (
                    self._event(
                        now,
                        actor_type="policy",
                        actor_ref="caretrust-policy-engine",
                        action=action,
                        summary=summary,
                        stage=(
                            ProviderStage.REVOKED
                            if session.stage is ProviderStage.REVOKED
                            else (
                                ProviderStage.ACTIVE
                                if allowed_count == len(projections)
                                else session.stage
                            )
                        ),
                    ),
                ),
            }
        )
        return self._save(updated)

    def revoke_assignment(
        self,
        session_id: str,
        *,
        actor_ref: str,
        reason: str,
        expected_version: int | None = None,
    ) -> ProviderSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"unknown provider session: {session_id}")
        self._check_version(session, expected_version)
        if not session.assignment or session.stage is ProviderStage.REVOKED:
            raise WorkflowConflict("there is no active assignment to revoke")
        if not reason.strip():
            raise WorkflowConflict("a revocation reason is required")
        now = self._now()
        assignment = session.assignment.model_copy(update={"status": "revoked"})
        reset_apps = tuple(
            app.model_copy(
                update={
                    "decision": AppDecision.NOT_REQUESTED,
                    "reason": "Assignment revoked; a fresh request will be denied.",
                    "data": {},
                    "decided_at": None,
                }
            )
            for app in session.app_projections
        )
        updated = session.model_copy(
            update={
                "version": session.version + 1,
                "stage": ProviderStage.REVOKED,
                "assignment": assignment,
                "app_projections": reset_apps,
                "metrics": session.metrics.model_copy(
                    update={
                        "app_packages_generated": 0,
                        "duplicate_app_entries_avoided": 0,
                    }
                ),
                "updated_at": now,
                "events": session.events
                + (
                    self._event(
                        now,
                        actor_type="human",
                        actor_ref=actor_ref,
                        action="assignment_revoked",
                        summary=f"Assignment revoked once for all apps: {reason.strip()}",
                        stage=ProviderStage.REVOKED,
                    ),
                ),
            }
        )
        return self._save(updated)

    def _require(
        self,
        session_id: str,
        stage: ProviderStage,
        expected_version: int | None,
    ) -> ProviderSession:
        try:
            session = self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown provider session: {session_id}") from exc
        self._check_version(session, expected_version)
        if session.stage is not stage:
            raise WorkflowConflict(
                f"command requires stage {stage.value}; current stage is {session.stage.value}"
            )
        return session

    @staticmethod
    def _check_version(
        session: ProviderSession, expected_version: int | None
    ) -> None:
        if expected_version is not None and expected_version != session.version:
            raise WorkflowConflict(
                f"version conflict: expected {expected_version}, current {session.version}"
            )

    def _save(self, session: ProviderSession) -> ProviderSession:
        self._sessions[session.session_id] = session
        return deepcopy(session)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now

    @staticmethod
    def _event(
        now: datetime,
        *,
        actor_type: str,
        actor_ref: str,
        action: str,
        summary: str,
        stage: ProviderStage,
    ) -> WorkflowEvent:
        return WorkflowEvent(
            event_id=f"event:{uuid4()}",
            occurred_at=now,
            actor_type=actor_type,
            actor_ref=actor_ref,
            action=action,
            summary=summary,
            stage=stage,
        )


def _reference_ai_facts() -> tuple[EvidenceFact, ...]:
    """Synthetic, reproducible AI output used by the public reference adapter."""

    return (
        EvidenceFact(
            field_path="patient.display_name",
            label="Care recipient",
            proposed_value="Malia K.",
            confidence=0.99,
            source_ref="referral:synthetic-transition-note",
            quote="Malia K.",
        ),
        EvidenceFact(
            field_path="service.type",
            label="Requested service",
            proposed_value="In-home respite support",
            confidence=0.97,
            source_ref="referral:synthetic-transition-note",
            quote="in-home respite support",
        ),
        EvidenceFact(
            field_path="service.start_date",
            label="Requested start",
            proposed_value="2026-08-05",
            confidence=0.93,
            source_ref="referral:synthetic-transition-note",
            quote="beginning August 5, 2026",
        ),
        EvidenceFact(
            field_path="service.schedule",
            label="Preferred schedule",
            proposed_value="Wednesday afternoons",
            confidence=0.74,
            source_ref="referral:synthetic-transition-note",
            quote="preferably Wednesday afternoons",
            needs_review=True,
        ),
        EvidenceFact(
            field_path="service.area",
            label="Service area",
            proposed_value="East Honolulu",
            confidence=0.98,
            source_ref="referral:synthetic-transition-note",
            quote="in East Honolulu",
        ),
        EvidenceFact(
            field_path="care_team.coordinator",
            label="Family coordinator",
            proposed_value="Leilani · daughter",
            confidence=0.95,
            source_ref="referral:synthetic-transition-note",
            quote="Her daughter Leilani is helping coordinate",
        ),
        EvidenceFact(
            field_path="preferences.cultural",
            label="Caregiver preference",
            proposed_value="Local cultural knowledge preferred",
            confidence=0.91,
            source_ref="referral:synthetic-transition-note",
            quote="a caregiver with local cultural knowledge is preferred",
        ),
        EvidenceFact(
            field_path="visit.preparation",
            label="First-visit preparation",
            proposed_value="Bring printed transition packet",
            confidence=0.98,
            source_ref="referral:synthetic-transition-note",
            quote="bring the printed transition packet to the first visit",
        ),
    )


def _worker_candidates() -> tuple[WorkerCandidate, ...]:
    return (
        WorkerCandidate(
            worker_id="worker:synthetic-kai-n",
            display_name="Kai N.",
            role="Certified nurse aide",
            qualifications=("Hawaiʻi CNA active (simulated)", "CPR current (simulated)"),
            availability="Wednesday 1:00–5:00 PM",
            eligible=True,
            deterministic_checks=(
                "required role satisfied",
                "simulated registry status active",
                "requested window available",
                "service area covered",
            ),
            ai_explanation=(
                "Strongest reviewed fit because the requested window, service area, "
                "and cultural preference align. A supervisor still decides."
            ),
        ),
        WorkerCandidate(
            worker_id="worker:synthetic-noa-p",
            display_name="Noa P.",
            role="Home care aide",
            qualifications=("Home care aide profile (simulated)",),
            availability="Wednesday 1:00–3:00 PM",
            eligible=False,
            deterministic_checks=(
                "required role not satisfied",
                "requested four-hour window not covered",
            ),
            ai_explanation=(
                "Potential relationship fit, but deterministic qualification and "
                "availability gates exclude this worker."
            ),
        ),
        WorkerCandidate(
            worker_id="worker:synthetic-liko-r",
            display_name="Liko R.",
            role="Certified nurse aide",
            qualifications=("Hawaiʻi CNA active (simulated)", "CPR current (simulated)"),
            availability="Friday mornings",
            eligible=False,
            deterministic_checks=(
                "required role satisfied",
                "simulated registry status active",
                "requested window unavailable",
            ),
            ai_explanation=(
                "Qualified, but the authoritative availability check does not match "
                "the approved schedule."
            ),
        ),
    )


def _initial_app_projections() -> tuple[AppProjection, ...]:
    return (
        AppProjection(
            app_id="app:synthetic-scheduler",
            app_name="OpenShift Scheduler",
            purpose="Schedule the approved respite visit",
        ),
        AppProjection(
            app_id="app:synthetic-field-client",
            app_name="Care Tasks Mobile",
            purpose="Show the assigned worker approved visit preparation",
        ),
    )


def _fact_value(session: ProviderSession, field_path: str) -> str:
    fact = next(item for item in session.facts if item.field_path == field_path)
    return fact.reviewed_value or fact.proposed_value


def _allow_projection(
    app: AppProjection, session: ProviderSession, now: datetime
) -> AppProjection:
    assert session.assignment is not None
    common = {
        "case_id": session.case_id,
        "care_recipient": _fact_value(session, "patient.display_name"),
        "assigned_worker": session.assignment.worker_name,
    }
    if app.app_id == "app:synthetic-scheduler":
        data = {
            **common,
            "service": _fact_value(session, "service.type"),
            "start_date": _fact_value(session, "service.start_date"),
            "visit_window": _fact_value(session, "service.schedule"),
            "service_area": _fact_value(session, "service.area"),
        }
        excluded = (
            "source document",
            "family relationship details",
            "clinical record",
            "credential evidence",
        )
    else:
        data = {
            **common,
            "visit_window": _fact_value(session, "service.schedule"),
            "first_visit_task": _fact_value(session, "visit.preparation"),
        }
        excluded = (
            "source document",
            "family relationship details",
            "exact home address",
            "clinical record",
            "credential evidence",
        )
    return app.model_copy(
        update={
            "decision": AppDecision.ALLOW,
            "reason": "Allowed by approved purpose, active assignment, and app policy.",
            "data": data,
            "excluded": excluded,
            "decided_at": now,
        }
    )
