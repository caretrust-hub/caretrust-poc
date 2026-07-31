from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_poc_evidence_manifest.py"

SPEC = importlib.util.spec_from_file_location("build_poc_evidence_manifest", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
manifest_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manifest_module)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _known_release() -> tuple[str, str]:
    """Return the newest reachable release without requiring HEAD to be tagged."""
    tag = _git(ROOT, "describe", "--tags", "--abbrev=0")
    return tag, _git(ROOT, "rev-list", "-n", "1", tag)


def _manifest() -> dict:
    release_tag, release_commit = _known_release()
    return manifest_module.build_manifest(
        root=ROOT,
        test_result_reference="artifacts/validation/release-readiness.json",
        public_repository_url="https://github.com/caretrust-hub/caretrust-poc",
        release_tag=release_tag,
        release_commit=release_commit,
    )


def test_manifest_is_deterministic_and_has_stable_artifact_hashes() -> None:
    first = _manifest()
    second = _manifest()
    assert first == second
    assert manifest_module.manifest_json(first) == manifest_module.manifest_json(second)
    assert "generated_at" not in first
    assert first["artifact_hash_algorithm"] == "sha256"
    assert re.fullmatch(r"[0-9a-f]{64}", first["artifact_set_sha256"])

    artifacts = first["artifacts"]
    assert [item["path"] for item in artifacts] == sorted(
        item["path"] for item in artifacts
    )
    assert len({item["path"] for item in artifacts}) == len(artifacts)
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in artifacts)
    assert all(item["bytes"] > 0 for item in artifacts)
    assert {
        "scripts/build_poc_evidence_manifest.py",
        "src/caretrust/federation.py",
        "src/caretrust/fhir_projection.py",
        "tests/test_federation.py",
        "tests/test_fhir_projection.py",
        "tests/test_oid4vc_artifacts.py",
    } <= {item["path"] for item in artifacts}


def test_manifest_separates_post_evaluation_evidence_from_frozen_run() -> None:
    manifest = _manifest()
    scope = manifest["evidence_scope"]
    assert scope["kind"] == "post_evaluation_repository_and_standards_evidence"
    assert scope["synthetic_only"] is True
    assert scope["frozen_model_evaluation_recomputed"] is False
    assert "does not rerun, replace, expand, or reinterpret" in scope["statement"]

    frozen = manifest["frozen_model_evaluation"]
    assert frozen["run_id"] == "20260730T085655.959974Z"
    assert frozen["case_count"] == 20
    assert frozen["state"] == "referenced_only_not_recomputed_or_replaced"
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in frozen["references"])
    assert {
        item["path"] for item in frozen["references"]
    } == set(manifest_module.FROZEN_EVALUATION_REFERENCES)


def test_status_matrix_uses_bounded_evidence_classes_and_non_claims() -> None:
    manifest = _manifest()
    statuses = {
        item["capability_id"]: item["status"]
        for item in manifest["implementation_status_matrix"]
    }
    assert statuses["aws-ocr-bedrock-intake"] == "retained_aws"
    assert statuses["caretrust-core-claim-and-policy-contract"] == "executed_local"
    assert statuses["fhir-r4-qualification-projection"] == "executed_local"
    assert statuses["oid4vci-and-oid4vp-exchange-artifacts"] == "contract_tested"
    assert statuses["openid-federation-trust-resolution"] == "local_simulation"
    assert statuses["caretrust-openapi-surface"] == "contract_tested"
    assert statuses["synthetic-clinical-data-holder-edge"] == "executed_local"

    non_claims = "\n".join(manifest["explicit_non_claims"]).lower()
    for boundary in (
        "cross-organization federation",
        "fhir conformance",
        "oid4vc deployment",
        "wallet",
        "live-registry",
        "ehr integration",
        "production",
    ):
        assert boundary in non_claims


def test_public_release_and_test_references_are_caller_supplied() -> None:
    manifest = _manifest()
    release_tag, release_commit = _known_release()
    assert manifest["publication"] == {
        "public_repository_url": "https://github.com/caretrust-hub/caretrust-poc",
        "release_tag": release_tag,
        "release_commit": release_commit,
        "identifiers_supplied_by_caller": True,
    }
    assert manifest["testing"] == {
        "result_reference": "artifacts/validation/release-readiness.json",
        "reference_supplied_by_caller": True,
        "tests_executed_by_manifest_generator": False,
    }


def test_repository_state_records_dirty_and_untracked_files(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Synthetic Test")
    _git(repository, "config", "user.email", "synthetic@example.invalid")
    tracked = repository / "tracked.txt"
    tracked.write_text("original\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "initial")

    tracked.write_text("changed\n", encoding="utf-8")
    (repository / "untracked.txt").write_text("synthetic\n", encoding="utf-8")
    state = manifest_module.repository_state(repository)
    assert state["is_dirty"] is True
    assert state["tracked_change_count"] == 1
    assert state["untracked_file_count"] == 1
    assert state["status_entries"] == [" M tracked.txt", "?? untracked.txt"]


def test_cli_writes_a_valid_manifest_and_excludes_its_output(
    tmp_path: Path,
) -> None:
    release_tag, release_commit = _known_release()
    output = tmp_path / "evidence-manifest.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--root",
        str(ROOT),
        "--output",
        str(output),
        "--test-result-reference",
        "artifacts/validation/release-readiness.json",
        "--public-repository-url",
        "https://github.com/caretrust-hub/caretrust-poc",
        "--release-tag",
        release_tag,
        "--release-commit",
        release_commit,
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(output.read_bytes())
    assert str(output) not in json.dumps(payload)
    assert payload["manifest_version"] == (
        "caretrust.post-evaluation-evidence.v0.2"
    )


def test_invalid_or_mismatched_release_identifiers_fail() -> None:
    release_tag, release_commit = _known_release()
    with pytest.raises(manifest_module.ManifestBuildError):
        manifest_module.build_manifest(
            root=ROOT,
            test_result_reference="synthetic-test-reference",
            public_repository_url="http://github.com/caretrust-hub/caretrust-poc",
            release_tag=release_tag,
            release_commit=release_commit,
        )
    with pytest.raises(manifest_module.ManifestBuildError):
        manifest_module.build_manifest(
            root=ROOT,
            test_result_reference="synthetic-test-reference",
            public_repository_url="https://github.com/caretrust-hub/caretrust-poc",
            release_tag=release_tag,
            release_commit="0" * 40,
        )


def test_standards_profiles_publish_exact_local_boundaries() -> None:
    profiles = {
        "fhir": (
            ROOT / "docs/standards/fhir-r4-projection-profile.md"
        ).read_text(encoding="utf-8"),
        "oid4vc": (
            ROOT / "docs/standards/oid4vc-exchange-profile.md"
        ).read_text(encoding="utf-8"),
        "federation": (
            ROOT / "docs/standards/openid-federation-trust-profile.md"
        ).read_text(encoding="utf-8"),
    }
    assert "executable local projection with deterministic local tests" in profiles["fhir"]
    assert "No EHR or FHIR server is contacted" in profiles["fhir"]
    assert "`contract_tested` — Contract tested" in profiles["oid4vc"]
    assert "No wallet is implemented or connected" in profiles["oid4vc"]
    federation = re.sub(r"\s+", " ", profiles["federation"])
    assert "`local_simulation` — Local simulation" in federation
    assert "local synthetic trust-resolution simulation only" in federation
    assert "does not demonstrate cross-organization federation" in federation
