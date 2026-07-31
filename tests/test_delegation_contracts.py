from __future__ import annotations

import json
from pathlib import Path
import re

import pytest
from pydantic import ValidationError

from caretrust.delegation import (
    ACTION_RESOURCE_REQUIREMENTS,
    DELEGATION_CONTRACTS,
    CareRelationshipClaim,
    ClarificationRequest,
    ClarificationResponse,
    DelegationAction,
    DelegationAudience,
    DelegationAuthorizationDecision,
    DelegationAuthorizationRequest,
    DelegationBlockingCode,
    DelegationDraft,
    DelegationGrant,
    DelegationPurpose,
    DelegationResource,
    DelegationRevocationRecord,
    DelegationUncertaintyCode,
    IntentStatement,
    InviteAcceptance,
    PatientApprovalRecord,
    PatientInvite,
    RelationshipCode,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "standards" / "examples" / "delegation"
VOCABULARY = (
    ROOT / "docs" / "standards" / "caretrust-delegation-vocabulary.v1.json"
)
SCHEMAS = ROOT / "schemas"

EXAMPLE_MODELS = {
    "intent-statement.json": IntentStatement,
    "delegation-draft.json": DelegationDraft,
    "clarification-request.json": ClarificationRequest,
    "clarification-response.json": ClarificationResponse,
    "patient-invite.json": PatientInvite,
    "invite-acceptance.json": InviteAcceptance,
    "patient-approval-record.json": PatientApprovalRecord,
    "care-relationship-claim.json": CareRelationshipClaim,
    "delegation-grant.json": DelegationGrant,
    "delegation-authorization-request.json": DelegationAuthorizationRequest,
    "delegation-authorization-decision.json": DelegationAuthorizationDecision,
    "delegation-revocation-record.json": DelegationRevocationRecord,
}

SCHEMA_MODELS = {
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
}


def payload(filename: str) -> dict:
    return json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))


def test_every_delegation_example_validates_and_is_synthetic() -> None:
    assert len(DELEGATION_CONTRACTS) == len(EXAMPLE_MODELS) == 12
    for filename, model in EXAMPLE_MODELS.items():
        raw = payload(filename)
        assert raw["synthetic"] is True
        assert model.model_validate(raw).schema_version.startswith("caretrust.")


@pytest.mark.parametrize(("filename", "model"), EXAMPLE_MODELS.items())
def test_contracts_reject_unknown_properties(filename: str, model: type) -> None:
    raw = payload(filename)
    raw["undeclared_trust_state"] = "active"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(raw)


def test_intent_hash_and_exact_character_spans_are_enforced() -> None:
    raw = payload("intent-statement.json")
    raw["utterance_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="hash the exact utterance"):
        IntentStatement.model_validate(raw)

    raw = payload("intent-statement.json")
    raw["spans"][0]["start_char"] += 1
    with pytest.raises(ValidationError, match="exact character offsets"):
        IntentStatement.model_validate(raw)

    raw = payload("intent-statement.json")
    raw["spans"][0]["intent_id"] = "intent:synthetic-other"
    with pytest.raises(ValidationError, match="refer to this intent"):
        IntentStatement.model_validate(raw)


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    (
        ("status", "active"),
        ("activation_permitted", True),
        ("authorization_permitted", True),
        ("proposed_by", "patient"),
        ("authority_basis", "patient_attestation"),
        ("legal_authority_status", "established"),
    ),
)
def test_ai_contract_is_irreducibly_draft_only(
    field: str, unsafe_value: object
) -> None:
    raw = payload("delegation-draft.json")
    raw[field] = unsafe_value
    with pytest.raises(ValidationError):
        DelegationDraft.model_validate(raw)


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    (
        ("allowed_actions", ["delete_medical_record"]),
        ("allowed_resources", ["all_health_information"]),
        ("allowed_purposes", ["anything"]),
        ("allowed_audiences", ["app:synthetic-unknown"]),
    ),
)
def test_unknown_scope_vocabulary_is_rejected(
    field: str, unsafe_value: object
) -> None:
    raw = payload("delegation-draft.json")
    raw[field] = unsafe_value
    with pytest.raises(ValidationError):
        DelegationDraft.model_validate(raw)


def test_draft_evidence_bindings_exactly_cover_proposed_values() -> None:
    raw = payload("delegation-draft.json")
    raw["evidence_bindings"].pop()
    with pytest.raises(ValidationError, match="exactly cover proposed values"):
        DelegationDraft.model_validate(raw)

    raw = payload("delegation-draft.json")
    raw["evidence_bindings"][0]["evidence_refs"] = []
    with pytest.raises(ValidationError, match="must cite source evidence"):
        DelegationDraft.model_validate(raw)


def test_blocking_uncertainty_requires_visible_blocking_state() -> None:
    raw = payload("delegation-draft.json")
    raw["uncertainties"] = [
        {
            "blocking": True,
            "code": DelegationUncertaintyCode.AMBIGUOUS_AUDIENCE.value,
            "evidence_refs": ["intent-span:synthetic-scheduling"],
            "field_paths": ["allowed_audiences"],
            "message": "The intended application is unclear.",
        }
    ]
    with pytest.raises(
        ValidationError, match="UNRESOLVED_MATERIAL_UNCERTAINTY"
    ):
        DelegationDraft.model_validate(raw)

    raw["blocking_issues"] = [
        DelegationBlockingCode.UNRESOLVED_MATERIAL_UNCERTAINTY.value
    ]
    DelegationDraft.model_validate(raw)


@pytest.mark.parametrize(
    ("filename", "model"),
    (
        ("delegation-draft.json", DelegationDraft),
        ("delegation-grant.json", DelegationGrant),
    ),
)
def test_exclusions_win_by_forbidding_allow_deny_overlap(
    filename: str, model: type
) -> None:
    raw = payload(filename)
    raw["allowed_resources"].append("billing")
    if filename == "delegation-draft.json":
        raw["evidence_bindings"].append(
            {
                "field_path": "allowed_resources",
                "value": "billing",
                "evidence_refs": ["intent-span:synthetic-exclusions"],
            }
        )
    with pytest.raises(ValidationError, match="exclusions win"):
        model.model_validate(raw)


def test_each_action_requires_its_governed_resource() -> None:
    raw = payload("delegation-grant.json")
    raw["allowed_resources"].remove("appointments")
    with pytest.raises(ValidationError, match="requires resources"):
        DelegationGrant.model_validate(raw)

    draft = payload("delegation-draft.json")
    draft["allowed_resources"].remove("appointments")
    draft["evidence_bindings"] = [
        item
        for item in draft["evidence_bindings"]
        if not (
            item["field_path"] == "allowed_resources"
            and item["value"] == "appointments"
        )
    ]
    with pytest.raises(ValidationError, match="MISSING_REQUIRED_RESOURCE"):
        DelegationDraft.model_validate(draft)
    draft["blocking_issues"] = ["MISSING_REQUIRED_RESOURCE"]
    DelegationDraft.model_validate(draft)


def test_invite_has_only_hashes_and_rejects_plaintext_contact() -> None:
    schema = PatientInvite.model_json_schema(mode="validation")
    properties = schema["properties"]
    forbidden_names = {
        "recipient_email",
        "recipient_phone",
        "recipient_contact",
        "email",
        "phone",
        "contact",
    }
    assert not forbidden_names & set(properties)
    assert {
        "recipient_hint_sha256",
        "invite_token_sha256",
        "nonce_sha256",
    } <= set(properties)

    for field, value in (
        ("recipient_email", "leilani@example.test"),
        ("recipient_phone", "808-555-0100"),
        ("recipient_contact", "Leilani"),
    ):
        raw = payload("patient-invite.json")
        raw[field] = value
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            PatientInvite.model_validate(raw)

    raw = payload("patient-invite.json")
    raw["patient_ref"] = "mailto:patient@example.test"
    with pytest.raises(ValidationError, match="not contact data"):
        PatientInvite.model_validate(raw)


def test_invite_is_single_use_bounded_and_hash_separated() -> None:
    raw = payload("patient-invite.json")
    raw["expires_at"] = raw["created_at"]
    with pytest.raises(ValidationError, match="expire after"):
        PatientInvite.model_validate(raw)

    raw = payload("patient-invite.json")
    raw["recipient_hint_sha256"] = raw["invite_token_sha256"]
    with pytest.raises(ValidationError, match="must differ"):
        PatientInvite.model_validate(raw)

    raw = payload("patient-invite.json")
    raw["single_use"] = False
    with pytest.raises(ValidationError):
        PatientInvite.model_validate(raw)


def test_relationship_consent_grant_and_legal_authority_stay_separate() -> None:
    relationship_schema = CareRelationshipClaim.model_json_schema(mode="validation")
    relationship_properties = set(relationship_schema["properties"])
    assert "relationship_code" in relationship_properties
    assert not {
        "allowed_actions",
        "allowed_resources",
        "allowed_purposes",
        "allowed_audiences",
    } & relationship_properties

    grant_schema = DelegationGrant.model_json_schema(mode="validation")
    grant_properties = set(grant_schema["properties"])
    assert "relationship_claim_id" in grant_properties
    assert "relationship_code" not in grant_properties
    assert "legal_authority_status" in grant_properties

    for filename, model in (
        ("invite-acceptance.json", InviteAcceptance),
        ("patient-approval-record.json", PatientApprovalRecord),
        ("care-relationship-claim.json", CareRelationshipClaim),
        ("delegation-grant.json", DelegationGrant),
    ):
        raw = payload(filename)
        raw["legal_authority_status"] = "established"
        with pytest.raises(ValidationError):
            model.model_validate(raw)

    raw = payload("care-relationship-claim.json")
    raw["allowed_actions"] = ["schedule_appointments"]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CareRelationshipClaim.model_validate(raw)


def test_lifecycle_status_and_subject_invariants_fail_closed() -> None:
    raw = payload("invite-acceptance.json")
    raw["caregiver_ref"] = raw["patient_ref"]
    with pytest.raises(ValidationError, match="different subjects"):
        InviteAcceptance.model_validate(raw)

    raw = payload("delegation-grant.json")
    raw["valid_until"] = "2026-01-01"
    with pytest.raises(ValidationError, match="must not precede"):
        DelegationGrant.model_validate(raw)

    raw = payload("delegation-grant.json")
    raw["status"] = "revoked"
    with pytest.raises(ValidationError, match="requires revoked_at"):
        DelegationGrant.model_validate(raw)

    raw["revoked_at"] = "2026-07-30T10:05:00Z"
    DelegationGrant.model_validate(raw)


def test_decisions_require_evidence_only_for_permits() -> None:
    permit = payload("delegation-authorization-decision.json")
    permit["supporting_grant_ids"] = []
    with pytest.raises(ValidationError, match="exactly one supporting grant"):
        DelegationAuthorizationDecision.model_validate(permit)

    deny = payload("delegation-authorization-decision.json")
    deny.update(
        {
            "decision": "deny",
            "reason_codes": ["RESOURCE_EXCLUDED"],
            "supporting_grant_ids": ["grant:synthetic-001"],
        }
    )
    with pytest.raises(ValidationError, match="cannot carry supporting grants"):
        DelegationAuthorizationDecision.model_validate(deny)

    deny["supporting_grant_ids"] = []
    DelegationAuthorizationDecision.model_validate(deny)


def test_patient_approval_binds_the_exact_clarification_sequence() -> None:
    raw = payload("patient-approval-record.json")
    raw["clarification_response_ids"].append(
        "clarification-response:synthetic-unbound"
    )
    with pytest.raises(ValidationError, match="bind the ordered response IDs"):
        PatientApprovalRecord.model_validate(raw)


def test_patient_directed_revocation_requires_patient_actor() -> None:
    raw = payload("delegation-revocation-record.json")
    raw["actor_ref"] = "admin:synthetic-001"
    with pytest.raises(ValidationError, match="requires patient actor"):
        DelegationRevocationRecord.model_validate(raw)


def test_machine_vocabulary_equals_runtime_enums_and_requirements() -> None:
    vocabulary = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    assert vocabulary["schema_version"] == "caretrust.delegation-vocabulary.v1"
    assert vocabulary["implementation_status"] == "executed_local_tested"
    assert vocabulary["synthetic_only"] is True

    assert {item["code"] for item in vocabulary["actions"]} == {
        item.value for item in DelegationAction
    }
    assert {item["code"] for item in vocabulary["resources"]} == {
        item.value for item in DelegationResource
    }
    assert {item["code"] for item in vocabulary["purposes"]} == {
        item.value for item in DelegationPurpose
    }
    assert {item["code"] for item in vocabulary["audiences"]} == {
        item.value for item in DelegationAudience
    }
    assert set(vocabulary["relationship_codes"]) == {
        item.value for item in RelationshipCode
    }
    published_requirements = {
        item["code"]: set(item["required_resources"])
        for item in vocabulary["actions"]
    }
    runtime_requirements = {
        action.value: {resource.value for resource in resources}
        for action, resources in ACTION_RESOURCE_REQUIREMENTS.items()
    }
    assert published_requirements == runtime_requirements

    invariants = "\n".join(vocabulary["semantic_invariants"]).lower()
    for required in (
        "always draft",
        "does not grant application permission",
        "does not establish legal authority",
        "exclusions win",
        "contact values are never retained in plaintext",
    ):
        assert required in invariants


def test_schema_exports_equal_runtime_contracts() -> None:
    for filename, model in SCHEMA_MODELS.items():
        exported = json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))
        runtime = model.model_json_schema(
            mode="validation",
            ref_template="#/$defs/{model}",
        )
        assert exported == runtime


def test_example_chain_preserves_referential_integrity() -> None:
    intent = IntentStatement.model_validate(payload("intent-statement.json"))
    draft = DelegationDraft.model_validate(payload("delegation-draft.json"))
    clarification = ClarificationRequest.model_validate(
        payload("clarification-request.json")
    )
    response = ClarificationResponse.model_validate(
        payload("clarification-response.json")
    )
    invite = PatientInvite.model_validate(payload("patient-invite.json"))
    acceptance = InviteAcceptance.model_validate(payload("invite-acceptance.json"))
    approval = PatientApprovalRecord.model_validate(
        payload("patient-approval-record.json")
    )
    relationship = CareRelationshipClaim.model_validate(
        payload("care-relationship-claim.json")
    )
    grant = DelegationGrant.model_validate(payload("delegation-grant.json"))
    request = DelegationAuthorizationRequest.model_validate(
        payload("delegation-authorization-request.json")
    )
    decision = DelegationAuthorizationDecision.model_validate(
        payload("delegation-authorization-decision.json")
    )
    revocation = DelegationRevocationRecord.model_validate(
        payload("delegation-revocation-record.json")
    )

    assert draft.intent_id == clarification.intent_id == response.intent_id == intent.intent_id
    assert draft.intent_sha256 == approval.intent_sha256 == intent.utterance_sha256
    assert invite.draft_id == approval.final_draft_id == draft.draft_id
    assert acceptance.invite_id == invite.invite_id
    assert acceptance.invite_token_sha256 == invite.invite_token_sha256
    assert acceptance.nonce_sha256 == invite.nonce_sha256
    assert approval.invite_acceptance_id == acceptance.acceptance_id
    assert response.response_id in approval.clarification_response_ids
    assert relationship.approval_id == grant.approval_id == approval.approval_id
    assert relationship.relationship_claim_id == grant.relationship_claim_id
    assert relationship.patient_ref == grant.patient_ref == request.patient_ref
    assert relationship.caregiver_ref == grant.delegate_ref == request.delegate_ref
    assert request.grant_id == decision.supporting_grant_ids[0] == revocation.grant_id
    assert decision.request_id == request.request_id


def test_public_delegation_artifacts_contain_no_contact_or_secret_material() -> None:
    text = "\n".join(
        [
            VOCABULARY.read_text(encoding="utf-8"),
            *(path.read_text(encoding="utf-8") for path in EXAMPLES.glob("*.json")),
        ]
    )
    for pattern in (
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"AKIA[0-9A-Z]{16}",
    ):
        assert re.search(pattern, text) is None
