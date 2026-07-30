from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from caretrust.authorization import AuthorizationPolicy
from caretrust.models import (
    ActiveCredentialClaim,
    AuthorizationRequest,
    ClaimStatus,
    DecisionValue,
    DraftCredentialClaim,
    DraftCredentialFields,
    DraftField,
)
from caretrust.security import (
    CareTrustTokenIssuer,
    CareTrustTokenVerifier,
    RevocationRegistry,
    SigningKeyPair,
    TokenErrorCode,
    TokenVerificationError,
)

NOW = datetime(2026, 7, 29, 20, 0, tzinfo=UTC)


def _claim() -> ActiveCredentialClaim:
    return ActiveCredentialClaim(
        schema_version="caretrust.active-credential-claim.v1",
        claim_id="claim:synthetic-hi-cna-1001",
        claim_type="professional_credential",
        credential_profile="hawaii_cna_smoke_v1",
        subject_ref="person:synthetic-leilani-kealoha",
        issuer_ref="org:caretrust-demo",
        jurisdiction="HI",
        registry_id="HI-CNA-SYN-1001",
        credential_type="Certified Nurse Aide",
        valid_from="2024-04-15",
        valid_until="2028-04-15",
        status=ClaimStatus.ACTIVE,
        allowed_audiences=("org:synthetic-care-provider",),
        allowed_purposes=("credentialing",),
        evidence_refs=("artifact:smoke-clean",),
        review_id="review:smoke-clean",
        registry_result_id="registry:smoke-clean",
        issued_at=NOW,
    )


def _request(
    *,
    audience: str = "org:synthetic-care-provider",
    purpose: str = "credentialing",
) -> AuthorizationRequest:
    return AuthorizationRequest(
        request_id=f"request:{audience}:{purpose}",
        subject_ref="person:synthetic-leilani-kealoha",
        claim_id="claim:synthetic-hi-cna-1001",
        requested_claim_type="professional_credential",
        audience=audience,
        purpose=purpose,
        requested_at=NOW,
    )


def _draft() -> DraftCredentialClaim:
    empty = DraftField(value=None, confidence=0, evidence_refs=())
    return DraftCredentialClaim(
        schema_version="caretrust.draft-credential-claim.v1",
        draft_id="draft:synthetic",
        evidence_id="artifact:synthetic",
        subject_ref="person:synthetic-leilani-kealoha",
        claim_type="professional_credential",
        credential_profile="hawaii_cna_smoke_v1",
        status="draft",
        fields=DraftCredentialFields(
            holder_name=empty,
            registry_id=empty,
            credential_type=empty,
            jurisdiction=empty,
            original_or_issue_date=empty,
            expiration_date=empty,
            credential_status=empty,
            restrictions_or_notes=empty,
            issuer_or_source=empty,
        ),
        uncertainties=(),
        blocking_issues=("human review required",),
    )


@pytest.fixture
def trust() -> tuple[
    CareTrustTokenIssuer,
    CareTrustTokenVerifier,
    RevocationRegistry,
]:
    # Private key material exists only in memory for the lifetime of this test.
    key = SigningKeyPair.generate(kid="test-key-1")
    revocations = RevocationRegistry()
    return (
        CareTrustTokenIssuer(
            issuer="https://issuer.synthetic.caretrust.example", signing_key=key
        ),
        CareTrustTokenVerifier(
            issuer="https://issuer.synthetic.caretrust.example",
            public_keys={key.kid: key.public_key},
            revocations=revocations,
        ),
        revocations,
    )


def test_valid_signed_token_round_trip(trust: tuple) -> None:
    issuer, verifier, _ = trust
    token = issuer.issue(_claim(), now=NOW, token_id="token:valid")

    verified = verifier.verify(
        token,
        now=NOW + timedelta(seconds=1),
        expected_audience="org:synthetic-care-provider",
        expected_purpose="credentialing",
        expected_subject_ref="person:synthetic-leilani-kealoha",
        expected_claim_id="claim:synthetic-hi-cna-1001",
    )

    assert verified.token_id == "token:valid"
    assert verified.claim_id == _claim().claim_id
    assert verified.status == "active"


def test_expired_token_is_rejected(trust: tuple) -> None:
    issuer, verifier, _ = trust
    token = issuer.issue(
        _claim(), now=NOW, ttl=timedelta(seconds=30), token_id="token:short"
    )

    with pytest.raises(TokenVerificationError) as error:
        verifier.verify(token, now=NOW + timedelta(seconds=30))

    assert error.value.code is TokenErrorCode.EXPIRED


def test_payload_tampering_invalidates_signature(trust: tuple) -> None:
    issuer, verifier, _ = trust
    token = issuer.issue(_claim(), now=NOW, token_id="token:tamper")
    header, payload, signature = token.split(".")
    padding = "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload + padding))
    data["sub"] = "person:attacker"
    changed = base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    ).rstrip(b"=").decode()

    with pytest.raises(TokenVerificationError) as error:
        verifier.verify(f"{header}.{changed}.{signature}", now=NOW)

    assert error.value.code is TokenErrorCode.SIGNATURE_INVALID


def test_revoked_claim_invalidates_previously_issued_token(trust: tuple) -> None:
    issuer, verifier, revocations = trust
    claim = _claim()
    token = issuer.issue(claim, now=NOW, token_id="token:revoked")
    revocations.revoke_claim(claim.claim_id)

    with pytest.raises(TokenVerificationError) as error:
        verifier.verify(token, now=NOW + timedelta(seconds=1))

    assert error.value.code is TokenErrorCode.REVOKED


def test_valid_claim_and_token_permit(trust: tuple) -> None:
    issuer, verifier, _ = trust
    claim = _claim()
    request = _request()
    token = issuer.issue(claim, now=NOW, token_id="token:permit")

    decision = AuthorizationPolicy(verifier=verifier).decide(
        request, claim, token, now=NOW + timedelta(seconds=1)
    )

    assert decision.decision is DecisionValue.PERMIT
    assert decision.supporting_claim_ids == (claim.claim_id,)


def test_a_draft_can_never_produce_a_permit(trust: tuple) -> None:
    issuer, verifier, _ = trust
    token = issuer.issue(_claim(), now=NOW, token_id="token:draft-test")

    # Deliberately violate the static ActiveCredentialClaim parameter type to
    # prove the runtime boundary also defaults to denial.
    decision = AuthorizationPolicy(verifier=verifier).decide(
        _request(), _draft(), token, now=NOW + timedelta(seconds=1)  # type: ignore[arg-type]
    )

    assert decision.decision is DecisionValue.DENY
    assert decision.supporting_claim_ids == ()
    assert decision.reason_codes == ("REVIEW_REQUIRED", "CLAIM_NOT_ACTIVE_TYPE")


def test_revocation_changes_permit_to_deny(trust: tuple) -> None:
    issuer, verifier, revocations = trust
    claim = _claim()
    request = _request()
    token = issuer.issue(claim, now=NOW, token_id="token:before-revocation")
    policy = AuthorizationPolicy(verifier=verifier)

    before = policy.decide(request, claim, token, now=NOW + timedelta(seconds=1))
    revocations.revoke_claim(claim.claim_id)
    after = policy.decide(request, claim, token, now=NOW + timedelta(seconds=2))

    assert before.decision is DecisionValue.PERMIT
    assert after.decision is DecisionValue.DENY
    assert after.supporting_claim_ids == ()
    assert TokenErrorCode.REVOKED.value in after.reason_codes


def test_revoked_status_cannot_be_issued_or_permitted(trust: tuple) -> None:
    issuer, verifier, _ = trust
    active = _claim()
    token = issuer.issue(active, now=NOW, token_id="token:status-transition")
    revoked = active.model_copy(
        update={"status": ClaimStatus.REVOKED, "revoked_at": NOW}
    )

    with pytest.raises(ValueError, match="only active claims"):
        issuer.issue(revoked, now=NOW)

    decision = AuthorizationPolicy(verifier=verifier).decide(
        _request(), revoked, token, now=NOW + timedelta(seconds=1)
    )
    assert decision.decision is DecisionValue.DENY
    assert decision.supporting_claim_ids == ()
    assert "CLAIM_REVOKED" in decision.reason_codes


def test_audience_and_purpose_are_both_enforced(trust: tuple) -> None:
    issuer, verifier, _ = trust
    claim = _claim()
    token = issuer.issue(claim, now=NOW, token_id="token:scope")

    decision = AuthorizationPolicy(verifier=verifier).decide(
        _request(audience="org:untrusted", purpose="care-planning"),
        claim,
        token,
        now=NOW + timedelta(seconds=1),
    )

    assert decision.decision is DecisionValue.DENY
    assert "AUDIENCE_NOT_ALLOWED" in decision.reason_codes
    assert "PURPOSE_NOT_ALLOWED" in decision.reason_codes
