from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from caretrust.fhir_projection import (
    CLAIM_SYSTEM,
    FHIRProjectionError,
    JURISDICTION_EXTENSION_URL,
    QUALIFICATION_CODE_SYSTEM,
    STATUS_EXTENSION_URL,
    project_active_claim_to_fhir_r4,
    validate_fhir_r4_projection,
)
from caretrust.models import ActiveCredentialClaim, ClaimStatus

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = (
    ROOT
    / "docs"
    / "standards"
    / "examples"
    / "fhir"
    / "synthetic-hawaii-cna-bundle.json"
)


def claim(**updates: object) -> ActiveCredentialClaim:
    values = {
        "schema_version": "caretrust.active-credential-claim.v1",
        "claim_id": "claim:synthetic-hi-cna-1001",
        "claim_type": "professional_credential",
        "credential_profile": "hawaii_cna_smoke_v1",
        "subject_ref": "person:synthetic-leilani-kealoha",
        "issuer_ref": "org:synthetic-caretrust-demo",
        "jurisdiction": "HI",
        "registry_id": "HI-CNA-SYN-1001",
        "credential_type": "Certified Nurse Aide",
        "valid_from": "2024-04-15",
        "valid_until": "2028-04-15",
        "status": ClaimStatus.ACTIVE,
        "allowed_audiences": ("org:synthetic-care-provider",),
        "allowed_purposes": ("credentialing",),
        "evidence_refs": ("artifact:synthetic-smoke-clean",),
        "review_id": "review:synthetic-smoke-clean",
        "registry_result_id": "registry:synthetic-smoke-clean",
        "issued_at": datetime(2026, 7, 29, 20, 0, tzinfo=UTC),
    }
    values.update(updates)
    return ActiveCredentialClaim(**values)


def resources(bundle: dict) -> dict[str, dict]:
    return {
        entry["resource"]["resourceType"]: entry["resource"]
        for entry in bundle["entry"]
    }


def test_projection_is_deterministic_bounded_and_matches_generated_example() -> None:
    source = claim()
    first = project_active_claim_to_fhir_r4(source)
    second = project_active_claim_to_fhir_r4(source)

    assert first == second
    validate_fhir_r4_projection(first, expected_claim=source)
    assert json.loads(EXAMPLE.read_text(encoding="utf-8")) == first

    projected = resources(first)
    practitioner = projected["Practitioner"]
    organization = projected["Organization"]
    provenance = projected["Provenance"]
    qualification = practitioner["qualification"][0]
    assert first["resourceType"] == "Bundle"
    assert first["type"] == "collection"
    assert first["identifier"]["system"] == CLAIM_SYSTEM
    assert set(projected) == {"Practitioner", "Organization", "Provenance"}
    assert qualification["code"]["coding"] == [
        {
            "system": QUALIFICATION_CODE_SYSTEM,
            "code": "hawaii-cna",
            "display": "Certified Nurse Aide",
        }
    ]
    assert qualification["period"] == {
        "start": "2024-04-15",
        "end": "2028-04-15",
    }
    assert qualification["issuer"] == {
        "reference": f"Organization/{organization['id']}"
    }
    assert {item["url"]: item["valueCode"] for item in qualification["extension"]} == {
        STATUS_EXTENSION_URL: "active",
        JURISDICTION_EXTENSION_URL: "HI",
    }
    assert provenance["target"] == [
        {"reference": f"Practitioner/{practitioner['id']}"}
    ]
    assert provenance["agent"][0]["who"] == {
        "reference": f"Organization/{organization['id']}"
    }
    assert [item["role"] for item in provenance["entity"]] == ["source", "source"]


@pytest.mark.parametrize(
    "updates",
    [
        {"status": ClaimStatus.REVOKED, "revoked_at": datetime(2026, 7, 30, tzinfo=UTC)},
        {"valid_from": None},
        {"valid_from": "04/15/2024"},
        {"valid_until": "2024-02-30"},
        {"valid_from": "2028-04-16", "valid_until": "2028-04-15"},
        {"registry_id": "12345"},
        {"evidence_refs": ()},
    ],
)
def test_projection_rejects_invalid_status_dates_or_nonsynthetic_input(
    updates: dict[str, object],
) -> None:
    with pytest.raises(FHIRProjectionError):
        project_active_claim_to_fhir_r4(claim(**updates))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(resourceType="Document"),
        lambda value: value["entry"][0]["resource"].update(id="invalid/id"),
        lambda value: value["entry"][0]["resource"].update(qualification=[]),
        lambda value: value["entry"][0]["resource"]["qualification"][0]["code"][
            "coding"
        ][0].update(system="http://example.invalid/proprietary"),
        lambda value: value["entry"][0]["resource"]["qualification"][0]["period"].update(
            end="not-a-date"
        ),
        lambda value: value["entry"][0]["resource"]["qualification"][0].update(
            issuer={"reference": "Organization/wrong"}
        ),
        lambda value: value["entry"][0]["resource"]["qualification"][0]["extension"][
            0
        ].update(valueCode="revoked"),
        lambda value: value["entry"][2]["resource"].update(
            target=[{"reference": "Practitioner/wrong"}]
        ),
        lambda value: value["entry"][2]["resource"]["agent"][0].update(
            who={"reference": "Organization/wrong"}
        ),
        lambda value: value["entry"][2]["resource"].update(entity=[]),
        lambda value: value.update(timestamp="2026-07-30T20:00:00Z"),
        lambda value: value["entry"][2]["resource"]["entity"][0]["what"][
            "identifier"
        ].update(value="claim:synthetic-different"),
    ],
)
def test_local_validator_rejects_broken_r4_projection_links(
    mutation,
) -> None:
    bundle = copy.deepcopy(project_active_claim_to_fhir_r4(claim()))
    mutation(bundle)

    with pytest.raises(FHIRProjectionError):
        validate_fhir_r4_projection(bundle)
