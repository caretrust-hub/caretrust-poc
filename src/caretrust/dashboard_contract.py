"""Derived, versioned dashboard contract for the synthetic CareTrust case.

This module is intentionally a read-only projection.  It consumes the canonical
case builder, retained compiler fixtures, and Core bridge validation artifact;
it never evaluates permissions or creates dashboard-only state.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from caretrust.case_bundle import build_synthetic_case_bundle


ROOT = Path(__file__).resolve().parents[2]
COMPILER_FIXTURES = ROOT / "fixtures" / "compiler"
CORE_ARTIFACT = ROOT / "artifacts" / "validation" / "core-v0.1" / "core-runtime-bridge-validation.json"
DASHBOARD_SCHEMA_VERSION = "caretrust.dashboard-contract.v1"
EVIDENCE_STATUSES = frozenset({"executed_local", "contract_tested", "mapped_only", "local_simulation", "retained_aws", "planned"})
DISCLOSURE_FIELDS = frozenset({"decision_id", "request_id", "request_sha256", "caregiver_ref", "application_id", "audience", "action", "purpose", "policy_id", "policy_version", "decision", "reason_code", "minimum_data", "evidence_status"})
FORBIDDEN_DISCLOSURE_TERMS = ("raw_packet", "raw_document", "uploaded_extraction_draft", "extraction_run", "ocr_text", "source_pages", "supporting_canonical_ids", "clinical_holder_revocation_deny")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _row(
    row_id: str,
    source: object,
    canonical_refs: Iterable[str],
    evidence_status: str,
    *,
    non_claims: Iterable[str] = (),
    **values: object,
) -> dict[str, object]:
    return {
        "row_id": row_id,
        "canonical_refs": sorted(set(canonical_refs)),
        "source_sha256": _hash(source),
        "evidence_status": evidence_status,
        "non_claims": list(non_claims),
        **values,
    }


def _fixture_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _read_json(COMPILER_FIXTURES / "intent-input.json"),
        _read_json(COMPILER_FIXTURES / "intent-compilation.json"),
        _read_json(COMPILER_FIXTURES / "application-input.json"),
        _read_json(COMPILER_FIXTURES / "application-compilation.json"),
    )


def _candidate_rows(
    kind: str,
    compilation: Mapping[str, Any],
    input_source: Mapping[str, Any],
) -> list[dict[str, object]]:
    """Expose candidate quote -> bounded value -> draft, without raw packets."""

    candidate = compilation.get("model_candidate") or {}
    draft = compilation["draft"]
    draft_id = str(draft["draft_id"])
    bindings = {
        (binding["field_path"], binding["value"]): binding
        for binding in draft.get("evidence_bindings", ())
    }
    rows: list[dict[str, object]] = []
    candidate_values: list[tuple[str, Mapping[str, Any]]] = []
    for name, value in candidate.items():
        if value is None:
            continue
        if isinstance(value, list):
            candidate_values.extend((name, item) for item in value)
        elif isinstance(value, Mapping):
            candidate_values.append((name, value))
    field_map = {
        "delegate_ref": "delegate_ref", "relationship_code": "relationship_code",
        "actions": "allowed_actions", "resources": "allowed_resources",
        "excluded_resources": "excluded_resources", "audience": "allowed_audiences",
        "purpose": "allowed_purposes", "valid_until": "valid_until",
    }
    for index, (name, item) in enumerate(candidate_values, start=1):
        citation = item.get("citation", {})
        value = str(item.get("value", ""))
        citations = [str(citation.get("span_id") or citation.get("citation_id") or "")]
        if kind == "application":
            field_path, binding_refs = _application_candidate_binding(
                name, value, citations[0], draft
            )
        else:
            field_path = field_map.get(name, "minimum_data_plan")
            binding = bindings.get((field_path, value))
            binding_refs = (binding or {}).get("evidence_refs", [])
        rows.append(
            _row(
                f"ai-review:{kind}:{index}", item, [draft_id, *[item for item in citations if item]],
                str(compilation.get("evidence_status", "contract_tested")),
                non_claims=(
                    "Candidate output is untrusted until deterministic validation and accountable review.",
                    "No live Bedrock invocation is claimed by this retained fixture.",
                ),
                compiler_kind=kind,
                compilation_mode=compilation.get("compilation_mode"),
                exact_candidate_quote=citation.get("quote"),
                candidate_citation_id=citations[0] or None,
                bounded_value=value,
                draft_id=draft_id,
                draft_binding_field=field_path,
                draft_binding_evidence_refs=binding_refs,
                deterministic_validation_errors=compilation.get("candidate_validation_errors", []),
                human_review_boundary={
                    "required": True,
                    "review_recorded_for_this_compiler_draft": False,
                    "authority_effect": "none",
                },
            )
        )
    return rows


def _application_candidate_binding(
    candidate_kind: str, value: str, citation_id: str, draft: Mapping[str, Any]
) -> tuple[str, list[str]]:
    """Resolve app candidate values to their draft's retained evidence fields."""

    rar = draft["proposed_rar"][0]
    if candidate_kind == "capability":
        if value not in str(draft["proposed_profile"]):
            raise ValueError("application capability candidate does not match proposed profile")
        refs = list(rar["evidence_refs"])
        return "proposed_profile/capability", [citation_id] if citation_id in refs else refs
    if candidate_kind == "action":
        if value not in rar["actions"]:
            raise ValueError("application action candidate does not resolve to proposed RAR action")
        refs = list(rar["evidence_refs"])
        return "proposed_rar.actions", [citation_id] if citation_id in refs else refs
    if candidate_kind == "data_fields":
        item = next((entry for entry in draft["minimum_data_plan"] if entry["field"] == value), None)
        if item is None:
            raise ValueError("application data candidate does not resolve to minimum-data plan")
        return "minimum_data_plan", list(item["evidence_refs"])
    if candidate_kind == "location":
        if value not in rar["locations"]:
            raise ValueError("application location candidate does not resolve to proposed RAR location")
        refs = list(rar["evidence_refs"])
        return "proposed_rar.locations", [citation_id] if citation_id in refs else refs
    raise ValueError("unknown application candidate kind")


def _minimum_receipt(row: Mapping[str, Any]) -> dict[str, object]:
    if set(row) - DISCLOSURE_FIELDS:
        raise ValueError("case application projection contains a non-disclosure field")
    result = {field: row[field] for field in DISCLOSURE_FIELDS if field in row}
    for item in result.get("minimum_data", []):
        if set(item) - {"approved_item_id", "kind", "category", "reviewed_text", "source_assertion", "clinically_authoritative", "requires_clinical_confirmation"}:
            raise ValueError("minimum-data projection has an unknown field")
    rendered = canonical_json(result).casefold()
    if any(term in rendered for term in FORBIDDEN_DISCLOSURE_TERMS):
        raise ValueError("application receipt leaked a forbidden source payload")
    return result


def build_dashboard_contract() -> dict[str, object]:
    """Build the dashboard payload from canonical source objects only."""

    bundle = build_synthetic_case_bundle()
    intent_input, intent_compilation, app_input, app_compilation = _fixture_inputs()
    core = _read_json(CORE_ARTIFACT)
    canonical_objects = bundle["canonical_objects"]
    projections = bundle["projections"]
    decisions_by_request = {item["request_id"]: item for item in bundle["decisions"]}
    requests_by_id = {item["request_id"]: item for item in canonical_objects["permission_requests"]}

    care_team = [
        _row(
            f"care-team:{item['caregiver_ref']}", item, [item["caregiver_ref"], *item["basis_ids"]],
            "executed_local", caregiver_ref=item["caregiver_ref"], role=item["role"], status=item["status"], basis_ids=item["basis_ids"],
            non_claims=("Care-team membership display is not a permission decision.",),
        )
        for item in projections["care_team"]
    ]
    permissions = [
        _row(
            f"permission:{decision['decision_id']}", decision,
            [decision["decision_id"], decision["request_id"], *decision["supporting_canonical_ids"]], decision["evidence_status"],
            source_decision_id=decision["decision_id"], request_id=decision["request_id"], request_sha256=decision["request_sha256"],
            caregiver_ref=decision["caregiver_ref"], application_id=decision["application_id"], audience=decision["audience"], action=decision["action"],
            purpose=decision["purpose"], decision=decision["decision"], reason_code=decision["reason_code"], policy_id=decision["policy_id"],
            policy_version=decision["policy_version"], supporting_canonical_ids=decision["supporting_canonical_ids"], as_of=decision["as_of"],
            non_claims=("This row renders an already-issued canonical decision; it does not decide access.",),
        )
        for decision in bundle["decisions"]
    ]
    history = [
        _row(
            f"history:{event['event_id']}", event, [event["event_id"], *event["canonical_ids"].values()], event["evidence_status"],
            event_id=event["event_id"], message_type=event["message_type"], canonical_hash=event["canonical_hash"], canonical_ids=event["canonical_ids"],
        )
        for event in projections["history"]
    ]
    receipts = [
        _row(
            f"receipt:{item['decision_id']}", item, [item["decision_id"], item["request_id"]], item["evidence_status"],
            disclosure=_minimum_receipt(item),
            non_claims=("Reference-client disclosure is a minimum-data projection, not a source packet.",),
        )
        for item in projections["applications"]
    ]
    application_rows = [
        _row(
            f"application:{app['application_id']}", app, [app["application_id"]], "executed_local",
            application_id=app["application_id"], supported_actions=app["supported_actions"],
            non_claims=("Application registry display is not application activation or OAuth deployment.",),
        )
        for app in bundle["applications"]
    ]
    app_draft = app_compilation["draft"]
    application_rows.append(
        _row(
            f"application-proposal:{app_draft['application_id']}", app_compilation,
            [app_draft["application_id"], app_draft["draft_id"]], app_compilation["evidence_status"],
            application_id=app_draft["application_id"], draft_id=app_draft["draft_id"], proposed_profile=app_draft["proposed_profile"],
            proposed_rar_type=app_draft["proposed_rar"][0]["type"], minimum_data_fields=[item["field"] for item in app_draft["minimum_data_plan"]],
            non_claims=("This compiler proposal did not register or activate an application.",),
        )
    )
    evidence = [
        _row(
            f"evidence:{item['canonical_id']}", item, [item["canonical_id"]], item["status"],
            canonical_id=item["canonical_id"], evidence_class=item["class"], application_disclosure=item["application_disclosure"],
            non_claims=("Restricted evidence is represented as metadata only in this dashboard contract.",),
        )
        for item in projections["evidence"]
    ]
    ai_review = _candidate_rows("intent", intent_compilation, intent_input) + _candidate_rows("application", app_compilation, app_input)
    correction = canonical_objects["uploaded_review_correction"]
    extraction = canonical_objects["uploaded_extraction_draft"]
    correction_timeline = [
        _row(
            "ai-correction:before", extraction, [extraction["draft_id"], extraction["document_id"]], "contract_tested",
            stage="before_accountable_review", draft_id=extraction["draft_id"], extraction_run_id=extraction["extraction_run_id"],
            candidate_ids=[item["item_id"] for item in extraction["candidate_items"]], application_disclosure=False,
            non_claims=("Candidate text and source pages are intentionally not present in this dashboard projection.",),
        ),
        _row(
            "ai-correction:after", correction, [correction["review_id"], correction["draft_id"], correction["document_id"]], "executed_local",
            stage="after_accountable_review", review_id=correction["review_id"], decision=correction["decision"],
            corrections=correction["corrections"], approved_item_ids=correction["approved_item_ids"], rejected_item_ids=correction["rejected_item_ids"],
            deferred_item_ids=correction["deferred_item_ids"], establishes_legal_authority=correction["establishes_legal_authority"],
            establishes_current_clinical_truth=correction["establishes_current_clinical_truth"], application_disclosure=False,
            non_claims=("Accountable correction is document-statement review, not clinical truth or authorization.",),
        ),
    ]
    revocation_sources = [
        {
            "name": "delegation", "source": canonical_objects["delegation_revocation"],
            "target": canonical_objects["delegation_revocation"]["grant_id"],
            "before_request_id": "request:case:family-permit-001",
            "after_request_id": "request:case:family-revoked-001",
        },
        {
            "name": "credential", "source": canonical_objects["credential_revocation"],
            "target": canonical_objects["credential_revocation"]["claim_id"],
            "before_request_id": "request:case:cna-permit-001",
            "after_request_id": "request:case:cna-revoked-001",
        },
        {
            "name": "respite", "source": canonical_objects["respite_service_grant_revocation"],
            "target": canonical_objects["respite_service_grant_revocation"]["grant_id"],
            "before_request_id": "request:case:respite-historical-001",
            "after_request_id": "request:case:respite-revoked-001",
        },
    ]
    revocations = []
    for link in revocation_sources:
        name, item, target = link["name"], link["source"], link["target"]
        before, after = decisions_by_request[link["before_request_id"]], decisions_by_request[link["after_request_id"]]
        revocations.append(_row(
            f"revocation:{name}", item, [str(target), before["decision_id"], after["decision_id"], *([item["revocation_id"]] if item.get("revocation_id") else [])],
            item.get("evidence_status", "executed_local"), revocation_id=item.get("revocation_id"), target_id=target,
            revoked_at=item.get("revoked_at"), before_decision_id=before["decision_id"], after_decision_id=after["decision_id"],
            before_request_id=before["request_id"], after_request_id=after["request_id"], reason_code=after["reason_code"],
            non_claims=("Revocation timeline displays canonical status effects; the dashboard cannot revoke anything.",),
        ))
    document_revocation = canonical_objects["document_share_revocation"]
    document_grant = canonical_objects["document_share_grant"]
    before_request = canonical_objects["document_share_request"]
    before_decision = canonical_objects["document_share_decision"]
    after_request = canonical_objects["post_revocation_document_share_request"]
    after_decision = canonical_objects["post_revocation_document_share_decision"]
    revocations.append(_row(
        "revocation:document-share", [document_grant, before_request, before_decision, document_revocation, after_request, after_decision],
        [document_grant["grant_id"], document_revocation["revocation_id"], before_request["request_id"], before_decision["decision_id"], after_request["request_id"], after_decision["decision_id"]],
        document_revocation.get("evidence_status", "executed_local"), revocation_id=document_revocation["revocation_id"],
        target_id=document_revocation["grant_id"], revoked_at=document_revocation["revoked_at"], linkage_type="canonical_document_share",
        before_request_id=before_request["request_id"], after_request_id=after_request["request_id"],
        before_decision_id=before_decision["decision_id"], after_decision_id=after_decision["decision_id"],
        canonical_fresh_deny_available=True, gap=None,
        non_claims=("Document-share post-revocation denial is a canonical document-share decision, not a case-permission decision.",),
    ))
    standards = [
        _row(
            f"standard:{item['canonical_id']}", item, [item["canonical_id"]], item["evidence_status"],
            canonical_id=item["canonical_id"], standard=item["standard"], standard_non_claim=item.get("non_claim"),
        )
        for item in projections["standards"]
    ]
    messages = [
        _row(
            f"core-message:{message['message_id']}", message, [message["message_id"], message["payload_hash"]["value"]], core["evidence_status"],
            message_id=message["message_id"], message_type=message["message_type"], payload_schema_uri=message["payload_schema_uri"],
            profile_uri=message["profile_uri"], payload_sha256=message["payload_hash"]["value"], trace_id=message["trace_id"],
            non_claims=("Core envelope is a local bridge artifact, not a deployed network message.",),
        )
        for message in core["message_envelopes"].values()
    ]
    mappings = [
        _row(
            f"core-mapping:{name}", mapping, [_mapping_ref(mapping["target"])], "mapped_only",
            mapping_name=name, source_schema_version=mapping["metadata"]["source_schema_version"], target_schema_uri=mapping["metadata"]["target_schema_uri"],
            conformance=mapping["metadata"]["conformance"], semantic_loss=mapping["metadata"]["semantic_loss"], bridge_generated_fields=mapping["metadata"]["bridge_generated_fields"],
            non_claims=("Mapping status is not independent conformance or deployed interoperability.",),
        )
        for name, mapping in core["mappings"].items()
    ]
    contract: dict[str, object] = {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "case_id": bundle["case_id"], "generated_at": bundle["generated_at"], "synthetic": True,
        "evidence_status": "executed_local",
        "source_hashes": {
            "case_bundle_sha256": bundle["bundle_sha256"], "intent_input_sha256": _hash(intent_input),
            "intent_compilation_sha256": _hash(intent_compilation), "application_input_sha256": _hash(app_input),
            "application_compilation_sha256": _hash(app_compilation), "core_bridge_artifact_sha256": _hash(core),
        },
        "non_claims": [
            "This contract is derived display data and cannot create or alter authority.",
            "All inputs are synthetic local fixtures; no live Bedrock, application, EHR, registry, or network is represented.",
        ],
        "views": {
            "case_overview": _row("case-overview", bundle, [bundle["case_id"], bundle["patient"]["patient_ref"]], "executed_local", patient_ref=bundle["patient"]["patient_ref"], policy_id=bundle["policy"]["policy_id"], policy_version=bundle["policy"]["policy_version"], caregiver_count=len(bundle["caregivers"]), decision_count=len(bundle["decisions"]), bundle_sha256=bundle["bundle_sha256"]),
            "care_team": care_team, "permissions": permissions, "history": history,
            "applications_and_receipts": {"applications": application_rows, "reference_client_receipts": receipts},
            "evidence": evidence,
            "ai_review": {"candidate_to_draft": ai_review, "correction_timeline": correction_timeline},
            "standards_messages_mappings_gaps": {"standards": standards, "messages": messages, "mappings": mappings, "gaps": [
                "Core bridge mappings are mapped_only; no independent profile conformance is claimed.",
                "No live OAuth/OIDC, EHR/HIE, Bedrock, registry, or federation deployment is evidenced.",
            ]},
            "revocation_timeline": revocations,
        },
    }
    contract["dashboard_sha256"] = _hash(contract)
    validate_dashboard_contract(contract)
    return contract


def _all_rows(views: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for value in views.values():
        if isinstance(value, Mapping) and "row_id" in value:
            yield value
        elif isinstance(value, list):
            yield from (item for item in value if isinstance(item, Mapping))
        elif isinstance(value, Mapping):
            yield from _all_rows(value)


def validate_dashboard_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != DASHBOARD_SCHEMA_VERSION or not contract.get("synthetic"):
        raise ValueError("unexpected dashboard contract identity")
    material = dict(contract)
    digest = material.pop("dashboard_sha256", None)
    if digest != _hash(material):
        raise ValueError("dashboard hash must bind the complete derived payload")
    if any(status not in EVIDENCE_STATUSES for status in _evidence_labels(contract["views"])):
        raise ValueError("dashboard contains an unknown evidence status")
    rows = list(_all_rows(contract["views"]))
    if any(not row.get("row_id") or not row.get("canonical_refs") or not row.get("source_sha256") for row in rows):
        raise ValueError("every material dashboard row requires canonical refs and a source hash")
    permissions = contract["views"]["permissions"]
    source_ids = {row["source_decision_id"] for row in permissions}
    if len(source_ids) != len(permissions):
        raise ValueError("dashboard permissions must each resolve to one canonical decision")
    canonical_case = build_synthetic_case_bundle()
    canonical_decisions = {
        item["decision_id"]: item for item in canonical_case["decisions"]
    }
    canonical_requests = {
        item["request_id"]: item
        for item in canonical_case["canonical_objects"]["permission_requests"]
    }
    for row in permissions:
        decision = canonical_decisions.get(row["source_decision_id"])
        request = canonical_requests.get(row["request_id"])
        if decision is None or request is None:
            raise ValueError("dashboard permission does not resolve to a canonical case object")
        if row["decision"] != decision["decision"] or row["request_sha256"] != _hash(request):
            raise ValueError("dashboard cannot contain a UI-only decision or request hash")
    for receipt in contract["views"]["applications_and_receipts"]["reference_client_receipts"]:
        disclosure = receipt["disclosure"]
        if set(disclosure) - DISCLOSURE_FIELDS or any(term in canonical_json(disclosure).casefold() for term in FORBIDDEN_DISCLOSURE_TERMS):
            raise ValueError("reference-client receipt is not minimum disclosure")
    if any("live bedrock" in claim.casefold() and "no live" not in claim.casefold() for claim in contract["non_claims"]):
        raise ValueError("dashboard makes an unsupported live-model claim")


def _evidence_labels(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        status = value.get("evidence_status")
        if isinstance(status, str):
            yield status
        for nested in value.values():
            yield from _evidence_labels(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _evidence_labels(nested)


def _mapping_ref(target: Mapping[str, Any]) -> str:
    for field in ("artifact_id", "request_id", "decision_id", "event_id", "artifact_ref"):
        value = target.get(field)
        if isinstance(value, str) and value:
            return value
    raise ValueError("Core mapping target has no canonical identifier")
