"""Strict contracts for patient-directed caregiver delegation.

These contracts deliberately keep five different concepts separate:

* a patient's natural-language intent;
* an AI-proposed, reviewable draft;
* an asserted personal relationship;
* a patient-approved delegation grant; and
* legal authority, which this prototype never establishes.

The module contains no model call, identity proofing, legal determination, or
application permit shortcut.  Unknown vocabulary is rejected and exclusions
fail closed.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from hashlib import sha256
import re
from typing import Literal

from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.models import StrictModel


class DelegationAction(StrEnum):
    """Patient-delegable actions in the bounded v0.3 prototype."""

    SCHEDULE_APPOINTMENTS = "schedule_appointments"
    VIEW_APPOINTMENTS = "view_appointments"
    VIEW_VISIT_INSTRUCTIONS = "view_visit_instructions"
    MESSAGE_CARE_TEAM = "message_care_team"


class DelegationResource(StrEnum):
    """Resource categories understood by the bounded prototype."""

    APPOINTMENTS = "appointments"
    VISIT_INSTRUCTIONS = "visit_instructions"
    CARE_TEAM_MESSAGES = "care_team_messages"
    BILLING = "billing"
    MENTAL_HEALTH_RECORDS = "mental_health_records"


class DelegationPurpose(StrEnum):
    """Purpose vocabulary used by local application policy."""

    CARE_COORDINATION = "care_coordination"
    APPOINTMENT_MANAGEMENT = "appointment_management"


class DelegationAudience(StrEnum):
    """Application audiences included in the bounded synthetic workflow."""

    SCHEDULING_APP = "app:synthetic-scheduling"
    CARE_PORTAL = "app:synthetic-care-portal"


class RelationshipCode(StrEnum):
    """Personal relationships; none of these codes establish legal authority."""

    CHILD = "child"
    SPOUSE_OR_PARTNER = "spouse_or_partner"
    PARENT = "parent"
    SIBLING = "sibling"
    OTHER_FAMILY = "other_family"
    FRIEND = "friend"
    NEIGHBOR = "neighbor"
    OTHER_PERSONAL_RELATIONSHIP = "other_personal_relationship"
    UNSPECIFIED = "unspecified"


class DelegationUncertaintyCode(StrEnum):
    AMBIGUOUS_DELEGATE = "AMBIGUOUS_DELEGATE"
    AMBIGUOUS_RELATIONSHIP = "AMBIGUOUS_RELATIONSHIP"
    AMBIGUOUS_ACTION = "AMBIGUOUS_ACTION"
    AMBIGUOUS_RESOURCE = "AMBIGUOUS_RESOURCE"
    AMBIGUOUS_AUDIENCE = "AMBIGUOUS_AUDIENCE"
    AMBIGUOUS_PURPOSE = "AMBIGUOUS_PURPOSE"
    AMBIGUOUS_DATE = "AMBIGUOUS_DATE"
    CONTRADICTORY_SCOPE = "CONTRADICTORY_SCOPE"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    UNSUPPORTED_RESOURCE = "UNSUPPORTED_RESOURCE"


class DelegationBlockingCode(StrEnum):
    UNRESOLVED_MATERIAL_UNCERTAINTY = "UNRESOLVED_MATERIAL_UNCERTAINTY"
    CONTRADICTORY_SCOPE = "CONTRADICTORY_SCOPE"
    MISSING_DELEGATE = "MISSING_DELEGATE"
    MISSING_DURATION = "MISSING_DURATION"
    MISSING_REQUIRED_RESOURCE = "MISSING_REQUIRED_RESOURCE"
    UNKNOWN_AUDIENCE = "UNKNOWN_AUDIENCE"


class ClarificationCode(StrEnum):
    IDENTIFY_DELEGATE = "IDENTIFY_DELEGATE"
    CONFIRM_RELATIONSHIP = "CONFIRM_RELATIONSHIP"
    CHOOSE_ACTION = "CHOOSE_ACTION"
    CHOOSE_RESOURCE = "CHOOSE_RESOURCE"
    CHOOSE_AUDIENCE = "CHOOSE_AUDIENCE"
    CHOOSE_PURPOSE = "CHOOSE_PURPOSE"
    SET_END_DATE = "SET_END_DATE"
    RESOLVE_CONTRADICTION = "RESOLVE_CONTRADICTION"


class GrantStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class DelegationDecisionValue(StrEnum):
    PERMIT = "permit"
    DENY = "deny"


class DelegationReasonCode(StrEnum):
    POLICY_REQUIREMENTS_SATISFIED = "POLICY_REQUIREMENTS_SATISFIED"
    GRANT_REQUIRED = "GRANT_REQUIRED"
    GRANT_NOT_ACTIVE = "GRANT_NOT_ACTIVE"
    PATIENT_MISMATCH = "PATIENT_MISMATCH"
    DELEGATE_MISMATCH = "DELEGATE_MISMATCH"
    AUDIENCE_NOT_ALLOWED = "AUDIENCE_NOT_ALLOWED"
    PURPOSE_NOT_ALLOWED = "PURPOSE_NOT_ALLOWED"
    ACTION_NOT_ALLOWED = "ACTION_NOT_ALLOWED"
    RESOURCE_NOT_ALLOWED = "RESOURCE_NOT_ALLOWED"
    RESOURCE_EXCLUDED = "RESOURCE_EXCLUDED"
    GRANT_NOT_YET_VALID = "GRANT_NOT_YET_VALID"
    GRANT_EXPIRED = "GRANT_EXPIRED"
    GRANT_REVOKED = "GRANT_REVOKED"


class DraftEvidenceField(StrEnum):
    DELEGATE_REF = "delegate_ref"
    RELATIONSHIP_CODE = "relationship_code"
    ALLOWED_ACTIONS = "allowed_actions"
    ALLOWED_RESOURCES = "allowed_resources"
    EXCLUDED_RESOURCES = "excluded_resources"
    ALLOWED_PURPOSES = "allowed_purposes"
    ALLOWED_AUDIENCES = "allowed_audiences"
    VALID_FROM = "valid_from"
    VALID_UNTIL = "valid_until"


ACTION_RESOURCE_REQUIREMENTS: dict[
    DelegationAction, frozenset[DelegationResource]
] = {
    DelegationAction.SCHEDULE_APPOINTMENTS: frozenset(
        {DelegationResource.APPOINTMENTS}
    ),
    DelegationAction.VIEW_APPOINTMENTS: frozenset(
        {DelegationResource.APPOINTMENTS}
    ),
    DelegationAction.VIEW_VISIT_INSTRUCTIONS: frozenset(
        {DelegationResource.VISIT_INSTRUCTIONS}
    ),
    DelegationAction.MESSAGE_CARE_TEAM: frozenset(
        {DelegationResource.CARE_TEAM_MESSAGES}
    ),
}

_OPAQUE_REF = re.compile(r"^[a-z][a-z0-9_-]*:[^\s@]+$")
_FORBIDDEN_REF_PREFIXES = ("email:", "mailto:", "phone:", "tel:")


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


def _opaque_ref(value: str) -> str:
    normalized = _nonblank(value)
    if (
        not _OPAQUE_REF.fullmatch(normalized)
        or normalized.lower().startswith(_FORBIDDEN_REF_PREFIXES)
    ):
        raise ValueError(
            "reference must be an opaque namespaced identifier, not contact data"
        )
    return normalized


def _unique_tuple(value: tuple[object, ...]) -> tuple[object, ...]:
    if len(value) != len(set(value)):
        raise ValueError("values must be unique")
    return value


class IntentSpan(StrictModel):
    """Exact character evidence within one natural-language intent statement."""

    span_id: str
    intent_id: str
    quote: str
    start_char: int
    end_char: int

    _span_nonblank = field_validator("span_id", "intent_id", "quote")(_nonblank)

    @model_validator(mode="after")
    def validate_offsets(self) -> IntentSpan:
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("intent span must have positive ordered offsets")
        return self


class IntentStatement(StrictModel):
    """Synthetic patient intent accepted as untrusted input."""

    schema_version: Literal["caretrust.intent-statement.v1"]
    intent_id: str
    patient_ref: str
    utterance: str
    utterance_sha256: str
    spans: tuple[IntentSpan, ...]
    created_at: AwareDatetime
    synthetic: Literal[True]

    _intent_nonblank = field_validator("intent_id", "utterance")(_nonblank)
    _patient_opaque = field_validator("patient_ref")(_opaque_ref)
    _utterance_hash = field_validator("utterance_sha256")(_sha256_digest)
    _unique_spans = field_validator("spans")(_unique_tuple)

    @model_validator(mode="after")
    def validate_content_and_spans(self) -> IntentStatement:
        actual_hash = sha256(self.utterance.encode("utf-8")).hexdigest()
        if self.utterance_sha256 != actual_hash:
            raise ValueError("utterance_sha256 must hash the exact utterance")
        span_ids: set[str] = set()
        for span in self.spans:
            if span.intent_id != self.intent_id:
                raise ValueError("every span must refer to this intent")
            if span.span_id in span_ids:
                raise ValueError("intent span identifiers must be unique")
            span_ids.add(span.span_id)
            if span.end_char > len(self.utterance):
                raise ValueError("intent span exceeds utterance length")
            if self.utterance[span.start_char : span.end_char] != span.quote:
                raise ValueError("intent span quote must match exact character offsets")
        return self


class DelegationUncertainty(StrictModel):
    code: DelegationUncertaintyCode
    field_paths: tuple[str, ...]
    message: str
    evidence_refs: tuple[str, ...]
    blocking: bool

    _message_nonblank = field_validator("message")(_nonblank)
    _unique_paths = field_validator("field_paths", "evidence_refs")(_unique_tuple)

    @model_validator(mode="after")
    def require_field_path(self) -> DelegationUncertainty:
        if not self.field_paths:
            raise ValueError("uncertainty must identify at least one field path")
        return self


class DraftEvidenceBinding(StrictModel):
    """Bind one proposed draft value to one or more intent/clarification spans."""

    field_path: DraftEvidenceField
    value: str
    evidence_refs: tuple[str, ...]

    _value_nonblank = field_validator("value")(_nonblank)
    _unique_refs = field_validator("evidence_refs")(_unique_tuple)

    @model_validator(mode="after")
    def require_evidence(self) -> DraftEvidenceBinding:
        if not self.evidence_refs:
            raise ValueError("draft values must cite source evidence")
        return self


class DelegationDraft(StrictModel):
    """The only patient-delegation object that an AI model may propose."""

    schema_version: Literal["caretrust.delegation-draft.v1"]
    draft_id: str
    draft_version: int
    intent_id: str
    intent_sha256: str
    patient_ref: str
    delegate_ref: str | None
    relationship_code: RelationshipCode | None
    allowed_actions: tuple[DelegationAction, ...]
    allowed_resources: tuple[DelegationResource, ...]
    excluded_resources: tuple[DelegationResource, ...]
    allowed_purposes: tuple[DelegationPurpose, ...]
    allowed_audiences: tuple[DelegationAudience, ...]
    valid_from: date | None
    valid_until: date | None
    evidence_bindings: tuple[DraftEvidenceBinding, ...]
    uncertainties: tuple[DelegationUncertainty, ...]
    blocking_issues: tuple[DelegationBlockingCode, ...]
    proposed_by: Literal["ai_model"]
    authority_basis: Literal["unverified_patient_intent"]
    legal_authority_status: Literal["not_established"]
    status: Literal["draft"]
    activation_permitted: Literal[False]
    authorization_permitted: Literal[False]
    synthetic: Literal[True]

    _ids_nonblank = field_validator("draft_id", "intent_id")(_nonblank)
    _patient_opaque = field_validator("patient_ref")(_opaque_ref)
    _intent_hash = field_validator("intent_sha256")(_sha256_digest)
    _unique_scopes = field_validator(
        "allowed_actions",
        "allowed_resources",
        "excluded_resources",
        "allowed_purposes",
        "allowed_audiences",
        "evidence_bindings",
        "blocking_issues",
    )(_unique_tuple)

    @field_validator("delegate_ref")
    @classmethod
    def validate_delegate_ref(cls, value: str | None) -> str | None:
        return None if value is None else _opaque_ref(value)

    @field_validator("draft_version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("draft_version must be at least one")
        return value

    @model_validator(mode="after")
    def validate_draft_scope(self) -> DelegationDraft:
        if self.delegate_ref == self.patient_ref:
            raise ValueError("patient and delegate must be different subjects")
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until must not precede valid_from")

        overlap = set(self.allowed_resources) & set(self.excluded_resources)
        if overlap:
            raise ValueError(
                "excluded resources cannot also be allowed; exclusions win"
            )

        required_resources = frozenset().union(
            *(ACTION_RESOURCE_REQUIREMENTS[action] for action in self.allowed_actions)
        )
        missing_resources = required_resources - set(self.allowed_resources)
        if (
            missing_resources
            and DelegationBlockingCode.MISSING_REQUIRED_RESOURCE
            not in self.blocking_issues
        ):
            raise ValueError(
                "actions missing their required resources must carry "
                "MISSING_REQUIRED_RESOURCE"
            )

        if any(item.blocking for item in self.uncertainties) and (
            DelegationBlockingCode.UNRESOLVED_MATERIAL_UNCERTAINTY
            not in self.blocking_issues
        ):
            raise ValueError(
                "blocking uncertainty requires UNRESOLVED_MATERIAL_UNCERTAINTY"
            )

        expected_bindings: set[tuple[DraftEvidenceField, str]] = set()
        if self.delegate_ref is not None:
            expected_bindings.add(
                (DraftEvidenceField.DELEGATE_REF, self.delegate_ref)
            )
        if self.relationship_code is not None:
            expected_bindings.add(
                (
                    DraftEvidenceField.RELATIONSHIP_CODE,
                    self.relationship_code.value,
                )
            )
        expected_bindings.update(
            (DraftEvidenceField.ALLOWED_ACTIONS, item.value)
            for item in self.allowed_actions
        )
        expected_bindings.update(
            (DraftEvidenceField.ALLOWED_RESOURCES, item.value)
            for item in self.allowed_resources
        )
        expected_bindings.update(
            (DraftEvidenceField.EXCLUDED_RESOURCES, item.value)
            for item in self.excluded_resources
        )
        expected_bindings.update(
            (DraftEvidenceField.ALLOWED_PURPOSES, item.value)
            for item in self.allowed_purposes
        )
        expected_bindings.update(
            (DraftEvidenceField.ALLOWED_AUDIENCES, item.value)
            for item in self.allowed_audiences
        )
        if self.valid_from is not None:
            expected_bindings.add(
                (DraftEvidenceField.VALID_FROM, self.valid_from.isoformat())
            )
        if self.valid_until is not None:
            expected_bindings.add(
                (DraftEvidenceField.VALID_UNTIL, self.valid_until.isoformat())
            )

        actual_bindings = {
            (binding.field_path, binding.value)
            for binding in self.evidence_bindings
        }
        if actual_bindings != expected_bindings:
            missing = sorted(
                f"{field.value}={value}"
                for field, value in expected_bindings - actual_bindings
            )
            unexpected = sorted(
                f"{field.value}={value}"
                for field, value in actual_bindings - expected_bindings
            )
            raise ValueError(
                "draft evidence bindings must exactly cover proposed values; "
                f"missing={missing}, unexpected={unexpected}"
            )
        return self


class ClarificationRequest(StrictModel):
    schema_version: Literal["caretrust.clarification-request.v1"]
    clarification_id: str
    intent_id: str
    draft_id: str
    code: ClarificationCode
    field_paths: tuple[str, ...]
    question: str
    options: tuple[str, ...]
    required: Literal[True]
    requested_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator(
        "clarification_id", "intent_id", "draft_id", "question"
    )(_nonblank)
    _unique_values = field_validator("field_paths", "options")(_unique_tuple)

    @model_validator(mode="after")
    def require_fields_and_options(self) -> ClarificationRequest:
        if not self.field_paths:
            raise ValueError("clarification must identify a field")
        if len(self.options) < 2:
            raise ValueError("clarification must provide at least two bounded options")
        if any(not item for item in self.options):
            raise ValueError("clarification options must not be blank")
        return self


class ClarificationResponse(StrictModel):
    schema_version: Literal["caretrust.clarification-response.v1"]
    response_id: str
    clarification_id: str
    intent_id: str
    patient_ref: str
    selected_values: tuple[str, ...]
    response_text: str
    response_sha256: str
    responded_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator(
        "response_id", "clarification_id", "intent_id", "response_text"
    )(_nonblank)
    _patient_opaque = field_validator("patient_ref")(_opaque_ref)
    _response_hash = field_validator("response_sha256")(_sha256_digest)
    _unique_values = field_validator("selected_values")(_unique_tuple)

    @model_validator(mode="after")
    def validate_response(self) -> ClarificationResponse:
        if not self.selected_values or any(not item for item in self.selected_values):
            raise ValueError("clarification response requires selected values")
        actual_hash = sha256(self.response_text.encode("utf-8")).hexdigest()
        if self.response_sha256 != actual_hash:
            raise ValueError("response_sha256 must hash the exact response_text")
        return self


class PatientInvite(StrictModel):
    """Single-use synthetic invite with no plaintext recipient contact."""

    schema_version: Literal["caretrust.patient-invite.v1"]
    invite_id: str
    patient_ref: str
    draft_id: str
    recipient_hint_sha256: str
    invite_token_sha256: str
    nonce_sha256: str
    delivery_channel: Literal["synthetic_out_of_band"]
    single_use: Literal[True]
    status: Literal["pending"]
    created_at: AwareDatetime
    expires_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator("invite_id", "draft_id")(_nonblank)
    _patient_opaque = field_validator("patient_ref")(_opaque_ref)
    _hashes = field_validator(
        "recipient_hint_sha256", "invite_token_sha256", "nonce_sha256"
    )(_sha256_digest)

    @model_validator(mode="after")
    def validate_expiry(self) -> PatientInvite:
        if self.expires_at <= self.created_at:
            raise ValueError("invite must expire after it is created")
        if len(
            {
                self.recipient_hint_sha256,
                self.invite_token_sha256,
                self.nonce_sha256,
            }
        ) != 3:
            raise ValueError(
                "recipient hint, invite token, and nonce hashes must differ"
            )
        return self


class InviteAcceptance(StrictModel):
    """Acceptance proves only control of a synthetic invited account."""

    schema_version: Literal["caretrust.invite-acceptance.v1"]
    acceptance_id: str
    invite_id: str
    patient_ref: str
    caregiver_ref: str
    invite_token_sha256: str
    nonce_sha256: str
    status: Literal["accepted"]
    identity_assurance: Literal["synthetic_account_only"]
    relationship_verified: Literal[False]
    patient_consent_established: Literal[False]
    delegation_activated: Literal[False]
    legal_authority_status: Literal["not_established"]
    accepted_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator("acceptance_id", "invite_id")(_nonblank)
    _refs_opaque = field_validator("patient_ref", "caregiver_ref")(_opaque_ref)
    _hashes = field_validator(
        "invite_token_sha256", "nonce_sha256"
    )(_sha256_digest)

    @model_validator(mode="after")
    def keep_subjects_separate(self) -> InviteAcceptance:
        if self.patient_ref == self.caregiver_ref:
            raise ValueError("patient and caregiver must be different subjects")
        return self


class PatientApprovalRecord(StrictModel):
    """Explicit patient approval bound to one final reviewed draft."""

    schema_version: Literal["caretrust.patient-approval-record.v1"]
    approval_id: str
    patient_ref: str
    final_draft_id: str
    invite_acceptance_id: str
    clarification_response_ids: tuple[str, ...]
    clarification_bundle_sha256: str
    intent_sha256: str
    final_draft_sha256: str
    decision: Literal["approved"]
    explicit_patient_action: Literal[True]
    approval_basis: Literal["patient_attestation"]
    legal_authority_status: Literal["not_established"]
    activation_permitted: Literal[False]
    authorization_permitted: Literal[False]
    approved_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator(
        "approval_id", "final_draft_id", "invite_acceptance_id"
    )(_nonblank)
    _patient_opaque = field_validator("patient_ref")(_opaque_ref)
    _hashes = field_validator(
        "clarification_bundle_sha256", "intent_sha256", "final_draft_sha256"
    )(_sha256_digest)
    _unique_clarifications = field_validator(
        "clarification_response_ids"
    )(_unique_tuple)

    @model_validator(mode="after")
    def validate_clarification_binding(self) -> PatientApprovalRecord:
        for response_id in self.clarification_response_ids:
            _opaque_ref(response_id)
        serialized_ids = "\n".join(self.clarification_response_ids)
        expected_hash = sha256(serialized_ids.encode("utf-8")).hexdigest()
        if self.clarification_bundle_sha256 != expected_hash:
            raise ValueError(
                "clarification_bundle_sha256 must bind the ordered response IDs"
            )
        return self


class CareRelationshipClaim(StrictModel):
    """Patient-attested relationship assertion without permission semantics."""

    schema_version: Literal["caretrust.care-relationship-claim.v1"]
    relationship_claim_id: str
    patient_ref: str
    caregiver_ref: str
    relationship_code: RelationshipCode
    relationship_basis: Literal["patient_attestation"]
    relationship_assertion_only: Literal[True]
    legal_authority_status: Literal["not_established"]
    invite_acceptance_id: str
    approval_id: str
    issuer_ref: str
    status: GrantStatus
    valid_from: date
    valid_until: date
    issued_at: AwareDatetime
    revoked_at: AwareDatetime | None = None
    synthetic: Literal[True]

    _ids_nonblank = field_validator(
        "relationship_claim_id", "invite_acceptance_id", "approval_id"
    )(_nonblank)
    _refs_opaque = field_validator(
        "patient_ref", "caregiver_ref", "issuer_ref"
    )(_opaque_ref)

    @model_validator(mode="after")
    def validate_relationship_lifecycle(self) -> CareRelationshipClaim:
        if self.patient_ref == self.caregiver_ref:
            raise ValueError("patient and caregiver must be different subjects")
        if self.valid_until < self.valid_from:
            raise ValueError("relationship valid_until must not precede valid_from")
        if self.status is GrantStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked relationship requires revoked_at")
        if self.status is not GrantStatus.REVOKED and self.revoked_at is not None:
            raise ValueError("only revoked relationship may carry revoked_at")
        return self


class DelegationGrant(StrictModel):
    """Patient-approved, least-privilege grant separate from relationship."""

    schema_version: Literal["caretrust.delegation-grant.v1"]
    grant_id: str
    relationship_claim_id: str
    approval_id: str
    patient_ref: str
    delegate_ref: str
    issuer_ref: str
    authority_basis: Literal["patient_attestation"]
    legal_authority_status: Literal["not_established"]
    status: GrantStatus
    allowed_actions: tuple[DelegationAction, ...]
    allowed_resources: tuple[DelegationResource, ...]
    excluded_resources: tuple[DelegationResource, ...]
    allowed_purposes: tuple[DelegationPurpose, ...]
    allowed_audiences: tuple[DelegationAudience, ...]
    application_decision_required: Literal[True]
    valid_from: date
    valid_until: date
    issued_at: AwareDatetime
    revoked_at: AwareDatetime | None = None
    synthetic: Literal[True]

    _ids_nonblank = field_validator(
        "grant_id", "relationship_claim_id", "approval_id"
    )(_nonblank)
    _refs_opaque = field_validator(
        "patient_ref", "delegate_ref", "issuer_ref"
    )(_opaque_ref)
    _unique_scope = field_validator(
        "allowed_actions",
        "allowed_resources",
        "excluded_resources",
        "allowed_purposes",
        "allowed_audiences",
    )(_unique_tuple)

    @model_validator(mode="after")
    def validate_grant(self) -> DelegationGrant:
        if self.patient_ref == self.delegate_ref:
            raise ValueError("patient and delegate must be different subjects")
        if not self.allowed_actions:
            raise ValueError("delegation grant requires an allowed action")
        if not self.allowed_resources:
            raise ValueError("delegation grant requires an allowed resource")
        if not self.allowed_purposes:
            raise ValueError("delegation grant requires an allowed purpose")
        if not self.allowed_audiences:
            raise ValueError("delegation grant requires an allowed audience")
        if self.valid_until < self.valid_from:
            raise ValueError("grant valid_until must not precede valid_from")

        overlap = set(self.allowed_resources) & set(self.excluded_resources)
        if overlap:
            raise ValueError(
                "excluded resources cannot also be allowed; exclusions win"
            )
        for action in self.allowed_actions:
            missing = ACTION_RESOURCE_REQUIREMENTS[action] - set(
                self.allowed_resources
            )
            if missing:
                raise ValueError(
                    f"{action.value} requires resources "
                    f"{sorted(item.value for item in missing)}"
                )

        if self.status is GrantStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked grant requires revoked_at")
        if self.status is not GrantStatus.REVOKED and self.revoked_at is not None:
            raise ValueError("only revoked grant may carry revoked_at")
        return self


class DelegationAuthorizationRequest(StrictModel):
    schema_version: Literal["caretrust.delegation-authorization-request.v1"]
    request_id: str
    grant_id: str
    patient_ref: str
    delegate_ref: str
    audience: DelegationAudience
    purpose: DelegationPurpose
    action: DelegationAction
    resource: DelegationResource
    requested_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator("request_id", "grant_id")(_nonblank)
    _refs_opaque = field_validator("patient_ref", "delegate_ref")(_opaque_ref)

    @model_validator(mode="after")
    def keep_subjects_separate(self) -> DelegationAuthorizationRequest:
        if self.patient_ref == self.delegate_ref:
            raise ValueError("patient and delegate must be different subjects")
        return self


class DelegationAuthorizationDecision(StrictModel):
    schema_version: Literal["caretrust.delegation-authorization-decision.v1"]
    decision_id: str
    request_id: str
    decision: DelegationDecisionValue
    reason_codes: tuple[DelegationReasonCode, ...]
    supporting_grant_ids: tuple[str, ...]
    policy_version: Literal["caretrust.delegation-authorization.v1"]
    decided_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator("decision_id", "request_id")(_nonblank)
    _unique_values = field_validator(
        "reason_codes", "supporting_grant_ids"
    )(_unique_tuple)

    @model_validator(mode="after")
    def validate_decision(self) -> DelegationAuthorizationDecision:
        if not self.reason_codes:
            raise ValueError("delegation decision requires a reason code")
        for grant_id in self.supporting_grant_ids:
            _opaque_ref(grant_id)
        if self.decision is DelegationDecisionValue.PERMIT:
            if len(self.supporting_grant_ids) != 1:
                raise ValueError("permit requires exactly one supporting grant")
            if self.reason_codes != (
                DelegationReasonCode.POLICY_REQUIREMENTS_SATISFIED,
            ):
                raise ValueError(
                    "permit requires only POLICY_REQUIREMENTS_SATISFIED"
                )
        elif self.supporting_grant_ids:
            raise ValueError("deny decision cannot carry supporting grants")
        return self


class DelegationRevocationRecord(StrictModel):
    schema_version: Literal["caretrust.delegation-revocation-record.v1"]
    revocation_id: str
    grant_id: str
    patient_ref: str
    actor_ref: str
    target_type: Literal["delegation_grant"]
    reason_code: Literal["PATIENT_REVOKED_DELEGATION"]
    reason: str
    revoked_at: AwareDatetime
    synthetic: Literal[True]

    _ids_nonblank = field_validator("revocation_id", "grant_id", "reason")(
        _nonblank
    )
    _refs_opaque = field_validator("patient_ref", "actor_ref")(_opaque_ref)

    @model_validator(mode="after")
    def require_patient_actor(self) -> DelegationRevocationRecord:
        if self.actor_ref != self.patient_ref:
            raise ValueError("patient-directed revocation requires patient actor")
        return self


DELEGATION_CONTRACTS = (
    IntentStatement,
    DelegationDraft,
    ClarificationRequest,
    ClarificationResponse,
    PatientInvite,
    InviteAcceptance,
    PatientApprovalRecord,
    CareRelationshipClaim,
    DelegationGrant,
    DelegationAuthorizationRequest,
    DelegationAuthorizationDecision,
    DelegationRevocationRecord,
)
