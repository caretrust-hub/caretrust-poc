from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from caretrust.trace import (
    EvidenceStatus,
    TraceBundle,
    TraceEnvelope,
    TraceRecorder,
    canonical_json,
    sha256_json,
)


NOW = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)


def _event_payload() -> dict[str, object]:
    return {
        "request_id": "request:synthetic-001",
        "purpose": "schedule_appointments",
        "allowed": True,
        "resources": ["Appointment"],
    }


def test_canonical_json_and_hash_are_order_independent() -> None:
    left = {"b": [2, 1], "a": {"value": True}}
    right = {"a": {"value": True}, "b": [2, 1]}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_json(left) == sha256_json(right)
    assert len(sha256_json(left)) == 64


def test_trace_recorder_builds_consecutive_hash_bound_events() -> None:
    recorder = TraceRecorder("trace:synthetic-delegation-001")
    first = recorder.append(
        event_id="event:intent:001",
        occurred_at=NOW,
        actor_ref="patient:synthetic-001",
        receiver_ref="caretrust:intent-intake",
        boundary="patient_intent_intake",
        message_type="IntentStatement",
        evidence_status=EvidenceStatus.EXECUTED_LOCAL,
        standard_refs=("CareTrust intent contract v1",),
        linked_ids={"intent_id": "intent:synthetic-001"},
        payload=_event_payload(),
        non_claims=("The utterance is not an authorization grant.",),
    )
    second = recorder.append(
        event_id="event:draft:001",
        occurred_at=NOW + timedelta(seconds=1),
        actor_ref="caretrust:intent-model-adapter",
        receiver_ref="caretrust:draft-validator",
        boundary="untrusted_model_output",
        message_type="DelegationDraft",
        evidence_status=EvidenceStatus.RETAINED_AWS,
        linked_ids={
            "intent_id": "intent:synthetic-001",
            "draft_id": "draft:synthetic-001",
        },
        payload={"status": "draft", "blocking_uncertainty": True},
    )
    bundle = recorder.bundle(
        title="Synthetic patient delegation",
        fixture_refs=("fixtures/delegation/hero.json",),
        limitations=("No real patient, caregiver, or application is contacted.",),
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert first.payload_sha256 == sha256_json(_event_payload())
    assert bundle.events == (first, second)
    assert bundle.synthetic_only is True


def test_trace_envelope_rejects_payload_hash_mismatch() -> None:
    with pytest.raises(ValidationError, match="does not bind"):
        TraceEnvelope(
            schema_version="caretrust.trace-envelope.v1",
            trace_id="trace:synthetic-001",
            event_id="event:synthetic-001",
            sequence=1,
            occurred_at=NOW,
            actor_ref="actor:synthetic",
            receiver_ref="receiver:synthetic",
            boundary="synthetic_boundary",
            message_type="SyntheticMessage",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=(),
            linked_ids={},
            payload={"value": "accepted"},
            payload_sha256="0" * 64,
        )


def test_trace_bundle_rejects_gaps_duplicates_and_time_reversal() -> None:
    recorder = TraceRecorder("trace:synthetic-001")
    first = recorder.append(
        event_id="event:one",
        occurred_at=NOW,
        actor_ref="actor:a",
        receiver_ref="actor:b",
        boundary="boundary:a-b",
        message_type="MessageOne",
        evidence_status=EvidenceStatus.EXECUTED_LOCAL,
        payload={"step": 1},
    )
    second = first.model_copy(
        update={
            "event_id": "event:two",
            "sequence": 3,
            "occurred_at": NOW - timedelta(seconds=1),
            "payload": {"step": 2},
            "payload_sha256": sha256_json({"step": 2}),
        }
    )
    with pytest.raises(ValidationError, match="consecutive"):
        TraceBundle(
            schema_version="caretrust.trace-bundle.v1",
            trace_id="trace:synthetic-001",
            title="Synthetic trace",
            synthetic_only=True,
            fixture_refs=("fixture:synthetic",),
            events=(first, second),
            limitations=("Synthetic only.",),
        )


def test_trace_recorder_is_append_only_and_time_ordered() -> None:
    recorder = TraceRecorder("trace:synthetic-001")
    recorder.append(
        event_id="event:one",
        occurred_at=NOW,
        actor_ref="actor:a",
        receiver_ref="actor:b",
        boundary="boundary:a-b",
        message_type="MessageOne",
        evidence_status=EvidenceStatus.EXECUTED_LOCAL,
        payload={"step": 1},
    )
    with pytest.raises(ValueError, match="already exists"):
        recorder.append(
            event_id="event:one",
            occurred_at=NOW,
            actor_ref="actor:a",
            receiver_ref="actor:b",
            boundary="boundary:a-b",
            message_type="MessageOne",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            payload={"step": 1},
        )
    with pytest.raises(ValueError, match="cannot precede"):
        recorder.append(
            event_id="event:two",
            occurred_at=NOW - timedelta(seconds=1),
            actor_ref="actor:b",
            receiver_ref="actor:c",
            boundary="boundary:b-c",
            message_type="MessageTwo",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            payload={"step": 2},
        )


@pytest.mark.parametrize("status", list(EvidenceStatus))
def test_all_evidence_statuses_round_trip(status: EvidenceStatus) -> None:
    recorder = TraceRecorder(f"trace:{status.value}")
    event = recorder.append(
        event_id=f"event:{status.value}",
        occurred_at=NOW,
        actor_ref="actor:synthetic",
        receiver_ref="receiver:synthetic",
        boundary="synthetic_boundary",
        message_type="SyntheticMessage",
        evidence_status=status,
        payload={"status": status.value},
    )
    assert TraceEnvelope.model_validate_json(event.model_dump_json()) == event
