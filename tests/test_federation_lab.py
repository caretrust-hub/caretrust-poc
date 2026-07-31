from __future__ import annotations

import json
from pathlib import Path

import pytest

from caretrust.federation import FederationErrorCode, FederationTrustError, apply_metadata_policy
from caretrust.federation_lab import LAB_PROFILE, build_two_hub_federation_lab
from scripts.build_federation_lab import OUTPUT, write_output


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "federation" / "two-hub-lab.json"


def test_two_independent_hubs_resolve_signed_participant_and_client_metadata() -> None:
    lab = build_two_hub_federation_lab()
    assert lab["artifact_type"] == LAB_PROFILE
    assert lab["evidence_status"] == "executed_local"
    assert lab["network_calls"] is False
    hubs = lab["two_independent_hubs"]
    assert len(hubs) == 2
    assert len({hub["trust_anchor_id"] for hub in hubs}) == 2
    assert len({hub["active_anchor_kid"] for hub in hubs}) == 2
    chains = lab["participant_and_client_entity_trust"]
    assert {chain["role"] for chain in chains} == {"participant_organization", "care_application_client"}
    assert all(chain["entity_trust_only"] is True for chain in chains)
    client = next(chain for chain in chains if chain["role"] == "care_application_client")
    assert client["metadata_after_policy"]["openid_relying_party"]["grant_types"] == ["authorization_code"]
    assert client["metadata_policy"]["openid_relying_party"]["grant_types"] == {"value": ["authorization_code"]}


def test_metadata_policy_fails_closed_when_signed_metadata_exceeds_one_of() -> None:
    with pytest.raises(FederationTrustError) as caught:
        apply_metadata_policy(
            {"openid_relying_party": {"grant_types": ["authorization_code", "implicit"]}},
            {"openid_relying_party": {"grant_types": {"one_of": ["authorization_code"]}}},
        )
    assert caught.value.code is FederationErrorCode.METADATA_POLICY_VIOLATION


def test_negative_and_rollover_exercises_fail_or_transition_as_expected() -> None:
    lab = build_two_hub_federation_lab()
    assert lab["negative_exercises"] == {
        "expired_statement": "FEDERATION_STATEMENT_EXPIRED",
        "tampered_statement": "FEDERATION_SIGNATURE_INVALID",
        "untrusted_anchor": "FEDERATION_MISSING_TRUST_ANCHOR",
        "stale_leaf_rollover": "FEDERATION_JWKS_MISMATCH",
    }
    rollover = lab["key_rollover"]
    assert rollover["transition"] == "fresh_anchor_statement_required"
    assert len(rollover["new_kids"]) == len(rollover["old_kids"]) + 1
    assert rollover["resolved_with_fresh_statement"] is True


def test_federation_trust_is_not_a_permission_and_fresh_case_policy_is_separate() -> None:
    lab = build_two_hub_federation_lab()
    decision = lab["fresh_local_caregiver_decision_after_trust"]
    assert decision["decision"] == "permit"
    assert decision["reason_code"] == "POLICY_REQUIREMENTS_SATISFIED"
    assert decision["policy_version"] == "case-access.v1"
    assert not ({"trust_anchor_id", "chain_sha256", "entity_id"} & set(decision))
    assert "separate fresh call" in lab["claim_boundary"][1]


def test_public_artifact_and_fixture_have_no_private_key_material() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["synthetic_only"] is True
    assert fixture["network_calls"] is False
    path = write_output()
    assert path == OUTPUT
    artifact_text = path.read_text(encoding="utf-8")
    artifact = json.loads(artifact_text)
    assert artifact["private_key_material_in_artifact"] is False
    assert '"d"' not in artifact_text
    assert "BEGIN PRIVATE KEY" not in artifact_text
