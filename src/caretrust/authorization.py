"""Deterministic, default-deny authorization policy for CareTrust claims."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from caretrust.models import (
    ActiveCredentialClaim,
    AuditEvent,
    AuditEventType,
    AuthorizationDecision,
    AuthorizationRequest,
    ClaimStatus,
    DecisionValue,
)
from caretrust.security import (
    CareTrustTokenVerifier,
    TokenErrorCode,
    TokenVerificationError,
)


class AuditEventSink(Protocol):
    """Append-only audit boundary used without coupling policy to storage."""

    def append(self, event: AuditEvent) -> None: ...


def _claim_boundary(value: str, *, end: bool) -> datetime:
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("claim validity datetime must be timezone-aware")
        return parsed.astimezone(UTC)
    if end:
        parsed_date += timedelta(days=1)
    return datetime.combine(parsed_date, time.min, UTC)


def _decision_id(
    request_id: str,
    policy_version: str,
    value: DecisionValue,
    reasons: tuple[str, ...],
) -> str:
    material = "|".join((request_id, policy_version, value.value, *reasons))
    return f"decision-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


class AuthorizationPolicy:
    """Evaluate an active claim and its signed token against one request.

    The public type accepts only :class:`ActiveCredentialClaim`; the runtime
    guard additionally makes dynamically typed callers default to denial.
    """

    def __init__(
        self,
        *,
        verifier: CareTrustTokenVerifier,
        policy_version: str = "caretrust.authorization.v1",
    ) -> None:
        self.verifier = verifier
        self.policy_version = policy_version

    def decide(
        self,
        request: AuthorizationRequest,
        claim: ActiveCredentialClaim,
        token: str,
        *,
        now: datetime,
        audit_log: AuditEventSink | None = None,
        actor_ref: str = "system:authorization-policy",
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> AuthorizationDecision:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        now = now.astimezone(UTC)

        # This is intentionally first. A DraftCredentialClaim can never reach a
        # permit branch even when a dynamic caller ignores the function type.
        if not isinstance(claim, ActiveCredentialClaim):
            decision = self._deny(
                request,
                ("REVIEW_REQUIRED", "CLAIM_NOT_ACTIVE_TYPE"),
                now,
            )
            self._record_decision(
                decision,
                token,
                audit_log=audit_log,
                actor_ref=actor_ref,
                trace_id=trace_id,
                event_id=event_id,
            )
            return decision

        reasons: list[str] = []
        if request.claim_id != claim.claim_id:
            reasons.append("CLAIM_ID_MISMATCH")
        if request.subject_ref != claim.subject_ref:
            reasons.append("SUBJECT_MISMATCH")
        if request.requested_claim_type != claim.claim_type:
            reasons.append("CLAIM_TYPE_MISMATCH")
        if claim.status is ClaimStatus.REVOKED:
            reasons.append("CLAIM_REVOKED")
        elif claim.status is ClaimStatus.EXPIRED:
            reasons.append("CLAIM_EXPIRED")
        elif claim.status is not ClaimStatus.ACTIVE:
            reasons.append("CLAIM_STATUS_NOT_ACTIVE")
        if request.audience not in claim.allowed_audiences:
            reasons.append("AUDIENCE_NOT_ALLOWED")
        if request.purpose not in claim.allowed_purposes:
            reasons.append("PURPOSE_NOT_ALLOWED")

        if claim.valid_from is not None and now < _claim_boundary(
            claim.valid_from, end=False
        ):
            reasons.append("CLAIM_NOT_YET_VALID")
        if now >= _claim_boundary(claim.valid_until, end=True):
            reasons.append("CLAIM_EXPIRED")

        try:
            verified = self.verifier.verify(
                token,
                now=now,
                expected_audience=request.audience,
                expected_purpose=request.purpose,
                expected_subject_ref=request.subject_ref,
                expected_claim_id=request.claim_id,
            )
        except TokenVerificationError as exc:
            reasons.append(exc.code.value)
        else:
            if verified.active_claim != claim:
                reasons.append("TOKEN_ACTIVE_CLAIM_MISMATCH")
            if verified.claim_type != request.requested_claim_type:
                reasons.append("TOKEN_CLAIM_TYPE_MISMATCH")
            if verified.status != ClaimStatus.ACTIVE.value:
                reasons.append("TOKEN_STATUS_NOT_ACTIVE")

        unique_reasons = tuple(dict.fromkeys(reasons))
        if unique_reasons:
            decision = self._deny(request, unique_reasons, now)
        else:
            decision = self._build_decision(
                request=request,
                value=DecisionValue.PERMIT,
                reasons=("POLICY_REQUIREMENTS_SATISFIED",),
                supporting_claim_ids=(claim.claim_id,),
                now=now,
            )
        self._record_decision(
            decision,
            token,
            audit_log=audit_log,
            actor_ref=actor_ref,
            trace_id=trace_id,
            event_id=event_id,
        )
        return decision

    def _record_decision(
        self,
        decision: AuthorizationDecision,
        token: str,
        *,
        audit_log: AuditEventSink | None,
        actor_ref: str,
        trace_id: str | None,
        event_id: str | None,
    ) -> None:
        if audit_log is None:
            return
        if not actor_ref or not trace_id or not event_id:
            raise ValueError(
                "actor_ref, trace_id, and event_id are required when audit_log is supplied"
            )
        audit_log.append(
            AuditEvent(
                event_id=event_id,
                event_type=AuditEventType.AUTHORIZATION_DECIDED,
                actor_ref=actor_ref,
                object_ref=decision.request_id,
                occurred_at=decision.decided_at,
                trace_id=trace_id,
                details={
                    "decision_id": decision.decision_id,
                    "decision": decision.decision.value,
                    "reason_codes": ",".join(decision.reason_codes),
                    "supporting_claim_ids": ",".join(
                        decision.supporting_claim_ids
                    ),
                    "policy_version": decision.policy_version,
                    "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                },
            )
        )

    def _deny(
        self,
        request: AuthorizationRequest,
        reasons: tuple[str, ...],
        now: datetime,
    ) -> AuthorizationDecision:
        return self._build_decision(
            request=request,
            value=DecisionValue.DENY,
            reasons=reasons,
            supporting_claim_ids=(),
            now=now,
        )

    def _build_decision(
        self,
        *,
        request: AuthorizationRequest,
        value: DecisionValue,
        reasons: tuple[str, ...],
        supporting_claim_ids: tuple[str, ...],
        now: datetime,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            decision_id=_decision_id(
                request.request_id, self.policy_version, value, reasons
            ),
            request_id=request.request_id,
            decision=value,
            reason_codes=reasons,
            supporting_claim_ids=supporting_claim_ids,
            policy_version=self.policy_version,
            decided_at=now,
        )
