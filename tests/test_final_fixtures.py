from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from caretrust.models import DraftCredentialClaim

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "cna" / "final"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
EXPECTED_DISTRIBUTION = {
    "clean": 10,
    "evidence_quality": 4,
    "source_or_status": 4,
    "security": 2,
}
FORBIDDEN_DRAFT_KEYS = {
    "active",
    "activated",
    "activation_allowed",
    "authorized",
    "registry_matched",
    "verified",
}
MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "Ä", "Ê", "\ufffd")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_paths() -> list[Path]:
    return sorted(path for path in FIXTURE_ROOT.glob("*.json") if path != MANIFEST_PATH)


def all_keys(value: object):
    if isinstance(value, dict):
        yield from value
        for child in value.values():
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


def test_exactly_twenty_predeclared_synthetic_cases() -> None:
    paths = fixture_paths()
    assert len(paths) == 20
    fixtures = [load(path) for path in paths]
    assert all(fixture["fixture_version"] == "1.0" for fixture in fixtures)
    assert all(fixture["synthetic"] is True for fixture in fixtures)
    assert all("not a real credential" in fixture["purpose"].lower() for fixture in fixtures)
    assert all(
        fixture["input"]["ocr_text"].startswith(
            "SYNTHETIC TEST RECORD — NOT A REAL CREDENTIAL"
        )
        for fixture in fixtures
    )


def test_case_ids_artifacts_subjects_and_registry_ids_are_synthetic_and_unique() -> None:
    fixtures = [load(path) for path in fixture_paths()]
    case_ids = [fixture["case_id"] for fixture in fixtures]
    artifact_ids = [fixture["input"]["artifact_id"] for fixture in fixtures]
    subject_refs = [
        fixture["fixed_output_identifiers"]["subject_ref"] for fixture in fixtures
    ]

    assert len(case_ids) == len(set(case_ids))
    assert len(artifact_ids) == len(set(artifact_ids))
    assert len(subject_refs) == len(set(subject_refs))
    assert all(case_id.startswith("final-") for case_id in case_ids)
    assert all(artifact_id.startswith("artifact:final-") for artifact_id in artifact_ids)
    assert all(subject.startswith("person:synthetic-") for subject in subject_refs)

    for fixture in fixtures:
        registry_id = fixture["expected"]["draft"]["fields"]["registry_id"]["value"]
        assert registry_id is None or registry_id.startswith("SYN-")
        raw = json.dumps(fixture, ensure_ascii=False)
        assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", raw)
        assert not re.search(r"\b\d{9}\b", raw)
        assert "@hawaii.gov" not in raw.lower()


def test_distribution_meets_the_frozen_matrix() -> None:
    distribution = Counter(
        load(path)["evaluation_category"] for path in fixture_paths()
    )
    assert distribution == EXPECTED_DISTRIBUTION

    manifest = load(MANIFEST_PATH)
    assert manifest["distribution"] == EXPECTED_DISTRIBUTION
    assert manifest["fixture_count"] == 20


def test_all_gold_drafts_strictly_validate_and_remain_draft_only() -> None:
    for path in fixture_paths():
        fixture = load(path)
        draft_data = fixture["expected"]["draft"]
        draft = DraftCredentialClaim.model_validate(draft_data)

        assert draft.status == "draft"
        assert not FORBIDDEN_DRAFT_KEYS.intersection(all_keys(draft_data))
        assert fixture["fixed_output_identifiers"] == {
            "draft_id": draft.draft_id,
            "evidence_id": draft.evidence_id,
            "subject_ref": draft.subject_ref,
        }
        assert draft.evidence_id == fixture["input"]["artifact_id"]


def test_every_gold_evidence_reference_resolves_to_supplied_source_text() -> None:
    for path in fixture_paths():
        fixture = load(path)
        ocr_text = fixture["input"]["ocr_text"]
        spans = fixture["input"]["source_spans"]
        span_ids = [span["span_id"] for span in spans]

        assert len(span_ids) == len(set(span_ids))
        assert all(span["quote"] in ocr_text for span in spans)

        known_refs = set(span_ids)
        draft = fixture["expected"]["draft"]
        for field in draft["fields"].values():
            assert set(field["evidence_refs"]).issubset(known_refs)
            if field["value"] is not None:
                assert field["evidence_refs"]
        for uncertainty in draft["uncertainties"]:
            assert uncertainty["evidence_refs"]
            assert set(uncertainty["evidence_refs"]).issubset(known_refs)


def test_gold_workflow_and_authorization_expectations_are_complete_and_coherent() -> None:
    permit_count = 0
    for path in fixture_paths():
        fixture = load(path)
        expected = fixture["expected"]
        workflow = fixture["workflow_inputs"]
        draft = expected["draft"]
        auth_input = workflow["authorization_request"]
        auth_expected = expected["authorization_expectation"]

        assert expected["review_route"] in {"approve", "review_required"}
        assert expected["registry_result"] in {
            "match",
            "mismatch",
            "not_found",
            "unavailable",
        }
        assert isinstance(expected["activation_allowed_after_review_and_match"], bool)
        assert auth_expected["decision"] in {"permit", "deny"}
        assert auth_expected["reason_codes"]
        assert workflow["policy_evaluation_date"] == "2026-07-29"
        assert workflow["human_review_decision"] in {"approved", "deferred"}
        assert workflow["registry_simulator_result"] in {
            "match",
            "mismatch",
            "not_found",
            "unavailable",
        }
        assert auth_input == {
            "audience": "org:synthetic-care-provider",
            "purpose": "credentialing",
            "token_valid": True,
            "revoked": False,
        }
        assert not {
            "decision",
            "expected_decision",
            "activation_allowed_after_review_and_match",
        }.intersection(workflow)

        status_active = (
            draft["fields"]["credential_status"]["normalized_value"] == "active"
        )
        expiration = draft["fields"]["expiration_date"]["normalized_value"]
        unexpired = expiration is not None and date.fromisoformat(expiration) >= date(
            2026, 7, 29
        )
        derived_activation = (
            workflow["human_review_decision"] == "approved"
            and workflow["registry_simulator_result"] == "match"
            and status_active
            and unexpired
            and not draft["blocking_issues"]
        )
        assert (
            expected["activation_allowed_after_review_and_match"]
            is derived_activation
        )
        assert (auth_expected["decision"] == "permit") is derived_activation
        permit_count += auth_expected["decision"] == "permit"

    assert permit_count == 10


def test_security_cases_are_inert_untrusted_text_and_default_deny() -> None:
    fixtures = [
        load(path)
        for path in fixture_paths()
        if load(path)["evaluation_category"] == "security"
    ]
    assert len(fixtures) == 2
    for fixture in fixtures:
        draft = fixture["expected"]["draft"]
        assert "UNTRUSTED DOCUMENT TEXT:" in fixture["input"]["ocr_text"]
        assert draft["status"] == "draft"
        assert draft["blocking_issues"] == ["PROMPT_INJECTION_ATTEMPT"]
        assert fixture["expected"]["review_route"] == "review_required"
        assert fixture["expected"]["activation_allowed_after_review_and_match"] is False
        assert fixture["expected"]["authorization_expectation"]["decision"] == "deny"
        assert not FORBIDDEN_DRAFT_KEYS.intersection(all_keys(draft))


def test_manifest_hashes_exact_final_fixture_bytes() -> None:
    manifest = load(MANIFEST_PATH)
    assert manifest["synthetic"] is True
    assert manifest["hash_algorithm"] == "sha256"
    assert manifest["fixture_count"] == 20

    listed_files = [item["file"] for item in manifest["fixtures"]]
    assert listed_files == [path.name for path in fixture_paths()]
    assert len(listed_files) == len(set(listed_files))
    for item in manifest["fixtures"]:
        fixture_bytes = (FIXTURE_ROOT / item["file"]).read_bytes()
        assert hashlib.sha256(fixture_bytes).hexdigest() == item["sha256"]


def test_fixture_bytes_are_clean_utf8_without_mojibake() -> None:
    for path in [*fixture_paths(), MANIFEST_PATH]:
        raw_bytes = path.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf")
        text = raw_bytes.decode("utf-8", errors="strict")
        assert not any(marker in text for marker in MOJIBAKE_MARKERS)
