"""Deterministic, one-way mappings from legacy POC contracts to Core 0.1.

The legacy delegation and uploaded-document contracts remain their own
experimental profiles.  These functions make their Core representation
inspectable; they never evaluate a request, activate a grant, or infer a
permit.  A Core permit is emitted only when the supplied legacy decision is
already a permit.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from hashlib import sha256
from typing import Any, Literal

from pydantic import field_validator

from caretrust.core_protocol import (
    AUTHORIZATION_DECISION_SCHEMA_URI,
    AUTHORIZATION_REQUEST_SCHEMA_URI,
    CORE_VERSION,
    STATUS_EVENT_SCHEMA_URI,
    TRUST_ARTIFACT_SCHEMA_URI,
    ArtifactReference,
    AuthorizationDecision,
    AuthorizationRequest,
    CanonicalHash,
    ProvenanceReference,
    StatusEvent,
    TrustArtifact,
    canonical_hash,
)
from caretrust.delegation import (
    DelegationAuthorizationDecision,
    DelegationAuthorizationRequest,
    DelegationGrant,
    DelegationRevocationRecord,
)
from caretrust.models import StrictModel
from caretrust.uploaded_care import (
    DocumentShareDecision,
    DocumentShareGrant,
    DocumentShareRequest,
    DocumentShareRevocationRecord,
)


_BRIDGE_ISSUER = "service:caretrust-core-bridge"
_PROVENANCE_RELATIONSHIP = "urn:caretrust:relationship:derived-from-legacy-contract"


class MappingMetadata(StrictModel):
    """Claim boundary accompanying, but never embedded in, a Core object."""

    source_schema_version: str
    target_schema_uri: str
    conformance: Literal["mapped_only"]
    semantic_loss: tuple[str, ...]
    bridge_generated_fields: tuple[str, ...]

    @field_validator("source_schema_version", "target_schema_uri")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("mapping metadata values must not be blank")
        return value


class CoreMapping(StrictModel):
    """A target Core contract plus its explicit interoperability boundary."""

    metadata: MappingMetadata
    target: dict[str, Any]


def _dump(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json")


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _legacy_ref(
    *, artifact_id: str,
    artifact_type: str,
    source: dict[str, Any],
    version: int = 1,
) -> ArtifactReference:
    """Reference a hash-bound legacy object without claiming a native profile."""

    return ArtifactReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        version=version,
        content_hash=canonical_hash(source),
    )


def _provenance(*, source_ref: str, source: dict[str, Any], at: datetime) -> tuple[ProvenanceReference, ...]:
    return (
        ProvenanceReference(
            source_ref=source_ref,
            relationship=_PROVENANCE_RELATIONSHIP,
            recorded_at=at,
            content_hash=canonical_hash(source),
        ),
    )


def _inclusive_date_end(value: Any) -> datetime:
    """Translate an inclusive legacy date boundary to an exclusive UTC instant."""

    return datetime.combine(value + timedelta(days=1), time.min, tzinfo=UTC)


def _at_start_of_date(value: Any) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _token(label: str, source_id: str) -> str:
    return sha256(f"caretrust-core-bridge|{label}|{source_id}".encode("utf-8")).hexdigest()


def _metadata(
    *, source_schema_version: str, target_schema_uri: str, semantic_loss: tuple[str, ...] = (), bridge_generated_fields: tuple[str, ...] = (),
) -> MappingMetadata:
    return MappingMetadata(
        source_schema_version=source_schema_version,
        target_schema_uri=target_schema_uri,
        conformance="mapped_only",
        semantic_loss=semantic_loss,
        bridge_generated_fields=bridge_generated_fields,
    )


def _wrap(target: Any, metadata: MappingMetadata) -> CoreMapping:
    return CoreMapping(metadata=metadata, target=target.model_dump(mode="json", exclude_none=True))


def delegation_grant_to_core(grant: DelegationGrant) -> CoreMapping:
    """Represent a legacy delegation grant as a hash-bound experimental artifact."""

    source = _dump(grant)
    payload = {
        "legacy_contract": source,
        "bridge": {
            "mapping_status": "mapped_only",
            "experimental_profile": True,
            "semantic_loss": [],
        },
    }
    target = TrustArtifact(
        schema_uri=TRUST_ARTIFACT_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:experimental:legacy-delegation-grant:0.1",
        spec_version=CORE_VERSION,
        artifact_id=grant.grant_id,
        artifact_type="urn:caretrust:artifact-type:experimental:legacy-delegation-grant",
        version=1,
        issuer_ref=grant.issuer_ref,
        subject_refs=(grant.patient_ref, grant.delegate_ref),
        issued_at=grant.issued_at,
        valid_from=_at_start_of_date(grant.valid_from),
        valid_until=_inclusive_date_end(grant.valid_until),
        status=_enum_value(grant.status),
        status_ref=f"urn:caretrust:status:legacy-delegation:{_enum_value(grant.status)}",
        provenance_refs=_provenance(source_ref=grant.grant_id, source=source, at=grant.issued_at),
        payload_schema_uri="urn:caretrust:schema:experimental:legacy-delegation-grant-payload:0.1",
        payload_hash=canonical_hash(payload),
        payload=payload,
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=grant.schema_version,
            target_schema_uri=TRUST_ARTIFACT_SCHEMA_URI,
            bridge_generated_fields=(
                "version=1",
                "valid_from at 00:00:00Z",
                "valid_until as the first instant after the inclusive legacy date",
                "Core provenance hash",
            ),
        ),
    )


def document_share_grant_to_core(grant: DocumentShareGrant) -> CoreMapping:
    """Represent a legacy document-share grant as a hash-bound experimental artifact."""

    source = _dump(grant)
    payload = {
        "legacy_contract": source,
        "bridge": {
            "mapping_status": "mapped_only",
            "experimental_profile": True,
            "semantic_loss": [],
        },
    }
    target = TrustArtifact(
        schema_uri=TRUST_ARTIFACT_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:experimental:legacy-document-share-grant:0.1",
        spec_version=CORE_VERSION,
        artifact_id=grant.grant_id,
        artifact_type="urn:caretrust:artifact-type:experimental:legacy-document-share-grant",
        version=1,
        issuer_ref=_BRIDGE_ISSUER,
        subject_refs=(grant.patient_ref,),
        issued_at=grant.issued_at,
        valid_from=grant.valid_from,
        valid_until=grant.valid_until,
        status=_enum_value(grant.status),
        status_ref=f"urn:caretrust:status:legacy-document-share:{_enum_value(grant.status)}",
        provenance_refs=_provenance(source_ref=grant.grant_id, source=source, at=grant.issued_at),
        payload_schema_uri="urn:caretrust:schema:experimental:legacy-document-share-grant-payload:0.1",
        payload_hash=canonical_hash(payload),
        payload=payload,
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=grant.schema_version,
            target_schema_uri=TRUST_ARTIFACT_SCHEMA_URI,
            bridge_generated_fields=("issuer_ref=service:caretrust-core-bridge", "version=1", "Core provenance hash"),
        ),
    )


def target_artifact(mapping: CoreMapping) -> TrustArtifact:
    """Validate and recover a TrustArtifact from an explicit mapping wrapper."""

    if mapping.metadata.target_schema_uri != TRUST_ARTIFACT_SCHEMA_URI:
        raise ValueError("mapping target is not a Core TrustArtifact")
    return TrustArtifact.model_validate(mapping.target)


def delegation_request_to_core(request: DelegationAuthorizationRequest, grant: TrustArtifact) -> CoreMapping:
    if request.grant_id != grant.artifact_id:
        raise ValueError("delegation request must reference the supplied grant artifact")
    target = AuthorizationRequest(
        schema_uri=AUTHORIZATION_REQUEST_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:authorization:0.1",
        spec_version=CORE_VERSION,
        request_id=request.request_id,
        requester_ref=request.delegate_ref,
        subject_ref=request.patient_ref,
        audience=request.audience.value,
        purpose=f"urn:caretrust:purpose:delegation:{request.purpose.value.replace('_', '-')}",
        action=f"urn:caretrust:action:delegation:{request.action.value.replace('_', '-')}",
        resource=f"urn:caretrust:resource:delegation:{request.resource.value.replace('_', '-')}",
        referenced_artifact_refs=(grant.reference(),),
        requested_at=request.requested_at,
        expires_at=request.requested_at + timedelta(minutes=5),
        nonce=_token("nonce", request.request_id),
        idempotency_key=_token("idempotency", request.request_id),
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=request.schema_version,
            target_schema_uri=AUTHORIZATION_REQUEST_SCHEMA_URI,
            bridge_generated_fields=("expires_at=requested_at+5 minutes", "nonce", "idempotency_key"),
        ),
    )


def document_share_request_to_core(request: DocumentShareRequest, grant: TrustArtifact) -> CoreMapping:
    if request.grant_id != grant.artifact_id:
        raise ValueError("document-share request must reference the supplied grant artifact")
    item_set = canonical_hash(list(request.requested_approved_item_ids)).value
    target = AuthorizationRequest(
        schema_uri=AUTHORIZATION_REQUEST_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:authorization:0.1",
        spec_version=CORE_VERSION,
        request_id=request.request_id,
        requester_ref=request.requester_ref,
        subject_ref=request.patient_ref,
        audience=request.audience.value,
        purpose=f"urn:caretrust:purpose:document-share:{request.purpose.value.replace('_', '-')}",
        action="urn:caretrust:action:document-share:read-approved-items",
        resource=f"urn:caretrust:resource-set:document-share:{item_set}",
        referenced_artifact_refs=(grant.reference(),),
        requested_at=request.requested_at,
        expires_at=request.requested_at + timedelta(minutes=5),
        nonce=_token("nonce", request.request_id),
        idempotency_key=_token("idempotency", request.request_id),
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=request.schema_version,
            target_schema_uri=AUTHORIZATION_REQUEST_SCHEMA_URI,
            semantic_loss=(
                "Core 0.1 has one resource URI; the ordered approved-item IDs are represented by a canonical hash-bound resource-set URI and remain inspectable in the legacy request.",
                "include_raw_document is not a Core request field; the legacy request remains authoritative for that explicit prohibition.",
            ),
            bridge_generated_fields=("expires_at=requested_at+5 minutes", "nonce", "idempotency_key", "resource-set SHA-256 URI"),
        ),
    )


def target_request(mapping: CoreMapping) -> AuthorizationRequest:
    if mapping.metadata.target_schema_uri != AUTHORIZATION_REQUEST_SCHEMA_URI:
        raise ValueError("mapping target is not a Core AuthorizationRequest")
    return AuthorizationRequest.model_validate(mapping.target)


def _decision(
    *,
    source: Any,
    request: AuthorizationRequest,
    grant: TrustArtifact,
    decision_id: str,
    outcome: str,
    reasons: tuple[str, ...],
    policy_version: str,
    decided_at: datetime,
    policy_uri: str,
    reason_namespace: str,
) -> AuthorizationDecision:
    if source.request_id != request.request_id:
        raise ValueError("legacy decision must bind the supplied Core request")
    if outcome == "permit" and grant.reference() not in request.referenced_artifact_refs:
        raise ValueError("permit mapping requires the request to reference its supporting artifact")
    return AuthorizationDecision.for_request(
        request=request,
        schema_uri=AUTHORIZATION_DECISION_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:authorization:0.1",
        spec_version=CORE_VERSION,
        decision_id=decision_id,
        request_id=request.request_id,
        issuer_ref=_BRIDGE_ISSUER,
        decision=outcome,
        reason_codes=tuple(
            f"urn:caretrust:reason:{reason_namespace}:{reason.lower().replace('_', '-')}" for reason in reasons
        ),
        supporting_artifact_refs=(grant.reference(),) if outcome == "permit" else (),
        policy_uri=policy_uri,
        policy_version=policy_version,
        status_checked_at=decided_at,
        decided_at=decided_at,
        expires_at=decided_at + timedelta(minutes=5),
    )


def delegation_decision_to_core(
    decision: DelegationAuthorizationDecision, request: AuthorizationRequest, grant: TrustArtifact
) -> CoreMapping:
    target = _decision(
        source=decision,
        request=request,
        grant=grant,
        decision_id=decision.decision_id,
        outcome=decision.decision.value,
        reasons=tuple(reason.value for reason in decision.reason_codes),
        policy_version=decision.policy_version,
        decided_at=decision.decided_at,
        policy_uri="urn:caretrust:policy:delegation-authorization",
        reason_namespace="delegation",
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=decision.schema_version,
            target_schema_uri=AUTHORIZATION_DECISION_SCHEMA_URI,
            bridge_generated_fields=("issuer_ref=service:caretrust-core-bridge", "status_checked_at=decided_at", "expires_at=decided_at+5 minutes"),
        ),
    )


def document_share_decision_to_core(
    decision: DocumentShareDecision, request: AuthorizationRequest, grant: TrustArtifact
) -> CoreMapping:
    target = _decision(
        source=decision,
        request=request,
        grant=grant,
        decision_id=decision.decision_id,
        outcome=decision.outcome,
        reasons=tuple(reason.value for reason in decision.reason_codes),
        policy_version=decision.policy_version,
        decided_at=decision.decided_at,
        policy_uri="urn:caretrust:policy:document-share",
        reason_namespace="document-share",
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=decision.schema_version,
            target_schema_uri=AUTHORIZATION_DECISION_SCHEMA_URI,
            semantic_loss=(
                "Granted approved-item IDs are intentionally not copied into Core AuthorizationDecision; applications must use the legacy minimum-data projection/receipt for item-level disclosure.",
            )
            if decision.outcome == "permit"
            else (),
            bridge_generated_fields=("issuer_ref=service:caretrust-core-bridge", "status_checked_at=decided_at", "expires_at=decided_at+5 minutes"),
        ),
    )


def target_decision(mapping: CoreMapping) -> AuthorizationDecision:
    if mapping.metadata.target_schema_uri != AUTHORIZATION_DECISION_SCHEMA_URI:
        raise ValueError("mapping target is not a Core AuthorizationDecision")
    return AuthorizationDecision.model_validate(mapping.target)


def _revocation_status(
    *,
    event_id: str,
    artifact: TrustArtifact,
    issuer_ref: str,
    actor_ref: str,
    at: datetime,
    source: Any,
    reason_code: str,
) -> StatusEvent:
    source_payload = _dump(source)
    return StatusEvent(
        schema_uri=STATUS_EVENT_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:artifact-status:0.1",
        spec_version=CORE_VERSION,
        event_id=event_id,
        artifact_ref=artifact.reference(),
        issuer_ref=issuer_ref,
        actor_ref=actor_ref,
        actor_role="urn:caretrust:role:patient",
        previous_status="active",
        new_status="revoked",
        reason_code=reason_code,
        sequence=1,
        effective_at=at,
        recorded_at=at,
        provenance_refs=_provenance(source_ref=event_id, source=source_payload, at=at),
    )


def delegation_revocation_to_status(revocation: DelegationRevocationRecord, grant: TrustArtifact) -> CoreMapping:
    if revocation.grant_id != grant.artifact_id:
        raise ValueError("delegation revocation must target the supplied grant artifact")
    if grant.status != "active":
        raise ValueError("delegation revocation mapping requires the pre-revocation active artifact")
    target = _revocation_status(
        event_id=revocation.revocation_id,
        artifact=grant,
        issuer_ref=grant.issuer_ref,
        actor_ref=revocation.actor_ref,
        at=revocation.revoked_at,
        source=revocation,
        reason_code="urn:caretrust:reason:delegation:patient-revoked-delegation",
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=revocation.schema_version,
            target_schema_uri=STATUS_EVENT_SCHEMA_URI,
            semantic_loss=(
                "The legacy revocation record has no ordered Core status-event history; sequence=1 begins a bridge-local event stream and previous_status=active is derived from the supplied pre-revocation artifact.",
            ),
            bridge_generated_fields=("sequence=1", "actor_role=patient", "previous_status=active"),
        ),
    )


def document_share_revocation_to_status(revocation: DocumentShareRevocationRecord, grant: TrustArtifact) -> CoreMapping:
    if revocation.grant_id != grant.artifact_id:
        raise ValueError("document-share revocation must target the supplied grant artifact")
    if grant.status != "active":
        raise ValueError("document-share revocation mapping requires the pre-revocation active artifact")
    target = _revocation_status(
        event_id=revocation.revocation_id,
        artifact=grant,
        issuer_ref=grant.issuer_ref,
        actor_ref=revocation.revoked_by_account_ref,
        at=revocation.revoked_at,
        source=revocation,
        reason_code="urn:caretrust:reason:document-share:patient-revoked-sharing",
    )
    return _wrap(
        target,
        _metadata(
            source_schema_version=revocation.schema_version,
            target_schema_uri=STATUS_EVENT_SCHEMA_URI,
            semantic_loss=(
                "The legacy revocation record has no ordered Core status-event history; sequence=1 begins a bridge-local event stream and previous_status=active is derived from the supplied pre-revocation artifact.",
            ),
            bridge_generated_fields=("sequence=1", "actor_role=patient", "previous_status=active"),
        ),
    )


def target_status(mapping: CoreMapping) -> StatusEvent:
    if mapping.metadata.target_schema_uri != STATUS_EVENT_SCHEMA_URI:
        raise ValueError("mapping target is not a Core StatusEvent")
    return StatusEvent.model_validate(mapping.target)
