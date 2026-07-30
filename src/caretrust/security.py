"""Small standards-facing security boundary for the CareTrust prototype.

The module implements compact JWTs as RFC 7515 EdDSA JWS objects.  Signing keys
are supplied by the caller and the demo generates one in memory; no private key
material is stored in the repository.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Any, Mapping, Protocol
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import ValidationError

from caretrust.models import (
    ActiveCredentialClaim,
    AuditEvent,
    AuditEventType,
    ClaimStatus,
)


class TokenErrorCode(StrEnum):
    MALFORMED = "TOKEN_MALFORMED"
    UNSUPPORTED_ALGORITHM = "TOKEN_UNSUPPORTED_ALGORITHM"
    UNKNOWN_KEY = "TOKEN_UNKNOWN_KEY"
    SIGNATURE_INVALID = "TOKEN_SIGNATURE_INVALID"
    CLAIMS_INVALID = "TOKEN_CLAIMS_INVALID"
    ISSUER_MISMATCH = "TOKEN_ISSUER_MISMATCH"
    NOT_YET_VALID = "TOKEN_NOT_YET_VALID"
    EXPIRED = "TOKEN_EXPIRED"
    REVOKED = "TOKEN_REVOKED"
    AUDIENCE_MISMATCH = "TOKEN_AUDIENCE_MISMATCH"
    PURPOSE_MISMATCH = "TOKEN_PURPOSE_MISMATCH"
    SUBJECT_MISMATCH = "TOKEN_SUBJECT_MISMATCH"
    CLAIM_MISMATCH = "TOKEN_CLAIM_MISMATCH"
    STATUS_INVALID = "TOKEN_STATUS_INVALID"


class TokenVerificationError(ValueError):
    """A safe, machine-readable JWT verification failure."""

    def __init__(self, code: TokenErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not value or any(character.isspace() for character in value):
        raise TokenVerificationError(TokenErrorCode.MALFORMED, "invalid base64url value")
    try:
        padding = "=" * (-len(value) % 4)
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise TokenVerificationError(
            TokenErrorCode.MALFORMED, "invalid base64url value"
        ) from exc


def _json_segment(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, separators=(",", ":"), sort_keys=True, ensure_ascii=True
    ).encode("utf-8")
    return _b64url_encode(encoded)


def _decode_object(segment: str) -> dict[str, Any]:
    try:
        value = json.loads(_b64url_decode(segment))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TokenVerificationError(
            TokenErrorCode.MALFORMED, "JWT segment is not a JSON object"
        ) from exc
    if not isinstance(value, dict):
        raise TokenVerificationError(
            TokenErrorCode.MALFORMED, "JWT segment is not a JSON object"
        )
    return value


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _numeric_date(value: datetime) -> int:
    return int(_require_aware(value, "JWT time").timestamp())


def _parse_numeric_date(claims: Mapping[str, Any], name: str) -> datetime:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TokenVerificationError(
            TokenErrorCode.CLAIMS_INVALID, f"{name} must be an integer NumericDate"
        )
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise TokenVerificationError(
            TokenErrorCode.CLAIMS_INVALID, f"{name} is outside the supported range"
        ) from exc


def _string_set(claims: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = claims.get(name)
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, list):
        values = tuple(value)
    else:
        raise TokenVerificationError(
            TokenErrorCode.CLAIMS_INVALID, f"{name} must be a string or string array"
        )
    if not values or any(not isinstance(item, str) or not item for item in values):
        raise TokenVerificationError(
            TokenErrorCode.CLAIMS_INVALID, f"{name} must contain nonblank strings"
        )
    return values


def _claim_expiry(value: str) -> datetime:
    """Interpret a date as valid through that date, or accept an ISO datetime."""

    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        try:
            parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("claim valid_until must be an ISO date or datetime") from exc
        return _require_aware(parsed_datetime, "claim valid_until")
    return datetime.combine(parsed_date + timedelta(days=1), time.min, UTC)


def _claim_start(value: str) -> datetime:
    """Interpret a date as starting at UTC midnight, or accept an ISO datetime."""

    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        try:
            parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("claim valid_from must be an ISO date or datetime") from exc
        return _require_aware(parsed_datetime, "claim valid_from")
    return datetime.combine(parsed_date, time.min, UTC)


@dataclass(frozen=True)
class SigningKeyPair:
    """An Ed25519 key pair intended to be injected from a real key service later."""

    kid: str
    private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls, *, kid: str = "caretrust-ephemeral-1") -> SigningKeyPair:
        return cls(kid=kid, private_key=Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, private_bytes: bytes, *, kid: str) -> SigningKeyPair:
        return cls(
            kid=kid,
            private_key=Ed25519PrivateKey.from_private_bytes(private_bytes),
        )

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    def public_jwk(self) -> dict[str, str]:
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "kty": "OKP",
            "crv": "Ed25519",
            "use": "sig",
            "alg": "EdDSA",
            "kid": self.kid,
            "x": _b64url_encode(public_bytes),
        }


class AuditEventSink(Protocol):
    """Minimal append-only boundary accepted by revocation operations."""

    def append(self, event: AuditEvent) -> None:
        """Retain one validated audit event."""


def _revocation_event(
    *,
    target_ref: str,
    target_type: str,
    audit_log: AuditEventSink | None,
    actor_ref: str | None,
    trace_id: str | None,
    event_id: str | None,
    occurred_at: datetime | None,
) -> AuditEvent | None:
    if audit_log is None:
        return None
    required = {
        "actor_ref": actor_ref,
        "trace_id": trace_id,
        "event_id": event_id,
        "occurred_at": occurred_at,
    }
    missing = tuple(name for name, value in required.items() if value is None or value == "")
    if missing:
        raise ValueError(
            "revocation audit metadata is required when audit_log is supplied: "
            + ", ".join(missing)
        )
    return AuditEvent(
        event_id=event_id,
        event_type=AuditEventType.CLAIM_REVOKED,
        actor_ref=actor_ref,
        object_ref=target_ref,
        occurred_at=occurred_at,
        trace_id=trace_id,
        details={
            "revocation_target": target_type,
            "reason_code": TokenErrorCode.REVOKED.value,
        },
    )


class RevocationRegistry:
    """In-memory revocation seam; replaceable by a durable status service."""

    def __init__(self) -> None:
        self._claim_ids: set[str] = set()
        self._token_ids: set[str] = set()

    def revoke_claim(
        self,
        claim_id: str,
        *,
        audit_log: AuditEventSink | None = None,
        actor_ref: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        if not claim_id:
            raise ValueError("claim_id must not be blank")
        event = _revocation_event(
            target_ref=claim_id,
            target_type="claim",
            audit_log=audit_log,
            actor_ref=actor_ref,
            trace_id=trace_id,
            event_id=event_id,
            occurred_at=occurred_at,
        )
        if event is not None:
            audit_log.append(event)
        self._claim_ids.add(claim_id)

    def revoke_token(
        self,
        token_id: str,
        *,
        audit_log: AuditEventSink | None = None,
        actor_ref: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        if not token_id:
            raise ValueError("token_id must not be blank")
        event = _revocation_event(
            target_ref=token_id,
            target_type="token",
            audit_log=audit_log,
            actor_ref=actor_ref,
            trace_id=trace_id,
            event_id=event_id,
            occurred_at=occurred_at,
        )
        if event is not None:
            audit_log.append(event)
        self._token_ids.add(token_id)

    def is_revoked(self, *, claim_id: str, token_id: str) -> bool:
        return claim_id in self._claim_ids or token_id in self._token_ids


@dataclass(frozen=True)
class VerifiedCareTrustToken:
    token_id: str
    claim_id: str
    subject_ref: str
    claim_type: str
    status: str
    audiences: tuple[str, ...]
    purposes: tuple[str, ...]
    issuer: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    active_claim: ActiveCredentialClaim
    raw_claims: Mapping[str, Any]


class CareTrustTokenIssuer:
    """Issue short-lived CareTrust capability JWTs from active claims only."""

    def __init__(self, *, issuer: str, signing_key: SigningKeyPair) -> None:
        if not issuer:
            raise ValueError("issuer must not be blank")
        self.issuer = issuer
        self.signing_key = signing_key

    def issue(
        self,
        claim: ActiveCredentialClaim,
        *,
        now: datetime,
        ttl: timedelta = timedelta(minutes=10),
        token_id: str | None = None,
    ) -> str:
        now = _require_aware(now, "now")
        if claim.status is not ClaimStatus.ACTIVE:
            raise ValueError("only active claims may be represented by a token")
        if not claim.evidence_refs:
            raise ValueError("active claims must retain at least one evidence reference")
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        expires_at = min(now + ttl, _claim_expiry(claim.valid_until))
        if expires_at <= now:
            raise ValueError("claim is already expired")

        header = {"alg": "EdDSA", "kid": self.signing_key.kid, "typ": "JWT"}
        payload = {
            "iss": self.issuer,
            "sub": claim.subject_ref,
            "jti": token_id or f"ctj-{uuid4()}",
            "iat": _numeric_date(now),
            "nbf": _numeric_date(now),
            "exp": _numeric_date(expires_at),
            "aud": list(claim.allowed_audiences),
            "purpose": list(claim.allowed_purposes),
            "ct_claim_id": claim.claim_id,
            "ct_claim_type": claim.claim_type,
            "ct_status": claim.status.value,
            "ct_claim_issuer": claim.issuer_ref,
            "ct_jurisdiction": claim.jurisdiction,
            "ct_valid_from": claim.valid_from,
            "ct_valid_until": claim.valid_until,
            "ct_evidence_refs": list(claim.evidence_refs),
            "ct_active_claim": claim.model_dump(mode="json"),
        }
        signing_input = f"{_json_segment(header)}.{_json_segment(payload)}"
        signature = self.signing_key.private_key.sign(signing_input.encode("ascii"))
        return f"{signing_input}.{_b64url_encode(signature)}"


class CareTrustTokenVerifier:
    """Verify JWT authenticity, lifetime, revocation, and claim relationships."""

    def __init__(
        self,
        *,
        issuer: str,
        public_keys: Mapping[str, Ed25519PublicKey],
        revocations: RevocationRegistry | None = None,
    ) -> None:
        if not issuer:
            raise ValueError("issuer must not be blank")
        self.issuer = issuer
        self.public_keys = dict(public_keys)
        self.revocations = revocations or RevocationRegistry()

    def verify(
        self,
        token: str,
        *,
        now: datetime,
        expected_audience: str | None = None,
        expected_purpose: str | None = None,
        expected_subject_ref: str | None = None,
        expected_claim_id: str | None = None,
    ) -> VerifiedCareTrustToken:
        now = _require_aware(now, "now")
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenVerificationError(
                TokenErrorCode.MALFORMED, "JWT must contain three segments"
            )
        encoded_header, encoded_payload, encoded_signature = parts
        header = _decode_object(encoded_header)
        if header.get("alg") != "EdDSA" or header.get("typ") != "JWT":
            raise TokenVerificationError(
                TokenErrorCode.UNSUPPORTED_ALGORITHM,
                "JWT must use EdDSA and typ JWT",
            )
        kid = header.get("kid")
        if not isinstance(kid, str) or kid not in self.public_keys:
            raise TokenVerificationError(
                TokenErrorCode.UNKNOWN_KEY, "JWT signing key is not trusted"
            )
        try:
            self.public_keys[kid].verify(
                _b64url_decode(encoded_signature),
                f"{encoded_header}.{encoded_payload}".encode("ascii"),
            )
        except InvalidSignature as exc:
            raise TokenVerificationError(
                TokenErrorCode.SIGNATURE_INVALID, "JWT signature is invalid"
            ) from exc

        claims = _decode_object(encoded_payload)
        required_strings = (
            "iss",
            "sub",
            "jti",
            "ct_claim_id",
            "ct_claim_type",
            "ct_status",
            "ct_claim_issuer",
            "ct_jurisdiction",
            "ct_valid_until",
        )
        if any(
            not isinstance(claims.get(name), str) or not claims[name]
            for name in required_strings
        ):
            raise TokenVerificationError(
                TokenErrorCode.CLAIMS_INVALID,
                "JWT is missing a required nonblank string claim",
            )
        issued_at = _parse_numeric_date(claims, "iat")
        not_before = _parse_numeric_date(claims, "nbf")
        expires_at = _parse_numeric_date(claims, "exp")
        audiences = _string_set(claims, "aud")
        purposes = _string_set(claims, "purpose")
        evidence_refs = _string_set(claims, "ct_evidence_refs")
        try:
            active_claim = ActiveCredentialClaim.model_validate(
                claims.get("ct_active_claim")
            )
        except ValidationError as exc:
            raise TokenVerificationError(
                TokenErrorCode.CLAIMS_INVALID,
                "JWT embedded active claim does not match the published contract",
            ) from exc

        bindings = {
            "claim identifier": (
                active_claim.claim_id,
                claims["ct_claim_id"],
            ),
            "subject": (active_claim.subject_ref, claims["sub"]),
            "claim type": (active_claim.claim_type, claims["ct_claim_type"]),
            "status": (active_claim.status.value, claims["ct_status"]),
            "claim issuer": (active_claim.issuer_ref, claims["ct_claim_issuer"]),
            "jurisdiction": (
                active_claim.jurisdiction,
                claims["ct_jurisdiction"],
            ),
            "valid from": (active_claim.valid_from, claims.get("ct_valid_from")),
            "valid until": (active_claim.valid_until, claims["ct_valid_until"]),
            "evidence references": (
                active_claim.evidence_refs,
                evidence_refs,
            ),
            "audiences": (active_claim.allowed_audiences, audiences),
            "purposes": (active_claim.allowed_purposes, purposes),
        }
        mismatched = tuple(
            name for name, (embedded, top_level) in bindings.items()
            if embedded != top_level
        )
        if mismatched:
            raise TokenVerificationError(
                TokenErrorCode.CLAIMS_INVALID,
                "JWT embedded active claim does not match top-level claims: "
                + ", ".join(mismatched),
            )

        if claims["iss"] != self.issuer:
            raise TokenVerificationError(
                TokenErrorCode.ISSUER_MISMATCH, "JWT issuer is not trusted"
            )
        if issued_at > now or not_before > now:
            raise TokenVerificationError(
                TokenErrorCode.NOT_YET_VALID, "JWT is not yet valid"
            )
        if now >= expires_at:
            raise TokenVerificationError(TokenErrorCode.EXPIRED, "JWT has expired")
        if claims["ct_status"] != ClaimStatus.ACTIVE.value:
            raise TokenVerificationError(
                TokenErrorCode.STATUS_INVALID, "JWT does not represent an active claim"
            )
        if active_claim.valid_from is not None and now < _claim_start(
            active_claim.valid_from
        ):
            raise TokenVerificationError(
                TokenErrorCode.NOT_YET_VALID,
                "embedded active claim is not yet valid",
            )
        if now >= _claim_expiry(active_claim.valid_until):
            raise TokenVerificationError(
                TokenErrorCode.EXPIRED,
                "embedded active claim has expired",
            )
        if self.revocations.is_revoked(
            claim_id=claims["ct_claim_id"], token_id=claims["jti"]
        ):
            raise TokenVerificationError(
                TokenErrorCode.REVOKED, "JWT or its supporting claim is revoked"
            )
        if expected_audience is not None and expected_audience not in audiences:
            raise TokenVerificationError(
                TokenErrorCode.AUDIENCE_MISMATCH,
                "JWT does not authorize the requested audience",
            )
        if expected_purpose is not None and expected_purpose not in purposes:
            raise TokenVerificationError(
                TokenErrorCode.PURPOSE_MISMATCH,
                "JWT does not authorize the requested purpose",
            )
        if (
            expected_subject_ref is not None
            and claims["sub"] != expected_subject_ref
        ):
            raise TokenVerificationError(
                TokenErrorCode.SUBJECT_MISMATCH,
                "JWT subject does not match the request",
            )
        if expected_claim_id is not None and claims["ct_claim_id"] != expected_claim_id:
            raise TokenVerificationError(
                TokenErrorCode.CLAIM_MISMATCH,
                "JWT claim identifier does not match the request",
            )

        return VerifiedCareTrustToken(
            token_id=claims["jti"],
            claim_id=claims["ct_claim_id"],
            subject_ref=claims["sub"],
            claim_type=claims["ct_claim_type"],
            status=claims["ct_status"],
            audiences=audiences,
            purposes=purposes,
            issuer=claims["iss"],
            issued_at=issued_at,
            not_before=not_before,
            expires_at=expires_at,
            active_claim=active_claim,
            raw_claims=claims,
        )
