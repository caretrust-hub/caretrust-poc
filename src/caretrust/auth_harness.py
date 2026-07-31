"""Provider-neutral local OAuth/OIDC authorization-code harness.

This is an executable local contract, not an HTTP authorization server or an
external identity-provider integration.  It terminates a synthetic upstream
OIDC token at CareTrust, keeps only its hash/link, and issues a distinct,
short-lived CareTrust resource token after a fresh case-policy decision.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.app_onboarding import ApplicationOnboardingDraft
from caretrust.models import StrictModel


AUTH_ISSUER = "https://auth.caretrust.synthetic.invalid"
CASE_ID = "case:synthetic-multi-caregiver-001"
CASE_APP_ID = "app:synthetic-scheduling"
CLIENT_ID = "client:synthetic-family-scheduling"
REDIRECT_URI = "https://scheduling.synthetic.example/oauth/callback"
RESOURCE = "https://scheduling.synthetic.example"
PURPOSE = "appointment_management"
AUTH_DETAIL_TYPE = "https://caretrust-hub.github.io/caretrust-spec/rar/care-data/v1"
_SYNTHETIC_PRIVATE_KEY = sha256(b"caretrust-auth-harness-synthetic-fixture-key-v1").digest()


class AuthHarnessError(ValueError):
    """Safe machine-readable failure for local authorization-flow checks."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _nonblank(value: str) -> str:
    if not value:
        raise ValueError("value must not be blank")
    return value


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def pkce_s256(verifier: str) -> str:
    """RFC 7636 S256 challenge; verifier is retained only at token exchange."""
    if len(verifier) < 43 or len(verifier) > 128:
        raise ValueError("PKCE verifier must be 43-128 characters")
    return base64.urlsafe_b64encode(sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _segment(value: Mapping[str, Any]) -> str:
    return _b64(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


class UpstreamIdentityLink(StrictModel):
    schema_version: str = "caretrust.upstream-oidc-identity-link.v1"
    link_id: str
    caregiver_ref: str
    upstream_issuer: str
    upstream_subject: str
    assurance: str
    oidc_nonce_sha256: str
    upstream_token_sha256: str
    linked_at: AwareDatetime
    upstream_token_retained: bool = False
    upstream_token_forwarded_to_application: bool = False
    external_identity_proofing_status: str = "planned_not_exercised"
    oidc_id_token_verified_locally: bool = True
    synthetic: bool = True

    _strings = field_validator("link_id", "caregiver_ref", "upstream_issuer", "upstream_subject", "assurance")(_nonblank)

    @field_validator("upstream_token_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
            raise ValueError("upstream token must be represented by a SHA-256 digest")
        return value.lower()

    @model_validator(mode="after")
    def _terminated(self) -> "UpstreamIdentityLink":
        if self.upstream_token_retained or self.upstream_token_forwarded_to_application or not self.oidc_id_token_verified_locally:
            raise ValueError("upstream bearer token must terminate at CareTrust")
        return self


class DeveloperClientMetadata(StrictModel):
    """Developer-supplied client metadata, reviewed separately from the AI draft."""

    client_id: str
    redirect_uris: tuple[str, ...]
    application_id: str
    synthetic: bool = True

    _strings = field_validator("client_id", "application_id")(_nonblank)

    @model_validator(mode="after")
    def _redirects(self) -> "DeveloperClientMetadata":
        if not self.redirect_uris or any(not value.startswith("https://") for value in self.redirect_uris):
            raise ValueError("developer metadata requires HTTPS redirect URIs")
        return self


class ApplicationRegistration(StrictModel):
    schema_version: str = "caretrust.application-registration.v1"
    registration_id: str
    application_id: str
    client_id: str
    redirect_uris: tuple[str, ...]
    allowed_resources: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    allowed_datatypes: tuple[str, ...]
    profile: str
    source_draft_id: str
    human_reviewer_ref: str
    review_decision: str = "approved"
    registered_at: AwareDatetime
    status: str = "active"
    synthetic: bool = True

    _strings = field_validator("registration_id", "application_id", "client_id", "source_draft_id", "human_reviewer_ref")(_nonblank)

    @model_validator(mode="after")
    def _reviewed(self) -> "ApplicationRegistration":
        if not self.redirect_uris or not self.allowed_resources or not self.allowed_purposes or not self.allowed_actions or not self.allowed_datatypes or not self.profile:
            raise ValueError("application registration requires bounded redirect, resource, purpose, action, datatype, and profile")
        if self.review_decision != "approved" or self.status != "active":
            raise ValueError("only an explicit human-approved active registration is usable")
        return self


class RichAuthorizationDetail(StrictModel):
    type: str
    locations: tuple[str, ...]
    actions: tuple[str, ...]
    datatypes: tuple[str, ...]
    purpose: str

    @model_validator(mode="after")
    def _bounded(self) -> "RichAuthorizationDetail":
        if not self.type or not self.locations or not self.actions or not self.datatypes or not self.purpose:
            raise ValueError("RAR detail requires type, locations, actions, datatypes, and purpose")
        return self


class AuthorizationCodeRequest(StrictModel):
    schema_version: str = "caretrust.oauth-authorization-code-request.v1"
    request_id: str
    case_id: str
    caregiver_ref: str
    identity_link_id: str
    client_id: str
    redirect_uri: str
    response_type: str = "code"
    state: str
    nonce: str
    code_challenge: str
    code_challenge_method: str = "S256"
    authorization_details: tuple[RichAuthorizationDetail, ...]
    resource: str
    purpose: str
    requested_at: AwareDatetime
    synthetic: bool = True

    _strings = field_validator("request_id", "case_id", "caregiver_ref", "identity_link_id", "client_id", "redirect_uri", "state", "nonce", "code_challenge", "resource", "purpose")(_nonblank)

    @model_validator(mode="after")
    def _oauth_shape(self) -> "AuthorizationCodeRequest":
        if self.response_type != "code" or self.code_challenge_method != "S256" or not self.authorization_details:
            raise ValueError("only authorization-code flow with S256 PKCE and RAR is supported")
        return self


class AuthorizationCodeReceipt(StrictModel):
    schema_version: str = "caretrust.authorization-code-receipt.v1"
    code_id: str
    request_id: str
    code_sha256: str
    client_id: str
    redirect_uri: str
    state: str
    expires_at: AwareDatetime
    one_time: bool = True
    used: bool = False
    synthetic: bool = True


class DownstreamTokenReceipt(StrictModel):
    schema_version: str = "caretrust.downstream-resource-token-receipt.v1"
    token_id: str
    token_sha256: str
    signed_with_kid: str
    decoded_claims: dict[str, str | int | list[str]]
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    evidence_status: str = "executed_local"
    synthetic: bool = True

    @model_validator(mode="after")
    def _safe_receipt(self) -> "DownstreamTokenReceipt":
        forbidden = {"private_key", "upstream_token", "access_token", "bearer_token"}
        if forbidden & set(self.decoded_claims):
            raise ValueError("receipt must not disclose bearer or private material")
        return self


@dataclass
class _StoredCode:
    request: AuthorizationCodeRequest
    registration: ApplicationRegistration
    decision: Mapping[str, Any]
    expires_at: datetime
    used: bool = False


class LocalAuthHarness:
    """Stateful local flow executor. No network or external provider is invoked."""

    def __init__(self, *, issuer: str = AUTH_ISSUER) -> None:
        self.issuer = issuer
        self._key = Ed25519PrivateKey.from_private_bytes(_SYNTHETIC_PRIVATE_KEY)
        self._idp_key = Ed25519PrivateKey.from_private_bytes(sha256(b"caretrust-auth-harness-synthetic-idp-key-v1").digest())
        self._codes: dict[str, _StoredCode] = {}

    def public_jwk(self) -> dict[str, str]:
        public = self._key.public_key().public_bytes_raw()
        return {"kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig", "kid": "auth-harness-synthetic-ed25519-v1", "x": _b64(public)}

    def issue_synthetic_oidc_id_token(self, *, caregiver_ref: str, nonce: str, now: datetime) -> str:
        claims = {"iss": "https://idp.synthetic.invalid", "sub": "oidc-subject:synthetic-caregiver-001", "aud": self.issuer, "nonce": nonce, "acr": "self_asserted_synthetic", "iat": int(now.timestamp()), "nbf": int(now.timestamp()), "exp": int((now + timedelta(minutes=5)).timestamp()), "ct_caregiver_ref": caregiver_ref}
        return self._sign(claims, key=self._idp_key, kid="synthetic-idp-ed25519-v1")

    def link_upstream_identity(self, *, caregiver_ref: str, upstream_id_token: str, expected_nonce: str, now: datetime) -> UpstreamIdentityLink:
        claims = self._verify_id_token(upstream_id_token, expected_nonce=expected_nonce, now=now)
        if claims.get("ct_caregiver_ref") != caregiver_ref:
            raise AuthHarnessError("IDENTITY_CAREGIVER_MISMATCH", "OIDC identity token does not bind this caregiver")
        return UpstreamIdentityLink(
            link_id="identity-link:synthetic-caregiver-001", caregiver_ref=caregiver_ref,
            upstream_issuer=claims["iss"], upstream_subject=claims["sub"], assurance=claims["acr"], oidc_nonce_sha256=_hash(expected_nonce),
            upstream_token_sha256=_hash(upstream_id_token), linked_at=now,
        )

    def register_application(self, draft: ApplicationOnboardingDraft, metadata: DeveloperClientMetadata, *, reviewer_ref: str, now: datetime) -> ApplicationRegistration:
        if draft.registration_permitted or draft.status != "draft" or metadata.application_id != draft.application_id:
            raise AuthHarnessError("AI_DRAFT_CANNOT_REGISTER", "AI draft cannot self-register an application")
        proposal = draft.proposed_rar[0]
        if metadata.redirect_uris != (proposal.locations[0] + "/oauth/callback",):
            raise AuthHarnessError("DEVELOPER_METADATA_NOT_REVIEWED", "redirect metadata is not the reviewed synthetic client callback")
        return ApplicationRegistration(
            registration_id="app-registration:synthetic-direct-care-001", application_id=draft.application_id,
            client_id=metadata.client_id, redirect_uris=metadata.redirect_uris,
            allowed_resources=proposal.locations, allowed_purposes=(proposal.purpose,), allowed_actions=proposal.actions,
            allowed_datatypes=proposal.datatypes, profile=draft.proposed_profile, source_draft_id=draft.draft_id,
            human_reviewer_ref=reviewer_ref, registered_at=now,
        )

    def authorize(self, request: AuthorizationCodeRequest, *, identity_link: UpstreamIdentityLink, registration: ApplicationRegistration, fresh_case_decision: Mapping[str, Any], now: datetime) -> tuple[str, AuthorizationCodeReceipt]:
        self._validate_request(request, identity_link, registration, fresh_case_decision, now)
        code = "code.synthetic." + sha256((request.request_id + request.state).encode("utf-8")).hexdigest()[:32]
        if _hash(code) in self._codes:
            raise AuthHarnessError("CODE_ALREADY_ISSUED", "same authorization request cannot issue another code")
        expires_at = now + timedelta(minutes=2)
        self._codes[_hash(code)] = _StoredCode(request, registration, fresh_case_decision, expires_at)
        return code, AuthorizationCodeReceipt(code_id="code-id:synthetic-001", request_id=request.request_id, code_sha256=_hash(code), client_id=request.client_id, redirect_uri=request.redirect_uri, state=request.state, expires_at=expires_at)

    def exchange_code(self, *, code: str, client_id: str, redirect_uri: str, code_verifier: str, resource: str, audience: str, purpose: str, now: datetime) -> tuple[str, DownstreamTokenReceipt]:
        stored = self._codes.get(_hash(code))
        if stored is None:
            raise AuthHarnessError("CODE_UNKNOWN", "authorization code is unknown")
        if stored.used:
            raise AuthHarnessError("CODE_USED", "authorization code has already been exchanged")
        if now >= stored.expires_at:
            raise AuthHarnessError("CODE_EXPIRED", "authorization code has expired")
        request = stored.request
        if client_id != request.client_id:
            raise AuthHarnessError("CLIENT_MISMATCH", "client does not match authorization code")
        if redirect_uri != request.redirect_uri:
            raise AuthHarnessError("REDIRECT_URI_MISMATCH", "redirect URI does not match authorization code")
        if pkce_s256(code_verifier) != request.code_challenge:
            raise AuthHarnessError("PKCE_VERIFIER_MISMATCH", "PKCE verifier does not match challenge")
        if resource != request.resource:
            raise AuthHarnessError("RESOURCE_MISMATCH", "resource does not match authorization request")
        if audience != request.resource:
            raise AuthHarnessError("AUDIENCE_MISMATCH", "audience does not match requested resource server")
        if purpose != request.purpose:
            raise AuthHarnessError("PURPOSE_MISMATCH", "purpose does not match authorization request")
        stored.used = True
        expires_at = min(now + timedelta(minutes=5), stored.decision["as_of_dt"] + timedelta(minutes=5))
        claims: dict[str, str | int | list[str]] = {
            "iss": self.issuer, "sub": request.caregiver_ref, "aud": audience, "resource": resource, "client_id": client_id,
            "purpose": purpose, "jti": "token:synthetic-resource-001", "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()), "exp": int(expires_at.timestamp()),
            "ct_case_id": request.case_id, "ct_case_decision_id": str(stored.decision["decision_id"]),
            "authorization_details": [detail.type for detail in request.authorization_details],
            "caretrust_actions": sorted({
                action
                for detail in request.authorization_details
                for action in detail.actions
            }),
            "caretrust_datatypes": sorted({
                datatype
                for detail in request.authorization_details
                for datatype in detail.datatypes
            }),
        }
        token = self._sign(claims)
        return token, DownstreamTokenReceipt(token_id=claims["jti"], token_sha256=_hash(token), signed_with_kid="auth-harness-synthetic-ed25519-v1", decoded_claims=claims, issued_at=now, expires_at=expires_at)

    def verify_downstream_token(self, token: str, *, resource: str, audience: str, client_id: str, purpose: str, now: datetime) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthHarnessError("TOKEN_MALFORMED", "downstream token must have three JWT segments")
        header = json.loads(_unb64(parts[0]))
        claims = json.loads(_unb64(parts[1]))
        if header != {"alg": "EdDSA", "kid": "auth-harness-synthetic-ed25519-v1", "typ": "JWT"}:
            raise AuthHarnessError("TOKEN_HEADER_INVALID", "unexpected downstream token header")
        try:
            self._key.public_key().verify(_unb64(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii"))
        except InvalidSignature as exc:
            raise AuthHarnessError("TOKEN_SIGNATURE_INVALID", "downstream token signature is invalid") from exc
        if claims.get("iss") != self.issuer or claims.get("nbf") > int(now.timestamp()) or claims.get("iat") > int(now.timestamp()) or now >= datetime.fromtimestamp(claims["exp"], UTC):
            raise AuthHarnessError("TOKEN_EXPIRED", "downstream token is expired")
        for name, expected in (("resource", resource), ("aud", audience), ("client_id", client_id), ("purpose", purpose)):
            if claims.get(name) != expected:
                raise AuthHarnessError(f"TOKEN_{name.upper()}_MISMATCH", f"downstream token {name} mismatch")
        return claims

    def _validate_request(self, request: AuthorizationCodeRequest, identity_link: UpstreamIdentityLink, registration: ApplicationRegistration, decision: Mapping[str, Any], now: datetime) -> None:
        if request.identity_link_id != identity_link.link_id or request.caregiver_ref != identity_link.caregiver_ref or _hash(request.nonce) != identity_link.oidc_nonce_sha256:
            raise AuthHarnessError("IDENTITY_LINK_MISMATCH", "authorization request is not bound to verified OIDC identity")
        if not identity_link.oidc_id_token_verified_locally or identity_link.upstream_token_retained or identity_link.upstream_token_forwarded_to_application or identity_link.upstream_issuer != "https://idp.synthetic.invalid" or identity_link.assurance != "self_asserted_synthetic" or now < identity_link.linked_at or now - identity_link.linked_at > timedelta(minutes=5):
            raise AuthHarnessError("IDENTITY_LINK_UNVERIFIED_OR_STALE", "verified OIDC link is not current")
        if now - request.requested_at > timedelta(minutes=2) or request.requested_at > now:
            raise AuthHarnessError("AUTHORIZATION_REQUEST_STALE", "authorization request is stale or from the future")
        if request.case_id != CASE_ID or request.client_id != registration.client_id or request.redirect_uri not in registration.redirect_uris:
            raise AuthHarnessError("CLIENT_OR_REDIRECT_NOT_REGISTERED", "request is not bound to active registration")
        if request.resource not in registration.allowed_resources or request.purpose not in registration.allowed_purposes:
            raise AuthHarnessError("RESOURCE_OR_PURPOSE_NOT_REGISTERED", "request exceeds registration")
        if any(
            detail.type != AUTH_DETAIL_TYPE
            or request.resource not in detail.locations
            or request.purpose != detail.purpose
            or not set(detail.actions) <= set(registration.allowed_actions)
            or not set(detail.datatypes) <= set(registration.allowed_datatypes)
            for detail in request.authorization_details
        ):
            raise AuthHarnessError("RAR_BINDING_INVALID", "RAR detail is not bound to resource and purpose")
        if decision.get("decision") != "permit" or decision.get("caregiver_ref") != request.caregiver_ref:
            raise AuthHarnessError("CASE_DECISION_DENIED", "fresh CareTrust case decision does not permit request")
        requested_actions = {
            action
            for detail in request.authorization_details
            for action in detail.actions
        }
        if requested_actions != {decision.get("action")}:
            raise AuthHarnessError(
                "CASE_ACTION_MISMATCH",
                "requested RAR action is not the freshly permitted CareTrust action",
            )
        decision_at = decision.get("as_of_dt")
        if not isinstance(decision_at, datetime) or decision_at != now:
            raise AuthHarnessError("CASE_DECISION_NOT_FRESH", "case decision must be evaluated at authorization time")

    def _verify_id_token(self, token: str, *, expected_nonce: str, now: datetime) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthHarnessError("OIDC_TOKEN_MALFORMED", "OIDC ID token must have three segments")
        header, claims = json.loads(_unb64(parts[0])), json.loads(_unb64(parts[1]))
        try:
            self._idp_key.public_key().verify(_unb64(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii"))
        except InvalidSignature as exc:
            raise AuthHarnessError("OIDC_SIGNATURE_INVALID", "OIDC ID token signature is invalid") from exc
        if header.get("kid") != "synthetic-idp-ed25519-v1" or claims.get("iss") != "https://idp.synthetic.invalid" or claims.get("aud") != self.issuer or claims.get("nonce") != expected_nonce or claims.get("nbf", 0) > int(now.timestamp()) or claims.get("iat", 0) > int(now.timestamp()) or claims.get("exp", 0) <= int(now.timestamp()):
            raise AuthHarnessError("OIDC_CLAIMS_INVALID", "OIDC ID token issuer, audience, nonce, or lifetime is invalid")
        return claims

    def _sign(self, claims: Mapping[str, Any], *, key: Ed25519PrivateKey | None = None, kid: str = "auth-harness-synthetic-ed25519-v1") -> str:
        header = {"alg": "EdDSA", "kid": kid, "typ": "JWT"}
        signing_input = f"{_segment(header)}.{_segment(claims)}"
        signature = (key or self._key).sign(signing_input.encode("ascii"))
        return f"{signing_input}.{_b64(signature)}"
