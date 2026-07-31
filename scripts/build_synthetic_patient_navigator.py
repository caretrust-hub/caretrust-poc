"""Build the deterministic synthetic patient navigator trace and projection."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from caretrust.delegation import (
    ClarificationRequest,
    ClarificationResponse,
    DelegationAuthorizationDecision,
    DelegationAuthorizationRequest,
    DelegationBlockingCode,
    DelegationDecisionValue,
    DelegationDraft,
    DelegationReasonCode,
    DelegationRevocationRecord,
    DelegationUncertaintyCode,
    IntentStatement,
    InviteAcceptance,
    PatientApprovalRecord,
    PatientInvite,
    CareRelationshipClaim,
    DelegationGrant,
)
from caretrust.navigator import project_patient_navigator
from caretrust.trace import EvidenceStatus, TraceRecorder

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "standards" / "examples" / "delegation"
TRACE_OUTPUT = (
    ROOT / "fixtures" / "delegation" / "synthetic-patient-navigator-trace.json"
)
PROJECTION_OUTPUT = (
    ROOT / "artifacts" / "validation" / "synthetic-patient-navigator.json"
)


def _load(filename: str, model: type):
    return model.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_trace():
    intent = _load("intent-statement.json", IntentStatement)
    final_draft = _load("delegation-draft.json", DelegationDraft)
    clarification = _load("clarification-request.json", ClarificationRequest)
    response = _load("clarification-response.json", ClarificationResponse)
    invite = _load("patient-invite.json", PatientInvite)
    acceptance = _load("invite-acceptance.json", InviteAcceptance)
    approval = _load("patient-approval-record.json", PatientApprovalRecord)
    relationship = _load("care-relationship-claim.json", CareRelationshipClaim)
    grant = _load("delegation-grant.json", DelegationGrant)
    request = _load(
        "delegation-authorization-request.json",
        DelegationAuthorizationRequest,
    )
    decision = _load(
        "delegation-authorization-decision.json",
        DelegationAuthorizationDecision,
    )
    revocation = _load(
        "delegation-revocation-record.json",
        DelegationRevocationRecord,
    )

    initial_draft_payload = final_draft.model_dump(mode="json")
    initial_draft_payload.update(
        {
            "draft_id": "delegation-draft:synthetic-001:v1",
            "draft_version": 1,
            "allowed_audiences": [],
            "evidence_bindings": [
                binding
                for binding in initial_draft_payload["evidence_bindings"]
                if binding["field_path"] != "allowed_audiences"
            ],
            "uncertainties": [
                {
                    "blocking": True,
                    "code": DelegationUncertaintyCode.AMBIGUOUS_AUDIENCE.value,
                    "evidence_refs": [
                        "intent-span:synthetic-scheduling",
                        "intent-span:synthetic-instructions",
                    ],
                    "field_paths": ["allowed_audiences"],
                    "message": "The intended applications are not explicit.",
                }
            ],
            "blocking_issues": [
                DelegationBlockingCode.UNRESOLVED_MATERIAL_UNCERTAINTY.value,
                DelegationBlockingCode.UNKNOWN_AUDIENCE.value,
            ],
        }
    )
    initial_draft = DelegationDraft.model_validate(initial_draft_payload)

    denied_request = request.model_copy(
        update={
            "request_id": "delegation-request:synthetic-002",
            "requested_at": datetime(2026, 7, 30, 10, 5, 1, tzinfo=UTC),
        }
    )
    denied_decision = decision.model_copy(
        update={
            "decision_id": "delegation-decision:synthetic-002",
            "request_id": denied_request.request_id,
            "decision": DelegationDecisionValue.DENY,
            "reason_codes": (DelegationReasonCode.GRANT_REVOKED,),
            "supporting_grant_ids": (),
            "decided_at": datetime(2026, 7, 30, 10, 5, 2, tzinfo=UTC),
        }
    )

    recorder = TraceRecorder("trace:synthetic-patient-navigator-001")

    def append(
        value,
        *,
        event_id: str,
        occurred_at: datetime,
        actor_ref: str,
        receiver_ref: str,
        boundary: str,
        linked_ids: dict[str, str],
        non_claims: tuple[str, ...] = (),
    ) -> None:
        recorder.append(
            event_id=event_id,
            occurred_at=occurred_at,
            actor_ref=actor_ref,
            receiver_ref=receiver_ref,
            boundary=boundary,
            message_type=type(value).__name__,
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=(f"CareTrust {type(value).__name__} v1",),
            linked_ids=linked_ids,
            payload=value.model_dump(mode="json"),
            non_claims=non_claims,
        )

    append(
        intent,
        event_id="event:navigator:intent:001",
        occurred_at=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
        actor_ref=intent.patient_ref,
        receiver_ref="caretrust:intent-intake",
        boundary="untrusted_patient_intent",
        linked_ids={"intent_id": intent.intent_id},
        non_claims=("Natural-language intent is not a delegation grant.",),
    )
    append(
        initial_draft,
        event_id="event:navigator:draft:001",
        occurred_at=datetime(2026, 7, 30, 10, 0, 1, tzinfo=UTC),
        actor_ref="caretrust:intent-model-adapter",
        receiver_ref="caretrust:draft-validator",
        boundary="untrusted_model_output",
        linked_ids={
            "intent_id": intent.intent_id,
            "draft_id": initial_draft.draft_id,
        },
        non_claims=("AI output is draft-only and has a blocking ambiguity.",),
    )
    append(
        clarification,
        event_id="event:navigator:clarification-request:001",
        occurred_at=datetime(2026, 7, 30, 10, 0, 5, tzinfo=UTC),
        actor_ref="caretrust:clarification-policy",
        receiver_ref=intent.patient_ref,
        boundary="material_ambiguity_gate",
        linked_ids={
            "intent_id": intent.intent_id,
            "draft_id": initial_draft.draft_id,
            "clarification_id": clarification.clarification_id,
        },
    )
    append(
        response,
        event_id="event:navigator:clarification-response:001",
        occurred_at=datetime(2026, 7, 30, 10, 0, 10, tzinfo=UTC),
        actor_ref=intent.patient_ref,
        receiver_ref="caretrust:clarification-policy",
        boundary="explicit_patient_clarification",
        linked_ids={
            "intent_id": intent.intent_id,
            "clarification_id": clarification.clarification_id,
            "response_id": response.response_id,
        },
    )
    append(
        final_draft,
        event_id="event:navigator:draft:002",
        occurred_at=datetime(2026, 7, 30, 10, 0, 11, tzinfo=UTC),
        actor_ref="caretrust:intent-model-adapter",
        receiver_ref="caretrust:draft-validator",
        boundary="corrected_draft_version",
        linked_ids={
            "intent_id": intent.intent_id,
            "draft_id": final_draft.draft_id,
            "supersedes_event_id": "event:navigator:draft:001",
        },
        non_claims=("The original ambiguous draft remains in history.",),
    )
    append(
        invite,
        event_id="event:navigator:invite:001",
        occurred_at=datetime(2026, 7, 30, 10, 1, tzinfo=UTC),
        actor_ref=intent.patient_ref,
        receiver_ref="caretrust:invite-service",
        boundary="hashed_single_use_invite",
        linked_ids={
            "draft_id": final_draft.draft_id,
            "invite_id": invite.invite_id,
        },
        non_claims=("No plaintext recipient contact is retained.",),
    )
    append(
        acceptance,
        event_id="event:navigator:invite-acceptance:001",
        occurred_at=datetime(2026, 7, 30, 10, 2, tzinfo=UTC),
        actor_ref=acceptance.caregiver_ref,
        receiver_ref="caretrust:invite-service",
        boundary="synthetic_account_acceptance",
        linked_ids={
            "invite_id": invite.invite_id,
            "acceptance_id": acceptance.acceptance_id,
        },
        non_claims=(
            "Invite acceptance proves neither relationship nor legal authority.",
        ),
    )
    append(
        approval,
        event_id="event:navigator:approval:001",
        occurred_at=datetime(2026, 7, 30, 10, 3, tzinfo=UTC),
        actor_ref=approval.patient_ref,
        receiver_ref="caretrust:approval-service",
        boundary="explicit_patient_approval",
        linked_ids={
            "draft_id": final_draft.draft_id,
            "acceptance_id": acceptance.acceptance_id,
            "approval_id": approval.approval_id,
        },
        non_claims=("Patient approval is not an application permit.",),
    )
    append(
        relationship,
        event_id="event:navigator:relationship:001",
        occurred_at=datetime(2026, 7, 30, 10, 3, 1, tzinfo=UTC),
        actor_ref="caretrust:relationship-activation-policy",
        receiver_ref="caretrust:relationship-store",
        boundary="relationship_assertion_activation",
        linked_ids={
            "approval_id": approval.approval_id,
            "relationship_claim_id": relationship.relationship_claim_id,
        },
        non_claims=(
            "The relationship assertion is not legal authority or permission.",
        ),
    )
    append(
        grant,
        event_id="event:navigator:grant:001",
        occurred_at=datetime(2026, 7, 30, 10, 3, 2, tzinfo=UTC),
        actor_ref="caretrust:delegation-activation-policy",
        receiver_ref="caretrust:delegation-store",
        boundary="least_privilege_delegation_activation",
        linked_ids={
            "approval_id": approval.approval_id,
            "relationship_claim_id": relationship.relationship_claim_id,
            "grant_id": grant.grant_id,
        },
        non_claims=("Each application still applies independent local policy.",),
    )
    append(
        request,
        event_id="event:navigator:request:001",
        occurred_at=datetime(2026, 7, 30, 10, 4, tzinfo=UTC),
        actor_ref=grant.delegate_ref,
        receiver_ref="app:synthetic-scheduling-policy",
        boundary="application_specific_request",
        linked_ids={"grant_id": grant.grant_id, "request_id": request.request_id},
    )
    append(
        decision,
        event_id="event:navigator:decision:001",
        occurred_at=datetime(2026, 7, 30, 10, 4, 1, tzinfo=UTC),
        actor_ref="app:synthetic-scheduling-policy",
        receiver_ref=grant.delegate_ref,
        boundary="application_local_authorization",
        linked_ids={
            "grant_id": grant.grant_id,
            "request_id": request.request_id,
            "decision_id": decision.decision_id,
        },
    )
    append(
        revocation,
        event_id="event:navigator:revocation:001",
        occurred_at=datetime(2026, 7, 30, 10, 5, tzinfo=UTC),
        actor_ref=revocation.actor_ref,
        receiver_ref="caretrust:delegation-status-seam",
        boundary="patient_directed_revocation",
        linked_ids={
            "grant_id": grant.grant_id,
            "revocation_id": revocation.revocation_id,
        },
        non_claims=(
            "The separate relationship record remains visible and active.",
        ),
    )
    append(
        denied_request,
        event_id="event:navigator:request:002",
        occurred_at=datetime(2026, 7, 30, 10, 5, 1, tzinfo=UTC),
        actor_ref=grant.delegate_ref,
        receiver_ref="app:synthetic-scheduling-policy",
        boundary="fresh_post_revocation_request",
        linked_ids={
            "grant_id": grant.grant_id,
            "request_id": denied_request.request_id,
        },
    )
    append(
        denied_decision,
        event_id="event:navigator:decision:002",
        occurred_at=datetime(2026, 7, 30, 10, 5, 2, tzinfo=UTC),
        actor_ref="app:synthetic-scheduling-policy",
        receiver_ref=grant.delegate_ref,
        boundary="application_local_authorization",
        linked_ids={
            "grant_id": grant.grant_id,
            "request_id": denied_request.request_id,
            "decision_id": denied_decision.decision_id,
            "revocation_id": revocation.revocation_id,
        },
        non_claims=(
            "Earlier permit receipts remain historical; existing sessions are not terminated.",
        ),
    )

    return recorder.bundle(
        title="Synthetic patient delegation case navigator source trace",
        fixture_refs=(
            "docs/standards/examples/delegation/",
            "docs/standards/caretrust-delegation-vocabulary.v1.json",
        ),
        limitations=(
            "Synthetic data and local policies only.",
            "No identity proofing, legal authority, clinical chart, EHR, or external application is represented.",
        ),
    )


def main() -> None:
    trace = build_trace()
    projection = project_patient_navigator(
        trace,
        patient_ref="patient:synthetic-001",
    )
    _write_json(TRACE_OUTPUT, trace)
    _write_json(PROJECTION_OUTPUT, projection)
    print(TRACE_OUTPUT.relative_to(ROOT))
    print(PROJECTION_OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
