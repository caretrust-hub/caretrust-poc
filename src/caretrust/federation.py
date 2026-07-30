"""Offline synthetic federation trust seam for the CareTrust prototype.

This module borrows the Entity Statement and Trust Anchor vocabulary from
OpenID Federation 1.0. It is a deliberately bounded local profile, not a
protocol-conformant implementation: statements are supplied by the caller,
trust anchors are pinned locally, and no discovery or network operation exists.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Mapping
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ENTITY_STATEMENT_TYPE = "entity-statement+jwt"
LOCAL_PROFILE = "caretrust.synthetic-federation.v1"


class FederationErrorCode(StrEnum):
    MALFORMED = "FEDERATION_STATEMENT_MALFORMED"
    UNSUPPORTED_HEADER = "FEDERATION_UNSUPPORTED_HEADER"
    UNKNOWN_KEY = "FEDERATION_UNKNOWN_KEY"
    SIGNATURE_INVALID = "FEDERATION_SIGNATURE_INVALID"
    CLAIMS_INVALID = "FEDERATION_CLAIMS_INVALID"
    NOT_YET_VALID = "FEDERATION_STATEMENT_NOT_YET_VALID"
    EXPIRED = "FEDERATION_STATEMENT_EXPIRED"
    MISSING_TRUST_ANCHOR = "FEDERATION_MISSING_TRUST_ANCHOR"
    AUTHORITY_HINT_MISMATCH = "FEDERATION_AUTHORITY_HINT_MISMATCH"
    JWKS_MISMATCH = "FEDERATION_JWKS_MISMATCH"


class FederationTrustError(ValueError):
    """Fail-closed federation verification error with a stable code."""

    def __init__(self, code: FederationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not value or any(character.isspace() for character in value):
        raise FederationTrustError(
            FederationErrorCode.MALFORMED, "invalid base64url segment"
        )
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (TypeError, ValueError) as exc:
        raise FederationTrustError(
            FederationErrorCode.MALFORMED, "invalid base64url segment"
        ) from exc


def _json_segment(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=True,
    ).encode("utf-8")
    return _b64url_encode(serialized)


def _decode_object(segment: str) -> dict[str, Any]:
    try:
        value = json.loads(_b64url_decode(segment))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FederationTrustError(
            FederationErrorCode.MALFORMED,
            "entity-statement segment is not a JSON object",
        ) from exc
    if not isinstance(value, dict):
        raise FederationTrustError(
            FederationErrorCode.MALFORMED,
            "entity-statement segment is not a JSON object",
        )
    return value


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _numeric_date(value: datetime) -> int:
    return int(_require_aware(value, "statement time").timestamp())


def _valid_entity_id(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.fragment


def _validate_jwk(jwk: object) -> dict[str, str]:
    if not isinstance(jwk, dict):
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID, "JWKS key must be an object"
        )
    required = {
        "kty": "OKP",
        "crv": "Ed25519",
        "use": "sig",
        "alg": "EdDSA",
    }
    if any(jwk.get(name) != expected for name, expected in required.items()):
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "local profile accepts only Ed25519 signature JWKs",
        )
    kid = jwk.get("kid")
    x = jwk.get("x")
    if not isinstance(kid, str) or not kid or not isinstance(x, str) or not x:
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "JWK kid and x must be nonblank strings",
        )
    try:
        raw_key = _b64url_decode(x)
        Ed25519PublicKey.from_public_bytes(raw_key)
    except (ValueError, FederationTrustError) as exc:
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "JWK x is not a valid Ed25519 public key",
        ) from exc
    return {
        "alg": "EdDSA",
        "crv": "Ed25519",
        "kid": kid,
        "kty": "OKP",
        "use": "sig",
        "x": x,
    }


def _validate_jwks(value: object) -> dict[str, list[dict[str, str]]]:
    if not isinstance(value, dict) or set(value) != {"keys"}:
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "jwks must be an object containing only keys",
        )
    keys = value.get("keys")
    if not isinstance(keys, list) or not keys:
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "jwks.keys must be a nonempty array",
        )
    normalized = [_validate_jwk(key) for key in keys]
    kids = [key["kid"] for key in normalized]
    if len(kids) != len(set(kids)):
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID, "JWK kid values must be unique"
        )
    return {"keys": sorted(normalized, key=lambda key: key["kid"])}


def _canonical_jwks(value: object) -> str:
    return json.dumps(
        _validate_jwks(value),
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True)
class FederationSigningKey:
    """Ephemeral Ed25519 key; only its public JWK belongs in artifacts."""

    kid: str
    private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls, *, kid: str) -> FederationSigningKey:
        if not kid:
            raise ValueError("kid must not be blank")
        return cls(kid=kid, private_key=Ed25519PrivateKey.generate())

    @property
    def public_jwk(self) -> dict[str, str]:
        raw = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "kty": "OKP",
            "crv": "Ed25519",
            "use": "sig",
            "alg": "EdDSA",
            "kid": self.kid,
            "x": _b64url_encode(raw),
        }


@dataclass(frozen=True)
class SyntheticFederationEntity:
    """Caller-supplied, in-memory synthetic entity and its signing keys."""

    entity_id: str
    signing_keys: tuple[FederationSigningKey, ...]
    active_kid: str
    metadata: Mapping[str, Any]
    authority_hints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _valid_entity_id(self.entity_id):
            raise ValueError("entity_id must be an HTTPS Entity Identifier")
        if not self.signing_keys:
            raise ValueError("at least one signing key is required")
        kids = tuple(key.kid for key in self.signing_keys)
        if len(kids) != len(set(kids)):
            raise ValueError("signing key identifiers must be unique")
        if self.active_kid not in kids:
            raise ValueError("active_kid must select an entity signing key")
        if any(not _valid_entity_id(hint) for hint in self.authority_hints):
            raise ValueError("authority hints must be HTTPS Entity Identifiers")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object")

    @property
    def active_key(self) -> FederationSigningKey:
        return next(key for key in self.signing_keys if key.kid == self.active_kid)

    @property
    def jwks(self) -> dict[str, list[dict[str, str]]]:
        return {
            "keys": sorted(
                (key.public_jwk for key in self.signing_keys),
                key=lambda jwk: jwk["kid"],
            )
        }


@dataclass(frozen=True)
class LocalTrustAnchor:
    """Pinned local trust anchor; no remote discovery is attempted."""

    entity_id: str
    jwks: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not _valid_entity_id(self.entity_id):
            raise ValueError("trust anchor ID must be an HTTPS Entity Identifier")
        _validate_jwks(self.jwks)


@dataclass(frozen=True)
class LocalTrustStore:
    anchors: tuple[LocalTrustAnchor, ...]

    def __post_init__(self) -> None:
        identifiers = tuple(anchor.entity_id for anchor in self.anchors)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("trust anchor identifiers must be unique")

    def require(self, entity_id: str) -> LocalTrustAnchor:
        for anchor in self.anchors:
            if anchor.entity_id == entity_id:
                return anchor
        raise FederationTrustError(
            FederationErrorCode.MISSING_TRUST_ANCHOR,
            f"no local trust anchor is configured for {entity_id}",
        )


@dataclass(frozen=True)
class ResolvedTrustChain:
    profile: str
    leaf_entity_id: str
    trust_anchor_id: str
    leaf_jwks: Mapping[str, Any]
    metadata: Mapping[str, Any]
    chain_sha256: str
    resolved_at: datetime
    synthetic: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "leaf_entity_id": self.leaf_entity_id,
            "trust_anchor_id": self.trust_anchor_id,
            "leaf_jwks": self.leaf_jwks,
            "metadata": self.metadata,
            "chain_sha256": self.chain_sha256,
            "resolved_at": self.resolved_at.isoformat().replace("+00:00", "Z"),
            "synthetic": self.synthetic,
        }


def _sign_statement(
    signer: FederationSigningKey,
    claims: Mapping[str, Any],
) -> str:
    header = {
        "alg": "EdDSA",
        "kid": signer.kid,
        "typ": ENTITY_STATEMENT_TYPE,
    }
    encoded_header = _json_segment(header)
    encoded_claims = _json_segment(claims)
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = signer.private_key.sign(signing_input)
    return f"{encoded_header}.{encoded_claims}.{_b64url_encode(signature)}"


def issue_entity_configuration(
    entity: SyntheticFederationEntity,
    *,
    issued_at: datetime,
    lifetime: timedelta = timedelta(minutes=10),
) -> str:
    issued_at = _require_aware(issued_at, "issued_at")
    if lifetime <= timedelta(0):
        raise ValueError("lifetime must be positive")
    claims: dict[str, Any] = {
        "iss": entity.entity_id,
        "sub": entity.entity_id,
        "iat": _numeric_date(issued_at),
        "exp": _numeric_date(issued_at + lifetime),
        "jwks": entity.jwks,
        "metadata": dict(entity.metadata),
    }
    if entity.authority_hints:
        claims["authority_hints"] = list(entity.authority_hints)
    return _sign_statement(entity.active_key, claims)


def issue_subordinate_statement(
    authority: SyntheticFederationEntity,
    subject: SyntheticFederationEntity,
    *,
    issued_at: datetime,
    lifetime: timedelta = timedelta(minutes=10),
) -> str:
    issued_at = _require_aware(issued_at, "issued_at")
    if lifetime <= timedelta(0):
        raise ValueError("lifetime must be positive")
    if authority.entity_id not in subject.authority_hints:
        raise ValueError("subject must name the authority in authority_hints")
    claims = {
        "iss": authority.entity_id,
        "sub": subject.entity_id,
        "iat": _numeric_date(issued_at),
        "exp": _numeric_date(issued_at + lifetime),
        "jwks": subject.jwks,
        "metadata": dict(subject.metadata),
    }
    return _sign_statement(authority.active_key, claims)


def decode_entity_statement_unverified(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode for diagnostics only; this function does not establish trust."""

    if not isinstance(token, str):
        raise FederationTrustError(
            FederationErrorCode.MALFORMED, "entity statement must be a string"
        )
    parts = token.split(".")
    if len(parts) != 3:
        raise FederationTrustError(
            FederationErrorCode.MALFORMED,
            "entity statement must contain three compact-JWT segments",
        )
    return _decode_object(parts[0]), _decode_object(parts[1])


def _verify_statement(
    token: str,
    *,
    trusted_jwks: object,
    now: datetime,
    expected_issuer: str | None = None,
    expected_subject: str | None = None,
) -> dict[str, Any]:
    now = _require_aware(now, "now")
    parts = token.split(".") if isinstance(token, str) else []
    if len(parts) != 3:
        raise FederationTrustError(
            FederationErrorCode.MALFORMED,
            "entity statement must contain three compact-JWT segments",
        )
    header = _decode_object(parts[0])
    claims = _decode_object(parts[1])
    if (
        header.get("alg") != "EdDSA"
        or header.get("typ") != ENTITY_STATEMENT_TYPE
        or not isinstance(header.get("kid"), str)
        or not header["kid"]
    ):
        raise FederationTrustError(
            FederationErrorCode.UNSUPPORTED_HEADER,
            "local profile requires typ entity-statement+jwt and alg EdDSA",
        )

    jwks = _validate_jwks(trusted_jwks)
    matching = [jwk for jwk in jwks["keys"] if jwk["kid"] == header["kid"]]
    if len(matching) != 1:
        raise FederationTrustError(
            FederationErrorCode.UNKNOWN_KEY,
            "statement kid is not present in the supplied trust material",
        )
    public_key = Ed25519PublicKey.from_public_bytes(_b64url_decode(matching[0]["x"]))
    try:
        public_key.verify(
            _b64url_decode(parts[2]),
            f"{parts[0]}.{parts[1]}".encode("ascii"),
        )
    except InvalidSignature as exc:
        raise FederationTrustError(
            FederationErrorCode.SIGNATURE_INVALID,
            "entity-statement signature verification failed",
        ) from exc

    issuer = claims.get("iss")
    subject = claims.get("sub")
    issued_at = claims.get("iat")
    expires_at = claims.get("exp")
    if (
        not isinstance(issuer, str)
        or not _valid_entity_id(issuer)
        or not isinstance(subject, str)
        or not _valid_entity_id(subject)
        or isinstance(issued_at, bool)
        or not isinstance(issued_at, int)
        or isinstance(expires_at, bool)
        or not isinstance(expires_at, int)
        or expires_at <= issued_at
    ):
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "iss, sub, iat, and exp claims are invalid",
        )
    if expected_issuer is not None and issuer != expected_issuer:
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID, "statement issuer does not match"
        )
    if expected_subject is not None and subject != expected_subject:
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID, "statement subject does not match"
        )
    now_timestamp = int(now.timestamp())
    if issued_at > now_timestamp:
        raise FederationTrustError(
            FederationErrorCode.NOT_YET_VALID, "entity statement is not yet valid"
        )
    if expires_at <= now_timestamp:
        raise FederationTrustError(
            FederationErrorCode.EXPIRED, "entity statement has expired"
        )
    claims["jwks"] = _validate_jwks(claims.get("jwks"))
    if not isinstance(claims.get("metadata"), dict):
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID, "metadata must be an object"
        )
    return claims


def resolve_trust_chain(
    *,
    entity_configuration: str,
    subordinate_statement: str,
    trust_store: LocalTrustStore,
    now: datetime,
) -> ResolvedTrustChain:
    """Resolve one offline leaf-to-anchor chain using only caller-supplied JWTs."""

    _, subordinate_unverified = decode_entity_statement_unverified(
        subordinate_statement
    )
    anchor_id = subordinate_unverified.get("iss")
    if not isinstance(anchor_id, str):
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "subordinate statement issuer is missing",
        )
    anchor = trust_store.require(anchor_id)
    subordinate = _verify_statement(
        subordinate_statement,
        trusted_jwks=anchor.jwks,
        now=now,
        expected_issuer=anchor.entity_id,
    )

    _, leaf_unverified = decode_entity_statement_unverified(entity_configuration)
    leaf_id = leaf_unverified.get("sub")
    leaf_jwks = leaf_unverified.get("jwks")
    if not isinstance(leaf_id, str):
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "entity configuration subject is missing",
        )
    leaf = _verify_statement(
        entity_configuration,
        trusted_jwks=leaf_jwks,
        now=now,
        expected_issuer=leaf_id,
        expected_subject=leaf_id,
    )
    if subordinate["sub"] != leaf_id:
        raise FederationTrustError(
            FederationErrorCode.CLAIMS_INVALID,
            "subordinate statement does not describe the leaf entity",
        )
    authority_hints = leaf.get("authority_hints")
    if (
        not isinstance(authority_hints, list)
        or any(not isinstance(item, str) for item in authority_hints)
        or anchor.entity_id not in authority_hints
    ):
        raise FederationTrustError(
            FederationErrorCode.AUTHORITY_HINT_MISMATCH,
            "leaf does not name the local trust anchor in authority_hints",
        )
    if _canonical_jwks(subordinate["jwks"]) != _canonical_jwks(leaf["jwks"]):
        raise FederationTrustError(
            FederationErrorCode.JWKS_MISMATCH,
            "anchor and leaf statements do not bind the same leaf JWKS",
        )

    digest = hashlib.sha256(
        f"{entity_configuration}\n{subordinate_statement}".encode("ascii")
    ).hexdigest()
    return ResolvedTrustChain(
        profile=LOCAL_PROFILE,
        leaf_entity_id=leaf_id,
        trust_anchor_id=anchor.entity_id,
        leaf_jwks=leaf["jwks"],
        metadata=subordinate["metadata"],
        chain_sha256=digest,
        resolved_at=_require_aware(now, "now"),
    )
