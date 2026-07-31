"""Export inspectable Core 0.1 bridge contracts for the synthetic POC case.

The output is validation evidence for a local mapping bridge.  It is not a
claim that the legacy POC artifacts natively conform to the published Core
profiles or that any external endpoint exchanged these messages.
"""

from __future__ import annotations

import json
from datetime import timedelta
import os
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from caretrust.core_mappings import (
    delegation_decision_to_core,
    delegation_grant_to_core,
    delegation_request_to_core,
    delegation_revocation_to_status,
    document_share_decision_to_core,
    document_share_grant_to_core,
    document_share_request_to_core,
    document_share_revocation_to_status,
    target_artifact,
    target_decision,
    target_request,
    target_status,
)
from caretrust.core_protocol import (
    AUTHORIZATION_DECISION_SCHEMA_URI,
    AUTHORIZATION_REQUEST_SCHEMA_URI,
    STATUS_EVENT_SCHEMA_URI,
    TRUST_ARTIFACT_SCHEMA_URI,
    envelope_for_payload,
)
from caretrust.delegation import (
    DelegationAuthorizationDecision,
    DelegationAuthorizationRequest,
    DelegationGrant,
    DelegationRevocationRecord,
)
from scripts.build_uploaded_care_document_trace import build_models


EXAMPLES = ROOT / "docs" / "standards" / "examples" / "delegation"
OUTPUT = ROOT / "artifacts" / "validation" / "core-v0.1" / "core-runtime-bridge-validation.json"
SPEC_ROOT = Path(
    os.environ.get("CARETRUST_SPEC_ROOT", str(ROOT.parent / "caretrust-spec"))
).resolve()
CORE_SCHEMA_DIR = SPEC_ROOT / "schemas" / "core" / "v0.1"


def _load(model: object, filename: str) -> object:
    return model.model_validate(json.loads((EXAMPLES / filename).read_text(encoding="utf-8")))


def _published_schema_registry() -> tuple[dict[str, dict[str, object]], Registry]:
    if not CORE_SCHEMA_DIR.is_dir():
        raise RuntimeError(
            "published Core schemas not found; clone caretrust-hub/caretrust-spec "
            "next to this repository or set CARETRUST_SPEC_ROOT"
        )
    schemas: dict[str, dict[str, object]] = {}
    registry = Registry()
    for path in sorted(CORE_SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise RuntimeError(f"published schema has no $id: {path}")
        schemas[schema_id] = schema
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return schemas, registry


def _validate_published_instance(
    *,
    instance: dict[str, object],
    schema_uri: str,
    schemas: dict[str, dict[str, object]],
    registry: Registry,
) -> None:
    schema = schemas.get(schema_uri)
    if schema is None:
        raise RuntimeError(f"published schema is not registered: {schema_uri}")
    errors = sorted(
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(instance),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '$'}: {error.message}"
            for error in errors
        )
        raise RuntimeError(f"{schema_uri} validation failed: {detail}")


def _spec_commit() -> str:
    return subprocess.run(
        ["git", "-C", str(SPEC_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build_contracts() -> dict[str, object]:
    delegation_grant = _load(DelegationGrant, "delegation-grant.json")
    delegation_request = _load(DelegationAuthorizationRequest, "delegation-authorization-request.json")
    delegation_decision = _load(DelegationAuthorizationDecision, "delegation-authorization-decision.json")
    delegation_revocation = _load(DelegationRevocationRecord, "delegation-revocation-record.json")
    assert isinstance(delegation_grant, DelegationGrant)
    assert isinstance(delegation_request, DelegationAuthorizationRequest)
    assert isinstance(delegation_decision, DelegationAuthorizationDecision)
    assert isinstance(delegation_revocation, DelegationRevocationRecord)

    document_models = build_models()
    document_grant = document_models["document-share-grant"]
    document_request = document_models["document-share-request"]
    document_decision = document_models["document-share-decision"]
    document_revocation = document_models["document-share-revocation-record"]
    post_revocation_request = document_models["post-revocation-share-request"]
    post_revocation_decision = document_models["post-revocation-share-decision"]

    delegation_artifact_mapping = delegation_grant_to_core(delegation_grant)
    delegation_artifact = target_artifact(delegation_artifact_mapping)
    delegation_request_mapping = delegation_request_to_core(delegation_request, delegation_artifact)
    delegation_core_request = target_request(delegation_request_mapping)
    delegation_decision_mapping = delegation_decision_to_core(
        delegation_decision, delegation_core_request, delegation_artifact
    )
    delegation_status_mapping = delegation_revocation_to_status(delegation_revocation, delegation_artifact)

    document_artifact_mapping = document_share_grant_to_core(document_grant)
    document_artifact = target_artifact(document_artifact_mapping)
    document_request_mapping = document_share_request_to_core(document_request, document_artifact)
    document_core_request = target_request(document_request_mapping)
    document_decision_mapping = document_share_decision_to_core(
        document_decision, document_core_request, document_artifact
    )
    document_status_mapping = document_share_revocation_to_status(document_revocation, document_artifact)
    post_request_mapping = document_share_request_to_core(post_revocation_request, document_artifact)
    post_decision_mapping = document_share_decision_to_core(
        post_revocation_decision, target_request(post_request_mapping), document_artifact
    )

    mappings = {
        "delegation_grant_artifact": delegation_artifact_mapping,
        "delegation_authorization_request": delegation_request_mapping,
        "delegation_authorization_decision": delegation_decision_mapping,
        "delegation_revocation_status": delegation_status_mapping,
        "document_share_grant_artifact": document_artifact_mapping,
        "document_share_request": document_request_mapping,
        "document_share_decision": document_decision_mapping,
        "document_share_revocation_status": document_status_mapping,
        "document_share_post_revocation_request": post_request_mapping,
        "document_share_post_revocation_decision": post_decision_mapping,
    }
    schema_by_target = {
        "delegation_grant_artifact": TRUST_ARTIFACT_SCHEMA_URI,
        "delegation_authorization_request": AUTHORIZATION_REQUEST_SCHEMA_URI,
        "delegation_authorization_decision": AUTHORIZATION_DECISION_SCHEMA_URI,
        "delegation_revocation_status": STATUS_EVENT_SCHEMA_URI,
        "document_share_grant_artifact": TRUST_ARTIFACT_SCHEMA_URI,
        "document_share_request": AUTHORIZATION_REQUEST_SCHEMA_URI,
        "document_share_decision": AUTHORIZATION_DECISION_SCHEMA_URI,
        "document_share_revocation_status": STATUS_EVENT_SCHEMA_URI,
        "document_share_post_revocation_request": AUTHORIZATION_REQUEST_SCHEMA_URI,
        "document_share_post_revocation_decision": AUTHORIZATION_DECISION_SCHEMA_URI,
    }
    targets = {name: mapping.model_dump(mode="json") for name, mapping in mappings.items()}
    envelopes = {
        name: envelope_for_payload(
            message_id=f"urn:caretrust:message:core-bridge:{name}",
            message_type=f"urn:caretrust:message-type:{name.replace('_', '-')}",
            sender_ref="service:caretrust-core-bridge",
            receiver_ref="service:caretrust-core-validation",
            sent_at=(
                target_artifact(mapping).issued_at
                if mapping.metadata.target_schema_uri == TRUST_ARTIFACT_SCHEMA_URI
                else target_request(mapping).requested_at
                if mapping.metadata.target_schema_uri == AUTHORIZATION_REQUEST_SCHEMA_URI
                else target_decision(mapping).decided_at
                if mapping.metadata.target_schema_uri == AUTHORIZATION_DECISION_SCHEMA_URI
                else target_status(mapping).recorded_at
            ),
            trace_id="trace:synthetic-core-v0.1-bridge",
            correlation_id="case:synthetic-multi-caregiver",
            payload_schema_uri=schema_by_target[name],
            payload=mapping.target,
        ).model_dump(mode="json", exclude_none=True)
        for name, mapping in mappings.items()
    }
    schemas, registry = _published_schema_registry()
    for name, mapping in mappings.items():
        _validate_published_instance(
            instance=mapping.target,
            schema_uri=schema_by_target[name],
            schemas=schemas,
            registry=registry,
        )
    for envelope in envelopes.values():
        _validate_published_instance(
            instance=envelope,
            schema_uri="urn:caretrust:schema:core:message-envelope:0.1",
            schemas=schemas,
            registry=registry,
        )
    return {
        "artifact_type": "caretrust.core-runtime-bridge-validation.v1",
        "evidence_status": "executed_local",
        "synthetic_only": True,
        "network_calls": False,
        "native_core_profile_conformance_claimed": False,
        "published_schema_source": "https://github.com/caretrust-hub/caretrust-spec/tree/main/schemas/core/v0.1",
        "published_schema_commit": _spec_commit(),
        "mappings": targets,
        "message_envelopes": envelopes,
        "checks": {
            "delegation_permit_request_hash_valid": target_decision(delegation_decision_mapping).validates_request(delegation_core_request),
            "document_permit_request_hash_valid": target_decision(document_decision_mapping).validates_request(document_core_request),
            "document_post_revocation_is_deny": target_decision(post_decision_mapping).decision == "deny",
            "published_schema_validation": True,
            "revocations_are_status_events": (
                target_status(delegation_status_mapping).new_status == "revoked"
                and target_status(document_status_mapping).new_status == "revoked"
            ),
        },
        "claim_boundary": [
            "This is a deterministic local mapping and validation artifact, not a native Core profile conformance assertion.",
            "The bridge maps already-existing legacy grants and decisions; it does not create, approve, activate, authorize, or revoke authority.",
            "Document approved-item sets and raw-document flags remain in the experimental legacy request/receipt path and are listed as semantic loss in the Core mapping metadata.",
            "All data is synthetic; no external endpoint, patient identity system, or production record was used.",
        ],
    }


def write_output() -> Path:
    output = build_contracts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(write_output().relative_to(ROOT))
