"""Run the synthetic CareTrust review-to-revocation vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from caretrust.authorization import AuthorizationPolicy
from caretrust.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    DraftCredentialClaim,
    DraftCredentialFields,
    DraftField,
    ReviewDecision,
)
from caretrust.security import (
    CareTrustTokenIssuer,
    CareTrustTokenVerifier,
    RevocationRegistry,
    SigningKeyPair,
)
from caretrust.workflow import (
    ActivationOutcome,
    JsonlAuditLog,
    SyntheticRegistrySimulator,
    decide_activation,
    record_review,
)


@dataclass(frozen=True)
class DemoScenarios:
    clean_draft: DraftCredentialClaim
    clean_request: AuthorizationRequest
    now: datetime


class ScenarioProvider(Protocol):
    def build(self) -> DemoScenarios: ...


class SyntheticScenarioProvider:
    """Supply a fully synthetic, evidence-linked Hawaii CNA draft."""

    def build(self) -> DemoScenarios:
        now = datetime(2026, 7, 29, 20, 0, tzinfo=UTC)

        def field(value: str, normalized: str, span: str) -> DraftField:
            return DraftField(
                value=value,
                normalized_value=normalized,
                confidence=0.99,
                evidence_refs=(span,),
            )

        draft = DraftCredentialClaim(
            schema_version="caretrust.draft-credential-claim.v1",
            draft_id="draft:synthetic-hi-cna-1001",
            evidence_id="artifact:synthetic-hi-cna-1001",
            subject_ref="person:synthetic-leilani-kealoha",
            claim_type="professional_credential",
            credential_profile="hawaii_cna_smoke_v1",
            status="draft",
            fields=DraftCredentialFields(
                holder_name=field("Leilani Kealoha", "Leilani Kealoha", "span:name"),
                registry_id=field(
                    "HI-CNA-SYN-1001", "HI-CNA-SYN-1001", "span:registry-id"
                ),
                credential_type=field(
                    "Certified Nurse Aide", "Certified Nurse Aide", "span:type"
                ),
                jurisdiction=field("HI", "HI", "span:jurisdiction"),
                original_or_issue_date=field(
                    "04/15/2024", "2024-04-15", "span:issue-date"
                ),
                expiration_date=field(
                    "04/15/2028", "2028-04-15", "span:expiration"
                ),
                credential_status=field("Active", "active", "span:status"),
                restrictions_or_notes=field("None", "none", "span:restrictions"),
                issuer_or_source=field(
                    "Prometric CNA Registry simulator",
                    "Prometric CNA Registry simulator",
                    "span:source",
                ),
            ),
            uncertainties=(),
            blocking_issues=(),
        )
        request = AuthorizationRequest(
            request_id="request:clean",
            subject_ref=draft.subject_ref,
            claim_id="claim:synthetic-hi-cna-1001",
            requested_claim_type="professional_credential",
            audience="org:synthetic-care-provider",
            purpose="credentialing",
            requested_at=now,
        )
        return DemoScenarios(draft, request, now)


def _review(
    draft: DraftCredentialClaim,
    *,
    decision: ReviewDecision,
    audit: JsonlAuditLog,
    now: datetime,
    suffix: str,
):
    return record_review(
        draft,
        review_id=f"review:{suffix}",
        reviewer_ref="reviewer:synthetic-authorized",
        decision=decision,
        reason=f"Synthetic {decision.value} scenario.",
        reviewed_at=now,
        audit_log=audit,
        actor_ref="reviewer:synthetic-authorized",
        trace_id=f"trace:{suffix}",
        event_id=f"event:review:{suffix}",
    )


def _source_check(
    draft: DraftCredentialClaim,
    *,
    audit: JsonlAuditLog,
    now: datetime,
    suffix: str,
):
    return SyntheticRegistrySimulator().check(
        draft,
        registry_result_id=f"registry:{suffix}",
        checked_at=now,
        audit_log=audit,
        actor_ref="system:synthetic-registry",
        trace_id=f"trace:{suffix}",
        event_id=f"event:registry:{suffix}",
    )


def _activate(
    draft: DraftCredentialClaim,
    *,
    review,
    registry,
    audit: JsonlAuditLog,
    now: datetime,
    suffix: str,
) -> ActivationOutcome:
    return decide_activation(
        draft,
        review_bundle=review,
        registry_result=registry,
        claim_id=f"claim:{suffix}",
        issuer_ref="https://issuer.synthetic.caretrust.example",
        allowed_audiences=("org:synthetic-care-provider",),
        allowed_purposes=("credentialing",),
        decided_at=now,
        audit_log=audit,
        actor_ref="system:activation-policy",
        trace_id=f"trace:{suffix}",
        event_id=f"event:activation:{suffix}",
    )


def _show_decision(label: str, decision: AuthorizationDecision) -> None:
    print(f"{label}: {decision.decision.value}")
    print(f"  reasons: {', '.join(decision.reason_codes)}")
    print(
        "  supporting claims: "
        + (", ".join(decision.supporting_claim_ids) or "none")
    )


def _show_activation(label: str, outcome: ActivationOutcome) -> None:
    print(f"{label}: {'permit' if outcome.permitted else 'deny'}")
    print(f"  reasons: {', '.join(outcome.reason_codes) or 'all gates satisfied'}")


def run_demo(provider: ScenarioProvider | None = None) -> None:
    scenarios = (provider or SyntheticScenarioProvider()).build()
    with TemporaryDirectory(prefix="caretrust-demo-") as directory:
        audit = JsonlAuditLog(Path(directory) / "audit.jsonl")

        clean_review = _review(
            scenarios.clean_draft,
            decision=ReviewDecision.APPROVED,
            audit=audit,
            now=scenarios.now,
            suffix="clean",
        )
        clean_registry = _source_check(
            scenarios.clean_draft,
            audit=audit,
            now=scenarios.now,
            suffix="clean",
        )
        clean_activation = _activate(
            scenarios.clean_draft,
            review=clean_review,
            registry=clean_registry,
            audit=audit,
            now=scenarios.now,
            suffix="synthetic-hi-cna-1001",
        )
        assert clean_activation.claim is not None

        mismatch_draft = scenarios.clean_draft.model_copy(
            update={
                "draft_id": "draft:synthetic-source-mismatch",
                "fields": scenarios.clean_draft.fields.model_copy(
                    update={
                        "registry_id": DraftField(
                            value="HI-CNA-SYN-MISMATCH",
                            normalized_value="HI-CNA-SYN-MISMATCH",
                            confidence=0.99,
                            evidence_refs=("span:registry-id",),
                        )
                    }
                ),
            }
        )
        mismatch_review = _review(
            mismatch_draft,
            decision=ReviewDecision.APPROVED,
            audit=audit,
            now=scenarios.now,
            suffix="mismatch",
        )
        mismatch_registry = _source_check(
            mismatch_draft,
            audit=audit,
            now=scenarios.now,
            suffix="mismatch",
        )
        mismatch_activation = _activate(
            mismatch_draft,
            review=mismatch_review,
            registry=mismatch_registry,
            audit=audit,
            now=scenarios.now,
            suffix="source-mismatch",
        )

        deferred_review = _review(
            scenarios.clean_draft,
            decision=ReviewDecision.DEFERRED,
            audit=audit,
            now=scenarios.now,
            suffix="deferred",
        )
        deferred_activation = _activate(
            scenarios.clean_draft,
            review=deferred_review,
            registry=clean_registry,
            audit=audit,
            now=scenarios.now,
            suffix="review-deferred",
        )

        key = SigningKeyPair.generate()
        revocations = RevocationRegistry()
        issuer = CareTrustTokenIssuer(
            issuer="https://issuer.synthetic.caretrust.example",
            signing_key=key,
        )
        verifier = CareTrustTokenVerifier(
            issuer=issuer.issuer,
            public_keys={key.kid: key.public_key},
            revocations=revocations,
        )
        policy = AuthorizationPolicy(verifier=verifier)
        token = issuer.issue(
            clean_activation.claim,
            now=scenarios.now,
            token_id="token:vertical-slice",
        )
        clean_decision = policy.decide(
            scenarios.clean_request,
            clean_activation.claim,
            token,
            now=scenarios.now,
        )

        print("CareTrust synthetic trust workflow")
        _show_decision("review + source match + policy", clean_decision)
        _show_activation("source/registry mismatch", mismatch_activation)
        _show_activation("human review deferred", deferred_activation)

        revocations.revoke_claim(clean_activation.claim.claim_id)
        print(f"revocation: recorded {clean_activation.claim.claim_id}")
        after = policy.decide(
            scenarios.clean_request,
            clean_activation.claim,
            token,
            now=scenarios.now,
        )
        _show_decision("post-revocation request", after)
        print(f"audit events retained during run: {len(audit.read())}")


if __name__ == "__main__":
    run_demo()
