"""Export deterministic synthetic clinical-data edge examples."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from caretrust.clinical_edge import (
    CareTrustClinicalContext,
    ClinicalContextStatus,
    ClinicalDataAuthorizationRequest,
    ClinicalDataExchangeRecord,
    FhirCoding,
    FhirMeta,
    FhirReference,
    SyntheticClinicalDataHolderAdapter,
    SyntheticFhirR4Bundle,
    SyntheticFhirR4BundleEntry,
    SyntheticFhirR4CarePlan,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "standards" / "examples" / "clinical-edge"
NOW = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
DATA_HOLDER = "https://ehr.synthetic.invalid"
PARTICIPANT = "org:synthetic-participating-provider-001"
AUTHORIZED_USER = "user:synthetic-care-coordinator-001"
REGISTERED_CLIENT = "https://care-app.synthetic.invalid"
PATIENT = "patient:synthetic-001"
CAREGIVER = "caregiver:synthetic-001"
LOCAL_PATIENT = "Patient/synthetic-local-001"


def context(
    suffix: str,
    *,
    patient_ref: str = PATIENT,
    status: ClinicalContextStatus = ClinicalContextStatus.ACTIVE,
) -> CareTrustClinicalContext:
    return CareTrustClinicalContext(
        schema_version="caretrust.clinical-context.v1",
        context_id=f"context:clinical:{suffix}",
        relationship_claim_id=f"claim:relationship:{suffix}",
        delegation_grant_id=f"grant:delegation:{suffix}",
        delegation_decision_id=f"decision:delegation:{suffix}",
        patient_ref=patient_ref,
        caregiver_ref=CAREGIVER,
        status=status,
        allowed_data_holders=(DATA_HOLDER,),
        allowed_purposes=("care_coordination",),
        allowed_fhir_resource_types=("CarePlan",),
        allowed_scopes=("patient/CarePlan.rs",),
        valid_from=date(2026, 7, 1),
        valid_until=date(2026, 12, 31),
        verified_at=NOW,
        revoked_at=NOW if status is ClinicalContextStatus.REVOKED else None,
        caretrust_role="delegation_and_trust_context_only",
        patient_match_authority="data_holder",
        disclosure_policy_authority="data_holder",
        legal_authority_status="not_established",
        synthetic=True,
    )


def request(
    suffix: str,
    caretrust_context: CareTrustClinicalContext,
    *,
    resource_types: tuple[str, ...] = ("CarePlan",),
    scopes: tuple[str, ...] = ("patient/CarePlan.rs",),
    prior_request_id: str | None = None,
    participant_org_ref: str = PARTICIPANT,
    authorized_user_ref: str = AUTHORIZED_USER,
    client_id: str = REGISTERED_CLIENT,
) -> ClinicalDataAuthorizationRequest:
    return ClinicalDataAuthorizationRequest(
        schema_version="caretrust.clinical-data-authorization-request.v1",
        request_id=f"request:clinical:{suffix}",
        data_holder_id=DATA_HOLDER,
        participant_org_ref=participant_org_ref,
        authorized_user_ref=authorized_user_ref,
        client_id=client_id,
        requesting_actor_role="authorized_participant_user",
        clinical_data_recipient="authorized_participant_application",
        caregiver_ref=caretrust_context.caregiver_ref,
        caregiver_is_requesting_actor=False,
        patient_match_hint=caretrust_context.patient_ref,
        purpose="care_coordination",
        requested_fhir_resource_types=resource_types,
        requested_scopes=scopes,
        caretrust_context=caretrust_context,
        prior_request_id=prior_request_id,
        requested_at=NOW,
        patient_match_requested=True,
        final_disclosure_decision_requested=True,
        synthetic=True,
    )


def bundle() -> SyntheticFhirR4Bundle:
    return SyntheticFhirR4Bundle(
        resourceType="Bundle",
        id="synthetic-care-plan-bundle-001",
        meta=FhirMeta(
            tag=(
                FhirCoding(
                    system=(
                        "https://caretrust.example/fhir/"
                        "CodeSystem/data-classification"
                    ),
                    code="synthetic",
                    display="Synthetic test data",
                ),
            )
        ),
        type="collection",
        timestamp=NOW,
        entry=(
            SyntheticFhirR4BundleEntry(
                fullUrl=(
                    "https://ehr.synthetic.invalid/fhir/"
                    "CarePlan/synthetic-care-plan-001"
                ),
                resource=SyntheticFhirR4CarePlan(
                    resourceType="CarePlan",
                    id="synthetic-care-plan-001",
                    status="active",
                    intent="plan",
                    subject=FhirReference(reference=LOCAL_PATIENT),
                    title="Synthetic caregiver visit instructions",
                    description=(
                        "Synthetic follow-up instructions for contract testing; "
                        "not a real clinical record."
                    ),
                ),
            ),
        ),
    )


def build_examples() -> dict[str, ClinicalDataExchangeRecord]:
    adapter = SyntheticClinicalDataHolderAdapter(
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
    )
    permit = request("permit-001", context("permit-001"))
    no_match = request(
        "no-match-001",
        context("no-match-001", patient_ref="patient:synthetic-no-match"),
    )
    insufficient = request(
        "insufficient-scope-001",
        context("insufficient-scope-001"),
        resource_types=("Observation",),
        scopes=("patient/Observation.rs",),
    )
    revoked = request(
        "revoked-fresh-001",
        context("revoked-fresh-001", status=ClinicalContextStatus.REVOKED),
        prior_request_id=permit.request_id,
    )
    unregistered_client = request(
        "unregistered-client-001",
        context("unregistered-client-001"),
        client_id="https://unregistered-care-app.synthetic.invalid",
    )
    return {
        "permit.json": adapter.decide(permit, now=NOW),
        "deny-unregistered-client.json": adapter.decide(
            unregistered_client,
            now=NOW,
        ),
        "deny-no-patient-match.json": adapter.decide(no_match, now=NOW),
        "deny-insufficient-scope.json": adapter.decide(insufficient, now=NOW),
        "deny-revoked-fresh-request.json": adapter.decide(revoked, now=NOW),
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, record in build_examples().items():
        output = OUTPUT / filename
        output.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
