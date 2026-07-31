"""Generate the public, token-safe local OAuth/OIDC harness trace."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from caretrust.app_onboarding import ApplicationOnboardingCompiler, make_application_description
from caretrust.auth_harness import AUTH_DETAIL_TYPE, CASE_APP_ID, CASE_ID, CLIENT_ID, PURPOSE, REDIRECT_URI, RESOURCE, AuthorizationCodeRequest, DeveloperClientMetadata, LocalAuthHarness, RichAuthorizationDetail, pkce_s256
from caretrust.case_bundle import build_synthetic_case_bundle, evaluate_case_permission

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "validation" / "auth-harness-trace.json"
NOW = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
VERIFIER = "v" * 64
NONCE = "nonce:synthetic-auth-harness-001"


def compiled_scheduling_draft():
    source = make_application_description(
        application_id=CASE_APP_ID,
        source_id="source:auth-harness-scheduling",
        description=(
            "Synthetic scheduling application at "
            "https://scheduling.synthetic.example creates and reschedules "
            "appointments for appointment management."
        ),
    )
    return ApplicationOnboardingCompiler().compile_application(source, now=NOW, run_id="compiler-run:auth-harness-001").draft


def fresh_case_decision(now: datetime = NOW, *, delegation_status: str | None = None, delegation_valid_until: str | None = None) -> dict[str, object]:
    bundle = build_synthetic_case_bundle()
    objects = bundle["canonical_objects"]
    request = next(item for item in objects["permission_requests"] if item["request_id"] == "request:case:family-permit-001")
    grant = dict(objects["delegation_grant"])
    if delegation_status is not None:
        grant["status"] = delegation_status
        if delegation_status == "revoked":
            grant["revoked_at"] = now.isoformat().replace("+00:00", "Z")
    if delegation_valid_until is not None:
        grant["valid_until"] = delegation_valid_until
    decision = evaluate_case_permission(request, relationship_claim=objects["relationship_claim"], delegation_grant=grant, approved_items={item["approved_item_id"]: item for item in objects["approved_document_items"]}, as_of=now)
    decision["as_of_dt"] = now
    return decision


def build_trace() -> dict[str, object]:
    harness = LocalAuthHarness()
    id_token = harness.issue_synthetic_oidc_id_token(caregiver_ref="account:synthetic-leilani", nonce=NONCE, now=NOW)
    identity = harness.link_upstream_identity(caregiver_ref="account:synthetic-leilani", upstream_id_token=id_token, expected_nonce=NONCE, now=NOW)
    draft = compiled_scheduling_draft()
    metadata = DeveloperClientMetadata(client_id=CLIENT_ID, application_id=CASE_APP_ID, redirect_uris=(REDIRECT_URI,))
    registration = harness.register_application(draft, metadata, reviewer_ref="reviewer:synthetic-org-admin-001", now=NOW)
    request = AuthorizationCodeRequest(request_id="auth-request:synthetic-scheduling-001", case_id=CASE_ID, caregiver_ref=identity.caregiver_ref, identity_link_id=identity.link_id, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI, state="state:synthetic-auth-harness-001", nonce=NONCE, code_challenge=pkce_s256(VERIFIER), authorization_details=(RichAuthorizationDetail(type=AUTH_DETAIL_TYPE, locations=(RESOURCE,), actions=registration.allowed_actions, datatypes=registration.allowed_datatypes, purpose=PURPOSE),), resource=RESOURCE, purpose=PURPOSE, requested_at=NOW)
    decision = fresh_case_decision()
    code, code_receipt = harness.authorize(request, identity_link=identity, registration=registration, fresh_case_decision=decision, now=NOW)
    token, token_receipt = harness.exchange_code(code=code, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI, code_verifier=VERIFIER, resource=RESOURCE, audience=RESOURCE, purpose=PURPOSE, now=NOW)
    verified = harness.verify_downstream_token(token, resource=RESOURCE, audience=RESOURCE, client_id=CLIENT_ID, purpose=PURPOSE, now=NOW)
    return {"record_type": "caretrust.local-auth-harness-trace.v1", "evidence_status": "executed_local", "network_calls": False, "synthetic": True, "upstream_identity_link": identity.model_dump(mode="json"), "application_onboarding_draft": draft.model_dump(mode="json"), "developer_client_metadata": metadata.model_dump(mode="json"), "human_reviewed_registration": registration.model_dump(mode="json"), "authorization_code_request": request.model_dump(mode="json"), "fresh_case_decision": {key: value for key, value in decision.items() if key != "as_of_dt"}, "authorization_code_receipt": code_receipt.model_dump(mode="json"), "downstream_token_receipt": token_receipt.model_dump(mode="json"), "introspection": {"active": True, "decoded_claims": verified}, "public_key": harness.public_jwk(), "non_claims": ["The locally verified synthetic upstream OIDC ID token terminates at CareTrust; only a hash and identity link are retained.", "No external IdP metadata, identity proofing, Cognito, Login.gov, HTTP endpoint, or production deployment was exercised.", "The public trace omits upstream/downstream bearer tokens and all private key material."]}


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_trace(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
