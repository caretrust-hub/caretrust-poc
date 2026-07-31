"""Append-only technical trace contracts for inspectable CareTrust workflows.

The trace is a presentation boundary, not a second source of workflow truth.
Callers record the same validated domain messages that drive state transitions.
Every event binds its exact JSON payload, actor, receiver, evidence class, linked
identifiers, and trust boundary so a reviewer can follow a claim end to end.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, JsonValue, field_validator, model_validator

from caretrust.models import StrictModel


class EvidenceStatus(StrEnum):
    """Bounded evidence classes used across runtime, UI, and documentation."""

    RETAINED_AWS = "retained_aws"
    EXECUTED_LOCAL = "executed_local"
    CONTRACT_TESTED = "contract_tested"
    LOCAL_SIMULATION = "local_simulation"
    MAPPED_ONLY = "mapped_only"
    PLANNED = "planned"


class TraceEnvelope(StrictModel):
    """One immutable message crossing a named trust or implementation boundary."""

    schema_version: Literal["caretrust.trace-envelope.v1"]
    trace_id: str
    event_id: str
    sequence: int
    occurred_at: AwareDatetime
    actor_ref: str
    receiver_ref: str
    boundary: str
    message_type: str
    evidence_status: EvidenceStatus
    standard_refs: tuple[str, ...]
    linked_ids: dict[str, str]
    payload: dict[str, JsonValue]
    payload_sha256: str
    non_claims: tuple[str, ...] = ()

    @field_validator(
        "trace_id",
        "event_id",
        "actor_ref",
        "receiver_ref",
        "boundary",
        "message_type",
    )
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("trace string values must not be blank")
        return value

    @field_validator("sequence")
    @classmethod
    def require_positive_sequence(cls, value: int) -> int:
        if value < 1:
            raise ValueError("trace sequence must begin at one")
        return value

    @field_validator("standard_refs")
    @classmethod
    def require_nonblank_standard_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item for item in value):
            raise ValueError("standard references must not be blank")
        if len(value) != len(set(value)):
            raise ValueError("standard references must be unique")
        return value

    @field_validator("linked_ids")
    @classmethod
    def validate_linked_ids(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key or not linked for key, linked in value.items()):
            raise ValueError("linked identifier names and values must not be blank")
        return value

    @field_validator("payload_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(
            char not in "0123456789abcdef" for char in normalized
        ):
            raise ValueError("payload_sha256 must be a 64-character SHA-256 digest")
        return normalized

    @model_validator(mode="after")
    def verify_payload_hash(self) -> TraceEnvelope:
        if self.payload_sha256 != sha256_json(self.payload):
            raise ValueError("payload_sha256 does not bind the canonical payload")
        return self


class TraceBundle(StrictModel):
    """A complete ordered trace suitable for browser replay and export."""

    schema_version: Literal["caretrust.trace-bundle.v1"]
    trace_id: str
    title: str
    synthetic_only: Literal[True]
    fixture_refs: tuple[str, ...]
    events: tuple[TraceEnvelope, ...]
    limitations: tuple[str, ...]

    @field_validator("trace_id", "title")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("trace bundle strings must not be blank")
        return value

    @field_validator("fixture_refs", "limitations")
    @classmethod
    def require_nonblank_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item for item in value):
            raise ValueError("trace bundle lists require nonblank values")
        return value

    @model_validator(mode="after")
    def validate_event_chain(self) -> TraceBundle:
        if not self.events:
            raise ValueError("trace bundle requires at least one event")
        if any(event.trace_id != self.trace_id for event in self.events):
            raise ValueError("every event must belong to the bundle trace_id")
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("trace event identifiers must be unique")
        expected_sequence = list(range(1, len(self.events) + 1))
        if [event.sequence for event in self.events] != expected_sequence:
            raise ValueError("trace events must be consecutive and ordered")
        occurred_at = [event.occurred_at for event in self.events]
        if occurred_at != sorted(occurred_at):
            raise ValueError("trace event timestamps must be nondecreasing")
        return self


def canonical_json(value: object) -> str:
    """Return stable JSON for hashes, artifacts, and browser equality checks."""

    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_json(value: object) -> str:
    """Hash canonical UTF-8 JSON bytes."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class TraceRecorder:
    """Small append-only builder that assigns sequence numbers deterministically."""

    def __init__(self, trace_id: str) -> None:
        if not trace_id:
            raise ValueError("trace_id must not be blank")
        self.trace_id = trace_id
        self._events: list[TraceEnvelope] = []

    @property
    def events(self) -> tuple[TraceEnvelope, ...]:
        return tuple(self._events)

    def append(
        self,
        *,
        event_id: str,
        occurred_at: AwareDatetime,
        actor_ref: str,
        receiver_ref: str,
        boundary: str,
        message_type: str,
        evidence_status: EvidenceStatus,
        payload: dict[str, JsonValue],
        standard_refs: tuple[str, ...] = (),
        linked_ids: dict[str, str] | None = None,
        non_claims: tuple[str, ...] = (),
    ) -> TraceEnvelope:
        if any(event.event_id == event_id for event in self._events):
            raise ValueError(f"trace event_id already exists: {event_id}")
        if self._events and occurred_at < self._events[-1].occurred_at:
            raise ValueError("trace event time cannot precede the prior event")
        event = TraceEnvelope(
            schema_version="caretrust.trace-envelope.v1",
            trace_id=self.trace_id,
            event_id=event_id,
            sequence=len(self._events) + 1,
            occurred_at=occurred_at,
            actor_ref=actor_ref,
            receiver_ref=receiver_ref,
            boundary=boundary,
            message_type=message_type,
            evidence_status=evidence_status,
            standard_refs=standard_refs,
            linked_ids=dict(linked_ids or {}),
            payload=payload,
            payload_sha256=sha256_json(payload),
            non_claims=non_claims,
        )
        self._events.append(event)
        return event

    def bundle(
        self,
        *,
        title: str,
        fixture_refs: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> TraceBundle:
        return TraceBundle(
            schema_version="caretrust.trace-bundle.v1",
            trace_id=self.trace_id,
            title=title,
            synthetic_only=True,
            fixture_refs=fixture_refs,
            events=self.events,
            limitations=limitations,
        )
