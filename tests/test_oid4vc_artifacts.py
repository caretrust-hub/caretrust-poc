from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from caretrust.models import AuthorizationDecision, AuthorizationRequest

ROOT = Path(__file__).resolve().parents[1]
STANDARDS = ROOT / "docs" / "standards"
PROFILE = STANDARDS / "oid4vc-exchange-profile.md"
EXAMPLES = STANDARDS / "examples" / "oid4vc"

FILES = {
    name: EXAMPLES / f"{name}.json"
    for name in (
        "credential-issuer-metadata",
        "oauth-authorization-server-metadata",
        "credential-offer",
        "authorization-details",
        "presentation-request",
        "presentation-response",
        "response-decision-linkage",
    )
}

ISSUER = "https://issuer.caretrust.example"
AUTHORIZATION_SERVER = "https://as.caretrust.example"
VERIFIER = "https://verifier.caretrust.example"
CONFIGURATION_ID = "caretrust_hawaii_cna_v1"
DCQL_ID = "caretrust_cna"
CLAIM_ID = "claim:synthetic-hi-cna-1001"
STATE = "state:synthetic-caretrust-oid4vp-001"


def _load(name: str) -> dict:
    return json.loads(FILES[name].read_text(encoding="utf-8"))


def test_all_oid4vc_examples_are_valid_json_and_explicitly_synthetic() -> None:
    assert set(path.stem for path in EXAMPLES.glob("*.json")) == set(FILES)
    for path in FILES.values():
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        serialized = json.dumps(payload).lower()
        assert "synthetic" in serialized or ".caretrust.example" in serialized


def test_issuer_offer_and_authorization_details_are_consistent() -> None:
    metadata = _load("credential-issuer-metadata")
    as_metadata = _load("oauth-authorization-server-metadata")
    offer = _load("credential-offer")
    details = _load("authorization-details")

    assert metadata["credential_issuer"] == offer["credential_issuer"] == ISSUER
    assert metadata["authorization_servers"] == [AUTHORIZATION_SERVER]
    assert as_metadata["issuer"] == AUTHORIZATION_SERVER
    assert metadata["credential_endpoint"] == f"{ISSUER}/credential"

    configurations = metadata["credential_configurations_supported"]
    assert set(configurations) == {CONFIGURATION_ID}
    configuration = configurations[CONFIGURATION_ID]
    assert configuration["format"] == "jwt_vc_json"
    assert configuration["scope"] == CONFIGURATION_ID
    assert configuration["credential_definition"]["type"] == [
        "https://www.w3.org/2018/credentials#VerifiableCredential",
        "https://credentials.caretrust.example/types/ProfessionalCredential",
    ]
    assert "jwt" in configuration["proof_types_supported"]

    assert offer["credential_configuration_ids"] == [CONFIGURATION_ID]
    assert set(offer["grants"]) == {"authorization_code"}
    assert (
        offer["grants"]["authorization_code"]["issuer_state"]
        == "issuer-state:synthetic-caretrust-001"
    )

    assert len(details["authorization_details"]) == 1
    detail = details["authorization_details"][0]
    assert detail["type"] == "openid_credential"
    assert detail["locations"] == [ISSUER]
    assert detail["credential_configuration_id"] == CONFIGURATION_ID

    advertised_paths = {
        tuple(claim["path"])
        for claim in configuration["credential_metadata"]["claims"]
    }
    requested_paths = {tuple(claim["path"]) for claim in detail["claims"]}
    assert requested_paths == advertised_paths


def test_oauth_metadata_is_bounded_to_authorization_code_with_pkce() -> None:
    metadata = _load("oauth-authorization-server-metadata")
    assert metadata == {
        "authorization_details_types_supported": ["openid_credential"],
        "authorization_endpoint": f"{AUTHORIZATION_SERVER}/authorize",
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code"],
        "issuer": AUTHORIZATION_SERVER,
        "response_types_supported": ["code"],
        "token_endpoint": f"{AUTHORIZATION_SERVER}/token",
    }


def test_oid4vp_dcql_request_and_response_link_by_state_and_query_id() -> None:
    request = _load("presentation-request")
    response = _load("presentation-response")

    assert request["client_id"] == VERIFIER
    assert request["response_uri"] == f"{VERIFIER}/oid4vp/response"
    assert request["response_type"] == "vp_token"
    assert request["response_mode"] == "direct_post"
    assert "redirect_uri" not in request
    assert request["nonce"] == "nonce:synthetic-caretrust-oid4vp-001"
    assert request["state"] == response["state"] == STATE

    credentials = request["dcql_query"]["credentials"]
    assert len(credentials) == 1
    query = credentials[0]
    assert query["id"] == DCQL_ID
    assert re.fullmatch(r"[A-Za-z0-9_-]+", query["id"])
    assert query["format"] == "jwt_vc_json"
    assert set(response["vp_token"]) == {query["id"]}
    assert response["vp_token"][query["id"]] == [
        "SYNTHETIC_PRESENTATION_PLACEHOLDER_NOT_A_CREDENTIAL"
    ]

    values_by_path = {
        tuple(claim["path"]): claim["values"] for claim in query["claims"]
    }
    assert values_by_path[("credentialSubject", "claimId")] == [CLAIM_ID]
    assert values_by_path[("credentialSubject", "credentialProfile")] == [
        "hawaii_cna_smoke_v1"
    ]
    assert values_by_path[("credentialSubject", "credentialType")] == [
        "Certified Nurse Aide"
    ]
    assert values_by_path[("credentialSubject", "jurisdiction")] == ["HI"]
    assert values_by_path[("credentialSubject", "status")] == ["active"]


def test_response_linkage_reuses_caretrust_contracts_and_reason_codes() -> None:
    request = _load("presentation-request")
    response = _load("presentation-response")
    linkage = _load("response-decision-linkage")

    authorization_request = AuthorizationRequest.model_validate(
        linkage["caretrust_authorization_request"]
    )
    authorization_decision = AuthorizationDecision.model_validate(
        linkage["caretrust_authorization_decision"]
    )

    assert linkage["illustrative_only"] is True
    assert (
        linkage["record_type"]
        == "caretrust.oid4vc-response-decision-linkage.v1"
    )
    assert linkage["presentation_request_id"] == (
        request["caretrust_request_context"]["request_id"]
    )
    assert linkage["state"] == request["state"] == response["state"]
    assert linkage["dcql_credential_query_id"] == DCQL_ID
    assert authorization_request.audience == (
        request["caretrust_request_context"]["audience"]
    )
    assert authorization_request.purpose == (
        request["caretrust_request_context"]["purpose"]
    )
    assert authorization_request.claim_id == CLAIM_ID
    assert authorization_decision.request_id == authorization_request.request_id
    assert authorization_decision.decision.value == "permit"
    assert authorization_decision.reason_codes == (
        "POLICY_REQUIREMENTS_SATISFIED",
    )
    assert authorization_decision.supporting_claim_ids == (CLAIM_ID,)
    assert authorization_decision.policy_version == "caretrust.authorization.v1"


def test_service_urls_and_identifiers_are_stable_and_nonproduction() -> None:
    issuer = _load("credential-issuer-metadata")
    authorization_server = _load("oauth-authorization-server-metadata")
    request = _load("presentation-request")

    service_urls = {
        issuer["credential_issuer"],
        issuer["credential_endpoint"],
        *issuer["authorization_servers"],
        authorization_server["issuer"],
        authorization_server["authorization_endpoint"],
        authorization_server["token_endpoint"],
        request["client_id"],
        request["response_uri"],
    }
    for url in service_urls:
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.hostname is not None
        assert parsed.hostname.endswith(".caretrust.example")
        assert parsed.username is None
        assert parsed.password is None
        assert parsed.query == ""
        assert parsed.fragment == ""

    assert _load("credential-offer")["credential_configuration_ids"] == [
        CONFIGURATION_ID
    ]
    assert request["dcql_query"]["credentials"][0]["id"] == DCQL_ID
    assert (
        request["caretrust_request_context"]["request_id"]
        == "request:oid4vp:synthetic-001"
    )


def test_oid4vc_artifacts_contain_no_secrets_or_personal_data() -> None:
    text = PROFILE.read_text(encoding="utf-8") + "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in FILES.values()
    )
    forbidden = (
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.",
    )
    for pattern in forbidden:
        assert re.search(pattern, text) is None


def test_profile_states_contract_only_and_nonconformance_boundaries() -> None:
    profile = PROFILE.read_text(encoding="utf-8")
    for boundary in (
        "illustrative, contract-tested exchange sketch",
        "not runtime behavior",
        "not asserted to be a",
        "not a conformance claim",
        "intentionally invalid synthetic presentation placeholder",
    ):
        assert boundary in profile
    assert "OpenID for Verifiable Credential Issuance 1.0 Final" in profile
    assert "OpenID for Verifiable Presentations 1.0 Final" in profile
