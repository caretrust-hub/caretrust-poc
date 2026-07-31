"""Tests for the deterministic six-minute judge walkthrough contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import caretrust.judge_walkthrough as walkthrough_module
from caretrust.judge_walkthrough import (
    JudgeWalkthroughError,
    build_judge_walkthrough_contract,
    render_walkthrough,
    validate_judge_walkthrough_contract,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "validation" / "judge-walkthrough-contract.json"


def test_artifact_reproduces_from_retained_canonical_sources() -> None:
    built = build_judge_walkthrough_contract()
    assert json.loads(ARTIFACT.read_text(encoding="utf-8")) == built
    validate_judge_walkthrough_contract(built)


def test_eight_steps_fit_six_minutes_and_are_source_bound() -> None:
    contract = build_judge_walkthrough_contract()
    assert contract["suggested_total_seconds"] == 340
    assert contract["suggested_total_seconds"] <= 360
    assert len(contract["steps"]) == 8
    for step in contract["steps"][:-1]:
        assert step["source_refs"]
        assert step["non_claims"]
        assert all(len(source["artifact_sha256"]) == 64 for source in step["source_refs"])
        assert all(source["canonical_ids"] for source in step["source_refs"])


def test_required_judge_flow_is_explicit_and_honest() -> None:
    steps = {step["step_id"]: step for step in build_judge_walkthrough_contract()["steps"]}
    assert len(steps["01-case-context"]["facts"]["caregivers"]) == 3
    assert steps["02-ai-intent"]["facts"]["human_approval_boundary"]["authority_effect"] == "none"
    assert steps["03-ai-app-onboarding"]["facts"]["proposed_rar"]
    assert steps["04-oidc-pkce-rar-token"]["facts"]["pkce"]["method"] == "S256"
    assert steps["05-fhir-smart-reference-app"]["facts"]["reference_app_result"]["external_fhir_server_executed"] is False
    assert steps["06-revocation-fresh-deny"]["facts"]["after_fresh_request"]["decision"] == "deny"
    assert steps["07-mcp-inspection"]["facts"]["state_mutated"] is False


def test_federation_segment_is_explicitly_planned_when_no_artifact_exists() -> None:
    federation = build_judge_walkthrough_contract()["steps"][-1]
    assert federation["step_id"] == "08-two-hub-federation"
    assert federation["evidence_status"] == "executed_local"
    assert federation["facts"]["status"] == "executed_local"
    assert federation["facts"]["segment_skipped"] is False
    assert len(federation["source_refs"][0]["artifact_sha256"]) == 64
    assert federation["facts"]["fresh_local_caregiver_decision"]["decision"] == "permit"
    assert all(item["entity_trust_only"] is True for item in federation["facts"]["participant_and_client_trust"])


def test_federation_segment_fails_closed_when_artifact_is_missing_stale_or_tampered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(walkthrough_module, "FEDERATION_ARTIFACT", missing)
    with pytest.raises(JudgeWalkthroughError, match="missing"):
        build_judge_walkthrough_contract()

    source = ROOT / "artifacts" / "validation" / "federation-two-hub-lab.json"
    stale = json.loads(source.read_text(encoding="utf-8"))
    stale["fresh_local_caregiver_decision_after_trust"]["case_bundle_sha256"] = "0" * 64
    material = dict(stale)
    material.pop("artifact_payload_sha256")
    stale["artifact_payload_sha256"] = walkthrough_module._hash(material)
    stale_path = tmp_path / "stale.json"
    stale_path.write_text(json.dumps(stale), encoding="utf-8")
    monkeypatch.setattr(walkthrough_module, "FEDERATION_ARTIFACT", stale_path)
    with pytest.raises(JudgeWalkthroughError, match="stale"):
        build_judge_walkthrough_contract()

    tampered = json.loads(source.read_text(encoding="utf-8"))
    tampered["negative_exercises"]["tampered_statement"] = "PERMIT"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(walkthrough_module, "FEDERATION_ARTIFACT", tampered_path)
    with pytest.raises(JudgeWalkthroughError, match="hash|tampered"):
        build_judge_walkthrough_contract()


def test_cli_render_contains_step_ids_elapsed_time_and_hashes() -> None:
    rendered = render_walkthrough(build_judge_walkthrough_contract())
    assert "CareTrust judge walkthrough (340 seconds)" in rendered
    assert "[04-oidc-pkce-rar-token] +70s" in rendered
    assert "[08-two-hub-federation] +30s" in rendered
    assert "artifacts/validation/federation-two-hub-lab.json sha256=" in rendered
