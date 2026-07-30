"""Bounded synthetic projection of one CareTrust claim into FHIR R4-shaped JSON.

This module implements a local prototype profile. Its validator checks the
declared projection contract; it is not a replacement for the official HL7
FHIR validator and does not establish FHIR conformance.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from caretrust.models import ActiveCredentialClaim, ClaimStatus

FHIR_BASE = "https://synthetic.caretrust.example/fhir"
LOCAL_BASE = "https://caretrust.example/fhir"
SUBJECT_SYSTEM = f"{LOCAL_BASE}/identifier/synthetic-subject"
ISSUER_SYSTEM = f"{LOCAL_BASE}/identifier/synthetic-issuer"
REGISTRY_SYSTEM = f"{LOCAL_BASE}/identifier/hawaii-cna-registry-synthetic"
CLAIM_SYSTEM = f"{LOCAL_BASE}/identifier/caretrust-claim"
EVIDENCE_SYSTEM = f"{LOCAL_BASE}/identifier/caretrust-evidence"
QUALIFICATION_CODE_SYSTEM = f"{LOCAL_BASE}/CodeSystem/caregiver-credential-type"
PROVENANCE_CODE_SYSTEM = f"{LOCAL_BASE}/CodeSystem/projection-activity"
AGENT_CODE_SYSTEM = f"{LOCAL_BASE}/CodeSystem/provenance-agent-role"
STATUS_EXTENSION_URL = (
    f"{LOCAL_BASE}/StructureDefinition/caretrust-qualification-status"
)
JURISDICTION_EXTENSION_URL = (
    f"{LOCAL_BASE}/StructureDefinition/caretrust-qualification-jurisdiction"
)

_FHIR_ID = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")
_SYNTHETIC_MARKER = re.compile(r"(?:synthetic|(?:^|[-:_])syn(?:[-:_]|$))", re.I)


class FHIRProjectionError(ValueError):
    """A deterministic projection or local-profile validation failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FHIRProjectionError(message)


def _require_synthetic(value: str, field: str) -> None:
    _require(
        bool(value and _SYNTHETIC_MARKER.search(value)),
        f"{field} must be explicitly synthetic",
    )


def _parse_date(value: object, field: str) -> date:
    _require(
        isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None,
        f"{field} must be a full FHIR date in YYYY-MM-DD form",
    )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise FHIRProjectionError(f"{field} is not a valid calendar date") from exc


def _parse_instant(value: object, field: str) -> datetime:
    _require(isinstance(value, str), f"{field} must be an instant string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FHIRProjectionError(f"{field} is not a valid FHIR instant") from exc
    _require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        f"{field} must include a timezone",
    )
    return parsed


def _stable_id(kind: str, source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
    value = f"ct-{kind}-{digest}"
    _require(bool(_FHIR_ID.fullmatch(value)), f"generated {kind} id is invalid")
    return value


def _instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _entry(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullUrl": f"{FHIR_BASE}/{resource['resourceType']}/{resource['id']}",
        "resource": resource,
    }


def project_active_claim_to_fhir_r4(
    claim: ActiveCredentialClaim,
) -> dict[str, Any]:
    """Project one active, synthetic Hawaii CNA claim into a collection Bundle."""

    _require(claim.status is ClaimStatus.ACTIVE, "only active claims may be projected")
    _require(claim.revoked_at is None, "an active projected claim cannot be revoked")
    _require(claim.valid_from is not None, "valid_from is required by this profile")
    _require(bool(claim.evidence_refs), "at least one evidence reference is required")
    for field, value in (
        ("claim_id", claim.claim_id),
        ("subject_ref", claim.subject_ref),
        ("issuer_ref", claim.issuer_ref),
        ("registry_id", claim.registry_id),
    ):
        _require_synthetic(value, field)
    for evidence_ref in claim.evidence_refs:
        _require_synthetic(evidence_ref, "evidence_ref")

    valid_from = _parse_date(claim.valid_from, "claim.valid_from")
    valid_until = _parse_date(claim.valid_until, "claim.valid_until")
    _require(valid_until >= valid_from, "valid_until must not precede valid_from")
    practitioner_id = _stable_id("practitioner", claim.subject_ref)
    organization_id = _stable_id("organization", claim.issuer_ref)
    provenance_id = _stable_id("provenance", claim.claim_id)
    bundle_id = _stable_id("bundle", claim.claim_id)
    practitioner_ref = f"Practitioner/{practitioner_id}"
    organization_ref = f"Organization/{organization_id}"

    practitioner = {
        "resourceType": "Practitioner",
        "id": practitioner_id,
        "identifier": [{"system": SUBJECT_SYSTEM, "value": claim.subject_ref}],
        "active": True,
        "qualification": [
            {
                "extension": [
                    {"url": STATUS_EXTENSION_URL, "valueCode": "active"},
                    {
                        "url": JURISDICTION_EXTENSION_URL,
                        "valueCode": claim.jurisdiction,
                    },
                ],
                "identifier": [
                    {"system": REGISTRY_SYSTEM, "value": claim.registry_id}
                ],
                "code": {
                    "coding": [
                        {
                            "system": QUALIFICATION_CODE_SYSTEM,
                            "code": "hawaii-cna",
                            "display": claim.credential_type,
                        }
                    ],
                    "text": claim.credential_type,
                },
                "period": {
                    "start": valid_from.isoformat(),
                    "end": valid_until.isoformat(),
                },
                "issuer": {"reference": organization_ref},
            }
        ],
    }
    organization = {
        "resourceType": "Organization",
        "id": organization_id,
        "identifier": [{"system": ISSUER_SYSTEM, "value": claim.issuer_ref}],
        "active": True,
        "name": "Synthetic CareTrust credential issuer",
    }
    provenance = {
        "resourceType": "Provenance",
        "id": provenance_id,
        "target": [{"reference": practitioner_ref}],
        "occurredDateTime": _instant(claim.issued_at),
        "recorded": _instant(claim.issued_at),
        "activity": {
            "coding": [
                {
                    "system": PROVENANCE_CODE_SYSTEM,
                    "code": "caretrust-claim-projection",
                    "display": "CareTrust claim projected to synthetic FHIR R4",
                }
            ]
        },
        "agent": [
            {
                "type": {
                    "coding": [
                        {
                            "system": AGENT_CODE_SYSTEM,
                            "code": "projecting-issuer",
                            "display": "Synthetic projecting issuer",
                        }
                    ]
                },
                "who": {"reference": organization_ref},
            }
        ],
        "entity": [
            {
                "role": "source",
                "what": {
                    "identifier": {
                        "system": CLAIM_SYSTEM,
                        "value": claim.claim_id,
                    }
                },
            },
            *[
                {
                    "role": "source",
                    "what": {
                        "identifier": {
                            "system": EVIDENCE_SYSTEM,
                            "value": evidence_ref,
                        }
                    },
                }
                for evidence_ref in claim.evidence_refs
            ],
        ],
    }
    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "identifier": {"system": CLAIM_SYSTEM, "value": claim.claim_id},
        "type": "collection",
        "timestamp": _instant(claim.issued_at),
        "entry": [
            _entry(practitioner),
            _entry(organization),
            _entry(provenance),
        ],
    }
    validate_fhir_r4_projection(bundle)
    return bundle


def _one_resource(
    resources: Mapping[str, list[Mapping[str, Any]]],
    resource_type: str,
) -> Mapping[str, Any]:
    values = resources.get(resource_type, [])
    _require(len(values) == 1, f"bundle must contain exactly one {resource_type}")
    return values[0]


def _identifier(
    value: object,
    *,
    system: str,
    field: str,
) -> str:
    _require(isinstance(value, Mapping), f"{field} must be an Identifier")
    _require(value.get("system") == system, f"{field}.system is not permitted")
    identifier_value = value.get("value")
    _require(isinstance(identifier_value, str), f"{field}.value must be a string")
    _require_synthetic(identifier_value, f"{field}.value")
    return identifier_value


def _local_coding(
    value: object,
    *,
    system: str,
    code: str,
    field: str,
) -> None:
    _require(isinstance(value, Mapping), f"{field} must be a CodeableConcept")
    coding = value.get("coding")
    _require(
        isinstance(coding, list) and len(coding) == 1,
        f"{field}.coding must contain exactly one local coding",
    )
    item = coding[0]
    _require(isinstance(item, Mapping), f"{field}.coding[0] must be an object")
    _require(item.get("system") == system, f"{field} coding system is not permitted")
    _require(item.get("code") == code, f"{field} coding code is not permitted")
    _require(
        isinstance(item.get("display"), str) and bool(item["display"]),
        f"{field} coding display is required",
    )


def validate_fhir_r4_projection(
    bundle: Mapping[str, Any],
    *,
    expected_claim: ActiveCredentialClaim | None = None,
) -> None:
    """Validate this local projection profile without claiming R4 conformance."""

    _require(bundle.get("resourceType") == "Bundle", "resourceType must be Bundle")
    _require(bundle.get("type") == "collection", "Bundle.type must be collection")
    bundle_id = bundle.get("id")
    _require(
        isinstance(bundle_id, str) and _FHIR_ID.fullmatch(bundle_id) is not None,
        "Bundle.id is invalid",
    )
    bundle_timestamp = _parse_instant(bundle.get("timestamp"), "Bundle.timestamp")
    claim_id = _identifier(
        bundle.get("identifier"),
        system=CLAIM_SYSTEM,
        field="Bundle.identifier",
    )

    entries = bundle.get("entry")
    _require(
        isinstance(entries, list) and len(entries) == 3,
        "Bundle.entry must contain exactly three resources",
    )
    resources: dict[str, list[Mapping[str, Any]]] = {}
    full_urls: set[str] = set()
    for index, entry in enumerate(entries):
        _require(isinstance(entry, Mapping), f"Bundle.entry[{index}] must be an object")
        _require(
            not {"request", "response", "search"}.intersection(entry),
            "collection entries cannot contain request, response, or search",
        )
        resource = entry.get("resource")
        _require(
            isinstance(resource, Mapping),
            f"Bundle.entry[{index}].resource is required",
        )
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        _require(
            resource_type in {"Practitioner", "Organization", "Provenance"},
            f"Bundle.entry[{index}] has an unsupported resourceType",
        )
        _require(
            isinstance(resource_id, str) and _FHIR_ID.fullmatch(resource_id) is not None,
            f"{resource_type}.id is invalid",
        )
        expected_full_url = f"{FHIR_BASE}/{resource_type}/{resource_id}"
        _require(
            entry.get("fullUrl") == expected_full_url,
            f"{resource_type} fullUrl does not bind to its id",
        )
        _require(expected_full_url not in full_urls, "Bundle.fullUrl values must be unique")
        full_urls.add(expected_full_url)
        resources.setdefault(str(resource_type), []).append(resource)

    practitioner = _one_resource(resources, "Practitioner")
    organization = _one_resource(resources, "Organization")
    provenance = _one_resource(resources, "Provenance")
    practitioner_ref = f"Practitioner/{practitioner['id']}"
    organization_ref = f"Organization/{organization['id']}"

    _require(practitioner.get("active") is True, "Practitioner.active must be true")
    practitioner_identifiers = practitioner.get("identifier")
    _require(
        isinstance(practitioner_identifiers, list)
        and len(practitioner_identifiers) == 1,
        "Practitioner.identifier must contain one synthetic subject identifier",
    )
    subject_ref = _identifier(
        practitioner_identifiers[0],
        system=SUBJECT_SYSTEM,
        field="Practitioner.identifier[0]",
    )
    qualifications = practitioner.get("qualification")
    _require(
        isinstance(qualifications, list) and len(qualifications) == 1,
        "Practitioner.qualification must contain exactly one qualification",
    )
    qualification = qualifications[0]
    _require(
        isinstance(qualification, Mapping),
        "Practitioner.qualification[0] must be an object",
    )
    qualification_identifiers = qualification.get("identifier")
    _require(
        isinstance(qualification_identifiers, list)
        and len(qualification_identifiers) == 1,
        "qualification.identifier must contain one registry identifier",
    )
    _identifier(
        qualification_identifiers[0],
        system=REGISTRY_SYSTEM,
        field="qualification.identifier[0]",
    )
    _local_coding(
        qualification.get("code"),
        system=QUALIFICATION_CODE_SYSTEM,
        code="hawaii-cna",
        field="qualification.code",
    )
    period = qualification.get("period")
    _require(isinstance(period, Mapping), "qualification.period is required")
    start = _parse_date(period.get("start"), "qualification.period.start")
    end = _parse_date(period.get("end"), "qualification.period.end")
    _require(end >= start, "qualification.period.end must not precede start")
    _require(
        qualification.get("issuer") == {"reference": organization_ref},
        "qualification.issuer must reference the bundled Organization",
    )
    extensions = qualification.get("extension")
    _require(
        isinstance(extensions, list) and len(extensions) == 2,
        "qualification must carry status and jurisdiction extensions",
    )
    extension_map = {
        item.get("url"): item.get("valueCode")
        for item in extensions
        if isinstance(item, Mapping)
    }
    _require(
        extension_map.get(STATUS_EXTENSION_URL) == "active",
        "qualification status must be active",
    )
    _require(
        extension_map.get(JURISDICTION_EXTENSION_URL) == "HI",
        "qualification jurisdiction must be HI",
    )

    _require(organization.get("active") is True, "Organization.active must be true")
    _require(
        isinstance(organization.get("name"), str) and bool(organization["name"]),
        "Organization.name is required",
    )
    organization_identifiers = organization.get("identifier")
    _require(
        isinstance(organization_identifiers, list)
        and len(organization_identifiers) == 1,
        "Organization.identifier must contain one issuer identifier",
    )
    issuer_ref = _identifier(
        organization_identifiers[0],
        system=ISSUER_SYSTEM,
        field="Organization.identifier[0]",
    )
    _require(
        bundle_id == _stable_id("bundle", claim_id),
        "Bundle.id must be deterministically derived from the claim identifier",
    )
    _require(
        practitioner["id"] == _stable_id("practitioner", subject_ref),
        "Practitioner.id must be deterministically derived from its subject identifier",
    )
    _require(
        organization["id"] == _stable_id("organization", issuer_ref),
        "Organization.id must be deterministically derived from its issuer identifier",
    )
    _require(
        provenance["id"] == _stable_id("provenance", claim_id),
        "Provenance.id must be deterministically derived from the claim identifier",
    )

    _require(
        provenance.get("target") == [{"reference": practitioner_ref}],
        "Provenance.target must reference the bundled Practitioner",
    )
    recorded = _parse_instant(provenance.get("recorded"), "Provenance.recorded")
    occurred = _parse_instant(
        provenance.get("occurredDateTime"),
        "Provenance.occurredDateTime",
    )
    _require(recorded == occurred, "Provenance recorded and occurred times must match")
    _require(
        bundle_timestamp == recorded,
        "Bundle.timestamp must match Provenance.recorded",
    )
    _local_coding(
        provenance.get("activity"),
        system=PROVENANCE_CODE_SYSTEM,
        code="caretrust-claim-projection",
        field="Provenance.activity",
    )
    agents = provenance.get("agent")
    _require(
        isinstance(agents, list) and len(agents) == 1,
        "Provenance.agent must contain exactly one projecting issuer",
    )
    agent = agents[0]
    _require(isinstance(agent, Mapping), "Provenance.agent[0] must be an object")
    _local_coding(
        agent.get("type"),
        system=AGENT_CODE_SYSTEM,
        code="projecting-issuer",
        field="Provenance.agent[0].type",
    )
    _require(
        agent.get("who") == {"reference": organization_ref},
        "Provenance.agent.who must reference the bundled Organization",
    )
    entities = provenance.get("entity")
    _require(
        isinstance(entities, list) and len(entities) >= 2,
        "Provenance.entity must retain claim and evidence sources",
    )
    entity_identifiers: list[tuple[str, str]] = []
    for index, entity in enumerate(entities):
        _require(
            isinstance(entity, Mapping) and entity.get("role") == "source",
            f"Provenance.entity[{index}] must have role source",
        )
        what = entity.get("what")
        _require(
            isinstance(what, Mapping),
            f"Provenance.entity[{index}].what is required",
        )
        identifier = what.get("identifier")
        _require(
            isinstance(identifier, Mapping),
            f"Provenance.entity[{index}].what.identifier is required",
        )
        system = identifier.get("system")
        _require(
            system in {CLAIM_SYSTEM, EVIDENCE_SYSTEM},
            f"Provenance.entity[{index}] uses an unsupported identifier system",
        )
        identifier_value = _identifier(
            identifier,
            system=str(system),
            field=f"Provenance.entity[{index}].what.identifier",
        )
        entity_identifiers.append((str(system), identifier_value))
    _require(
        entity_identifiers.count((CLAIM_SYSTEM, claim_id)) == 1
        and sum(
            system == EVIDENCE_SYSTEM for system, _ in entity_identifiers
        )
        >= 1,
        "Provenance.entity must contain one claim and at least one evidence source",
    )

    if expected_claim is not None:
        expected = project_active_claim_to_fhir_r4(expected_claim)
        _require(
            dict(bundle) == expected,
            "bundle does not exactly match the expected CareTrust claim projection",
        )
