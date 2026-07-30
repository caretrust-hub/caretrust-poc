from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from caretrust.federation import (
    ENTITY_STATEMENT_TYPE,
    FederationErrorCode,
    FederationSigningKey,
    FederationTrustError,
    LocalTrustAnchor,
    LocalTrustStore,
    SyntheticFederationEntity,
    decode_entity_statement_unverified,
    issue_entity_configuration,
    issue_subordinate_statement,
    resolve_trust_chain,
)

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
ANCHOR_ID = "https://trust.synthetic.invalid"
ORG_A_ID = "https://care-a.synthetic.invalid"
ORG_B_ID = "https://care-b.synthetic.invalid"
EXAMPLE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "standards"
    / "examples"
    / "federation"
    / "two-care-organizations.json"
)


def _entity(
    entity_id: str,
    *,
    key: FederationSigningKey,
    role: str,
    authority_hints: tuple[str, ...] = (),
    extra_keys: tuple[FederationSigningKey, ...] = (),
) -> SyntheticFederationEntity:
    return SyntheticFederationEntity(
        entity_id=entity_id,
        signing_keys=(key, *extra_keys),
        active_kid=key.kid,
        authority_hints=authority_hints,
        metadata={
            "caretrust_care_organization": {
                "display_name": f"Synthetic {role}",
                "role": role,
                "synthetic": True,
            }
        },
    )


@pytest.fixture
def synthetic_federation() -> tuple[
    SyntheticFederationEntity,
    SyntheticFederationEntity,
    SyntheticFederationEntity,
    LocalTrustStore,
]:
    anchor = _entity(
        ANCHOR_ID,
        key=FederationSigningKey.generate(kid="anchor-2026-01"),
        role="local-trust-anchor",
    )
    org_a = _entity(
        ORG_A_ID,
        key=FederationSigningKey.generate(kid="care-a-2026-01"),
        role="credential-issuer",
        authority_hints=(ANCHOR_ID,),
    )
    org_b = _entity(
        ORG_B_ID,
        key=FederationSigningKey.generate(kid="care-b-2026-01"),
        role="care-application",
        authority_hints=(ANCHOR_ID,),
    )
    trust_store = LocalTrustStore(
        anchors=(LocalTrustAnchor(entity_id=ANCHOR_ID, jwks=anchor.jwks),)
    )
    return anchor, org_a, org_b, trust_store


def test_two_synthetic_care_organizations_resolve_to_local_anchor(
    synthetic_federation: tuple[
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        LocalTrustStore,
    ],
) -> None:
    anchor, org_a, org_b, trust_store = synthetic_federation
    chains = []
    for entity in (org_a, org_b):
        configuration = issue_entity_configuration(entity, issued_at=NOW)
        subordinate = issue_subordinate_statement(
            anchor, entity, issued_at=NOW
        )
        header, claims = decode_entity_statement_unverified(configuration)
        assert header == {
            "alg": "EdDSA",
            "kid": entity.active_kid,
            "typ": ENTITY_STATEMENT_TYPE,
        }
        assert claims["iss"] == claims["sub"] == entity.entity_id
        assert claims["authority_hints"] == [ANCHOR_ID]
        assert claims["jwks"] == entity.jwks

        first = resolve_trust_chain(
            entity_configuration=configuration,
            subordinate_statement=subordinate,
            trust_store=trust_store,
            now=NOW + timedelta(seconds=1),
        )
        second = resolve_trust_chain(
            entity_configuration=configuration,
            subordinate_statement=subordinate,
            trust_store=trust_store,
            now=NOW + timedelta(seconds=1),
        )
        assert first == second
        assert first.trust_anchor_id == ANCHOR_ID
        assert first.leaf_entity_id == entity.entity_id
        assert first.metadata == entity.metadata
        assert first.synthetic is True
        chains.append(first)

    assert chains[0].chain_sha256 != chains[1].chain_sha256


def test_leaf_rotation_requires_fresh_anchor_statement(
    synthetic_federation: tuple[
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        LocalTrustStore,
    ],
) -> None:
    anchor, old_entity, _, trust_store = synthetic_federation
    stale_subordinate = issue_subordinate_statement(
        anchor, old_entity, issued_at=NOW
    )
    new_key = FederationSigningKey.generate(kid="care-a-2026-02")
    rotated = SyntheticFederationEntity(
        entity_id=old_entity.entity_id,
        signing_keys=(*old_entity.signing_keys, new_key),
        active_kid=new_key.kid,
        authority_hints=old_entity.authority_hints,
        metadata=old_entity.metadata,
    )
    rotated_configuration = issue_entity_configuration(rotated, issued_at=NOW)
    fresh_subordinate = issue_subordinate_statement(
        anchor, rotated, issued_at=NOW
    )

    resolved = resolve_trust_chain(
        entity_configuration=rotated_configuration,
        subordinate_statement=fresh_subordinate,
        trust_store=trust_store,
        now=NOW + timedelta(seconds=1),
    )
    assert [key["kid"] for key in resolved.leaf_jwks["keys"]] == [
        "care-a-2026-01",
        "care-a-2026-02",
    ]

    with pytest.raises(FederationTrustError) as caught:
        resolve_trust_chain(
            entity_configuration=rotated_configuration,
            subordinate_statement=stale_subordinate,
            trust_store=trust_store,
            now=NOW + timedelta(seconds=1),
        )
    assert caught.value.code is FederationErrorCode.JWKS_MISMATCH


def test_anchor_rotation_requires_updated_local_trust(
    synthetic_federation: tuple[
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        LocalTrustStore,
    ],
) -> None:
    old_anchor, org_a, _, _ = synthetic_federation
    new_key = FederationSigningKey.generate(kid="anchor-2026-02")
    rotated_anchor = SyntheticFederationEntity(
        entity_id=old_anchor.entity_id,
        signing_keys=(*old_anchor.signing_keys, new_key),
        active_kid=new_key.kid,
        metadata=old_anchor.metadata,
    )
    configuration = issue_entity_configuration(org_a, issued_at=NOW)
    subordinate = issue_subordinate_statement(
        rotated_anchor, org_a, issued_at=NOW
    )
    updated_store = LocalTrustStore(
        anchors=(
            LocalTrustAnchor(entity_id=ANCHOR_ID, jwks=rotated_anchor.jwks),
        )
    )
    resolve_trust_chain(
        entity_configuration=configuration,
        subordinate_statement=subordinate,
        trust_store=updated_store,
        now=NOW + timedelta(seconds=1),
    )

    old_store = LocalTrustStore(
        anchors=(LocalTrustAnchor(entity_id=ANCHOR_ID, jwks=old_anchor.jwks),)
    )
    with pytest.raises(FederationTrustError) as caught:
        resolve_trust_chain(
            entity_configuration=configuration,
            subordinate_statement=subordinate,
            trust_store=old_store,
            now=NOW + timedelta(seconds=1),
        )
    assert caught.value.code is FederationErrorCode.UNKNOWN_KEY


def test_missing_trust_anchor_fails_closed(
    synthetic_federation: tuple[
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        LocalTrustStore,
    ],
) -> None:
    anchor, org_a, _, _ = synthetic_federation
    with pytest.raises(FederationTrustError) as caught:
        resolve_trust_chain(
            entity_configuration=issue_entity_configuration(org_a, issued_at=NOW),
            subordinate_statement=issue_subordinate_statement(
                anchor, org_a, issued_at=NOW
            ),
            trust_store=LocalTrustStore(anchors=()),
            now=NOW + timedelta(seconds=1),
        )
    assert caught.value.code is FederationErrorCode.MISSING_TRUST_ANCHOR


def _tamper_payload(token: str) -> str:
    header, payload, signature = token.split(".")
    decoded = json.loads(
        base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    )
    decoded["metadata"]["caretrust_care_organization"]["role"] = "tampered"
    changed = base64.urlsafe_b64encode(
        json.dumps(decoded, separators=(",", ":"), sort_keys=True).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{changed}.{signature}"


def test_tampered_statement_is_rejected(
    synthetic_federation: tuple[
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        LocalTrustStore,
    ],
) -> None:
    anchor, org_a, _, trust_store = synthetic_federation
    with pytest.raises(FederationTrustError) as caught:
        resolve_trust_chain(
            entity_configuration=issue_entity_configuration(org_a, issued_at=NOW),
            subordinate_statement=_tamper_payload(
                issue_subordinate_statement(anchor, org_a, issued_at=NOW)
            ),
            trust_store=trust_store,
            now=NOW + timedelta(seconds=1),
        )
    assert caught.value.code is FederationErrorCode.SIGNATURE_INVALID


@pytest.mark.parametrize("expire_configuration", [True, False])
def test_expired_statement_is_rejected(
    synthetic_federation: tuple[
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        SyntheticFederationEntity,
        LocalTrustStore,
    ],
    expire_configuration: bool,
) -> None:
    anchor, org_a, _, trust_store = synthetic_federation
    short = timedelta(seconds=30)
    configuration = issue_entity_configuration(
        org_a,
        issued_at=NOW,
        lifetime=short if expire_configuration else timedelta(minutes=5),
    )
    subordinate = issue_subordinate_statement(
        anchor,
        org_a,
        issued_at=NOW,
        lifetime=timedelta(minutes=5) if expire_configuration else short,
    )
    with pytest.raises(FederationTrustError) as caught:
        resolve_trust_chain(
            entity_configuration=configuration,
            subordinate_statement=subordinate,
            trust_store=trust_store,
            now=NOW + timedelta(seconds=31),
        )
    assert caught.value.code is FederationErrorCode.EXPIRED


def test_checked_in_machine_example_resolves_offline() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert example["profile"] == "caretrust.synthetic-federation.v1"
    assert example["synthetic_only"] is True
    assert example["network_calls"] is False
    assert example["private_key_material_in_artifact"] is False
    assert '"d"' not in EXAMPLE.read_text(encoding="utf-8")
    trust_store = LocalTrustStore(
        anchors=(
            LocalTrustAnchor(
                entity_id=example["trust_anchor"]["entity_id"],
                jwks=example["trust_anchor"]["jwks"],
            ),
        )
    )
    resolved_ids = []
    for entity in example["care_organizations"]:
        resolved = resolve_trust_chain(
            entity_configuration=entity["entity_configuration_jwt"],
            subordinate_statement=entity["subordinate_statement_jwt"],
            trust_store=trust_store,
            now=NOW + timedelta(seconds=1),
        )
        assert resolved.chain_sha256 == entity["expected_chain_sha256"]
        resolved_ids.append(resolved.leaf_entity_id)
    assert resolved_ids == [ORG_A_ID, ORG_B_ID]
