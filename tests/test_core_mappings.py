from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from caretrust.core_mappings import (
    delegation_grant_to_core,
    delegation_request_to_core,
    document_share_request_to_core,
    target_artifact,
    target_decision,
    target_request,
    target_status,
)
from caretrust.delegation import DelegationGrant
from scripts.build_uploaded_care_document_trace import build_models
from scripts.export_core_case_contracts import (
    OUTPUT,
    SPEC_ROOT,
    build_contracts,
    write_output,
)


ROOT = Path(__file__).resolve().parents[1]
DELEGATION_EXAMPLES = ROOT / "docs" / "standards" / "examples" / "delegation"


def delegation_grant() -> DelegationGrant:
    return DelegationGrant.model_validate(
        json.loads((DELEGATION_EXAMPLES / "delegation-grant.json").read_text(encoding="utf-8"))
    )


def test_delegation_mapping_preserves_existing_authority_only() -> None:
    grant = delegation_grant()
    artifact_mapping = delegation_grant_to_core(grant)
    artifact = target_artifact(artifact_mapping)
    assert artifact.profile_uri == "urn:caretrust:profile:experimental:legacy-delegation-grant:0.1"
    assert artifact.status == "active"
    assert artifact.payload["legacy_contract"]["grant_id"] == grant.grant_id
    assert artifact_mapping.metadata.conformance == "mapped_only"

    request_payload = json.loads(
        (DELEGATION_EXAMPLES / "delegation-authorization-request.json").read_text(encoding="utf-8")
    )
    from caretrust.delegation import DelegationAuthorizationRequest

    request = DelegationAuthorizationRequest.model_validate(request_payload)
    mapped_request = target_request(delegation_request_to_core(request, artifact))
    assert mapped_request.requester_ref == request.delegate_ref
    assert mapped_request.subject_ref == request.patient_ref
    assert mapped_request.referenced_artifact_refs == (artifact.reference(),)

    mismatched = request.model_copy(update={"grant_id": "grant:other"})
    with pytest.raises(ValueError, match="supplied grant artifact"):
        delegation_request_to_core(mismatched, artifact)


def test_document_mapping_exposes_loss_and_never_replays_revoked_permit() -> None:
    contracts = build_contracts()
    mappings = contracts["mappings"]
    document_request = mappings["document_share_request"]
    document_decision = mappings["document_share_decision"]
    post_revocation = mappings["document_share_post_revocation_decision"]
    revoked_status = mappings["document_share_revocation_status"]

    assert document_request["metadata"]["semantic_loss"]
    assert "resource-set URI" in document_request["metadata"]["semantic_loss"][0]
    assert document_decision["target"]["decision"] == "permit"
    assert post_revocation["target"]["decision"] == "deny"
    assert revoked_status["target"]["new_status"] == "revoked"
    assert contracts["checks"]["document_post_revocation_is_deny"] is True
    assert contracts["checks"]["document_permit_request_hash_valid"] is True


def test_exported_validation_artifact_contains_all_core_contract_families() -> None:
    path = write_output()
    assert path == OUTPUT
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert artifact["evidence_status"] == "executed_local"
    assert artifact["native_core_profile_conformance_claimed"] is False
    assert artifact["checks"] == {
        "delegation_permit_request_hash_valid": True,
        "document_permit_request_hash_valid": True,
        "document_post_revocation_is_deny": True,
        "published_schema_validation": True,
        "revocations_are_status_events": True,
    }
    expected_spec_commit = subprocess.run(
        ["git", "-C", str(SPEC_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert artifact["published_schema_commit"] == expected_spec_commit
    envelope_schemas = {value["payload_schema_uri"] for value in artifact["message_envelopes"].values()}
    assert envelope_schemas == {
        "urn:caretrust:schema:core:trust-artifact:0.1",
        "urn:caretrust:schema:core:authorization-request:0.1",
        "urn:caretrust:schema:core:authorization-decision:0.1",
        "urn:caretrust:schema:core:status-event:0.1",
    }
    assert all(value["payload_hash"]["canonicalization"] == "urn:ietf:rfc:8785" for value in artifact["message_envelopes"].values())
