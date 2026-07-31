from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from caretrust.core_protocol import (
    AUTHORIZATION_DECISION_SCHEMA_URI,
    AUTHORIZATION_REQUEST_SCHEMA_URI,
    MESSAGE_ENVELOPE_SCHEMA_URI,
    STATUS_EVENT_SCHEMA_URI,
    TRUST_ARTIFACT_SCHEMA_URI,
    ArtifactReference,
    AuthorizationDecision,
    AuthorizationRequest,
    MessageEnvelope,
    ProvenanceReference,
    StatusEvent,
    TrustArtifact,
    canonical_json,
    canonical_hash,
    envelope_for_payload,
    validate_status_sequence,
)


NOW = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)


def artifact() -> TrustArtifact:
    payload = {"legacy_contract": {"grant_id": "grant:synthetic-001"}}
    return TrustArtifact(
        schema_uri=TRUST_ARTIFACT_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:experimental:test:0.1",
        spec_version="0.1",
        artifact_id="grant:synthetic-001",
        artifact_type="urn:caretrust:artifact-type:experimental:test",
        version=1,
        issuer_ref="org:synthetic-caretrust",
        subject_refs=("patient:synthetic-001", "account:synthetic-leilani"),
        issued_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(days=1),
        status="active",
        status_ref="urn:caretrust:status:active",
        provenance_refs=(
            ProvenanceReference(
                source_ref="grant:synthetic-001",
                relationship="urn:caretrust:relationship:derived-from-legacy-contract",
                recorded_at=NOW,
                content_hash=canonical_hash(payload),
            ),
        ),
        payload_schema_uri="urn:caretrust:schema:experimental:test-payload:0.1",
        payload_hash=canonical_hash(payload),
        payload=payload,
    )


def request(value: TrustArtifact | None = None) -> AuthorizationRequest:
    support = value or artifact()
    return AuthorizationRequest(
        schema_uri=AUTHORIZATION_REQUEST_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:authorization:0.1",
        spec_version="0.1",
        request_id="request:synthetic-001",
        requester_ref="account:synthetic-leilani",
        subject_ref="patient:synthetic-001",
        audience="app:synthetic-scheduling",
        purpose="urn:caretrust:purpose:test",
        action="urn:caretrust:action:test",
        resource="urn:caretrust:resource:test",
        referenced_artifact_refs=(support.reference(),),
        requested_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        nonce="n" * 16,
        idempotency_key="i" * 16,
    )


def test_core_models_are_strict_and_hash_bound() -> None:
    support = artifact()
    req = request(support)
    decision = AuthorizationDecision.for_request(
        request=req,
        schema_uri=AUTHORIZATION_DECISION_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:authorization:0.1",
        spec_version="0.1",
        decision_id="decision:synthetic-001",
        request_id=req.request_id,
        issuer_ref="service:caretrust-policy",
        decision="permit",
        reason_codes=("urn:caretrust:reason:test:policy-satisfied",),
        supporting_artifact_refs=(support.reference(),),
        policy_uri="urn:caretrust:policy:test",
        policy_version="test.v1",
        status_checked_at=NOW,
        decided_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    envelope = envelope_for_payload(
        message_id="urn:caretrust:message:test-001",
        message_type="urn:caretrust:message-type:test",
        sender_ref="service:caretrust-policy",
        receiver_ref="app:synthetic-scheduling",
        sent_at=NOW,
        trace_id="trace:synthetic-core-test",
        payload_schema_uri=AUTHORIZATION_DECISION_SCHEMA_URI,
        payload=decision.model_dump(mode="json"),
    )
    assert decision.validates_request(req)
    assert envelope.schema_uri == MESSAGE_ENVELOPE_SCHEMA_URI
    assert envelope.payload_hash == canonical_hash(decision.model_dump(mode="json"))

    raw = support.model_dump(mode="json")
    raw["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TrustArtifact.model_validate(raw)


def test_hash_binding_and_rfc3339_temporal_failures_are_rejected() -> None:
    raw = artifact().model_dump(mode="json")
    raw["payload"]["legacy_contract"]["grant_id"] = "grant:tampered"
    with pytest.raises(ValidationError, match="payload_hash"):
        TrustArtifact.model_validate(raw)

    raw = request().model_dump(mode="json")
    raw["expires_at"] = "2026-07-30T17:59:59Z"
    with pytest.raises(ValidationError, match="expires_at must follow"):
        AuthorizationRequest.model_validate(raw)

    raw = request().model_dump(mode="json")
    raw["requested_at"] = "2026-07-30"
    with pytest.raises(ValidationError, match="RFC 3339"):
        AuthorizationRequest.model_validate(raw)


def test_decision_reason_namespace_request_hash_and_revocation_sequence_fail_closed() -> None:
    support = artifact()
    req = request(support)
    decision_values = {
        "schema_uri": AUTHORIZATION_DECISION_SCHEMA_URI,
        "profile_uri": "urn:caretrust:profile:core:authorization:0.1",
        "spec_version": "0.1",
        "decision_id": "decision:synthetic-001",
        "request_id": req.request_id,
        "issuer_ref": "service:caretrust-policy",
        "decision": "permit",
        "reason_codes": ("not-a-uri",),
        "supporting_artifact_refs": (support.reference(),),
        "policy_uri": "urn:caretrust:policy:test",
        "policy_version": "test.v1",
        "status_checked_at": NOW,
        "decided_at": NOW,
        "expires_at": NOW + timedelta(minutes=1),
    }
    with pytest.raises(ValidationError, match="absolute URI"):
        AuthorizationDecision.for_request(request=req, **decision_values)

    valid = AuthorizationDecision.for_request(
        request=req,
        **{**decision_values, "reason_codes": ("urn:caretrust:reason:test:ok",)},
    )
    assert valid.validates_request(req)
    tampered = req.model_copy(update={"action": "urn:caretrust:action:tampered"})
    assert not valid.validates_request(tampered)

    revoked = StatusEvent(
        schema_uri=STATUS_EVENT_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:artifact-status:0.1",
        spec_version="0.1",
        event_id="revocation:synthetic-001",
        artifact_ref=support.reference(),
        issuer_ref=support.issuer_ref,
        actor_ref="patient:synthetic-001",
        actor_role="urn:caretrust:role:patient",
        previous_status="active",
        new_status="revoked",
        reason_code="urn:caretrust:reason:test:revoked",
        sequence=1,
        effective_at=NOW,
        recorded_at=NOW,
        provenance_refs=(
            ProvenanceReference(
                source_ref="revocation:synthetic-001",
                relationship="urn:caretrust:relationship:derived-from-legacy-contract",
                recorded_at=NOW,
            ),
        ),
    )
    validate_status_sequence((revoked,))
    bad_sequence = revoked.model_copy(update={"sequence": 2})
    with pytest.raises(ValueError, match="start at one"):
        validate_status_sequence((bad_sequence,))


def test_envelope_rejects_stale_payload_hash() -> None:
    payload = {"decision": "deny"}
    raw = envelope_for_payload(
        message_id="urn:caretrust:message:test-002",
        message_type="urn:caretrust:message-type:test",
        sender_ref="service:caretrust-policy",
        receiver_ref="app:synthetic-scheduling",
        sent_at=NOW,
        trace_id="trace:synthetic-core-test",
        payload_schema_uri=AUTHORIZATION_DECISION_SCHEMA_URI,
        payload=payload,
    ).model_dump(mode="json")
    raw["payload"]["decision"] = "permit"
    with pytest.raises(ValidationError, match="payload_hash"):
        MessageEnvelope.model_validate(raw)


def test_canonical_json_uses_rfc8785_utf16_property_order() -> None:
    value = {
        "\u20ac": "Euro Sign",
        "\r": "Carriage Return",
        "\ufb33": "Hebrew Letter Dalet With Dagesh",
        "1": "One",
        "\U0001f600": "Emoji: Grinning Face",
        "\u0080": "Control",
        "\u00f6": "Latin Small Letter O With Diaeresis",
    }
    assert canonical_json(value).decode("utf-8") == (
        '{"\\r":"Carriage Return","1":"One","\u0080":"Control",'
        '"\u00f6":"Latin Small Letter O With Diaeresis","\u20ac":"Euro Sign",'
        '"\U0001f600":"Emoji: Grinning Face","\ufb33":"Hebrew Letter Dalet With Dagesh"}'
    )


@pytest.mark.parametrize("value", [2**53, -(2**53), 1.5, {"bad\ud800": True}])
def test_canonical_json_rejects_values_outside_supported_rfc8785_domain(value: object) -> None:
    with pytest.raises(ValueError):
        canonical_json(value)
