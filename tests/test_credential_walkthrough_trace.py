from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from caretrust.models import AuthorizationDecision, DecisionValue
from caretrust.trace import EvidenceStatus, TraceBundle, canonical_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_credential_walkthrough_trace.py"
SPEC = importlib.util.spec_from_file_location("build_credential_walkthrough_trace", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _bundle() -> TraceBundle:
    return module.build_credential_walkthrough_trace()


def test_credential_trace_is_deterministic_and_referentially_intact() -> None:
    first = _bundle()
    second = _bundle()
    assert canonical_json(first) == canonical_json(second)
    assert first.trace_id == module.TRACE_ID
    assert len(first.events) == 13

    claim_ids = {
        event.linked_ids["claim_id"]
        for event in first.events
        if "claim_id" in event.linked_ids
    }
    assert claim_ids == {module.CLAIM_ID}
    event_ids = {event.event_id for event in first.events}
    assert len(event_ids) == len(first.events)


def test_two_apps_execute_distinct_real_requests_and_permits() -> None:
    bundle = _bundle()
    requests = [
        event.payload
        for event in bundle.events
        if event.message_type == "AuthorizationRequest"
    ]
    decisions = [
        AuthorizationDecision.model_validate(event.payload)
        for event in bundle.events
        if event.message_type == "AuthorizationDecision"
    ]
    assert requests[0]["audience"] == module.APP_A_AUDIENCE
    assert requests[0]["purpose"] == module.APP_A_PURPOSE
    assert requests[1]["audience"] == module.APP_B_AUDIENCE
    assert requests[1]["purpose"] == module.APP_B_PURPOSE
    assert requests[0]["claim_id"] == requests[1]["claim_id"] == module.CLAIM_ID
    assert decisions[0].decision is DecisionValue.PERMIT
    assert decisions[1].decision is DecisionValue.PERMIT
    assert decisions[0].policy_version != decisions[1].policy_version


def test_revocation_preserves_permits_and_fresh_request_denies() -> None:
    bundle = _bundle()
    decisions = [
        AuthorizationDecision.model_validate(event.payload)
        for event in bundle.events
        if event.message_type == "AuthorizationDecision"
    ]
    assert [decision.decision for decision in decisions] == [
        DecisionValue.PERMIT,
        DecisionValue.PERMIT,
        DecisionValue.DENY,
    ]
    assert decisions[-1].reason_codes == ("TOKEN_REVOKED",)
    assert decisions[-1].supporting_claim_ids == ()
    assert any(event.message_type == "RevocationRecord" for event in bundle.events)


def test_trace_labels_retained_and_executed_evidence_without_blending() -> None:
    bundle = _bundle()
    extraction = next(
        event for event in bundle.events if event.message_type == "ExtractionRecord"
    )
    evidence = next(
        event for event in bundle.events if event.message_type == "EvidenceArtifact"
    )
    assert extraction.evidence_status is EvidenceStatus.RETAINED_AWS
    assert evidence.evidence_status is EvidenceStatus.EXECUTED_LOCAL
    assert "not the retained Textract" in " ".join(bundle.limitations)


def test_cli_output_shape_matches_runtime_bundle(tmp_path: Path) -> None:
    output = tmp_path / "trace.json"
    bundle = _bundle()
    output.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert TraceBundle.model_validate_json(output.read_text(encoding="utf-8")) == bundle
    token_receipt = next(
        event.payload
        for event in bundle.events
        if event.message_type == "CareTrustJwtVerificationReceipt"
    )
    assert token_receipt["private_key_material_retained"] is False
    assert token_receipt["raw_token_retained_in_artifact"] is False
    assert "raw_token" not in token_receipt
