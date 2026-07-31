"""Executable offline two-hub federation laboratory for synthetic CareTrust data.

This local lab resolves entity metadata only.  It deliberately invokes the
existing CareTrust case policy afterwards to demonstrate that federation trust
does not grant caregiver access by itself.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import base64
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from caretrust.case_bundle import build_synthetic_case_bundle, evaluate_case_permission
from caretrust.federation import (
    FederationErrorCode,
    FederationSigningKey,
    FederationTrustError,
    LocalTrustAnchor,
    LocalTrustStore,
    SyntheticFederationEntity,
    issue_entity_configuration,
    issue_subordinate_statement,
    resolve_trust_chain,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "federation" / "two-hub-lab.json"
LAB_PROFILE = "caretrust.synthetic-two-hub-federation-lab.v1"
LAB_NOW = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)


def _load_fixture() -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture.get("profile") != LAB_PROFILE or fixture.get("synthetic_only") is not True:
        raise ValueError("invalid synthetic two-hub federation fixture")
    hubs = fixture.get("hubs")
    if not isinstance(hubs, list) or len(hubs) != 2:
        raise ValueError("two independent hub configurations are required")
    return fixture


def _entity(config: dict[str, Any], *, anchor: bool) -> SyntheticFederationEntity:
    entity_id = config["trust_anchor_entity_id"] if anchor else config["leaf_entity_id"]
    kid = f"{config['hub_id'].replace(':', '-')}-{'anchor' if anchor else 'leaf'}-2026-01"
    return SyntheticFederationEntity(
        entity_id=entity_id,
        signing_keys=(_fixture_key(kid),),
        active_kid=kid,
        authority_hints=() if anchor else (config["trust_anchor_entity_id"],),
        metadata=(
            {"caretrust_federation_hub": {"hub_id": config["hub_id"], "synthetic": True}}
            if anchor
            else config["leaf_metadata"]
        ),
    )


def _fixture_key(kid: str) -> FederationSigningKey:
    """Derive a reproducible synthetic-only fixture key, never serialized.

    The derivation is intentionally not a production key-management design.
    It exists solely to make the public laboratory artifact reproducible while
    retaining no private material in that artifact.
    """

    seed = sha256(f"caretrust-synthetic-federation-lab|{kid}".encode("utf-8")).digest()
    return FederationSigningKey(kid=kid, private_key=Ed25519PrivateKey.from_private_bytes(seed))


def _tamper(token: str) -> str:
    header, payload, signature = token.split(".")
    decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    decoded["metadata"][next(iter(decoded["metadata"]))]["tampered"] = True
    changed = base64.urlsafe_b64encode(
        json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    return f"{header}.{changed}.{signature}"


def _fresh_local_caregiver_decision() -> dict[str, Any]:
    """Call the existing case evaluator after trust resolution, not through it."""

    bundle = build_synthetic_case_bundle()
    objects = bundle["canonical_objects"]
    request = next(
        item for item in objects["permission_requests"]
        if item["request_id"] == "request:case:family-permit-001"
    )
    decision = evaluate_case_permission(
        request,
        relationship_claim=objects["relationship_claim"],
        delegation_grant=objects["delegation_grant"],
        approved_items={item["approved_item_id"]: item for item in objects["approved_document_items"]},
        as_of=LAB_NOW,
    )
    return {
        key: decision[key]
        for key in (
            "decision_id", "request_id", "request_sha256", "policy_id", "policy_version",
            "decision", "reason_code", "as_of", "evidence_status",
        )
    } | {"case_id": bundle["case_id"], "case_bundle_sha256": bundle["bundle_sha256"]}


def _canonical_hash(value: Any) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _public_chain_view(chain: Any, *, entity_configuration: str, subordinate_statement: str, role: str) -> dict[str, Any]:
    return {
        "entity_id": chain.leaf_entity_id,
        "role": role,
        "trust_anchor_id": chain.trust_anchor_id,
        "chain_sha256": chain.chain_sha256,
        "entity_configuration_sha256": sha256(entity_configuration.encode("ascii")).hexdigest(),
        "subordinate_statement_sha256": sha256(subordinate_statement.encode("ascii")).hexdigest(),
        "public_jwks": chain.leaf_jwks,
        "metadata_after_policy": chain.metadata,
        "metadata_policy": chain.metadata_policy,
        "entity_trust_only": True,
    }


def build_two_hub_federation_lab(*, now: datetime = LAB_NOW) -> dict[str, Any]:
    """Resolve independently configured participant/client trust chains locally."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    fixture = _load_fixture()
    configs = fixture["hubs"]
    assert isinstance(configs, list)
    anchors = [_entity(config, anchor=True) for config in configs]
    leaves = [_entity(config, anchor=False) for config in configs]
    store = LocalTrustStore(
        anchors=tuple(LocalTrustAnchor(entity_id=anchor.entity_id, jwks=anchor.jwks) for anchor in anchors)
    )
    issued = now - timedelta(seconds=1)
    chains: list[dict[str, Any]] = []
    issued_pairs: list[tuple[str, str]] = []
    for config, anchor, leaf in zip(configs, anchors, leaves, strict=True):
        configuration = issue_entity_configuration(leaf, issued_at=issued)
        subordinate = issue_subordinate_statement(
            anchor, leaf, issued_at=issued, metadata_policy=config["metadata_policy"]
        )
        chain = resolve_trust_chain(
            entity_configuration=configuration,
            subordinate_statement=subordinate,
            trust_store=store,
            now=now,
        )
        chains.append(_public_chain_view(
            chain, entity_configuration=configuration, subordinate_statement=subordinate, role=config["leaf_role"]
        ))
        issued_pairs.append((configuration, subordinate))

    # Negative/transition exercises operate entirely on local in-memory objects.
    participant_anchor, client_anchor = anchors
    participant_leaf, client_leaf = leaves
    participant_config, participant_subordinate = issued_pairs[0]
    expiry_configuration = issue_entity_configuration(
        participant_leaf, issued_at=issued, lifetime=timedelta(seconds=1)
    )
    expiry_subordinate = issue_subordinate_statement(
        participant_anchor, participant_leaf, issued_at=issued, lifetime=timedelta(seconds=1)
    )

    def negative_code(operation: Any) -> str:
        try:
            operation()
        except FederationTrustError as exc:
            return exc.code.value
        raise AssertionError("federation negative exercise unexpectedly resolved")

    rotated_key = _fixture_key("hub-synthetic-pacific-client-leaf-2026-02")
    rotated_client = SyntheticFederationEntity(
        entity_id=client_leaf.entity_id,
        signing_keys=(*client_leaf.signing_keys, rotated_key),
        active_kid=rotated_key.kid,
        authority_hints=client_leaf.authority_hints,
        metadata=client_leaf.metadata,
    )
    rotated_configuration = issue_entity_configuration(rotated_client, issued_at=issued)
    stale_client_subordinate = issued_pairs[1][1]
    fresh_client_subordinate = issue_subordinate_statement(
        client_anchor, rotated_client, issued_at=issued, metadata_policy=configs[1]["metadata_policy"]
    )
    rotated_chain = resolve_trust_chain(
        entity_configuration=rotated_configuration,
        subordinate_statement=fresh_client_subordinate,
        trust_store=store,
        now=now,
    )

    negatives = {
        "expired_statement": negative_code(lambda: resolve_trust_chain(
            entity_configuration=expiry_configuration, subordinate_statement=expiry_subordinate,
            trust_store=store, now=now + timedelta(seconds=1),
        )),
        "tampered_statement": negative_code(lambda: resolve_trust_chain(
            entity_configuration=participant_config, subordinate_statement=_tamper(participant_subordinate),
            trust_store=store, now=now,
        )),
        "untrusted_anchor": negative_code(lambda: resolve_trust_chain(
            entity_configuration=participant_config, subordinate_statement=participant_subordinate,
            trust_store=LocalTrustStore(anchors=()), now=now,
        )),
        "stale_leaf_rollover": negative_code(lambda: resolve_trust_chain(
            entity_configuration=rotated_configuration, subordinate_statement=stale_client_subordinate,
            trust_store=store, now=now,
        )),
    }
    artifact = {
        "artifact_type": LAB_PROFILE,
        "evidence_status": "executed_local",
        "synthetic_only": True,
        "network_calls": False,
        "private_key_material_in_artifact": False,
        "two_independent_hubs": [
            {"hub_id": config["hub_id"], "trust_anchor_id": anchor.entity_id, "active_anchor_kid": anchor.active_kid}
            for config, anchor in zip(configs, anchors, strict=True)
        ],
        "participant_and_client_entity_trust": chains,
        "negative_exercises": negatives,
        "key_rollover": {
            "transition": "fresh_anchor_statement_required",
            "old_kids": [key.kid for key in client_leaf.signing_keys],
            "new_kids": [key["kid"] for key in rotated_chain.leaf_jwks["keys"]],
            "resolved_with_fresh_statement": True,
        },
        "fresh_local_caregiver_decision_after_trust": _fresh_local_caregiver_decision(),
        "claim_boundary": [
            "Entity statements establish only synthetic participant/client metadata trust under separately pinned local anchors.",
            "The caregiver decision is a separate fresh call to the existing CareTrust case policy and is not issued by federation resolution.",
            "No live discovery, remote endpoint, operational federation, or cross-organization network exchange was performed.",
        ],
    }
    artifact["fixture_sha256"] = sha256(FIXTURE.read_bytes()).hexdigest()
    artifact["artifact_payload_sha256"] = _canonical_hash(artifact)
    return artifact
