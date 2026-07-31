from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from caretrust.clinical_edge import (
    ClinicalDataAuthorizationDecision,
    ClinicalDataAuthorizationRequest,
    ClinicalDataExchangeRecord,
    PatientMatchResult,
)
from caretrust.delegation import (
    CareRelationshipClaim,
    ClarificationRequest,
    ClarificationResponse,
    DelegationAuthorizationDecision,
    DelegationAuthorizationRequest,
    DelegationDraft,
    DelegationGrant,
    DelegationRevocationRecord,
    IntentStatement,
    InviteAcceptance,
    PatientApprovalRecord,
    PatientInvite,
)
from caretrust.models import (
    ActiveCredentialClaim,
    AuditEvent,
    AuthorizationDecision,
    AuthorizationRequest,
    DraftCredentialClaim,
    EvidenceArtifact,
    ExtractionRecord,
    RegistryResult,
    ReviewRecord,
    RevocationRecord,
)
from caretrust.navigator import PatientNavigatorProjection
from caretrust.security import TokenErrorCode
from caretrust.trace import TraceBundle, TraceEnvelope

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
STANDARDS = ROOT / "docs" / "standards"
EXAMPLES = STANDARDS / "examples"
OPENAPI = STANDARDS / "caretrust-openapi-3.1.json"
HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)

EXPORTS = {
    "evidence-artifact.schema.json": EvidenceArtifact,
    "draft-credential-claim.schema.json": DraftCredentialClaim,
    "extraction-record.schema.json": ExtractionRecord,
    "review-record.schema.json": ReviewRecord,
    "registry-result.schema.json": RegistryResult,
    "active-credential-claim.schema.json": ActiveCredentialClaim,
    "authorization-request.schema.json": AuthorizationRequest,
    "authorization-decision.schema.json": AuthorizationDecision,
    "revocation-record.schema.json": RevocationRecord,
    "audit-event.schema.json": AuditEvent,
    "trace-envelope.schema.json": TraceEnvelope,
    "trace-bundle.schema.json": TraceBundle,
    "intent-statement.schema.json": IntentStatement,
    "delegation-draft.schema.json": DelegationDraft,
    "clarification-request.schema.json": ClarificationRequest,
    "clarification-response.schema.json": ClarificationResponse,
    "patient-invite.schema.json": PatientInvite,
    "invite-acceptance.schema.json": InviteAcceptance,
    "patient-approval-record.schema.json": PatientApprovalRecord,
    "care-relationship-claim.schema.json": CareRelationshipClaim,
    "delegation-grant.schema.json": DelegationGrant,
    "delegation-authorization-request.schema.json": DelegationAuthorizationRequest,
    "delegation-authorization-decision.schema.json": DelegationAuthorizationDecision,
    "delegation-revocation-record.schema.json": DelegationRevocationRecord,
    "clinical-data-authorization-request.schema.json": (
        ClinicalDataAuthorizationRequest
    ),
    "patient-match-result.schema.json": PatientMatchResult,
    "clinical-data-authorization-decision.schema.json": (
        ClinicalDataAuthorizationDecision
    ),
    "clinical-data-exchange-record.schema.json": ClinicalDataExchangeRecord,
    "patient-navigator-projection.schema.json": PatientNavigatorProjection,
}


def _runtime_schema(model: type) -> dict:
    return model.model_json_schema(
        mode="validation",
        ref_template="#/$defs/{model}",
    )


def test_schema_exports_equal_runtime_contracts() -> None:
    for filename, model in EXPORTS.items():
        exported = json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))
        assert exported == _runtime_schema(model)


def test_synthetic_examples_validate() -> None:
    examples = {
        "evidence-artifact.json": EvidenceArtifact,
        "extraction-record.json": ExtractionRecord,
        "review-record.json": ReviewRecord,
        "registry-result.json": RegistryResult,
        "active-credential-claim.json": ActiveCredentialClaim,
        "authorization-request.json": AuthorizationRequest,
        "authorization-request-deny.json": AuthorizationRequest,
        "authorization-decision-permit.json": AuthorizationDecision,
        "authorization-decision-deny.json": AuthorizationDecision,
        "revocation-record.json": RevocationRecord,
        "audit-event.json": AuditEvent,
        "delegation/intent-statement.json": IntentStatement,
        "delegation/delegation-draft.json": DelegationDraft,
        "delegation/clarification-request.json": ClarificationRequest,
        "delegation/clarification-response.json": ClarificationResponse,
        "delegation/patient-invite.json": PatientInvite,
        "delegation/invite-acceptance.json": InviteAcceptance,
        "delegation/patient-approval-record.json": PatientApprovalRecord,
        "delegation/care-relationship-claim.json": CareRelationshipClaim,
        "delegation/delegation-grant.json": DelegationGrant,
        "delegation/delegation-authorization-request.json": DelegationAuthorizationRequest,
        "delegation/delegation-authorization-decision.json": DelegationAuthorizationDecision,
        "delegation/delegation-revocation-record.json": DelegationRevocationRecord,
    }
    for filename, model in examples.items():
        payload = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
        assert "synthetic" in json.dumps(payload).lower()
        model.model_validate(payload)

    permit = AuthorizationDecision.model_validate_json(
        (EXAMPLES / "authorization-decision-permit.json").read_text()
    )
    deny = AuthorizationDecision.model_validate_json(
        (EXAMPLES / "authorization-decision-deny.json").read_text()
    )
    assert permit.decision.value == "permit"
    assert permit.supporting_claim_ids
    assert deny.decision.value == "deny"
    assert not deny.supporting_claim_ids
    deny_request = AuthorizationRequest.model_validate_json(
        (EXAMPLES / "authorization-request-deny.json").read_text()
    )
    assert deny.request_id == deny_request.request_id


def _resolve_json_pointer(document: object, fragment: str) -> object:
    assert fragment == "" or fragment.startswith("/")
    current = document
    for raw_part in fragment.removeprefix("/").split("/") if fragment else ():
        part = raw_part.replace("~1", "/").replace("~0", "~")
        assert isinstance(current, dict)
        assert part in current
        current = current[part]
    return current


def _assert_local_refs_resolve(
    node: object,
    *,
    source_path: Path,
    source_document: object,
    visited: set[tuple[Path, str]],
) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            assert "://" not in ref, f"remote $ref is outside the bounded contract: {ref}"
            path_part, separator, fragment = ref.partition("#")
            target_path = (
                source_path
                if not path_part
                else (source_path.parent / path_part).resolve()
            )
            assert target_path.is_relative_to(ROOT)
            assert target_path.is_file(), f"unresolved $ref document: {ref}"
            target_document = (
                source_document
                if target_path == source_path
                else json.loads(target_path.read_text(encoding="utf-8"))
            )
            target = _resolve_json_pointer(
                target_document,
                fragment if separator else "",
            )
            ref_key = (target_path, fragment)
            if ref_key not in visited:
                visited.add(ref_key)
                _assert_local_refs_resolve(
                    target,
                    source_path=target_path,
                    source_document=target_document,
                    visited=visited,
                )
        for value in node.values():
            _assert_local_refs_resolve(
                value,
                source_path=source_path,
                source_document=source_document,
                visited=visited,
            )
    elif isinstance(node, list):
        for value in node:
            _assert_local_refs_resolve(
                value,
                source_path=source_path,
                source_document=source_document,
                visited=visited,
            )


def test_openapi_contract_is_valid_json_31_with_resolvable_local_refs() -> None:
    contract = json.loads(OPENAPI.read_text(encoding="utf-8"))
    assert contract["openapi"] == "3.1.0"
    assert (
        contract["jsonSchemaDialect"]
        == "https://json-schema.org/draft/2020-12/schema"
    )
    _assert_local_refs_resolve(
        contract,
        source_path=OPENAPI.resolve(),
        source_document=contract,
        visited=set(),
    )


def test_openapi_operation_ids_are_unique_and_surface_is_bounded() -> None:
    contract = json.loads(OPENAPI.read_text(encoding="utf-8"))
    operations = [
        operation
        for path_item in contract["paths"].values()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    ]
    operation_ids = [operation["operationId"] for operation in operations]
    assert len(operation_ids) == len(set(operation_ids))
    assert all(
        operation["x-caretrust-runtime-status"]
        == "contract-only-planned-phase-2"
        for operation in operations
    )
    assert {
        "/evidence",
        "/drafts/{draft_id}/reviews",
        "/drafts/{draft_id}/registry-checks",
        "/drafts/{draft_id}/activations",
        "/claims/{claim_id}",
        "/claims/{claim_id}/revocations",
        "/authorization-decisions",
        "/evaluation/extractions/{extraction_id}",
        "/evaluation/audit-events/{event_id}",
    } <= set(contract["paths"])

    status = contract["x-caretrust-implementation-status"]
    assert status == {
        "phase1_transport": "not-deployed",
        "phase2_surface": "contract-only",
        "production_ready": False,
        "synthetic_only": True,
    }
    assert "No HTTP server is deployed in Phase 1" in contract["info"]["description"]
    assert "servers" not in contract


def test_openapi_publishes_stable_reason_and_status_vocabularies() -> None:
    contract = json.loads(OPENAPI.read_text(encoding="utf-8"))
    schemas = contract["components"]["schemas"]
    assert schemas["LifecycleStatus"]["enum"] == [
        "draft",
        "active",
        "revoked",
        "expired",
    ]
    assert schemas["ReviewStatus"]["enum"] == [
        "approved",
        "corrected",
        "rejected",
        "deferred",
    ]
    assert schemas["RegistryStatus"]["enum"] == [
        "match",
        "mismatch",
        "not_found",
        "unavailable",
    ]
    assert schemas["AuthorizationDecisionStatus"]["enum"] == ["permit", "deny"]

    published_codes = set(schemas["ReasonCode"]["enum"])
    implemented_codes = (
        _uppercase_literals(ROOT / "src/caretrust/workflow.py", "decide_activation")
        | _uppercase_literals(ROOT / "src/caretrust/authorization.py", "decide")
        | _simulator_reason_literals()
        | {code.value for code in TokenErrorCode}
    )
    assert implemented_codes <= published_codes


def _uppercase_literals(path: Path, function_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    assert len(functions) == 1
    return {
        node.value
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.fullmatch(r"[A-Z][A-Z0-9_]+", node.value)
        and node.value != "HI"
    }


def _simulator_reason_literals() -> set[str]:
    tree = ast.parse((ROOT / "src/caretrust/workflow.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SyntheticRegistrySimulator":
            return {
                child.value
                for child in ast.walk(node)
                if isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and child.value.startswith("SYNTHETIC_REGISTRY_")
            }
    raise AssertionError("SyntheticRegistrySimulator not found")


def test_reason_catalog_contains_every_implemented_code() -> None:
    catalog = (STANDARDS / "lifecycle-and-reason-codes.md").read_text(
        encoding="utf-8"
    )
    implemented = (
        _uppercase_literals(ROOT / "src/caretrust/workflow.py", "decide_activation")
        | _uppercase_literals(ROOT / "src/caretrust/authorization.py", "decide")
        | _simulator_reason_literals()
        | {code.value for code in TokenErrorCode}
    )
    missing = sorted(code for code in implemented if f"`{code}`" not in catalog)
    assert missing == []


def test_status_labels_and_nonconformance_boundary_are_explicit() -> None:
    status = (STANDARDS / "standards-status.md").read_text(encoding="utf-8")
    for label in (
        "`retained_aws` — Retained AWS trace",
        "`executed_local` — Executed local",
        "`contract_tested` — Contract tested",
        "`local_simulation` — Local simulation",
        "`mapped_only` — Mapped only",
        "`planned` — Planned",
    ):
        assert label in status
    for boundary in (
        "No official HL7 validator",
        "no VC document",
        "There is no discovery",
        "no driver-license",
        "no screen scraping",
    ):
        assert boundary in status


def test_public_artifacts_contain_no_obvious_secrets_or_real_phi() -> None:
    checked = [
        *STANDARDS.rglob("*.md"),
        OPENAPI,
        *EXAMPLES.glob("*.json"),
        *(SCHEMAS / filename for filename in EXPORTS),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
    forbidden = (
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, text) is None
