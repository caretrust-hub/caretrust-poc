from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from caretrust.models import DraftCredentialClaim

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "cna" / "smoke"


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_schema(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_schema(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_schema(child)


def test_all_frozen_expected_drafts_validate() -> None:
    fixture_paths = sorted(
        path for path in FIXTURE_ROOT.glob("*.json") if path.name != "manifest.json"
    )
    assert len(fixture_paths) == 5
    for path in fixture_paths:
        fixture = load_fixture(path)
        validated = DraftCredentialClaim.model_validate(fixture["expected"]["draft"])
        assert validated.status == "draft"


@pytest.mark.parametrize("forbidden_key", ["verified", "active", "authorized"])
def test_draft_rejects_forbidden_state(forbidden_key: str) -> None:
    fixture = load_fixture(FIXTURE_ROOT / "clean.json")
    candidate = copy.deepcopy(fixture["expected"]["draft"])
    candidate[forbidden_key] = True
    with pytest.raises(ValidationError):
        DraftCredentialClaim.model_validate(candidate)


def test_draft_rejects_active_status() -> None:
    fixture = load_fixture(FIXTURE_ROOT / "clean.json")
    candidate = copy.deepcopy(fixture["expected"]["draft"])
    candidate["status"] = "active"
    with pytest.raises(ValidationError):
        DraftCredentialClaim.model_validate(candidate)


def test_populated_field_requires_evidence_reference() -> None:
    fixture = load_fixture(FIXTURE_ROOT / "clean.json")
    candidate = copy.deepcopy(fixture["expected"]["draft"])
    candidate["fields"]["holder_name"]["evidence_refs"] = []
    with pytest.raises(ValidationError):
        DraftCredentialClaim.model_validate(candidate)


def test_draft_schema_uses_closed_objects_and_avoids_bedrock_constraints() -> None:
    schema = DraftCredentialClaim.model_json_schema(mode="validation")
    forbidden_keywords = {"minimum", "maximum", "minLength", "maxLength"}
    object_nodes = [
        node for node in walk_schema(schema) if node.get("type") == "object"
    ]
    assert object_nodes
    assert all(node.get("additionalProperties") is False for node in object_nodes)
    assert not any(forbidden_keywords.intersection(node) for node in walk_schema(schema))


def test_fixture_manifest_hashes_match_bytes() -> None:
    manifest = load_fixture(FIXTURE_ROOT / "manifest.json")
    assert manifest["synthetic"] is True
    assert len(manifest["fixtures"]) == 5
    for item in manifest["fixtures"]:
        fixture_bytes = (FIXTURE_ROOT / item["file"]).read_bytes()
        assert hashlib.sha256(fixture_bytes).hexdigest() == item["sha256"]
