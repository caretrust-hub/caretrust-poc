"""Read-only patient/case navigator projections over CareTrust trace messages.

The navigator is intentionally not an authoritative store.  It validates and
derives view rows from an append-only :class:`~caretrust.trace.TraceBundle`.
Every row preserves the source event identifiers and payload hashes from which
it was derived.  Superseded events and revoked grants remain visible.

This is an administrative trust view, explicitly not a clinical chart.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.delegation import (
    ACTION_RESOURCE_REQUIREMENTS,
    CareRelationshipClaim,
    ClarificationRequest,
    ClarificationResponse,
    DelegationAuthorizationDecision,
    DelegationAuthorizationRequest,
    DelegationDraft,
    DelegationGrant,
    DelegationResource,
    DelegationRevocationRecord,
    GrantStatus,
    IntentStatement,
    InviteAcceptance,
    PatientApprovalRecord,
    PatientInvite,
)
from caretrust.models import StrictModel
from caretrust.trace import EvidenceStatus, TraceBundle, TraceEnvelope, sha256_json


class NavigatorProjectionError(ValueError):
    """Fail-closed error raised when a trace cannot support a safe projection."""


class EvidenceKind(StrEnum):
    ROLE = "role"
    PURPOSE = "purpose"
    APPROVAL = "approval"
    LIFECYCLE = "lifecycle"


class NavigatorGrantState(StrEnum):
    ACTIVE = "active"
    NOT_YET_VALID = "not_yet_valid"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PermissionEffect(StrEnum):
    ALLOW = "allow"
    EXCLUDE = "exclude"


class HistoryRecordState(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


def _nonblank(value: str) -> str:
    if not value:
        raise ValueError("value must not be blank")
    return value


def _sha256_digest(value: str) -> str:
    normalized = value.lower()
    if len(normalized) != 64 or any(
        char not in "0123456789abcdef" for char in normalized
    ):
        raise ValueError("value must be a 64-character SHA-256 hex digest")
    return normalized


def _unique_tuple(value: tuple[object, ...]) -> tuple[object, ...]:
    if len(value) != len(set(value)):
        raise ValueError("values must be unique")
    return value


class ProjectionEvidence(StrictModel):
    """Visible pointer from a derived row back to one source message field."""

    kind: EvidenceKind
    source_event_id: str
    source_message_type: str
    source_id: str
    payload_path: str
    value: str
    payload_sha256: str
    evidence_status: EvidenceStatus

    _nonblank_fields = field_validator(
        "source_event_id",
        "source_message_type",
        "source_id",
        "payload_path",
        "value",
    )(_nonblank)
    _payload_hash = field_validator("payload_sha256")(_sha256_digest)


class SourceReference(StrictModel):
    """Stable identifier retained from a trace envelope."""

    name: str
    value: str

    _nonblank_fields = field_validator("name", "value")(_nonblank)


class GrantHistoryReference(StrictModel):
    """One grant's current lifecycle view without erasing its source history."""

    grant_id: str
    state: NavigatorGrantState
    was_ever_active: bool
    grant_event_id: str
    grant_payload_sha256: str
    revocation_event_id: str | None = None
    revocation_id: str | None = None

    _nonblank_fields = field_validator("grant_id", "grant_event_id")(_nonblank)
    _grant_hash = field_validator("grant_payload_sha256")(_sha256_digest)

    @model_validator(mode="after")
    def validate_revocation_links(self) -> GrantHistoryReference:
        linked = self.revocation_event_id is not None or self.revocation_id is not None
        if self.state is NavigatorGrantState.REVOKED:
            if self.revocation_event_id is None or self.revocation_id is None:
                raise ValueError("revoked grant state requires revocation source IDs")
        elif linked:
            raise ValueError("only revoked grant state may carry revocation source IDs")
        return self


class CareTeamRow(StrictModel):
    """Administrative relationship row derived from a relationship claim."""

    row_id: str
    patient_ref: str
    caregiver_ref: str
    relationship_claim_id: str
    relationship_code: str
    relationship_status: GrantStatus
    relationship_valid_from: date
    relationship_valid_until: date
    authority_basis: Literal["patient_attestation"]
    legal_authority_status: Literal["not_established"]
    grant_history: tuple[GrantHistoryReference, ...]
    role_evidence: tuple[ProjectionEvidence, ...]
    source_event_ids: tuple[str, ...]
    source_payload_sha256s: tuple[str, ...]

    _nonblank_fields = field_validator(
        "row_id",
        "patient_ref",
        "caregiver_ref",
        "relationship_claim_id",
        "relationship_code",
    )(_nonblank)
    _unique_sources = field_validator("source_event_ids")(_unique_tuple)

    @field_validator("source_payload_sha256s")
    @classmethod
    def validate_source_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_sha256_digest(item) for item in value)

    @model_validator(mode="after")
    def require_role_provenance(self) -> CareTeamRow:
        if not self.role_evidence:
            raise ValueError("care-team row requires visible role evidence")
        if not self.source_event_ids or not self.source_payload_sha256s:
            raise ValueError("care-team row requires source event and hash provenance")
        return self


class PermissionMatrixRow(StrictModel):
    """One derived grant permission or explicit exclusion."""

    row_id: str
    grant_id: str
    relationship_claim_id: str
    patient_ref: str
    delegate_ref: str
    effect: PermissionEffect
    action: str | None
    resource: DelegationResource
    audiences: tuple[str, ...]
    purposes: tuple[str, ...]
    grant_state: NavigatorGrantState
    currently_effective: bool
    approval_id: str
    role_evidence: tuple[ProjectionEvidence, ...]
    purpose_evidence: tuple[ProjectionEvidence, ...]
    source_event_ids: tuple[str, ...]
    source_payload_sha256s: tuple[str, ...]

    _nonblank_fields = field_validator(
        "row_id",
        "grant_id",
        "relationship_claim_id",
        "patient_ref",
        "delegate_ref",
        "approval_id",
    )(_nonblank)
    _unique_values = field_validator(
        "audiences",
        "purposes",
        "source_event_ids",
    )(_unique_tuple)

    @field_validator("source_payload_sha256s")
    @classmethod
    def validate_source_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_sha256_digest(item) for item in value)

    @model_validator(mode="after")
    def validate_permission_semantics(self) -> PermissionMatrixRow:
        if not self.audiences or not self.purposes:
            raise ValueError("permission row requires audience and purpose visibility")
        if not self.role_evidence or not self.purpose_evidence:
            raise ValueError("permission row requires visible role and purpose evidence")
        if self.effect is PermissionEffect.ALLOW and self.action is None:
            raise ValueError("allowed permission row requires an action")
        if self.effect is PermissionEffect.EXCLUDE:
            if self.action is not None:
                raise ValueError("resource exclusion must not imply an allowed action")
            if self.currently_effective:
                raise ValueError("explicit exclusions are never effective permissions")
        if self.grant_state is not NavigatorGrantState.ACTIVE and self.currently_effective:
            raise ValueError("inactive grant cannot produce an effective permission")
        return self


class CaseHistoryRow(StrictModel):
    """One source trace event retained in append-only case history."""

    row_id: str
    source_event_id: str
    trace_sequence: int
    occurred_at: AwareDatetime
    actor_ref: str
    receiver_ref: str
    boundary: str
    message_type: str
    summary_code: str
    evidence_status: EvidenceStatus
    source_payload_sha256: str
    source_ids: tuple[SourceReference, ...]
    record_state: HistoryRecordState
    supersedes_event_id: str | None = None
    superseded_by_event_id: str | None = None

    _nonblank_fields = field_validator(
        "row_id",
        "source_event_id",
        "actor_ref",
        "receiver_ref",
        "boundary",
        "message_type",
        "summary_code",
    )(_nonblank)
    _payload_hash = field_validator("source_payload_sha256")(_sha256_digest)
    _unique_sources = field_validator("source_ids")(_unique_tuple)

    @field_validator("trace_sequence")
    @classmethod
    def validate_sequence(cls, value: int) -> int:
        if value < 1:
            raise ValueError("history sequence must be positive")
        return value

    @model_validator(mode="after")
    def validate_supersession(self) -> CaseHistoryRow:
        if self.record_state is HistoryRecordState.SUPERSEDED:
            if self.superseded_by_event_id is None:
                raise ValueError("superseded history row requires superseding event")
        elif self.superseded_by_event_id is not None:
            raise ValueError("current history row cannot name a superseding event")
        return self


class NavigatorMetadata(StrictModel):
    """Projection provenance and the explicit non-chart boundary."""

    schema_version: Literal["caretrust.navigator-metadata.v1"]
    source_trace_id: str
    source_trace_sha256: str
    patient_ref: str
    projected_as_of: AwareDatetime
    synthetic_only: Literal[True]
    not_clinical_chart: Literal[True]
    clinical_chart_status: Literal["not_a_clinical_chart"]
    source_event_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    _nonblank_fields = field_validator("source_trace_id", "patient_ref")(_nonblank)
    _trace_hash = field_validator("source_trace_sha256")(_sha256_digest)
    _unique_events = field_validator("source_event_ids")(_unique_tuple)

    @field_validator("limitations")
    @classmethod
    def require_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item for item in value):
            raise ValueError("navigator metadata requires explicit limitations")
        return _unique_tuple(value)  # type: ignore[return-value]


class PatientNavigatorProjection(StrictModel):
    """Complete deterministic view for one synthetic patient case."""

    schema_version: Literal["caretrust.patient-navigator-projection.v1"]
    metadata: NavigatorMetadata
    care_team_rows: tuple[CareTeamRow, ...]
    permission_matrix_rows: tuple[PermissionMatrixRow, ...]
    case_history_rows: tuple[CaseHistoryRow, ...]

    @model_validator(mode="after")
    def validate_projection_integrity(self) -> PatientNavigatorProjection:
        for rows, label in (
            (self.care_team_rows, "care-team"),
            (self.permission_matrix_rows, "permission"),
            (self.case_history_rows, "history"),
        ):
            row_ids = [row.row_id for row in rows]
            if len(row_ids) != len(set(row_ids)):
                raise ValueError(f"{label} row identifiers must be unique")
        sequences = [row.trace_sequence for row in self.case_history_rows]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("case history must preserve source trace order")
        history_events = tuple(row.source_event_id for row in self.case_history_rows)
        if history_events != self.metadata.source_event_ids:
            raise ValueError(
                "metadata source_event_ids must equal ordered case history events"
            )
        return self


_DELEGATION_MESSAGE_MODELS = {
    "IntentStatement": IntentStatement,
    "DelegationDraft": DelegationDraft,
    "ClarificationRequest": ClarificationRequest,
    "ClarificationResponse": ClarificationResponse,
    "PatientInvite": PatientInvite,
    "InviteAcceptance": InviteAcceptance,
    "PatientApprovalRecord": PatientApprovalRecord,
    "CareRelationshipClaim": CareRelationshipClaim,
    "DelegationGrant": DelegationGrant,
    "DelegationAuthorizationRequest": DelegationAuthorizationRequest,
    "DelegationAuthorizationDecision": DelegationAuthorizationDecision,
    "DelegationRevocationRecord": DelegationRevocationRecord,
}


def _row_id(kind: str, *parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts)
    digest = sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"navigator-{kind}:{digest}"


def _parse_delegation_events(
    trace: TraceBundle,
) -> dict[str, list[tuple[TraceEnvelope, StrictModel]]]:
    parsed: dict[str, list[tuple[TraceEnvelope, StrictModel]]] = {
        name: [] for name in _DELEGATION_MESSAGE_MODELS
    }
    for event in trace.events:
        model = _DELEGATION_MESSAGE_MODELS.get(event.message_type)
        if model is None:
            continue
        try:
            value = model.model_validate(event.payload)
        except Exception as exc:
            raise NavigatorProjectionError(
                f"{event.event_id} has invalid {event.message_type} payload"
            ) from exc
        parsed[event.message_type].append((event, value))
    return parsed


def _supersession_index(
    trace: TraceBundle,
) -> tuple[dict[str, str], dict[str, str]]:
    events = {event.event_id: event for event in trace.events}
    superseded_by: dict[str, str] = {}
    supersedes: dict[str, str] = {}
    for event in trace.events:
        target_id = event.linked_ids.get("supersedes_event_id")
        if target_id is None:
            continue
        target = events.get(target_id)
        if target is None:
            raise NavigatorProjectionError(
                f"{event.event_id} supersedes missing event {target_id}"
            )
        if target.sequence >= event.sequence:
            raise NavigatorProjectionError(
                f"{event.event_id} must supersede an earlier event"
            )
        if target.message_type != event.message_type:
            raise NavigatorProjectionError(
                "supersession must retain the same message_type"
            )
        if target_id in superseded_by:
            raise NavigatorProjectionError(
                f"{target_id} has more than one direct superseder"
            )
        superseded_by[target_id] = event.event_id
        supersedes[event.event_id] = target_id
    return superseded_by, supersedes


def _latest_unsuperseded(
    values: list[tuple[TraceEnvelope, StrictModel]],
    *,
    id_attribute: str,
    superseded_by: dict[str, str],
) -> dict[str, tuple[TraceEnvelope, StrictModel]]:
    grouped: dict[str, list[tuple[TraceEnvelope, StrictModel]]] = {}
    for event, value in values:
        source_id = getattr(value, id_attribute)
        grouped.setdefault(source_id, []).append((event, value))
    selected: dict[str, tuple[TraceEnvelope, StrictModel]] = {}
    for source_id, items in grouped.items():
        current = [item for item in items if item[0].event_id not in superseded_by]
        if len(current) != 1:
            raise NavigatorProjectionError(
                f"{source_id} must have exactly one unsuperseded source event"
            )
        selected[source_id] = current[0]
    return selected


def _grant_state(
    grant: DelegationGrant,
    *,
    as_of: datetime,
    revocation: tuple[TraceEnvelope, DelegationRevocationRecord] | None,
) -> NavigatorGrantState:
    if revocation is not None and revocation[1].revoked_at <= as_of:
        return NavigatorGrantState.REVOKED
    if grant.status is GrantStatus.REVOKED:
        return NavigatorGrantState.REVOKED
    if as_of.date() < grant.valid_from:
        return NavigatorGrantState.NOT_YET_VALID
    if grant.status is GrantStatus.EXPIRED or as_of.date() > grant.valid_until:
        return NavigatorGrantState.EXPIRED
    return NavigatorGrantState.ACTIVE


def _evidence(
    *,
    kind: EvidenceKind,
    event: TraceEnvelope,
    source_id: str,
    payload_path: str,
    value: object,
) -> ProjectionEvidence:
    return ProjectionEvidence(
        kind=kind,
        source_event_id=event.event_id,
        source_message_type=event.message_type,
        source_id=source_id,
        payload_path=payload_path,
        value=str(value),
        payload_sha256=event.payload_sha256,
        evidence_status=event.evidence_status,
    )


def _summary_code(event: TraceEnvelope) -> str:
    payload = event.payload
    if event.message_type in {
        "DelegationAuthorizationDecision",
        "AuthorizationDecision",
    }:
        return f"authorization_{payload.get('decision', 'recorded')}"
    if event.message_type in {
        "DelegationRevocationRecord",
        "RevocationRecord",
    }:
        return "delegation_revoked"
    if event.message_type == "DelegationDraft":
        return (
            "delegation_draft_blocked"
            if payload.get("blocking_issues")
            else "delegation_draft_ready_for_review"
        )
    return re_case(event.message_type)


def re_case(value: str) -> str:
    """Convert a PascalCase message type to a stable lowercase summary code."""

    output: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index and not value[index - 1].isupper():
            output.append("_")
        output.append(char.lower())
    return "".join(output)


def project_patient_navigator(
    trace: TraceBundle,
    *,
    patient_ref: str,
    as_of: AwareDatetime | None = None,
) -> PatientNavigatorProjection:
    """Derive one navigator projection without creating authoritative state."""

    if not patient_ref:
        raise NavigatorProjectionError("patient_ref must not be blank")
    if not trace.events:
        raise NavigatorProjectionError("trace must contain events")
    projected_as_of = as_of or trace.events[-1].occurred_at
    if projected_as_of < trace.events[0].occurred_at:
        raise NavigatorProjectionError("as_of cannot precede the trace")

    visible_events = tuple(
        event for event in trace.events if event.occurred_at <= projected_as_of
    )
    working_trace = trace.model_copy(update={"events": visible_events})
    parsed = _parse_delegation_events(working_trace)
    superseded_by, supersedes = _supersession_index(working_trace)
    explicit_patient_refs = {
        value
        for event in working_trace.events
        if isinstance((value := event.payload.get("patient_ref")), str)
    }
    if patient_ref not in explicit_patient_refs:
        raise NavigatorProjectionError(
            "trace contains no delegation messages for patient_ref"
        )
    if explicit_patient_refs != {patient_ref}:
        raise NavigatorProjectionError(
            "patient navigator trace must not mix patient references"
        )

    relationships = _latest_unsuperseded(
        parsed["CareRelationshipClaim"],
        id_attribute="relationship_claim_id",
        superseded_by=superseded_by,
    )
    grants = _latest_unsuperseded(
        parsed["DelegationGrant"],
        id_attribute="grant_id",
        superseded_by=superseded_by,
    )

    revocations: dict[
        str, tuple[TraceEnvelope, DelegationRevocationRecord]
    ] = {}
    for event, raw_value in parsed["DelegationRevocationRecord"]:
        value = raw_value
        assert isinstance(value, DelegationRevocationRecord)
        if value.grant_id in revocations:
            raise NavigatorProjectionError(
                f"{value.grant_id} has more than one revocation record"
            )
        revocations[value.grant_id] = (event, value)

    approval_events: dict[str, TraceEnvelope] = {}
    for event, raw_value in parsed["PatientApprovalRecord"]:
        value = raw_value
        assert isinstance(value, PatientApprovalRecord)
        approval_events[value.approval_id] = event

    typed_relationships: dict[
        str, tuple[TraceEnvelope, CareRelationshipClaim]
    ] = {}
    for relationship_id, (event, raw_value) in relationships.items():
        value = raw_value
        assert isinstance(value, CareRelationshipClaim)
        if value.patient_ref == patient_ref:
            typed_relationships[relationship_id] = (event, value)

    typed_grants: dict[str, tuple[TraceEnvelope, DelegationGrant]] = {}
    grant_states: dict[str, NavigatorGrantState] = {}
    grant_references: dict[str, GrantHistoryReference] = {}
    for grant_id, (event, raw_value) in grants.items():
        value = raw_value
        assert isinstance(value, DelegationGrant)
        if value.patient_ref != patient_ref:
            continue
        if value.relationship_claim_id not in typed_relationships:
            raise NavigatorProjectionError(
                f"{grant_id} references no current relationship for patient"
            )
        revocation = revocations.get(grant_id)
        if revocation is not None and revocation[0].sequence <= event.sequence:
            raise NavigatorProjectionError(
                f"{grant_id} revocation must follow its grant event"
            )
        state = _grant_state(
            value,
            as_of=projected_as_of,
            revocation=revocation,
        )
        typed_grants[grant_id] = (event, value)
        grant_states[grant_id] = state
        grant_references[grant_id] = GrantHistoryReference(
            grant_id=grant_id,
            state=state,
            was_ever_active=(
                value.status is GrantStatus.ACTIVE
                and value.valid_from <= projected_as_of.date()
            ),
            grant_event_id=event.event_id,
            grant_payload_sha256=event.payload_sha256,
            revocation_event_id=(
                revocation[0].event_id
                if state is NavigatorGrantState.REVOKED and revocation is not None
                else None
            ),
            revocation_id=(
                revocation[1].revocation_id
                if state is NavigatorGrantState.REVOKED and revocation is not None
                else None
            ),
        )

    care_team_rows: list[CareTeamRow] = []
    for relationship_id, (event, relationship) in sorted(
        typed_relationships.items()
    ):
        related_grants = [
            reference
            for grant_id, reference in sorted(grant_references.items())
            if typed_grants[grant_id][1].relationship_claim_id == relationship_id
        ]
        source_events = [event]
        for reference in related_grants:
            source_events.append(typed_grants[reference.grant_id][0])
            revocation = revocations.get(reference.grant_id)
            if revocation is not None:
                source_events.append(revocation[0])
        source_events = sorted(
            {source.event_id: source for source in source_events}.values(),
            key=lambda item: item.sequence,
        )
        role_evidence = (
            _evidence(
                kind=EvidenceKind.ROLE,
                event=event,
                source_id=relationship_id,
                payload_path="relationship_code",
                value=relationship.relationship_code.value,
            ),
            _evidence(
                kind=EvidenceKind.APPROVAL,
                event=event,
                source_id=relationship.approval_id,
                payload_path="approval_id",
                value=relationship.approval_id,
            ),
        )
        care_team_rows.append(
            CareTeamRow(
                row_id=_row_id(
                    "care-team",
                    relationship.patient_ref,
                    relationship.caregiver_ref,
                    relationship_id,
                ),
                patient_ref=relationship.patient_ref,
                caregiver_ref=relationship.caregiver_ref,
                relationship_claim_id=relationship_id,
                relationship_code=relationship.relationship_code.value,
                relationship_status=relationship.status,
                relationship_valid_from=relationship.valid_from,
                relationship_valid_until=relationship.valid_until,
                authority_basis=relationship.relationship_basis,
                legal_authority_status=relationship.legal_authority_status,
                grant_history=tuple(related_grants),
                role_evidence=role_evidence,
                source_event_ids=tuple(item.event_id for item in source_events),
                source_payload_sha256s=tuple(
                    item.payload_sha256 for item in source_events
                ),
            )
        )

    permission_rows: list[PermissionMatrixRow] = []
    for grant_id, (event, grant) in sorted(typed_grants.items()):
        state = grant_states[grant_id]
        relationship_event = typed_relationships[grant.relationship_claim_id][0]
        approval_event = approval_events.get(grant.approval_id)
        if approval_event is None:
            raise NavigatorProjectionError(
                f"{grant_id} references no PatientApprovalRecord event"
            )
        source_events = [relationship_event, approval_event, event]
        revocation = revocations.get(grant_id)
        if revocation is not None:
            source_events.append(revocation[0])
        source_events = sorted(
            {source.event_id: source for source in source_events}.values(),
            key=lambda item: item.sequence,
        )
        source_event_ids = tuple(item.event_id for item in source_events)
        source_hashes = tuple(item.payload_sha256 for item in source_events)
        role_evidence = (
            _evidence(
                kind=EvidenceKind.ROLE,
                event=relationship_event,
                source_id=grant.relationship_claim_id,
                payload_path="relationship_claim_id",
                value=grant.relationship_claim_id,
            ),
            _evidence(
                kind=EvidenceKind.APPROVAL,
                event=approval_event,
                source_id=grant.approval_id,
                payload_path="approval_id",
                value=grant.approval_id,
            ),
        )
        purpose_evidence = tuple(
            _evidence(
                kind=EvidenceKind.PURPOSE,
                event=event,
                source_id=grant_id,
                payload_path="allowed_purposes",
                value=purpose.value,
            )
            for purpose in grant.allowed_purposes
        )
        audiences = tuple(item.value for item in grant.allowed_audiences)
        purposes = tuple(item.value for item in grant.allowed_purposes)

        for action in grant.allowed_actions:
            for resource in sorted(
                ACTION_RESOURCE_REQUIREMENTS[action],
                key=lambda item: item.value,
            ):
                permission_rows.append(
                    PermissionMatrixRow(
                        row_id=_row_id(
                            "permission",
                            grant_id,
                            PermissionEffect.ALLOW.value,
                            action.value,
                            resource.value,
                        ),
                        grant_id=grant_id,
                        relationship_claim_id=grant.relationship_claim_id,
                        patient_ref=grant.patient_ref,
                        delegate_ref=grant.delegate_ref,
                        effect=PermissionEffect.ALLOW,
                        action=action.value,
                        resource=resource,
                        audiences=audiences,
                        purposes=purposes,
                        grant_state=state,
                        currently_effective=state is NavigatorGrantState.ACTIVE,
                        approval_id=grant.approval_id,
                        role_evidence=role_evidence,
                        purpose_evidence=purpose_evidence,
                        source_event_ids=source_event_ids,
                        source_payload_sha256s=source_hashes,
                    )
                )
        for resource in sorted(
            grant.excluded_resources,
            key=lambda item: item.value,
        ):
            permission_rows.append(
                PermissionMatrixRow(
                    row_id=_row_id(
                        "permission",
                        grant_id,
                        PermissionEffect.EXCLUDE.value,
                        resource.value,
                    ),
                    grant_id=grant_id,
                    relationship_claim_id=grant.relationship_claim_id,
                    patient_ref=grant.patient_ref,
                    delegate_ref=grant.delegate_ref,
                    effect=PermissionEffect.EXCLUDE,
                    action=None,
                    resource=resource,
                    audiences=audiences,
                    purposes=purposes,
                    grant_state=state,
                    currently_effective=False,
                    approval_id=grant.approval_id,
                    role_evidence=role_evidence,
                    purpose_evidence=purpose_evidence,
                    source_event_ids=source_event_ids,
                    source_payload_sha256s=source_hashes,
                )
            )

    history_rows: list[CaseHistoryRow] = []
    for event in working_trace.events:
        source_ids = tuple(
            SourceReference(name=name, value=value)
            for name, value in sorted(event.linked_ids.items())
            if name != "supersedes_event_id"
        )
        history_rows.append(
            CaseHistoryRow(
                row_id=_row_id("history", event.event_id),
                source_event_id=event.event_id,
                trace_sequence=event.sequence,
                occurred_at=event.occurred_at,
                actor_ref=event.actor_ref,
                receiver_ref=event.receiver_ref,
                boundary=event.boundary,
                message_type=event.message_type,
                summary_code=_summary_code(event),
                evidence_status=event.evidence_status,
                source_payload_sha256=event.payload_sha256,
                source_ids=source_ids,
                record_state=(
                    HistoryRecordState.SUPERSEDED
                    if event.event_id in superseded_by
                    else HistoryRecordState.CURRENT
                ),
                supersedes_event_id=supersedes.get(event.event_id),
                superseded_by_event_id=superseded_by.get(event.event_id),
            )
        )

    source_event_ids = tuple(row.source_event_id for row in history_rows)
    projection = PatientNavigatorProjection(
        schema_version="caretrust.patient-navigator-projection.v1",
        metadata=NavigatorMetadata(
            schema_version="caretrust.navigator-metadata.v1",
            source_trace_id=trace.trace_id,
            source_trace_sha256=sha256_json(trace),
            patient_ref=patient_ref,
            projected_as_of=projected_as_of,
            synthetic_only=True,
            not_clinical_chart=True,
            clinical_chart_status="not_a_clinical_chart",
            source_event_ids=source_event_ids,
            limitations=(
                "Administrative trust projection only; not a clinical chart.",
                "Rows derive from synthetic trace messages and are not authoritative records.",
                "Relationship, patient approval, delegation, and legal authority remain separate.",
            ),
        ),
        care_team_rows=tuple(care_team_rows),
        permission_matrix_rows=tuple(
            sorted(permission_rows, key=lambda item: item.row_id)
        ),
        case_history_rows=tuple(history_rows),
    )
    return projection
