"""Run the synthetic CareTrust review-to-revocation vertical slice."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    DraftField,
    FieldCorrection,
    RegistryStatus,
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
    ReviewerAuthorizationPolicy,
    SyntheticRegistrySimulator,
    decide_activation,
    intake_evidence,
    record_review,
    validate_and_record_extraction,
)

ROOT = Path(__file__).resolve().parents[1]
FINAL_RUN = ROOT / "artifacts" / "evaluation" / "20260730T085655.959974Z"
FINAL_FIXTURE = ROOT / "fixtures" / "cna" / "final" / "01-clean-standard.json"


@dataclass(frozen=True)
class DemoScenarios:
    clean_draft: DraftCredentialClaim
    clean_request: AuthorizationRequest
    now: datetime
    retained_run_id: str
    retained_case_id: str
    retained_response_sha256: str


class ScenarioProvider(Protocol):
    def build(self, audit: JsonlAuditLog) -> DemoScenarios: ...


class RetainedBedrockScenarioProvider:
    """Replay a retained real-Bedrock draft through the local trust workflow."""

    def build(self, audit: JsonlAuditLog) -> DemoScenarios:
        now = datetime(2026, 7, 29, 20, 0, tzinfo=UTC)
        fixture = json.loads(FINAL_FIXTURE.read_text(encoding="utf-8"))
        frozen = json.loads(
            (FINAL_RUN / "frozen-config.json").read_text(encoding="utf-8")
        )
        result = next(
            json.loads(line)
            for line in (FINAL_RUN / "results.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if json.loads(line)["case_id"] == fixture["case_id"]
        )
        source = fixture["input"]
        ocr_text = source["ocr_text"]
        artifact = intake_evidence(
            {
                "artifact_id": source["artifact_id"],
                "fixture_id": fixture["case_id"],
                "synthetic": True,
                "document_type": source["document_type"],
                "content_type": source["content_type"],
                "source_filename": source["source_filename"],
                "content_sha256": hashlib.sha256(
                    ocr_text.encode("utf-8")
                ).hexdigest(),
                "ocr_text": ocr_text,
                "spans": [
                    {
                        "span_id": span["span_id"],
                        "artifact_id": source["artifact_id"],
                        "quote": span["quote"],
                    }
                    for span in source["source_spans"]
                ],
            },
            audit_log=audit,
            actor_ref="person:synthetic-direct-care-worker",
            trace_id="trace:retained-clean",
            occurred_at=datetime.fromisoformat(result["started_at"]),
            event_id="event:evidence:retained-clean",
        )
        extraction = validate_and_record_extraction(
            result["raw_response"],
            artifact,
            extraction_id=f"extraction:{fixture['case_id']}",
            model_id=result["model_id"],
            aws_region=result["region"],
            prompt_sha256=frozen["prompt_sha256"],
            schema_sha256=frozen["schema_sha256"],
            started_at=datetime.fromisoformat(result["started_at"]),
            completed_at=datetime.fromisoformat(result["completed_at"]),
            latency_ms=result["latency_ms"],
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            estimated_cost_usd=result["estimated_cost_usd"],
            audit_log=audit,
            actor_ref="system:retained-bedrock-extraction",
            trace_id="trace:retained-clean",
            event_id="event:extraction:retained-clean",
        )
        if extraction.draft is None:
            raise RuntimeError("retained clean Bedrock result did not validate")
        draft = extraction.draft
        request = AuthorizationRequest(
            request_id="request:clean",
            subject_ref=draft.subject_ref,
            claim_id="claim:synthetic-hi-cna-1001",
            requested_claim_type="professional_credential",
            audience="org:synthetic-care-provider",
            purpose="credentialing",
            requested_at=now,
        )
        return DemoScenarios(
            draft,
            request,
            now,
            result["run_id"],
            result["case_id"],
            result["raw_response_sha256"],
        )


def _review(
    draft: DraftCredentialClaim,
    *,
    decision: ReviewDecision,
    audit: JsonlAuditLog,
    now: datetime,
    suffix: str,
    corrections: tuple[FieldCorrection, ...] = (),
):
    return record_review(
        draft,
        review_id=f"review:{suffix}",
        reviewer_ref="reviewer:synthetic-authorized",
        decision=decision,
        corrections=corrections,
        reason=f"Synthetic {decision.value} scenario.",
        reviewed_at=now,
        audit_log=audit,
        actor_ref="reviewer:synthetic-authorized",
        trace_id=f"trace:{suffix}",
        event_id=f"event:review:{suffix}",
        authorization_policy=ReviewerAuthorizationPolicy(
            allowed_reviewer_refs=frozenset(
                {"reviewer:synthetic-authorized"}
            )
        ),
    )


def _source_check(
    draft: DraftCredentialClaim,
    *,
    audit: JsonlAuditLog,
    now: datetime,
    suffix: str,
):
    clean_registry_id = (
        draft.fields.registry_id.normalized_value
        or draft.fields.registry_id.value
    )
    results = {
        "SYN-CNA-FINAL-2001": RegistryStatus.MATCH,
        "HI-CNA-SYN-MISMATCH": RegistryStatus.MISMATCH,
    }
    if clean_registry_id and clean_registry_id not in results:
        results[clean_registry_id] = RegistryStatus.NOT_FOUND
    return SyntheticRegistrySimulator(results).check(
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


def run_demo(
    provider: ScenarioProvider | None = None,
    *,
    output_path: Path | None = None,
) -> dict[str, object]:
    with TemporaryDirectory(prefix="caretrust-demo-") as directory:
        audit = JsonlAuditLog(Path(directory) / "audit.jsonl")
        scenarios = (provider or RetainedBedrockScenarioProvider()).build(audit)
        type_correction = FieldCorrection(
            field_path="fields.credential_type",
            previous_value=(
                scenarios.clean_draft.fields.credential_type.normalized_value
                or scenarios.clean_draft.fields.credential_type.value
            ),
            corrected_value="Certified Nurse Aide",
            reason=(
                "Authorized reviewer normalized the retained model output to "
                "the bounded synthetic CNA profile."
            ),
            evidence_refs=scenarios.clean_draft.fields.credential_type.evidence_refs,
        )

        clean_review = _review(
            scenarios.clean_draft,
            decision=ReviewDecision.CORRECTED,
            audit=audit,
            now=scenarios.now,
            suffix="clean",
            corrections=(type_correction,),
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
            decision=ReviewDecision.CORRECTED,
            audit=audit,
            now=scenarios.now,
            suffix="mismatch",
            corrections=(type_correction,),
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
        verified_before_revocation = verifier.verify(
            token,
            now=scenarios.now,
            expected_audience=scenarios.clean_request.audience,
            expected_purpose=scenarios.clean_request.purpose,
            expected_subject_ref=scenarios.clean_request.subject_ref,
            expected_claim_id=scenarios.clean_request.claim_id,
        )
        clean_decision = policy.decide(
            scenarios.clean_request,
            clean_activation.claim,
            token,
            now=scenarios.now,
            audit_log=audit,
            actor_ref="system:authorization-policy",
            trace_id="trace:retained-clean",
            event_id="event:authorization:initial",
        )

        print("CareTrust synthetic trust workflow")
        print(
            "retained Bedrock extraction replayed from run: "
            f"{scenarios.retained_run_id}"
        )
        _show_decision("review + source match + policy", clean_decision)
        _show_activation("source/registry mismatch", mismatch_activation)
        _show_activation("human review deferred", deferred_activation)

        revocations.revoke_claim(
            clean_activation.claim.claim_id,
            audit_log=audit,
            actor_ref="reviewer:synthetic-authorized",
            trace_id="trace:retained-clean",
            event_id="event:revocation:claim",
            occurred_at=scenarios.now,
        )
        print(f"revocation: recorded {clean_activation.claim.claim_id}")
        after = policy.decide(
            scenarios.clean_request,
            clean_activation.claim,
            token,
            now=scenarios.now,
            audit_log=audit,
            actor_ref="system:authorization-policy",
            trace_id="trace:retained-clean",
            event_id="event:authorization:post-revocation",
        )
        _show_decision("post-revocation request", after)
        if verified_before_revocation.active_claim != clean_activation.claim:
            raise RuntimeError("signed token did not bind the complete active claim")
        events = audit.read()
        print(f"audit events retained during run: {len(events)}")
        record: dict[str, object] = {
            "record_type": "caretrust.connected-vertical-slice.v2",
            "synthetic_only": True,
            "retained_bedrock_evidence": {
                "run_id": scenarios.retained_run_id,
                "case_id": scenarios.retained_case_id,
                "raw_response_sha256": scenarios.retained_response_sha256,
            },
            "implementation_sha256": {
                relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                for relative in (
                    "src/caretrust/models.py",
                    "src/caretrust/workflow.py",
                    "src/caretrust/security.py",
                    "src/caretrust/authorization.py",
                    "scripts/demo_vertical_slice.py",
                )
            },
            "results": {
                "review_source_policy": {
                    "decision": clean_decision.decision.value,
                    "reason_codes": list(clean_decision.reason_codes),
                },
                "source_mismatch": {
                    "permitted": mismatch_activation.permitted,
                    "reason_codes": list(mismatch_activation.reason_codes),
                },
                "review_deferred": {
                    "permitted": deferred_activation.permitted,
                    "reason_codes": list(deferred_activation.reason_codes),
                },
                "post_revocation": {
                    "decision": after.decision.value,
                    "reason_codes": list(after.reason_codes),
                },
            },
            "signed_claim": {
                "complete_active_claim_bound": True,
                "claim_id": verified_before_revocation.active_claim.claim_id,
                "jurisdiction": verified_before_revocation.active_claim.jurisdiction,
                "evidence_ref_count": len(
                    verified_before_revocation.active_claim.evidence_refs
                ),
                "signature_profile": "EdDSA compact JWS/JWT",
            },
            "audit": {
                "event_count": len(events),
                "event_types": [event.event_type.value for event in events],
                "authorization_events": sum(
                    event.event_type.value == "authorization_decided"
                    for event in events
                ),
                "revocation_events": sum(
                    event.event_type.value == "claim_revoked" for event in events
                ),
            },
            "limitations": [
                "The Bedrock draft is replayed from a retained real-model response; "
                "this command does not incur a new model call.",
                "Registry, reviewer identity, keys, and revocation state are "
                "synthetic local controls, not production services.",
                "The signed claim is a CareTrust prototype JWT profile, not a "
                "W3C Verifiable Credential or protocol-conformance claim.",
            ],
        }
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the machine-readable validation record.",
    )
    arguments = parser.parse_args()
    run_demo(output_path=arguments.output)
