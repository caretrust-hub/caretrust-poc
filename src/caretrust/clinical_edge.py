"""Bounded synthetic HIE/EHR clinical-data authorization edge.

CareTrust supplies a delegation/trust context to a data holder.  The data
holder, not CareTrust, owns patient matching and the final disclosure policy.
This module performs no network call and contains no live HIE or EHR adapter.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal, Mapping
from urllib.parse import urlparse

from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.models import StrictModel


class ClinicalContextStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PatientMatchStatus(StrEnum):
    MATCHED = "matched"
    NO_MATCH = "no_match"
    NOT_ATTEMPTED = "not_attempted"


class ClinicalDataDecisionValue(StrEnum):
    PERMIT = "permit"
    DENY = "deny"


class ClinicalDataReasonCode(StrEnum):
    DATA_HOLDER_POLICY_SATISFIED = "DATA_HOLDER_POLICY_SATISFIED"
    PARTICIPANT_NOT_ELIGIBLE = "PARTICIPANT_NOT_ELIGIBLE"
    CLIENT_NOT_REGISTERED = "CLIENT_NOT_REGISTERED"
    AUTHORIZED_USER_NOT_ELIGIBLE = "AUTHORIZED_USER_NOT_ELIGIBLE"
    PATIENT_NO_MATCH = "PATIENT_NO_MATCH"
    CARETRUST_CONTEXT_NOT_ACTIVE = "CARETRUST_CONTEXT_NOT_ACTIVE"
    CARETRUST_CONTEXT_REVOKED = "CARETRUST_CONTEXT_REVOKED"
    CARETRUST_CONTEXT_EXPIRED = "CARETRUST_CONTEXT_EXPIRED"
    INSUFFICIENT_DELEGATED_SCOPE = "INSUFFICIENT_DELEGATED_SCOPE"
    DATA_HOLDER_POLICY_DENIED = "DATA_HOLDER_POLICY_DENIED"


def _nonblank(value: str) -> str:
    if not value:
        raise ValueError("value must not be blank")
    return value


def _opaque_ref(value: str) -> str:
    _nonblank(value)
    if ":" not in value or any(char.isspace() for char in value) or "@" in value:
        raise ValueError("value must be an opaque non-contact reference")
    return value


def _unique_nonblank(values: tuple[str, ...]) -> tuple[str, ...]:
    if not values or any(not value for value in values):
        raise ValueError("value must contain unique nonblank entries")
    if len(values) != len(set(values)):
        raise ValueError("value must not contain duplicates")
    return values


def _clinical_scopes(values: tuple[str, ...]) -> tuple[str, ...]:
    _unique_nonblank(values)
    allowed = {
        "patient/Appointment.rs",
        "patient/CarePlan.rs",
        "patient/Observation.rs",
    }
    if not set(values) <= allowed:
        raise ValueError("unsupported synthetic clinical scope")
    return values


def _synthetic_endpoint(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or not (
            parsed.hostname.endswith(".invalid")
            or parsed.hostname.endswith(".example")
        )
    ):
        raise ValueError(
            "data holder must use a synthetic HTTPS .invalid or .example endpoint"
        )
    return value


class CareTrustClinicalContext(StrictModel):
    """Projection of CareTrust trust/delegation facts, not a disclosure grant."""

    schema_version: Literal["caretrust.clinical-context.v1"]
    context_id: str
    relationship_claim_id: str
    delegation_grant_id: str
    delegation_decision_id: str
    patient_ref: str
    caregiver_ref: str
    status: ClinicalContextStatus
    allowed_data_holders: tuple[str, ...]
    allowed_purposes: tuple[Literal["care_coordination"], ...]
    allowed_fhir_resource_types: tuple[
        Literal["Appointment", "CarePlan", "Observation"], ...
    ]
    allowed_scopes: tuple[str, ...]
    valid_from: date
    valid_until: date
    verified_at: AwareDatetime
    revoked_at: AwareDatetime | None = None
    caretrust_role: Literal["delegation_and_trust_context_only"]
    patient_match_authority: Literal["data_holder"]
    disclosure_policy_authority: Literal["data_holder"]
    legal_authority_status: Literal["not_established"]
    synthetic: Literal[True]

    _ids_opaque = field_validator(
        "context_id",
        "relationship_claim_id",
        "delegation_grant_id",
        "delegation_decision_id",
        "patient_ref",
        "caregiver_ref",
    )(_opaque_ref)
    _unique_values = field_validator(
        "allowed_data_holders",
        "allowed_purposes",
        "allowed_fhir_resource_types",
        "allowed_scopes",
    )(_unique_nonblank)
    _synthetic_holders = field_validator("allowed_data_holders")(
        lambda values: tuple(_synthetic_endpoint(value) for value in values)
    )
    _supported_scopes = field_validator("allowed_scopes")(_clinical_scopes)

    @model_validator(mode="after")
    def validate_context_lifecycle(self) -> CareTrustClinicalContext:
        if self.patient_ref == self.caregiver_ref:
            raise ValueError("patient and caregiver must be different subjects")
        if self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        if self.status is ClinicalContextStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked context requires revoked_at")
        if self.status is not ClinicalContextStatus.REVOKED and self.revoked_at:
            raise ValueError("only revoked context may carry revoked_at")
        return self


class ClinicalDataAuthorizationRequest(StrictModel):
    """One fresh participant-application request delivered to a data holder."""

    schema_version: Literal["caretrust.clinical-data-authorization-request.v1"]
    request_id: str
    data_holder_id: str
    participant_org_ref: str
    authorized_user_ref: str
    client_id: str
    requesting_actor_role: Literal["authorized_participant_user"]
    clinical_data_recipient: Literal["authorized_participant_application"]
    caregiver_ref: str
    caregiver_is_requesting_actor: Literal[False]
    patient_match_hint: str
    purpose: Literal["care_coordination"]
    requested_fhir_resource_types: tuple[
        Literal["Appointment", "CarePlan", "Observation"], ...
    ]
    requested_scopes: tuple[str, ...]
    caretrust_context: CareTrustClinicalContext
    prior_request_id: str | None = None
    requested_at: AwareDatetime
    patient_match_requested: Literal[True]
    final_disclosure_decision_requested: Literal[True]
    synthetic: Literal[True]

    _opaque_fields = field_validator(
        "request_id",
        "participant_org_ref",
        "authorized_user_ref",
        "caregiver_ref",
        "patient_match_hint",
    )(_opaque_ref)
    _data_holder_synthetic = field_validator("data_holder_id")(
        _synthetic_endpoint
    )
    _client_synthetic = field_validator("client_id")(_synthetic_endpoint)
    _unique_values = field_validator(
        "requested_fhir_resource_types", "requested_scopes"
    )(_unique_nonblank)
    _supported_scopes = field_validator("requested_scopes")(_clinical_scopes)

    @field_validator("prior_request_id")
    @classmethod
    def validate_prior_request_id(cls, value: str | None) -> str | None:
        return None if value is None else _opaque_ref(value)

    @model_validator(mode="after")
    def validate_context_binding(self) -> ClinicalDataAuthorizationRequest:
        context = self.caretrust_context
        if self.authorized_user_ref == self.caregiver_ref:
            raise ValueError(
                "caregiver cannot be the participant application's authorized user"
            )
        if self.caregiver_ref != context.caregiver_ref:
            raise ValueError("request caregiver must match CareTrust context")
        if self.patient_match_hint != context.patient_ref:
            raise ValueError("patient hint must match the CareTrust context reference")
        if self.data_holder_id not in context.allowed_data_holders:
            raise ValueError("request data holder is outside the CareTrust context")
        if self.prior_request_id == self.request_id:
            raise ValueError("fresh request cannot reference itself")
        return self


class PatientMatchResult(StrictModel):
    """Patient-match result owned and produced by the synthetic data holder."""

    schema_version: Literal["caretrust.patient-match-result.v1"]
    match_id: str
    request_id: str
    data_holder_id: str
    status: PatientMatchStatus
    local_patient_ref: str | None = None
    method: Literal[
        "synthetic_data_holder_index",
        "not_attempted_requesting_party_gate",
        "not_attempted_caretrust_context_gate",
    ]
    authority: Literal["data_holder"]
    match_inputs_disclosed_to_caretrust: Literal[False]
    performed_at: AwareDatetime
    synthetic: Literal[True]

    _ids_opaque = field_validator("match_id", "request_id")(_opaque_ref)
    _data_holder_synthetic = field_validator("data_holder_id")(
        _synthetic_endpoint
    )

    @model_validator(mode="after")
    def validate_match_result(self) -> PatientMatchResult:
        if self.status is PatientMatchStatus.MATCHED:
            if self.local_patient_ref is None:
                raise ValueError("matched result requires local_patient_ref")
            _nonblank(self.local_patient_ref)
        elif self.local_patient_ref is not None:
            raise ValueError("unmatched result cannot disclose local_patient_ref")
        return self


class ClinicalDataAuthorizationDecision(StrictModel):
    """Final clinical-data disclosure decision made by the data holder."""

    schema_version: Literal["caretrust.clinical-data-authorization-decision.v1"]
    decision_id: str
    request_id: str
    patient_match_id: str
    data_holder_id: str
    participant_org_ref: str
    authorized_user_ref: str
    client_id: str
    decision: ClinicalDataDecisionValue
    reason_codes: tuple[ClinicalDataReasonCode, ...]
    granted_fhir_resource_types: tuple[str, ...]
    granted_scopes: tuple[str, ...]
    supporting_caretrust_context_ids: tuple[str, ...]
    policy_version: Literal["synthetic.data-holder.disclosure.v1"]
    patient_match_authority: Literal["data_holder"]
    requesting_party_eligibility_authority: Literal["data_holder"]
    disclosure_policy_authority: Literal["data_holder"]
    caretrust_role: Literal["delegation_and_trust_context_only"]
    fhir_bundle_included: bool
    decided_at: AwareDatetime
    synthetic: Literal[True]

    _ids_opaque = field_validator(
        "decision_id", "request_id", "patient_match_id"
    )(_opaque_ref)
    _data_holder_synthetic = field_validator("data_holder_id")(
        _synthetic_endpoint
    )
    _client_synthetic = field_validator("client_id")(_synthetic_endpoint)
    _requesting_refs_opaque = field_validator(
        "participant_org_ref", "authorized_user_ref"
    )(_opaque_ref)
    _unique_values = field_validator(
        "granted_fhir_resource_types",
        "granted_scopes",
        "supporting_caretrust_context_ids",
    )(
        lambda values: (
            values
            if not values
            else _unique_nonblank(values)
        )
    )

    @model_validator(mode="after")
    def validate_decision(self) -> ClinicalDataAuthorizationDecision:
        if not self.reason_codes:
            raise ValueError("decision requires a reason code")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason codes must be unique")
        if self.decision is ClinicalDataDecisionValue.PERMIT:
            if self.reason_codes != (
                ClinicalDataReasonCode.DATA_HOLDER_POLICY_SATISFIED,
            ):
                raise ValueError(
                    "permit requires only DATA_HOLDER_POLICY_SATISFIED"
                )
            if (
                not self.granted_fhir_resource_types
                or not self.granted_scopes
                or len(self.supporting_caretrust_context_ids) != 1
                or not self.fhir_bundle_included
            ):
                raise ValueError(
                    "permit requires grants, one context, and a FHIR bundle"
                )
        elif (
            self.granted_fhir_resource_types
            or self.granted_scopes
            or self.supporting_caretrust_context_ids
            or self.fhir_bundle_included
        ):
            raise ValueError("deny cannot carry grants, context support, or data")
        return self


class FhirReference(StrictModel):
    reference: str

    _reference_nonblank = field_validator("reference")(_nonblank)


class FhirCoding(StrictModel):
    system: str
    code: str
    display: str

    _values_nonblank = field_validator("system", "code", "display")(_nonblank)


class FhirMeta(StrictModel):
    tag: tuple[FhirCoding, ...]

    @model_validator(mode="after")
    def require_synthetic_tag(self) -> FhirMeta:
        if not any(
            item.system
            == "https://caretrust.example/fhir/CodeSystem/data-classification"
            and item.code == "synthetic"
            for item in self.tag
        ):
            raise ValueError("FHIR fixture must carry the synthetic data tag")
        return self


class SyntheticFhirR4CarePlan(StrictModel):
    """Strict local subset of a synthetic FHIR R4 CarePlan."""

    resourceType: Literal["CarePlan"]
    id: str
    status: Literal["active"]
    intent: Literal["plan"]
    subject: FhirReference
    title: str
    description: str

    _text_nonblank = field_validator("id", "title", "description")(_nonblank)


class SyntheticFhirR4BundleEntry(StrictModel):
    fullUrl: str
    resource: SyntheticFhirR4CarePlan

    _url_synthetic = field_validator("fullUrl")(_synthetic_endpoint)


class SyntheticFhirR4Bundle(StrictModel):
    """Strict local FHIR R4-shaped collection; not a conformance claim."""

    resourceType: Literal["Bundle"]
    id: str
    meta: FhirMeta
    type: Literal["collection"]
    timestamp: AwareDatetime
    entry: tuple[SyntheticFhirR4BundleEntry, ...]

    _id_nonblank = field_validator("id")(_nonblank)

    @model_validator(mode="after")
    def validate_bundle(self) -> SyntheticFhirR4Bundle:
        if not self.entry:
            raise ValueError("permit bundle must contain at least one entry")
        urls = [entry.fullUrl for entry in self.entry]
        if len(urls) != len(set(urls)):
            raise ValueError("bundle fullUrl values must be unique")
        return self


class ClinicalDataExchangeRecord(StrictModel):
    """Complete synthetic request/match/decision/data-holder exchange record."""

    record_type: Literal["caretrust.synthetic-clinical-data-edge.v1"]
    request: ClinicalDataAuthorizationRequest
    patient_match: PatientMatchResult
    decision: ClinicalDataAuthorizationDecision
    returned_fhir_bundle: SyntheticFhirR4Bundle | None = None
    network_calls: Literal[False]
    live_hie_or_ehr_connected: Literal[False]
    synthetic: Literal[True]

    @model_validator(mode="after")
    def validate_linkage(self) -> ClinicalDataExchangeRecord:
        request = self.request
        match = self.patient_match
        decision = self.decision
        if match.request_id != request.request_id:
            raise ValueError("patient match must link to request")
        if decision.request_id != request.request_id:
            raise ValueError("decision must link to request")
        if decision.patient_match_id != match.match_id:
            raise ValueError("decision must link to patient match")
        if (
            decision.participant_org_ref != request.participant_org_ref
            or decision.authorized_user_ref != request.authorized_user_ref
            or decision.client_id != request.client_id
        ):
            raise ValueError("decision must bind the requesting participant")
        if not (
            request.data_holder_id
            == match.data_holder_id
            == decision.data_holder_id
        ):
            raise ValueError("one data holder must own match and decision")
        if decision.decision is ClinicalDataDecisionValue.PERMIT:
            if match.status is not PatientMatchStatus.MATCHED:
                raise ValueError("permit requires a data-holder patient match")
            if self.returned_fhir_bundle is None:
                raise ValueError("permit requires returned FHIR bundle")
            expected_subject = match.local_patient_ref
            if any(
                entry.resource.subject.reference != expected_subject
                for entry in self.returned_fhir_bundle.entry
            ):
                raise ValueError("returned resources must reference matched patient")
            resource_types = {
                entry.resource.resourceType
                for entry in self.returned_fhir_bundle.entry
            }
            if not resource_types <= set(decision.granted_fhir_resource_types):
                raise ValueError("bundle exceeds granted FHIR resource types")
        elif self.returned_fhir_bundle is not None:
            raise ValueError("denied exchange cannot return FHIR data")
        return self


class SyntheticClinicalDataHolderAdapter:
    """Deterministic data-holder-owned match and disclosure policy fixture."""

    def __init__(
        self,
        *,
        data_holder_id: str,
        patient_index: Mapping[str, str],
        care_plan_by_local_patient: Mapping[str, SyntheticFhirR4Bundle],
        eligible_participant_orgs: frozenset[str],
        registered_clients_by_participant: Mapping[str, frozenset[str]],
        authorized_users_by_participant: Mapping[str, frozenset[str]],
        allowed_purposes: frozenset[str] = frozenset({"care_coordination"}),
        allowed_resource_types: frozenset[str] = frozenset({"CarePlan"}),
        allowed_scopes: frozenset[str] = frozenset({"patient/CarePlan.rs"}),
    ) -> None:
        self.data_holder_id = _synthetic_endpoint(data_holder_id)
        self.patient_index = dict(patient_index)
        self.care_plan_by_local_patient = dict(care_plan_by_local_patient)
        self.eligible_participant_orgs = frozenset(
            _opaque_ref(value) for value in eligible_participant_orgs
        )
        self.registered_clients_by_participant = {
            _opaque_ref(participant): frozenset(
                _synthetic_endpoint(client) for client in clients
            )
            for participant, clients in registered_clients_by_participant.items()
        }
        self.authorized_users_by_participant = {
            _opaque_ref(participant): frozenset(
                _opaque_ref(user) for user in users
            )
            for participant, users in authorized_users_by_participant.items()
        }
        self.allowed_purposes = allowed_purposes
        self.allowed_resource_types = allowed_resource_types
        self.allowed_scopes = allowed_scopes

    def decide(
        self,
        request: ClinicalDataAuthorizationRequest,
        *,
        now: datetime,
    ) -> ClinicalDataExchangeRecord:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        now = now.astimezone(UTC)
        if request.data_holder_id != self.data_holder_id:
            raise ValueError("request targets a different data holder")

        context = request.caretrust_context
        reasons: tuple[ClinicalDataReasonCode, ...]
        match_status = PatientMatchStatus.NOT_ATTEMPTED
        local_patient_ref: str | None = None
        match_method: Literal[
            "synthetic_data_holder_index",
            "not_attempted_requesting_party_gate",
            "not_attempted_caretrust_context_gate",
        ] = "not_attempted_requesting_party_gate"

        if request.participant_org_ref not in self.eligible_participant_orgs:
            reasons = (ClinicalDataReasonCode.PARTICIPANT_NOT_ELIGIBLE,)
        elif request.client_id not in self.registered_clients_by_participant.get(
            request.participant_org_ref, frozenset()
        ):
            reasons = (ClinicalDataReasonCode.CLIENT_NOT_REGISTERED,)
        elif request.authorized_user_ref not in self.authorized_users_by_participant.get(
            request.participant_org_ref, frozenset()
        ):
            reasons = (ClinicalDataReasonCode.AUTHORIZED_USER_NOT_ELIGIBLE,)
        elif context.status is ClinicalContextStatus.REVOKED:
            match_method = "not_attempted_caretrust_context_gate"
            reasons = (ClinicalDataReasonCode.CARETRUST_CONTEXT_REVOKED,)
        elif context.status is not ClinicalContextStatus.ACTIVE:
            match_method = "not_attempted_caretrust_context_gate"
            reasons = (ClinicalDataReasonCode.CARETRUST_CONTEXT_NOT_ACTIVE,)
        elif now.date() < context.valid_from or now.date() > context.valid_until:
            match_method = "not_attempted_caretrust_context_gate"
            reasons = (ClinicalDataReasonCode.CARETRUST_CONTEXT_EXPIRED,)
        else:
            match_method = "synthetic_data_holder_index"
            local_patient_ref = self.patient_index.get(request.patient_match_hint)
            if local_patient_ref is None:
                match_status = PatientMatchStatus.NO_MATCH
                reasons = (ClinicalDataReasonCode.PATIENT_NO_MATCH,)
            else:
                match_status = PatientMatchStatus.MATCHED
                requested_types = set(request.requested_fhir_resource_types)
                requested_scopes = set(request.requested_scopes)
                if (
                    not requested_types
                    <= set(context.allowed_fhir_resource_types)
                    or not requested_scopes <= set(context.allowed_scopes)
                ):
                    reasons = (
                        ClinicalDataReasonCode.INSUFFICIENT_DELEGATED_SCOPE,
                    )
                elif (
                    request.purpose not in self.allowed_purposes
                    or not requested_types <= self.allowed_resource_types
                    or not requested_scopes <= self.allowed_scopes
                ):
                    reasons = (ClinicalDataReasonCode.DATA_HOLDER_POLICY_DENIED,)
                else:
                    reasons = (
                        ClinicalDataReasonCode.DATA_HOLDER_POLICY_SATISFIED,
                    )

        match = PatientMatchResult(
            schema_version="caretrust.patient-match-result.v1",
            match_id=f"match:{request.request_id.removeprefix('request:')}",
            request_id=request.request_id,
            data_holder_id=self.data_holder_id,
            status=match_status,
            local_patient_ref=local_patient_ref,
            method=match_method,
            authority="data_holder",
            match_inputs_disclosed_to_caretrust=False,
            performed_at=now,
            synthetic=True,
        )
        permitted = reasons == (
            ClinicalDataReasonCode.DATA_HOLDER_POLICY_SATISFIED,
        )
        decision_material = "|".join((request.request_id, *(item.value for item in reasons)))
        decision = ClinicalDataAuthorizationDecision(
            schema_version="caretrust.clinical-data-authorization-decision.v1",
            decision_id=(
                "decision:clinical:"
                + sha256(decision_material.encode("utf-8")).hexdigest()[:20]
            ),
            request_id=request.request_id,
            patient_match_id=match.match_id,
            data_holder_id=self.data_holder_id,
            participant_org_ref=request.participant_org_ref,
            authorized_user_ref=request.authorized_user_ref,
            client_id=request.client_id,
            decision=(
                ClinicalDataDecisionValue.PERMIT
                if permitted
                else ClinicalDataDecisionValue.DENY
            ),
            reason_codes=reasons,
            granted_fhir_resource_types=(
                request.requested_fhir_resource_types if permitted else ()
            ),
            granted_scopes=request.requested_scopes if permitted else (),
            supporting_caretrust_context_ids=(
                (context.context_id,) if permitted else ()
            ),
            policy_version="synthetic.data-holder.disclosure.v1",
            patient_match_authority="data_holder",
            requesting_party_eligibility_authority="data_holder",
            disclosure_policy_authority="data_holder",
            caretrust_role="delegation_and_trust_context_only",
            fhir_bundle_included=permitted,
            decided_at=now,
            synthetic=True,
        )
        bundle = (
            self.care_plan_by_local_patient.get(local_patient_ref)
            if permitted and local_patient_ref is not None
            else None
        )
        if permitted and bundle is None:
            raise ValueError("synthetic data holder has no permitted bundle")
        return ClinicalDataExchangeRecord(
            record_type="caretrust.synthetic-clinical-data-edge.v1",
            request=request,
            patient_match=match,
            decision=decision,
            returned_fhir_bundle=bundle,
            network_calls=False,
            live_hie_or_ehr_connected=False,
            synthetic=True,
        )
