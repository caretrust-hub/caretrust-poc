"""Build the static v0.3 browser data bundle from retained generated artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DELEGATION = ROOT / "docs" / "standards" / "examples" / "delegation"
UPLOADED = ROOT / "docs" / "standards" / "examples" / "uploaded-care"
OUTPUT = ROOT / "demo" / "network-data.js"
VALIDATION = ROOT / "artifacts" / "validation"
COMPILER = ROOT / "fixtures" / "compiler"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _provider_operations(case: dict[str, Any]) -> dict[str, Any]:
    """Derive provider-facing proof counts without inventing field outcomes."""

    decisions = case["decisions"]
    permits = [item for item in decisions if item["decision"] == "permit"]
    denials = [item for item in decisions if item["decision"] == "deny"]
    return {
        "schema_version": "caretrust.provider-operations-summary.v1",
        "case_id": case["case_id"],
        "synthetic": True,
        "evidence_status": "executed_local",
        "care_context_count": len(case["caregivers"]),
        "application_count": len(case["applications"]),
        "decision_count": len(decisions),
        "permit_count": len(permits),
        "deny_count": len(denials),
        "care_contexts": [item["role"] for item in case["caregivers"]],
        "application_ids": [
            item["application_id"] for item in case["applications"]
        ],
        "field_outcomes_measured": False,
        "field_outcome_label": "Not yet",
        "field_outcome_next_step": "Phase 2 measurement",
        "non_claims": [
            "Counts describe one synthetic local case, not provider deployment outcomes.",
            "No time saved, burden reduction, worker retention, or care-quality improvement has been measured.",
        ],
    }


def build_data() -> dict[str, Any]:
    """Return the exact retained objects used by the static message inspector."""

    case = _read(VALIDATION / "synthetic-multi-caregiver-case.json")
    return {
        "case_bundle": case,
        "provider_operations": _provider_operations(case),
        "dashboard_contract": _read(
            VALIDATION / "dashboard-contract.json"
        ),
        "auth_harness": _read(
            VALIDATION / "auth-harness-trace.json"
        ),
        "fhir_scheduling": _read(
            VALIDATION / "fhir-smart-scheduling-projection.json"
        ),
        "federation_lab": _read(
            VALIDATION / "federation-two-hub-lab.json"
        ),
        "judge_walkthrough": _read(
            VALIDATION / "judge-walkthrough-contract.json"
        ),
        "intent_compilation": _read(
            COMPILER / "intent-compilation.json"
        ),
        "application_compilation": _read(
            COMPILER / "application-compilation.json"
        ),
        "smart40_summary": _read(
            VALIDATION / "intent-compiler-bedrock-40" / "summary.json"
        ),
        "intent": _read(DELEGATION / "intent-statement.json"),
        "draft": _read(DELEGATION / "delegation-draft.json"),
        "clarification": {
            "request": _read(DELEGATION / "clarification-request.json"),
            "response": _read(DELEGATION / "clarification-response.json"),
        },
        "invite": _read(DELEGATION / "patient-invite.json"),
        "acceptance": _read(DELEGATION / "invite-acceptance.json"),
        "approval": _read(DELEGATION / "patient-approval-record.json"),
        "relationship": _read(DELEGATION / "care-relationship-claim.json"),
        "grant": _read(DELEGATION / "delegation-grant.json"),
        "schedule_decision": {
            "request": _read(
                DELEGATION / "delegation-authorization-request.json"
            ),
            "decision": _read(
                DELEGATION / "delegation-authorization-decision.json"
            ),
        },
        "navigator": _read(
            ROOT / "artifacts" / "validation" / "synthetic-patient-navigator.json"
        ),
        "care_document": _read(UPLOADED / "uploaded-care-document.json"),
        "document_extraction": _read(
            UPLOADED / "document-extraction-draft.json"
        ),
        "document_review": _read(
            UPLOADED / "document-review-correction-record.json"
        ),
        "approved_document_items": _read(
            UPLOADED / "approved-document-items.json"
        ),
        "document_share_grant": _read(
            UPLOADED / "document-share-grant.json"
        ),
        "document_share": {
            "request": _read(UPLOADED / "document-share-request.json"),
            "decision": _read(UPLOADED / "document-share-decision.json"),
        },
        "document_fhir_projection": _read(
            UPLOADED / "uploaded-document-fhir-projection.json"
        ),
        "document_revocation": _read(
            UPLOADED / "document-share-revocation-record.json"
        ),
        "document_post_revocation": {
            "request": _read(
                UPLOADED / "post-revocation-share-request.json"
            ),
            "decision": _read(
                UPLOADED / "post-revocation-share-decision.json"
            ),
        },
    }


def render(data: dict[str, Any] | None = None) -> str:
    payload = build_data() if data is None else data
    serialized = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    return (
        "/* Generated by scripts/build_network_demo_data.py; do not edit. */\n"
        f"window.CARETRUST_DEMO_DATA = {serialized};\n"
    )


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8", newline="\n")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
