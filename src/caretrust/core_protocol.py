"""Executable, strict CareTrust Core 0.1 contracts.

This module is a small runtime bridge for the published Core JSON Schemas.  It
does not evaluate policy or issue authority: callers must provide an already
made decision or an already existing artifact.  Hashes use the RFC 8785 JSON
canonicalization profile named by the Core schemas.  The supported JSON domain
intentionally excludes floats, avoiding non-portable number rendering.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any, Literal

from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.models import StrictModel


CORE_VERSION = "0.1"
CANONICALIZATION_URI = "urn:ietf:rfc:8785"
MESSAGE_ENVELOPE_SCHEMA_URI = "urn:caretrust:schema:core:message-envelope:0.1"
TRUST_ARTIFACT_SCHEMA_URI = "urn:caretrust:schema:core:trust-artifact:0.1"
AUTHORIZATION_REQUEST_SCHEMA_URI = "urn:caretrust:schema:core:authorization-request:0.1"
AUTHORIZATION_DECISION_SCHEMA_URI = "urn:caretrust:schema:core:authorization-decision:0.1"
STATUS_EVENT_SCHEMA_URI = "urn:caretrust:schema:core:status-event:0.1"

_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+$")


def _uri(value: str) -> str:
    if not _URI.fullmatch(value):
        raise ValueError("value must be a non-empty absolute URI")
    return value


def _optional_uri(value: str | None) -> str | None:
    return None if value is None else _uri(value)


def _rfc3339(value: datetime | str) -> datetime | str:
    if not isinstance(value, (datetime, str)):
        raise ValueError("value must be an RFC 3339 date-time string")
    if isinstance(value, str):
        # The JSON Schema uses RFC 3339's date-time form, not a bare date.
        if "T" not in value or not (value.endswith("Z") or re.search(r"[+-]\d\d:\d\d$", value)):
            raise ValueError("value must be an RFC 3339 date-time with an offset")
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("value must be timezone-aware")
    return value.astimezone(UTC)


def _unique(values: tuple[object, ...]) -> tuple[object, ...]:
    if len(values) != len(set(values)):
        raise ValueError("values must be unique")
    return values


def _json_string(value: str) -> str:
    """Reject Unicode surrogate code points, which RFC 8785 does not permit."""

    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("canonical JSON strings must contain valid Unicode scalar values")
    return value


def _json_value(value: Any) -> Any:
    """Return a JSON-only value accepted by the deterministic hash profile."""

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, int):
        # RFC 8785 uses ECMAScript number serialization.  Restricting this
        # bridge to exactly representable integers makes Python's decimal
        # spelling identical without pretending to support the full binary64
        # formatting algorithm.
        if not -(2**53 - 1) <= value <= 2**53 - 1:
            raise ValueError("canonical JSON integers must be IEEE-754 safe integers")
        return value
    if isinstance(value, float):
        raise ValueError("floats are not accepted by the Core canonical hash helper")
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("canonical JSON object keys must be strings")
        return {_json_string(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, StrictModel):
        return _json_value(value.model_dump(mode="json"))
    raise ValueError(f"unsupported canonical JSON value: {type(value)!r}")


def _serialize_canonical(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_serialize_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        # RFC 8785 sorts object property names by their UTF-16 code units,
        # including the unescaped property name.  Python's normal key sort is
        # by Unicode code point and differs for supplementary-plane characters.
        ordered = sorted(value, key=lambda key: key.encode("utf-16-be"))
        return (
            "{"
            + ",".join(
                f"{_serialize_canonical(key)}:{_serialize_canonical(value[key])}"
                for key in ordered
            )
            + "}"
        )
    raise ValueError(f"unsupported normalized JSON value: {type(value)!r}")


def canonical_json(value: Any) -> bytes:
    """Serialize the supported JSON subset exactly as RFC 8785 requires.

    The bridge accepts valid Unicode strings, IEEE-754-safe integers, booleans,
    null, arrays, and objects.  Floats and larger integers are rejected so this
    helper never claims coverage of number forms it does not implement.
    """

    normalized = _json_value(value)
    return _serialize_canonical(normalized).encode("utf-8")


class CanonicalHash(StrictModel):
    algorithm: Literal["sha-256"]
    canonicalization: Literal["urn:ietf:rfc:8785"]
    value: str

    @field_validator("value")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        normalized = value.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("value must be a lowercase 64-character SHA-256 digest")
        return normalized


def canonical_hash(value: Any) -> CanonicalHash:
    return CanonicalHash(
        algorithm="sha-256",
        canonicalization=CANONICALIZATION_URI,
        value=sha256(canonical_json(value)).hexdigest(),
    )


class ArtifactReference(StrictModel):
    artifact_id: str
    artifact_type: str
    version: int
    content_hash: CanonicalHash

    _uri_fields = field_validator("artifact_id", "artifact_type")(_uri)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("version must be at least one")
        return value


class ProvenanceReference(StrictModel):
    source_ref: str
    relationship: str
    recorded_at: AwareDatetime
    content_hash: CanonicalHash | None = None

    _uri_fields = field_validator("source_ref", "relationship")(_uri)
    _time_format = field_validator("recorded_at", mode="before")(_rfc3339)
    _time_utc = field_validator("recorded_at")(_utc)


class MessageEnvelope(StrictModel):
    schema_uri: Literal["urn:caretrust:schema:core:message-envelope:0.1"]
    profile_uri: Literal["urn:caretrust:profile:core:message-envelope:0.1"]
    spec_version: Literal["0.1"]
    message_id: str
    message_type: str
    sender_ref: str
    receiver_ref: str
    sent_at: AwareDatetime
    trace_id: str
    correlation_id: str | None = None
    payload_schema_uri: str
    payload_hash: CanonicalHash
    payload: dict[str, Any]

    _uri_fields = field_validator(
        "message_id", "message_type", "sender_ref", "receiver_ref", "trace_id", "payload_schema_uri"
    )(_uri)
    _correlation_uri = field_validator("correlation_id")(_optional_uri)
    _time_format = field_validator("sent_at", mode="before")(_rfc3339)
    _time_utc = field_validator("sent_at")(_utc)

    @model_validator(mode="after")
    def bind_payload_hash(self) -> "MessageEnvelope":
        if self.payload_hash != canonical_hash(self.payload):
            raise ValueError("payload_hash must bind the exact canonical payload")
        return self


class TrustArtifact(StrictModel):
    schema_uri: Literal["urn:caretrust:schema:core:trust-artifact:0.1"]
    profile_uri: str
    spec_version: Literal["0.1"]
    artifact_id: str
    artifact_type: str
    version: int
    issuer_ref: str
    subject_refs: tuple[str, ...]
    issued_at: AwareDatetime
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    status: Literal["draft", "active", "suspended", "revoked", "expired", "superseded"]
    status_ref: str
    previous_version_ref: ArtifactReference | None = None
    provenance_refs: tuple[ProvenanceReference, ...]
    payload_schema_uri: str
    payload_hash: CanonicalHash
    payload: dict[str, Any]

    _uri_fields = field_validator(
        "profile_uri", "artifact_id", "artifact_type", "issuer_ref", "status_ref", "payload_schema_uri"
    )(_uri)
    _subject_uri = field_validator("subject_refs")(lambda values: tuple(_uri(item) for item in values))
    _time_format = field_validator("issued_at", "valid_from", "valid_until", mode="before")(_rfc3339)
    _time_utc = field_validator("issued_at", "valid_from", "valid_until")(_utc)
    _unique_subjects = field_validator("subject_refs")(_unique)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("version must be at least one")
        return value

    @model_validator(mode="after")
    def validate_temporal_and_hash_binding(self) -> "TrustArtifact":
        if not self.subject_refs:
            raise ValueError("subject_refs must contain at least one subject")
        if not self.provenance_refs:
            raise ValueError("provenance_refs must contain at least one reference")
        if self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        if self.payload_hash != canonical_hash(self.payload):
            raise ValueError("payload_hash must bind the exact canonical payload")
        return self

    def reference(self) -> ArtifactReference:
        return ArtifactReference(
            artifact_id=self.artifact_id,
            artifact_type=self.artifact_type,
            version=self.version,
            content_hash=self.payload_hash,
        )


class AuthorizationRequest(StrictModel):
    schema_uri: Literal["urn:caretrust:schema:core:authorization-request:0.1"]
    profile_uri: Literal["urn:caretrust:profile:core:authorization:0.1"]
    spec_version: Literal["0.1"]
    request_id: str
    requester_ref: str
    subject_ref: str
    audience: str
    purpose: str
    action: str
    resource: str
    referenced_artifact_refs: tuple[ArtifactReference, ...]
    requested_at: AwareDatetime
    expires_at: AwareDatetime
    nonce: str
    idempotency_key: str

    _uri_fields = field_validator(
        "request_id", "requester_ref", "subject_ref", "audience", "purpose", "action", "resource"
    )(_uri)
    _time_format = field_validator("requested_at", "expires_at", mode="before")(_rfc3339)
    _time_utc = field_validator("requested_at", "expires_at")(_utc)

    @field_validator("nonce", "idempotency_key")
    @classmethod
    def validate_replay_value(cls, value: str) -> str:
        if not 16 <= len(value) <= 256:
            raise ValueError("nonce and idempotency_key must be 16 to 256 characters")
        return value

    @model_validator(mode="after")
    def validate_temporal_and_refs(self) -> "AuthorizationRequest":
        if self.expires_at <= self.requested_at:
            raise ValueError("expires_at must follow requested_at")
        references = tuple(
            (item.artifact_id, item.artifact_type, item.version, item.content_hash.value)
            for item in self.referenced_artifact_refs
        )
        if len(references) != len(set(references)):
            raise ValueError("referenced_artifact_refs must be unique")
        return self


class AuthorizationDecision(StrictModel):
    schema_uri: Literal["urn:caretrust:schema:core:authorization-decision:0.1"]
    profile_uri: Literal["urn:caretrust:profile:core:authorization:0.1"]
    spec_version: Literal["0.1"]
    decision_id: str
    request_id: str
    issuer_ref: str
    decision: Literal["permit", "deny"]
    reason_codes: tuple[str, ...]
    supporting_artifact_refs: tuple[ArtifactReference, ...]
    request_hash: CanonicalHash
    policy_uri: str
    policy_version: str
    status_checked_at: AwareDatetime
    decided_at: AwareDatetime
    expires_at: AwareDatetime

    _uri_fields = field_validator("decision_id", "request_id", "issuer_ref", "policy_uri")(_uri)
    _reason_uri = field_validator("reason_codes")(lambda values: tuple(_uri(item) for item in values))
    _time_format = field_validator("status_checked_at", "decided_at", "expires_at", mode="before")(_rfc3339)
    _time_utc = field_validator("status_checked_at", "decided_at", "expires_at")(_utc)
    _unique_reasons = field_validator("reason_codes")(_unique)

    @field_validator("policy_version")
    @classmethod
    def validate_policy_version(cls, value: str) -> str:
        if not value:
            raise ValueError("policy_version must not be blank")
        return value

    @model_validator(mode="after")
    def validate_default_deny_shape(self) -> "AuthorizationDecision":
        if not self.reason_codes:
            raise ValueError("reason_codes must contain at least one reason")
        if self.decision == "permit" and not self.supporting_artifact_refs:
            raise ValueError("permit requires supporting_artifact_refs")
        if self.status_checked_at > self.decided_at or self.expires_at <= self.decided_at:
            raise ValueError("decision times must be status_checked_at <= decided_at < expires_at")
        return self

    @classmethod
    def for_request(cls, *, request: AuthorizationRequest, **values: Any) -> "AuthorizationDecision":
        """Construct a decision with an immutable binding to ``request``."""

        if values.get("request_id") != request.request_id:
            raise ValueError("decision request_id must match the bound request")
        return cls(request_hash=canonical_hash(request.model_dump(mode="json")), **values)

    def validates_request(self, request: AuthorizationRequest) -> bool:
        return self.request_id == request.request_id and self.request_hash == canonical_hash(
            request.model_dump(mode="json")
        )


class StatusEvent(StrictModel):
    schema_uri: Literal["urn:caretrust:schema:core:status-event:0.1"]
    profile_uri: Literal["urn:caretrust:profile:core:artifact-status:0.1"]
    spec_version: Literal["0.1"]
    event_id: str
    artifact_ref: ArtifactReference
    issuer_ref: str
    actor_ref: str
    actor_role: str
    previous_status: Literal["draft", "active", "suspended", "revoked", "expired", "superseded"] | None
    new_status: Literal["draft", "active", "suspended", "revoked", "expired", "superseded"]
    reason_code: str
    sequence: int
    effective_at: AwareDatetime
    recorded_at: AwareDatetime
    replacement_artifact_ref: ArtifactReference | None = None
    status_list_ref: str | None = None
    provenance_refs: tuple[ProvenanceReference, ...]

    _uri_fields = field_validator(
        "event_id", "issuer_ref", "actor_ref", "actor_role", "reason_code"
    )(_uri)
    _status_list_uri = field_validator("status_list_ref")(_optional_uri)
    _time_format = field_validator("effective_at", "recorded_at", mode="before")(_rfc3339)
    _time_utc = field_validator("effective_at", "recorded_at")(_utc)

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, value: int) -> int:
        if value < 1:
            raise ValueError("sequence must be at least one")
        return value

    @model_validator(mode="after")
    def validate_event(self) -> "StatusEvent":
        if not self.provenance_refs:
            raise ValueError("provenance_refs must contain at least one reference")
        if self.recorded_at < self.effective_at:
            raise ValueError("recorded_at must not precede effective_at")
        if self.previous_status == self.new_status:
            raise ValueError("status event must change status")
        if self.new_status == "superseded" and self.replacement_artifact_ref is None:
            raise ValueError("superseded status requires replacement_artifact_ref")
        return self


def validate_status_sequence(events: tuple[StatusEvent, ...]) -> None:
    """Validate a complete ordered event sequence for one artifact version."""

    if not events:
        raise ValueError("status sequence must contain at least one event")
    ordered = tuple(sorted(events, key=lambda event: event.sequence))
    if ordered != events:
        raise ValueError("status events must be supplied in ascending sequence order")
    first = events[0]
    for expected, event in enumerate(events, start=1):
        if event.sequence != expected:
            raise ValueError("status event sequences must start at one and be contiguous")
        if event.artifact_ref != first.artifact_ref:
            raise ValueError("status events must target one artifact version")
        if expected > 1 and event.previous_status != events[expected - 2].new_status:
            raise ValueError("status events must chain previous_status values")


def envelope_for_payload(
    *,
    message_id: str,
    message_type: str,
    sender_ref: str,
    receiver_ref: str,
    sent_at: datetime,
    trace_id: str,
    payload_schema_uri: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> MessageEnvelope:
    return MessageEnvelope(
        schema_uri=MESSAGE_ENVELOPE_SCHEMA_URI,
        profile_uri="urn:caretrust:profile:core:message-envelope:0.1",
        spec_version=CORE_VERSION,
        message_id=message_id,
        message_type=message_type,
        sender_ref=sender_ref,
        receiver_ref=receiver_ref,
        sent_at=sent_at,
        trace_id=trace_id,
        correlation_id=correlation_id,
        payload_schema_uri=payload_schema_uri,
        payload_hash=canonical_hash(payload),
        payload=payload,
    )
