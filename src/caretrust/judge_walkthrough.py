"""Deterministic, evidence-bound six-minute CareTrust judge walkthrough."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "artifacts" / "validation"
SCHEMA_VERSION = "caretrust.judge-walkthrough-contract.v1"
FEDERATION_ARTIFACT = VALIDATION / "federation-two-hub-lab.json"
FEDERATION_FIXTURE = ROOT / "fixtures" / "federation" / "two-hub-lab.json"
FEDERATION_PROFILE = "caretrust.synthetic-two-hub-federation-lab.v1"
EVIDENCE_STATUSES = frozenset({"executed_local", "contract_tested", "mapped_only", "planned", "retained_aws", "local_simulation"})


class JudgeWalkthroughError(ValueError):
    """Raised if a walkthrough step cannot resolve its retained source evidence."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _source(relative: str, payload: Mapping[str, Any], ids: list[str]) -> dict[str, object]:
    return {"artifact": relative, "artifact_sha256": _hash(payload), "canonical_ids": ids}


def _decision(case: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
    result = next((row for row in case["decisions"] if row["request_id"] == request_id), None)
    if result is None:
        raise JudgeWalkthroughError(f"missing canonical decision for {request_id}")
    return result


def _candidate_lineage(compilation: Mapping[str, Any], candidate_name: str) -> list[dict[str, object]]:
    candidate = compilation.get("model_candidate") or {}
    draft = compilation["draft"]
    values = candidate.get(candidate_name)
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    return [
        {
            "bounded_value": item["value"],
            "exact_quote": item["citation"]["quote"],
            "citation_id": item["citation"].get("span_id") or item["citation"].get("citation_id"),
            "draft_id": draft["draft_id"],
        }
        for item in values
    ]


def build_judge_walkthrough_contract() -> dict[str, object]:
    """Build the eight-step walkthrough from retained canonical artifacts only."""

    case = _load("artifacts/validation/synthetic-multi-caregiver-case.json")
    intent_input = _load("fixtures/compiler/intent-input.json")
    intent = _load("fixtures/compiler/intent-compilation.json")
    app_input = _load("fixtures/compiler/application-input.json")
    app = _load("fixtures/compiler/application-compilation.json")
    auth = _load("artifacts/validation/auth-harness-trace.json")
    fhir = _load("artifacts/validation/fhir-smart-scheduling-projection.json")
    mcp = _load("artifacts/validation/mcp-adapter-contract.json")
    core = _load("artifacts/validation/core-v0.1/core-runtime-bridge-validation.json")
    family_permit = _decision(case, "request:case:family-permit-001")
    family_revoked = _decision(case, "request:case:family-revoked-001")
    family = case["caregivers"][0]
    cna = case["caregivers"][1]
    respite = case["caregivers"][2]
    intent_actions = _candidate_lineage(intent, "actions")
    app_capability = _candidate_lineage(app, "capability")
    app_data = _candidate_lineage(app, "data_fields")

    steps: list[dict[str, object]] = [
        {
            "step_id": "01-case-context", "suggested_elapsed_seconds": 35,
            "title": "One synthetic patient, three different caregiver contexts",
            "evidence_status": "executed_local",
            "source_refs": [_source("artifacts/validation/synthetic-multi-caregiver-case.json", case, [case["case_id"], case["patient"]["patient_ref"], *[row["caregiver_ref"] for row in case["caregivers"]]])],
            "facts": {"patient_ref": case["patient"]["patient_ref"], "caregivers": [family, cna, respite], "policy_id": case["policy"]["policy_id"]},
            "standards_messages": ["CareTrust synthetic case bundle v1", "Core decisions are independently source-bound."],
            "non_claims": ["Care-team display is not authority; all inputs are synthetic."],
        },
        {
            "step_id": "02-ai-intent", "suggested_elapsed_seconds": 45,
            "title": "AI intent candidate is exact-evidence cited and remains a draft",
            "evidence_status": intent["evidence_status"],
            "source_refs": [
                _source("fixtures/compiler/intent-input.json", intent_input, [intent_input["intent_id"]]),
                _source("fixtures/compiler/intent-compilation.json", intent, [intent["draft"]["draft_id"], intent["run"]["run_id"]]),
            ],
            "facts": {"candidate_actions": intent_actions, "draft_status": intent["draft"]["status"], "draft_sha256": _hash(intent["draft"]), "compilation_mode": intent["compilation_mode"], "human_approval_boundary": {"required": True, "recorded_for_this_draft": False, "authority_effect": "none"}},
            "standards_messages": ["CareTrust delegation draft v1", "Exact retained source-span citation"],
            "non_claims": ["Candidate output is not approval, activation, or authorization.", "No live Bedrock call is claimed by retained compiler fixtures."],
        },
        {
            "step_id": "03-ai-app-onboarding", "suggested_elapsed_seconds": 45,
            "title": "AI application candidate proposes a bounded RAR/profile/minimum-data plan",
            "evidence_status": app["evidence_status"],
            "source_refs": [
                _source("fixtures/compiler/application-input.json", app_input, [app_input["application_id"], app_input["source_id"]]),
                _source("fixtures/compiler/application-compilation.json", app, [app["draft"]["draft_id"], app["run"]["run_id"]]),
            ],
            "facts": {"capability_candidate": app_capability, "data_candidates": app_data, "proposed_profile": app["draft"]["proposed_profile"], "proposed_rar": app["draft"]["proposed_rar"], "minimum_data_plan": app["draft"]["minimum_data_plan"]},
            "standards_messages": ["CareTrust RAR-shaped authorization details", "CareTrust application onboarding draft v1"],
            "non_claims": ["The proposal does not register, activate, or authorize an application."],
        },
        {
            "step_id": "04-oidc-pkce-rar-token", "suggested_elapsed_seconds": 70,
            "title": "Synthetic OIDC link, reviewed registration, PKCE/RAR, fresh decision, and resource-token receipt",
            "evidence_status": auth["evidence_status"],
            "source_refs": [
                _source("artifacts/validation/auth-harness-trace.json", auth, [auth["upstream_identity_link"]["link_id"], auth["human_reviewed_registration"]["registration_id"], auth["authorization_code_request"]["request_id"], auth["authorization_code_receipt"]["code_id"], auth["downstream_token_receipt"]["token_id"], auth["fresh_case_decision"]["decision_id"]]),
            ],
            "facts": {"oidc_identity_link": {"link_id": auth["upstream_identity_link"]["link_id"], "verified_locally": auth["upstream_identity_link"]["oidc_id_token_verified_locally"], "upstream_token_forwarded": auth["upstream_identity_link"]["upstream_token_forwarded_to_application"]}, "registration": {"registration_id": auth["human_reviewed_registration"]["registration_id"], "review_decision": auth["human_reviewed_registration"]["review_decision"]}, "pkce": {"method": auth["authorization_code_request"]["code_challenge_method"], "state": auth["authorization_code_request"]["state"]}, "rar": auth["authorization_code_request"]["authorization_details"], "fresh_decision": auth["fresh_case_decision"], "resource_token_receipt": {"token_id": auth["downstream_token_receipt"]["token_id"], "token_sha256": auth["downstream_token_receipt"]["token_sha256"], "expires_at": auth["downstream_token_receipt"]["expires_at"]}},
            "standards_messages": ["OIDC identity-link contract", "OAuth authorization code with PKCE", "OAuth RAR-shaped authorization details"],
            "non_claims": auth["non_claims"],
        },
        {
            "step_id": "05-fhir-smart-reference-app", "suggested_elapsed_seconds": 45,
            "title": "FHIR Appointment/SMART least privilege and synthetic reference-app result",
            "evidence_status": fhir["evidence_status"],
            "source_refs": [
                _source("artifacts/validation/fhir-smart-scheduling-projection.json", fhir, [fhir["case_id"], fhir["fresh_revocation_check"]["decision_id"], *[row["caretrust_decision_id"] for row in fhir["capability_matrix"]]]),
                _source("artifacts/validation/auth-harness-trace.json", auth, [auth["downstream_token_receipt"]["token_id"], auth["fresh_case_decision"]["decision_id"]]),
            ],
            "facts": {"business_action_mapping": fhir["business_action_mapping"], "availability_boundary": fhir["availability"], "caregiver_capabilities": fhir["capability_matrix"], "appointment_workflow": fhir["proposed_appointment_workflow"], "reference_app_result": {"fresh_decision_id": auth["fresh_case_decision"]["decision_id"], "token_receipt_id": auth["downstream_token_receipt"]["token_id"], "external_fhir_server_executed": fhir["source_metadata"]["external_fhir_server_executed"]}},
            "standards_messages": ["FHIR R4 Appointment", "FHIR R4 AppointmentResponse", "SMART App Launch 2.2 resource scopes"],
            "non_claims": fhir["non_claims"],
        },
        {
            "step_id": "06-revocation-fresh-deny", "suggested_elapsed_seconds": 40,
            "title": "Revocation changes a fresh request into a deterministic deny",
            "evidence_status": family_revoked["evidence_status"],
            "source_refs": [
                _source("artifacts/validation/synthetic-multi-caregiver-case.json", case, [family_permit["decision_id"], family_permit["request_id"], family_revoked["decision_id"], family_revoked["request_id"], case["canonical_objects"]["delegation_revocation"]["revocation_id"]]),
                _source("artifacts/validation/core-v0.1/core-runtime-bridge-validation.json", core, [core["message_envelopes"]["delegation_revocation_status"]["message_id"]]),
            ],
            "facts": {"before": {"decision_id": family_permit["decision_id"], "decision": family_permit["decision"]}, "revocation": case["canonical_objects"]["delegation_revocation"], "after_fresh_request": {"decision_id": family_revoked["decision_id"], "decision": family_revoked["decision"], "reason_code": family_revoked["reason_code"]}},
            "standards_messages": ["CareTrust delegation revocation record", core["message_envelopes"]["delegation_revocation_status"]["message_type"]],
            "non_claims": ["The trace demonstrates a fresh local decision, not external token termination."],
        },
        {
            "step_id": "07-mcp-inspection", "suggested_elapsed_seconds": 30,
            "title": "MCP inspects, validates, and simulates without changing authority",
            "evidence_status": mcp["evidence_status"],
            "source_refs": [_source("artifacts/validation/mcp-adapter-contract.json", mcp, [case["case_id"], mcp["canonical_state_hash_before"], mcp["canonical_state_hash_after"]])],
            "facts": {"transport": mcp["transport"], "state_mutated": mcp["state_mutated"], "network_calls": mcp["network_calls"], "canonical_state_hash_before": mcp["canonical_state_hash_before"], "canonical_state_hash_after": mcp["canonical_state_hash_after"]},
            "standards_messages": ["MCP local stdio JSON-RPC adapter contract"],
            "non_claims": mcp["claim_boundary"],
        },
        _federation_step(case),
    ]
    contract: dict[str, object] = {
        "schema_version": SCHEMA_VERSION, "case_id": case["case_id"], "synthetic": True,
        "suggested_total_seconds": sum(step["suggested_elapsed_seconds"] for step in steps),
        "steps": steps,
        "non_claims": ["This is a deterministic local walkthrough contract, not a UI state machine or deployment claim."],
    }
    contract["walkthrough_sha256"] = _hash(contract)
    validate_judge_walkthrough_contract(contract)
    return contract


def _federation_step(case: Mapping[str, Any]) -> dict[str, object]:
    if not FEDERATION_ARTIFACT.exists():
        raise JudgeWalkthroughError("required two-hub federation artifact is missing")
    try:
        payload = json.loads(FEDERATION_ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeWalkthroughError("two-hub federation artifact is unreadable") from exc
    _validate_federation_artifact(payload, case)
    chains = payload["participant_and_client_entity_trust"]
    decision = payload["fresh_local_caregiver_decision_after_trust"]
    return {
        "step_id": "08-two-hub-federation", "suggested_elapsed_seconds": 30,
        "title": "Two independently configured hubs establish entity trust; local policy decides caregiver access",
        "evidence_status": "executed_local",
        "source_refs": [_source(
            str(FEDERATION_ARTIFACT.relative_to(ROOT)).replace("\\", "/"), payload,
            [*[chain["entity_id"] for chain in chains], decision["request_id"], decision["decision_id"]],
        )],
        "facts": {
            "status": "executed_local",
            "segment_skipped": False,
            "artifact_payload_sha256": payload["artifact_payload_sha256"],
            "participant_and_client_trust": [
                {key: chain[key] for key in ("entity_id", "role", "trust_anchor_id", "chain_sha256", "entity_trust_only")}
                for chain in chains
            ],
            "metadata_policy_applied": [chain["metadata_policy"] for chain in chains],
            "negative_exercises": payload["negative_exercises"],
            "fresh_local_caregiver_decision": decision,
        },
        "standards_messages": ["OpenID Federation 1.0 entity statement/trust-anchor concepts", "Separate fresh CareTrust local authorization decision"],
        "non_claims": [*payload["claim_boundary"], "Federation entity trust is not caregiver permission, token issuance, or a live network deployment."],
    }


def _validate_federation_artifact(payload: Mapping[str, Any], case: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise JudgeWalkthroughError("two-hub federation artifact must be an object")
    if (
        payload.get("artifact_type") != FEDERATION_PROFILE
        or payload.get("evidence_status") != "executed_local"
        or payload.get("synthetic_only") is not True
        or payload.get("network_calls") is not False
        or payload.get("private_key_material_in_artifact") is not False
    ):
        raise JudgeWalkthroughError("two-hub federation artifact has an invalid execution boundary")
    integrity = payload.get("artifact_payload_sha256")
    material = dict(payload)
    material.pop("artifact_payload_sha256", None)
    if not isinstance(integrity, str) or integrity != _hash(material):
        raise JudgeWalkthroughError("two-hub federation artifact hash is stale or tampered")
    if not FEDERATION_FIXTURE.exists() or payload.get("fixture_sha256") != sha256(FEDERATION_FIXTURE.read_bytes()).hexdigest():
        raise JudgeWalkthroughError("two-hub federation artifact fixture linkage is stale or missing")
    hubs = payload.get("two_independent_hubs")
    chains = payload.get("participant_and_client_entity_trust")
    if not isinstance(hubs, list) or not isinstance(chains, list) or len(hubs) != 2 or len(chains) != 2:
        raise JudgeWalkthroughError("two-hub federation artifact must contain exactly two linked hubs")
    anchor_ids = {hub.get("trust_anchor_id") for hub in hubs}
    roles = {chain.get("role") for chain in chains}
    if len(anchor_ids) != 2 or roles != {"participant_organization", "care_application_client"}:
        raise JudgeWalkthroughError("two-hub federation artifact does not establish distinct participant/client trust")
    if not all(chain.get("entity_trust_only") is True and isinstance(chain.get("chain_sha256"), str) and len(chain["chain_sha256"]) == 64 for chain in chains):
        raise JudgeWalkthroughError("federation trust-chain evidence is incomplete")
    required_negatives = {
        "expired_statement": "FEDERATION_STATEMENT_EXPIRED",
        "tampered_statement": "FEDERATION_SIGNATURE_INVALID",
        "untrusted_anchor": "FEDERATION_MISSING_TRUST_ANCHOR",
        "stale_leaf_rollover": "FEDERATION_JWKS_MISMATCH",
    }
    if payload.get("negative_exercises") != required_negatives or payload.get("key_rollover", {}).get("resolved_with_fresh_statement") is not True:
        raise JudgeWalkthroughError("federation negative or key-rollover evidence is incomplete")
    decision = payload.get("fresh_local_caregiver_decision_after_trust")
    if not isinstance(decision, Mapping):
        raise JudgeWalkthroughError("federation artifact lacks a fresh local caregiver decision")
    current = _decision(case, str(decision.get("request_id", "")))
    if (
        decision.get("case_id") != case.get("case_id")
        or decision.get("case_bundle_sha256") != case.get("bundle_sha256")
        or decision.get("request_sha256") != current.get("request_sha256")
        or decision.get("decision_id") != current.get("decision_id")
        or decision.get("decision") != current.get("decision")
        or decision.get("policy_id") != current.get("policy_id")
        or decision.get("policy_version") != current.get("policy_version")
    ):
        raise JudgeWalkthroughError("federation artifact fresh local decision linkage is stale or tampered")
    boundaries = payload.get("claim_boundary")
    if not isinstance(boundaries, list) or not any("separate fresh" in str(item).lower() for item in boundaries) or not any("no live" in str(item).lower() for item in boundaries):
        raise JudgeWalkthroughError("federation artifact omits required non-claim boundaries")


def validate_judge_walkthrough_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != SCHEMA_VERSION or contract.get("synthetic") is not True:
        raise JudgeWalkthroughError("unexpected walkthrough identity")
    material = dict(contract)
    digest = material.pop("walkthrough_sha256", None)
    if digest != _hash(material):
        raise JudgeWalkthroughError("walkthrough hash does not bind payload")
    steps = contract.get("steps")
    if not isinstance(steps, list) or [item.get("step_id") for item in steps] != [f"0{index}-{name}" for index, name in enumerate(("case-context", "ai-intent", "ai-app-onboarding", "oidc-pkce-rar-token", "fhir-smart-reference-app", "revocation-fresh-deny", "mcp-inspection", "two-hub-federation"), start=1)]:
        raise JudgeWalkthroughError("walkthrough steps are incomplete or unordered")
    if sum(item.get("suggested_elapsed_seconds", 0) for item in steps) != contract.get("suggested_total_seconds") or contract["suggested_total_seconds"] > 360:
        raise JudgeWalkthroughError("walkthrough must total no more than six minutes")
    for step in steps:
        if step.get("evidence_status") not in EVIDENCE_STATUSES or not step.get("source_refs") or not step.get("non_claims"):
            raise JudgeWalkthroughError("every step needs status, source references, and non-claims")
        for source in step["source_refs"]:
            if source.get("artifact_present") is False:
                continue
            digest = source.get("artifact_sha256")
            if not isinstance(digest, str) or len(digest) != 64 or not source.get("canonical_ids"):
                raise JudgeWalkthroughError("executed walkthrough sources require hashes and canonical IDs")
    if steps[-1]["evidence_status"] == "planned" and steps[-1]["facts"].get("status") != "planned_or_awaited":
        raise JudgeWalkthroughError("missing federation artifact must remain explicitly planned")


def render_walkthrough(contract: Mapping[str, Any]) -> str:
    """Return deterministic CLI text suitable for a six-minute walkthrough."""

    lines = [f"CareTrust judge walkthrough ({contract['suggested_total_seconds']} seconds)"]
    for step in contract["steps"]:
        lines.append(f"[{step['step_id']}] +{step['suggested_elapsed_seconds']}s {step['title']} ({step['evidence_status']})")
        for source in step["source_refs"]:
            artifact = source.get("artifact") or ", ".join(source.get("expected_artifact", []))
            digest = source.get("artifact_sha256") or "awaited"
            lines.append(f"  source: {artifact} sha256={digest}")
    return "\n".join(lines) + "\n"
