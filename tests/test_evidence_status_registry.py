from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "standards" / "evidence-status-registry.json"
LINEAGES_PATH = ROOT / "docs" / "standards" / "provenance-lineages.json"
MANIFEST_SCRIPT = ROOT / "scripts" / "build_poc_evidence_manifest.py"

EXPECTED_STATUS_IDS = {
    "retained_aws",
    "executed_local",
    "contract_tested",
    "local_simulation",
    "mapped_only",
    "planned",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_registry(registry: dict) -> None:
    assert registry["schema_version"] == "caretrust.evidence-status-registry.v1"
    statuses = registry["statuses"]
    status_ids = [item["id"] for item in statuses]
    assert set(status_ids) == EXPECTED_STATUS_IDS
    assert len(status_ids) == len(set(status_ids))
    assert all(item["display_label"].strip() for item in statuses)
    assert all(item["description"].strip() for item in statuses)

    capability_ids: set[str] = set()
    for capability in registry["capabilities"]:
        capability_id = capability["capability_id"]
        assert capability_id not in capability_ids
        capability_ids.add(capability_id)
        assert capability["evidence_status"] in EXPECTED_STATUS_IDS
        assert capability["boundary"].strip()
        assert capability["evidence"]
        for relative in capability["evidence"]:
            assert (ROOT / relative).is_file(), relative


def test_registry_defines_only_the_six_canonical_evidence_statuses() -> None:
    _validate_registry(_load(REGISTRY_PATH))


def test_unknown_evidence_status_fails_registry_validation() -> None:
    registry = copy.deepcopy(_load(REGISTRY_PATH))
    registry["capabilities"][0]["evidence_status"] = "almost_implemented"
    with pytest.raises(AssertionError):
        _validate_registry(registry)


def test_manifest_status_matrix_is_sourced_from_registry() -> None:
    spec = importlib.util.spec_from_file_location(
        "build_poc_evidence_manifest_status_test",
        MANIFEST_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    registry = _load(REGISTRY_PATH)
    expected = {
        item["capability_id"]: item["evidence_status"]
        for item in registry["capabilities"]
        if item["include_in_manifest"]
    }
    actual = {
        item["capability_id"]: item["status"]
        for item in module.IMPLEMENTATION_STATUS_MATRIX
    }
    assert actual == expected


def test_documented_lineages_use_registry_statuses_and_explicit_relations() -> None:
    lineages = _load(LINEAGES_PATH)
    assert lineages["schema_version"] == "caretrust.provenance-lineages.v1"
    assert "Matching identifier text is not proof" in (
        lineages["canonicalization_rule"]
    )

    trace_ids = [item["trace_id"] for item in lineages["trace_families"]]
    assert len(trace_ids) == len(set(trace_ids))
    assert all(
        item["evidence_status"] in EXPECTED_STATUS_IDS
        for item in lineages["trace_families"]
    )
    assert all(item["terminal_state"] for item in lineages["trace_families"])
    assert all(item["source_artifacts"] for item in lineages["trace_families"])
    for trace in lineages["trace_families"]:
        for relative in trace["source_artifacts"]:
            assert (ROOT / relative).is_file(), relative

    known = set(trace_ids)
    for relation in lineages["relations"]:
        assert relation["from_trace_id"] in known
        assert relation["to_trace_id"] is None or relation["to_trace_id"] in known
        assert relation["relation"]

    aws = next(
        item
        for item in lineages["trace_families"]
        if item["evidence_status"] == "retained_aws"
    )
    lifecycle = next(
        item
        for item in lineages["trace_families"]
        if item["trace_id"]
        == "deterministic-lifecycle-retained-evaluation-clean"
    )
    assert aws["terminal_state"] == "unverified_draft_with_blocking_uncertainties"
    assert aws["identifiers"]["claim_id"] is None
    assert lifecycle["terminal_state"] == "fresh_request_denied_token_revoked"
    assert (
        aws["integrity"]["model_raw_response_sha256"]
        != lifecycle["integrity"]["retained_model_raw_response_sha256"]
    )


def test_docs_and_demo_use_canonical_status_ids() -> None:
    checked_files = (
        ROOT / "README.md",
        ROOT / "docs" / "POC-EVIDENCE.md",
        ROOT / "docs" / "standards" / "README.md",
        ROOT / "docs" / "standards" / "standards-status.md",
        ROOT / "docs" / "standards" / "fhir-r4-practitioner-qualification-mapping.md",
        ROOT / "docs" / "standards" / "fhir-r4-projection-profile.md",
        ROOT / "docs" / "standards" / "oid4vc-exchange-profile.md",
        ROOT / "docs" / "standards" / "openid-federation-trust-profile.md",
        ROOT / "demo" / "index.html",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_files)
    for status_id in EXPECTED_STATUS_IDS:
        assert status_id in combined

    demo = (ROOT / "demo" / "index.html").read_text(encoding="utf-8")
    demo_statuses = {
        fragment.split('"', 1)[0]
        for fragment in demo.split('data-evidence-status="')[1:]
    }
    assert demo_statuses
    assert demo_statuses <= EXPECTED_STATUS_IDS
