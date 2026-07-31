from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

import pytest

from caretrust.auth_harness import AUTH_DETAIL_TYPE, CASE_APP_ID, CASE_ID, CLIENT_ID, PURPOSE, REDIRECT_URI, RESOURCE, AuthHarnessError, AuthorizationCodeRequest, DeveloperClientMetadata, LocalAuthHarness, RichAuthorizationDetail, pkce_s256
from scripts.build_auth_harness_trace import NONCE, NOW, VERIFIER, compiled_scheduling_draft, fresh_case_decision, main

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "validation" / "auth-harness-trace.json"


def _prepared():
    harness = LocalAuthHarness()
    token = harness.issue_synthetic_oidc_id_token(caregiver_ref="account:synthetic-leilani", nonce=NONCE, now=NOW)
    link = harness.link_upstream_identity(caregiver_ref="account:synthetic-leilani", upstream_id_token=token, expected_nonce=NONCE, now=NOW)
    draft = compiled_scheduling_draft()
    registration = harness.register_application(draft, DeveloperClientMetadata(client_id=CLIENT_ID, application_id=CASE_APP_ID, redirect_uris=(REDIRECT_URI,)), reviewer_ref="reviewer:synthetic-001", now=NOW)
    request = AuthorizationCodeRequest(request_id="auth-request:test-001", case_id=CASE_ID, caregiver_ref=link.caregiver_ref, identity_link_id=link.link_id, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI, state="state:test-001", nonce=NONCE, code_challenge=pkce_s256(VERIFIER), authorization_details=(RichAuthorizationDetail(type=AUTH_DETAIL_TYPE, locations=(RESOURCE,), actions=registration.allowed_actions, datatypes=registration.allowed_datatypes, purpose=PURPOSE),), resource=RESOURCE, purpose=PURPOSE, requested_at=NOW)
    code, receipt = harness.authorize(request, identity_link=link, registration=registration, fresh_case_decision=fresh_case_decision(), now=NOW)
    return harness, link, registration, request, code, receipt


def _exchange(harness, code, **overrides):
    return harness.exchange_code(code=code, client_id=overrides.get("client_id", CLIENT_ID), redirect_uri=overrides.get("redirect_uri", REDIRECT_URI), code_verifier=overrides.get("code_verifier", VERIFIER), resource=overrides.get("resource", RESOURCE), audience=overrides.get("audience", RESOURCE), purpose=overrides.get("purpose", PURPOSE), now=overrides.get("now", NOW))


def test_verified_oidc_identity_is_causal_and_state_nonce_are_bound() -> None:
    harness, link, registration, request, code, receipt = _prepared()
    assert receipt.state == request.state
    token, token_receipt = _exchange(harness, code)
    claims = harness.verify_downstream_token(token, resource=RESOURCE, audience=RESOURCE, client_id=CLIENT_ID, purpose=PURPOSE, now=NOW)
    assert claims["aud"] == RESOURCE and claims["client_id"] == CLIENT_ID and claims["iss"] == harness.issuer
    assert claims["ct_case_decision_id"] == fresh_case_decision()["decision_id"]
    assert claims["caretrust_actions"] == ["schedule_appointments"]
    assert claims["caretrust_datatypes"] == sorted(registration.allowed_datatypes)
    assert token_receipt.token_sha256 != token
    mismatched = request.model_copy(update={"caregiver_ref": "account:wrong"})
    with pytest.raises(AuthHarnessError) as error:
        harness.authorize(mismatched, identity_link=link, registration=registration, fresh_case_decision=fresh_case_decision(), now=NOW)
    assert error.value.code == "IDENTITY_LINK_MISMATCH"
    unverified = link.model_copy(update={"oidc_id_token_verified_locally": False})
    with pytest.raises(AuthHarnessError) as error:
        harness.authorize(request, identity_link=unverified, registration=registration, fresh_case_decision=fresh_case_decision(), now=NOW)
    assert error.value.code == "IDENTITY_LINK_UNVERIFIED_OR_STALE"
    nonce_mismatch = request.model_copy(update={"nonce": "nonce:wrong"})
    with pytest.raises(AuthHarnessError) as error:
        harness.authorize(nonce_mismatch, identity_link=link, registration=registration, fresh_case_decision=fresh_case_decision(), now=NOW)
    assert error.value.code == "IDENTITY_LINK_MISMATCH"


@pytest.mark.parametrize(("overrides", "expected"), [({"client_id": "client:wrong"}, "CLIENT_MISMATCH"), ({"redirect_uri": "https://wrong.synthetic.invalid/callback"}, "REDIRECT_URI_MISMATCH"), ({"code_verifier": "x" * 64}, "PKCE_VERIFIER_MISMATCH"), ({"resource": "https://wrong.synthetic.invalid"}, "RESOURCE_MISMATCH"), ({"audience": "https://wrong.synthetic.invalid"}, "AUDIENCE_MISMATCH"), ({"purpose": "wrong"}, "PURPOSE_MISMATCH")])
def test_exchange_rejects_all_bindings(overrides, expected) -> None:
    harness, _, _, _, code, _ = _prepared()
    with pytest.raises(AuthHarnessError) as error:
        _exchange(harness, code, **overrides)
    assert error.value.code == expected


def test_code_lifecycle_and_case_basis_denials() -> None:
    harness, _, _, _, code, _ = _prepared()
    with pytest.raises(AuthHarnessError) as error:
        _exchange(harness, code, now=NOW + timedelta(minutes=3))
    assert error.value.code == "CODE_EXPIRED"
    harness, _, _, _, code, _ = _prepared(); _exchange(harness, code)
    with pytest.raises(AuthHarnessError) as error: _exchange(harness, code)
    assert error.value.code == "CODE_USED"
    harness, link, registration, request, _, _ = _prepared()
    for decision in (fresh_case_decision(delegation_status="revoked"), fresh_case_decision(delegation_valid_until="2026-07-29")):
        with pytest.raises(AuthHarnessError) as error:
            harness.authorize(request, identity_link=link, registration=registration, fresh_case_decision=decision, now=NOW)
        assert error.value.code == "CASE_DECISION_DENIED"
    mismatched_action = fresh_case_decision()
    mismatched_action["action"] = "view_appointments"
    with pytest.raises(AuthHarnessError) as error:
        harness.authorize(
            request,
            identity_link=link,
            registration=registration,
            fresh_case_decision=mismatched_action,
            now=NOW,
        )
    assert error.value.code == "CASE_ACTION_MISMATCH"


def test_rar_profile_and_action_datatype_type_escalation_rejected() -> None:
    harness, link, registration, request, _, _ = _prepared()
    for update in (
        {"authorization_details": (RichAuthorizationDetail(type="unknown", locations=(RESOURCE,), actions=registration.allowed_actions, datatypes=registration.allowed_datatypes, purpose=PURPOSE),)},
        {"authorization_details": (RichAuthorizationDetail(type=AUTH_DETAIL_TYPE, locations=(RESOURCE,), actions=("delete",), datatypes=registration.allowed_datatypes, purpose=PURPOSE),)},
        {"authorization_details": (RichAuthorizationDetail(type=AUTH_DETAIL_TYPE, locations=(RESOURCE,), actions=registration.allowed_actions, datatypes=("all_records",), purpose=PURPOSE),)},
    ):
        with pytest.raises(AuthHarnessError) as error:
            harness.authorize(request.model_copy(update=update), identity_link=link, registration=registration, fresh_case_decision=fresh_case_decision(), now=NOW)
        assert error.value.code == "RAR_BINDING_INVALID"
    self_registering = compiled_scheduling_draft().model_copy(update={"registration_permitted": True})
    with pytest.raises(AuthHarnessError) as error:
        harness.register_application(self_registering, DeveloperClientMetadata(client_id=CLIENT_ID, application_id=CASE_APP_ID, redirect_uris=(REDIRECT_URI,)), reviewer_ref="reviewer:synthetic-001", now=NOW)
    assert error.value.code == "AI_DRAFT_CANNOT_REGISTER"


def test_token_issuer_nbf_and_client_binding_are_verified() -> None:
    harness, _, _, _, code, _ = _prepared(); token, _ = _exchange(harness, code)
    with pytest.raises(AuthHarnessError) as error:
        harness.verify_downstream_token(token, resource=RESOURCE, audience=RESOURCE, client_id=CLIENT_ID, purpose=PURPOSE, now=NOW - timedelta(minutes=1))
    assert error.value.code == "TOKEN_EXPIRED"
    assert harness.verify_downstream_token(token, resource=RESOURCE, audience=RESOURCE, client_id=CLIENT_ID, purpose=PURPOSE, now=NOW)["client_id"] == CLIENT_ID
    with pytest.raises(AuthHarnessError) as error:
        harness.verify_downstream_token(token, resource=RESOURCE, audience=RESOURCE, client_id="client:wrong", purpose=PURPOSE, now=NOW)
    assert error.value.code == "TOKEN_CLIENT_ID_MISMATCH"


def test_public_trace_is_safe_and_external_paths_are_not_exercised() -> None:
    main(); artifact = json.loads(ARTIFACT.read_text(encoding="utf-8")); serialized = json.dumps(artifact).lower()
    assert artifact["evidence_status"] == "executed_local" and artifact["network_calls"] is False
    for forbidden in ("upstream.synthetic", "code.synthetic", "private_key", "access_token", "bearer_token"):
        assert forbidden not in serialized
    assert artifact["upstream_identity_link"]["oidc_id_token_verified_locally"] is True
    assert artifact["human_reviewed_registration"]["source_draft_id"] == artifact["application_onboarding_draft"]["draft_id"]
