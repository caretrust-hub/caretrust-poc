"""Tests for the derived dashboard integration contract."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from caretrust.dashboard_contract import (
    FORBIDDEN_DISCLOSURE_TERMS,
    build_dashboard_contract,
    canonical_json,
    validate_dashboard_contract,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "validation" / "dashboard-contract.json"


def test_dashboard_artifact_reproduces_from_canonical_inputs() -> None:
    built = build_dashboard_contract()
    retained = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert retained == built
    assert built["schema_version"] == "caretrust.dashboard-contract.v1"


def test_every_permission_resolves_to_canonical_decision_and_request_hash() -> None:
    contract = build_dashboard_contract()
    permissions = contract["views"]["permissions"]
    assert len(permissions) == 10
    assert all(row["source_decision_id"] in row["canonical_refs"] for row in permissions)
    assert all(len(row["request_sha256"]) == 64 for row in permissions)
    validate_dashboard_contract(contract)


def test_validation_rejects_a_ui_only_decision() -> None:
    contract = build_dashboard_contract()
    tampered = json.loads(json.dumps(contract))
    tampered["views"]["permissions"][0]["decision"] = "deny"
    material = dict(tampered)
    material.pop("dashboard_sha256")
    tampered["dashboard_sha256"] = sha256(canonical_json(material).encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="UI-only decision"):
        validate_dashboard_contract(tampered)


def test_reference_client_receipts_are_minimum_disclosure_only() -> None:
    contract = build_dashboard_contract()
    for row in contract["views"]["applications_and_receipts"]["reference_client_receipts"]:
        rendered = canonical_json(row["disclosure"]).casefold()
        assert not any(term in rendered for term in FORBIDDEN_DISCLOSURE_TERMS)
        assert "supporting_canonical_ids" not in row["disclosure"]
        assert "raw_document" not in row["disclosure"]


def test_ai_review_and_timelines_are_evidence_linked_and_honest() -> None:
    contract = build_dashboard_contract()
    ai_review = contract["views"]["ai_review"]
    candidate_rows = ai_review["candidate_to_draft"]
    assert candidate_rows
    assert all(row["exact_candidate_quote"] and row["bounded_value"] for row in candidate_rows)
    assert all(row["human_review_boundary"]["required"] for row in candidate_rows)
    assert all(row["human_review_boundary"]["authority_effect"] == "none" for row in candidate_rows)
    app_rows = [row for row in candidate_rows if row["compiler_kind"] == "application"]
    assert {row["draft_binding_field"] for row in app_rows} == {
        "proposed_profile/capability", "proposed_rar.actions",
        "minimum_data_plan", "proposed_rar.locations"
    }
    assert all(row["draft_binding_evidence_refs"] for row in app_rows)
    assert {row["stage"] for row in ai_review["correction_timeline"]} == {
        "before_accountable_review", "after_accountable_review"
    }
    assert len(contract["views"]["revocation_timeline"]) == 4
    assert all(row["evidence_status"] in {"executed_local", "contract_tested"} for row in candidate_rows)


def test_revocations_link_only_their_specific_before_and_after_decisions() -> None:
    contract = build_dashboard_contract()
    rows = {row["row_id"]: row for row in contract["views"]["revocation_timeline"]}
    assert rows["revocation:delegation"]["before_request_id"] == "request:case:family-permit-001"
    assert rows["revocation:delegation"]["after_request_id"] == "request:case:family-revoked-001"
    assert rows["revocation:credential"]["before_request_id"] == "request:case:cna-permit-001"
    assert rows["revocation:credential"]["after_request_id"] == "request:case:cna-revoked-001"
    assert rows["revocation:respite"]["before_request_id"] == "request:case:respite-historical-001"
    assert rows["revocation:respite"]["after_request_id"] == "request:case:respite-revoked-001"
    assert rows["revocation:document-share"]["linkage_type"] == "canonical_document_share"
    assert rows["revocation:document-share"]["canonical_fresh_deny_available"] is True
    assert rows["revocation:document-share"]["before_request_id"] == "document-share-request:synthetic-scheduling-permit-001"
    assert rows["revocation:document-share"]["after_request_id"] == "document-share-request:synthetic-after-revocation-001"
    assert rows["revocation:document-share"]["before_decision_id"] == "decision:document-share-request:synthetic-scheduling-permit-001"
    assert rows["revocation:document-share"]["after_decision_id"] == "decision:document-share-request:synthetic-after-revocation-001"
    for key in ("revocation:delegation", "revocation:credential", "revocation:respite"):
        row = rows[key]
        decision_refs = {ref for ref in row["canonical_refs"] if ref.startswith("decision:case:")}
        assert decision_refs == {row["before_decision_id"], row["after_decision_id"]}


def test_core_mapping_and_message_labels_do_not_claim_deployment() -> None:
    contract = build_dashboard_contract()
    standards = contract["views"]["standards_messages_mappings_gaps"]
    assert standards["messages"]
    assert all(row["evidence_status"] == "executed_local" for row in standards["messages"])
    assert all(row["conformance"] == "mapped_only" for row in standards["mappings"])
    assert any("No live OAuth/OIDC" in gap for gap in standards["gaps"])
