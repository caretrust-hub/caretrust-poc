from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from caretrust.models import (
    ActiveCredentialClaim,
    AuthorizationDecision,
    AuthorizationRequest,
)
from caretrust.security import TokenErrorCode

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
STANDARDS = ROOT / "docs" / "standards"
EXAMPLES = STANDARDS / "examples"

EXPORTS = {
    "active-credential-claim.schema.json": ActiveCredentialClaim,
    "authorization-request.schema.json": AuthorizationRequest,
    "authorization-decision.schema.json": AuthorizationDecision,
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
        "active-credential-claim.json": ActiveCredentialClaim,
        "authorization-request.json": AuthorizationRequest,
        "authorization-request-deny.json": AuthorizationRequest,
        "authorization-decision-permit.json": AuthorizationDecision,
        "authorization-decision-deny.json": AuthorizationDecision,
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
        "Implemented and tested",
        "Mapped only — not implemented",
        "Planned / not implemented",
        "Out of scope / not implemented",
    ):
        assert label in status
    for boundary in (
        "no FHIR resource",
        "no VC document",
        "no entity statements",
        "no driver-license",
        "no screen scraping",
    ):
        assert boundary in status


def test_public_artifacts_contain_no_obvious_secrets_or_real_phi() -> None:
    checked = [
        *STANDARDS.rglob("*.md"),
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
