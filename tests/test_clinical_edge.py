from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from caretrust.clinical_edge import (
    ClinicalContextStatus,
    ClinicalDataDecisionValue,
    ClinicalDataExchangeRecord,
    ClinicalDataReasonCode,
    SyntheticClinicalDataHolderAdapter,
)
from scripts.export_clinical_edge_examples import (
    AUTHORIZED_USER,
    DATA_HOLDER,
    LOCAL_PATIENT,
    NOW,
    PATIENT,
    PARTICIPANT,
    REGISTERED_CLIENT,
    build_examples,
    bundle,
    context,
    request,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "standards" / "examples" / "clinical-edge"


def adapter(
    *,
    allowed_resource_types: frozenset[str] = frozenset({"CarePlan"}),
) -> SyntheticClinicalDataHolderAdapter:
    return SyntheticClinicalDataHolderAdapter(
        data_holder_id=DATA_HOLDER,
        patient_index={PATIENT: LOCAL_PATIENT},
        care_plan_by_local_patient={LOCAL_PATIENT: bundle()},
        eligible_participant_orgs=frozenset({PARTICIPANT}),
        registered_clients_by_participant={
            PARTICIPANT: frozenset({REGISTERED_CLIENT})
        },
        authorized_users_by_participant={
            PARTICIPANT: frozenset({AUTHORIZED_USER})
        },
        allowed_resource_types=allowed_resource_types,
    )


def test_checked_examples_are_generated_from_executed_adapter_records() -> None:
    generated = build_examples()
    assert set(generated) == {
        "permit.json",
        "deny-unregistered-client.json",
        "deny-no-patient-match.json",
        "deny-insufficient-scope.json",
        "deny-revoked-fresh-request.json",
    }
    for filename, expected in generated.items():
        checked = ClinicalDataExchangeRecord.model_validate_json(
            (EXAMPLES / filename).read_text(encoding="utf-8")
        )
        assert checked == expected
        assert checked.synthetic is True
        assert checked.network_calls is False
        assert checked.live_hie_or_ehr_connected is False


def test_data_holder_permit_includes_only_granted_synthetic_fhir_data() -> None:
    record = adapter().decide(
        request("permit-test", context("permit-test")),
        now=NOW,
    )
    assert record.decision.decision is ClinicalDataDecisionValue.PERMIT
    assert record.decision.reason_codes == (
        ClinicalDataReasonCode.DATA_HOLDER_POLICY_SATISFIED,
    )
    assert record.patient_match.authority == "data_holder"
    assert record.patient_match.local_patient_ref == LOCAL_PATIENT
    assert record.decision.disclosure_policy_authority == "data_holder"
    assert record.decision.caretrust_role == (
        "delegation_and_trust_context_only"
    )
    assert record.request.requesting_actor_role == "authorized_participant_user"
    assert record.request.clinical_data_recipient == (
        "authorized_participant_application"
    )
    assert record.request.caregiver_is_requesting_actor is False
    assert record.request.authorized_user_ref != record.request.caregiver_ref
    assert record.decision.requesting_party_eligibility_authority == "data_holder"
    assert record.decision.participant_org_ref == PARTICIPANT
    assert record.decision.authorized_user_ref == AUTHORIZED_USER
    assert record.decision.client_id == REGISTERED_CLIENT
    assert record.returned_fhir_bundle is not None
    assert {
        entry.resource.resourceType
        for entry in record.returned_fhir_bundle.entry
    } == {"CarePlan"}
    assert all(
        entry.resource.subject.reference == LOCAL_PATIENT
        for entry in record.returned_fhir_bundle.entry
    )


def test_data_holder_no_match_denies_without_disclosing_local_identifier() -> None:
    record = adapter().decide(
        request(
            "no-match-test",
            context("no-match-test", patient_ref="patient:synthetic-missing"),
        ),
        now=NOW,
    )
    assert record.patient_match.status.value == "no_match"
    assert record.patient_match.local_patient_ref is None
    assert record.decision.decision is ClinicalDataDecisionValue.DENY
    assert record.decision.reason_codes == (
        ClinicalDataReasonCode.PATIENT_NO_MATCH,
    )
    assert record.returned_fhir_bundle is None


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        (
            {"participant_org_ref": "org:synthetic-ineligible"},
            ClinicalDataReasonCode.PARTICIPANT_NOT_ELIGIBLE,
        ),
        (
            {"client_id": "https://unregistered-care-app.synthetic.invalid"},
            ClinicalDataReasonCode.CLIENT_NOT_REGISTERED,
        ),
        (
            {"authorized_user_ref": "user:synthetic-ineligible"},
            ClinicalDataReasonCode.AUTHORIZED_USER_NOT_ELIGIBLE,
        ),
    ],
)
def test_requesting_party_failure_denies_before_patient_match(
    overrides: dict[str, str],
    expected_reason: ClinicalDataReasonCode,
) -> None:
    record = adapter().decide(
        request(
            "requesting-party-test",
            context("requesting-party-test"),
            **overrides,
        ),
        now=NOW,
    )
    assert record.patient_match.status.value == "not_attempted"
    assert record.patient_match.method == "not_attempted_requesting_party_gate"
    assert record.decision.reason_codes == (expected_reason,)
    assert record.returned_fhir_bundle is None


def test_insufficient_delegated_scope_denies_after_data_holder_match() -> None:
    record = adapter().decide(
        request(
            "scope-test",
            context("scope-test"),
            resource_types=("Observation",),
            scopes=("patient/Observation.rs",),
        ),
        now=NOW,
    )
    assert record.patient_match.status.value == "matched"
    assert record.decision.decision is ClinicalDataDecisionValue.DENY
    assert record.decision.reason_codes == (
        ClinicalDataReasonCode.INSUFFICIENT_DELEGATED_SCOPE,
    )
    assert record.returned_fhir_bundle is None


def test_fresh_request_after_revocation_denies_before_patient_match() -> None:
    prior_request_id = "request:clinical:permit-historical"
    revoked = context(
        "revoked-test",
        status=ClinicalContextStatus.REVOKED,
    )
    fresh = request(
        "revoked-fresh-test",
        revoked,
        prior_request_id=prior_request_id,
    )
    record = adapter().decide(fresh, now=NOW)
    assert record.request.request_id != prior_request_id
    assert record.patient_match.status.value == "not_attempted"
    assert record.decision.reason_codes == (
        ClinicalDataReasonCode.CARETRUST_CONTEXT_REVOKED,
    )
    assert record.returned_fhir_bundle is None


def test_data_holder_can_deny_even_when_caretrust_context_allows_request() -> None:
    local_policy_denies_all = adapter(allowed_resource_types=frozenset())
    record = local_policy_denies_all.decide(
        request("holder-policy-test", context("holder-policy-test")),
        now=NOW,
    )
    assert record.patient_match.status.value == "matched"
    assert record.decision.reason_codes == (
        ClinicalDataReasonCode.DATA_HOLDER_POLICY_DENIED,
    )
    assert record.returned_fhir_bundle is None


def test_request_and_exchange_contracts_fail_closed() -> None:
    valid = request("strict-test", context("strict-test"))
    unexpected = valid.model_dump(mode="json")
    unexpected["unexpected"] = "field"
    with pytest.raises(ValidationError, match="Extra inputs"):
        type(valid).model_validate(unexpected)

    wrong_caregiver = valid.model_dump(mode="json")
    wrong_caregiver["caregiver_ref"] = "caregiver:synthetic-other"
    with pytest.raises(ValidationError, match="caregiver"):
        type(valid).model_validate(wrong_caregiver)

    unsupported_scope = valid.model_dump(mode="json")
    unsupported_scope["requested_scopes"] = ["patient/*.*"]
    with pytest.raises(ValidationError, match="unsupported synthetic clinical scope"):
        type(valid).model_validate(unsupported_scope)

    permit = adapter().decide(valid, now=NOW)
    mismatched_subject = permit.model_dump(mode="json")
    assert mismatched_subject["returned_fhir_bundle"] is not None
    mismatched_subject["returned_fhir_bundle"]["entry"][0]["resource"]["subject"][
        "reference"
    ] = "Patient/synthetic-wrong"
    with pytest.raises(ValidationError, match="matched patient"):
        ClinicalDataExchangeRecord.model_validate(mismatched_subject)


def test_adapter_rejects_naive_time_and_non_synthetic_endpoint() -> None:
    valid = request("time-test", context("time-test"))
    with pytest.raises(ValueError, match="timezone-aware"):
        adapter().decide(valid, now=datetime(2026, 7, 30, 18, 0))
    with pytest.raises(ValueError, match="synthetic HTTPS"):
        SyntheticClinicalDataHolderAdapter(
            data_holder_id="https://real.example.org",
            patient_index={},
            care_plan_by_local_patient={},
            eligible_participant_orgs=frozenset(),
            registered_clients_by_participant={},
            authorized_users_by_participant={},
        )


def test_examples_contain_no_live_hie_claim_or_personal_data() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(EXAMPLES.glob("*.json"))
    )
    assert "hawaii health information exchange" not in text.lower()
    assert "hhie" not in text.lower()
    assert '"live_hie_or_ehr_connected": false' in text
    assert '"caregiver_is_requesting_actor": false' in text
    assert '"clinical_data_recipient": "authorized_participant_application"' in text
    assert "professional_claim_id" not in text
    assert "@" not in text
    assert "not a real clinical record" in text
    for path in EXAMPLES.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
