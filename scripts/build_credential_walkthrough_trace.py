"""Generate the exact executable professional-credential walkthrough trace.

This trace intentionally does not claim to be the retained Textract on-ramp.
It replays a separately retained Bedrock evaluation draft, then executes the
local review, source-simulator, activation, signing, two-app policy, revocation,
and fresh-denial path. The browser can consume the generated messages directly.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from caretrust.authorization import AuthorizationPolicy
from caretrust.models import (
    AuthorizationRequest,
    FieldCorrection,
    RegistryStatus,
    RevocationRecord,
    RevocationTargetType,
    ReviewDecision,
)
from caretrust.security import (
    CareTrustTokenIssuer,
    CareTrustTokenVerifier,
    RevocationRegistry,
    SigningKeyPair,
)
from caretrust.trace import EvidenceStatus, TraceBundle, TraceRecorder, canonical_json
from caretrust.workflow import (
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
TRACE_ID = "trace:credential-lifecycle:synthetic-hi-cna-1001:v1"
CLAIM_ID = "claim:synthetic-hi-cna-1001"
APP_A_AUDIENCE = "urn:caretrust:app:onboarding"
APP_A_PURPOSE = "workforce-onboarding"
APP_B_AUDIENCE = "urn:caretrust:app:scheduling"
APP_B_PURPOSE = "shift-assignment"
TEST_KEY_LABEL = b"caretrust-public-synthetic-walkthrough-key-v1"


def _decode_jwt_segment(segment: str) -> dict[str, object]:
    padding = "=" * (-len(segment) % 4)
    decoded = base64.urlsafe_b64decode(segment + padding)
    value = json.loads(decoded)
    if not isinstance(value, dict):
        raise ValueError("decoded JWT segment must be an object")
    return value


def _retained_input() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    fixture = json.loads(FINAL_FIXTURE.read_text(encoding="utf-8"))
    frozen = json.loads((FINAL_RUN / "frozen-config.json").read_text(encoding="utf-8"))
    result = next(
        json.loads(line)
        for line in (FINAL_RUN / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["case_id"] == fixture["case_id"]
    )
    return fixture, frozen, result


def build_credential_walkthrough_trace() -> TraceBundle:
    fixture, frozen, result = _retained_input()
    source = fixture["input"]
    now = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
    recorder = TraceRecorder(TRACE_ID)

    with TemporaryDirectory(prefix="caretrust-credential-trace-") as directory:
        audit = JsonlAuditLog(Path(directory) / "audit.jsonl")
        ocr_text = source["ocr_text"]
        artifact = intake_evidence(
            {
                "artifact_id": source["artifact_id"],
                "fixture_id": fixture["case_id"],
                "synthetic": True,
                "document_type": source["document_type"],
                "content_type": source["content_type"],
                "source_filename": source["source_filename"],
                "content_sha256": hashlib.sha256(ocr_text.encode("utf-8")).hexdigest(),
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
            actor_ref="caregiver:synthetic-direct-care-worker",
            trace_id=TRACE_ID,
            occurred_at=now,
            event_id="audit:evidence:credential-001",
        )
        recorder.append(
            event_id="trace:evidence:credential-001",
            occurred_at=now,
            actor_ref="caregiver:synthetic-direct-care-worker",
            receiver_ref="caretrust:evidence-intake",
            boundary="untrusted_legacy_evidence",
            message_type="EvidenceArtifact",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=("CareTrust EvidenceArtifact v1",),
            linked_ids={"artifact_id": artifact.artifact_id},
            payload=artifact.model_dump(mode="json"),
            non_claims=("Frozen OCR text is not the retained Textract response.",),
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
            actor_ref="caretrust:retained-bedrock-adapter",
            trace_id=TRACE_ID,
            event_id="audit:extraction:credential-001",
        )
        if extraction.draft is None:
            raise RuntimeError("retained credential draft did not validate")
        draft = extraction.draft
        recorder.append(
            event_id="trace:extraction:credential-001",
            occurred_at=now + timedelta(seconds=1),
            actor_ref="caretrust:retained-bedrock-adapter",
            receiver_ref="caretrust:draft-validator",
            boundary="untrusted_model_output",
            message_type="ExtractionRecord",
            evidence_status=EvidenceStatus.RETAINED_AWS,
            standard_refs=("Amazon Bedrock Converse retained response", "CareTrust DraftCredentialClaim v1"),
            linked_ids={
                "artifact_id": artifact.artifact_id,
                "extraction_id": extraction.extraction_id,
                "draft_id": draft.draft_id,
            },
            payload=extraction.model_dump(mode="json"),
            non_claims=("The retained Bedrock response is a draft and cannot activate itself.",),
        )

        correction = FieldCorrection(
            field_path="fields.credential_type",
            previous_value=(
                draft.fields.credential_type.normalized_value
                or draft.fields.credential_type.value
            ),
            corrected_value="Certified Nurse Aide",
            reason="Authorized reviewer normalized the bounded synthetic CNA type.",
            evidence_refs=draft.fields.credential_type.evidence_refs,
        )
        review_bundle = record_review(
            draft,
            review_id="review:credential:001",
            reviewer_ref="reviewer:synthetic-authorized",
            decision=ReviewDecision.CORRECTED,
            corrections=(correction,),
            reason="Synthetic reviewer accepted the evidence-linked correction.",
            reviewed_at=now + timedelta(seconds=2),
            audit_log=audit,
            actor_ref="reviewer:synthetic-authorized",
            trace_id=TRACE_ID,
            event_id="audit:review:credential-001",
            authorization_policy=ReviewerAuthorizationPolicy(
                allowed_reviewer_refs=frozenset({"reviewer:synthetic-authorized"})
            ),
        )
        review = review_bundle.review
        recorder.append(
            event_id="trace:review:credential-001",
            occurred_at=now + timedelta(seconds=2),
            actor_ref="reviewer:synthetic-authorized",
            receiver_ref="caretrust:review-service",
            boundary="human_accountability",
            message_type="ReviewRecord",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=("CareTrust ReviewRecord v1",),
            linked_ids={"draft_id": draft.draft_id, "review_id": review.review_id},
            payload=review.model_dump(mode="json"),
        )

        registry = SyntheticRegistrySimulator(
            {"SYN-CNA-FINAL-2001": RegistryStatus.MATCH}
        ).check(
            draft,
            registry_result_id="registry:credential:001",
            checked_at=now + timedelta(seconds=3),
            audit_log=audit,
            actor_ref="caretrust:synthetic-registry-adapter",
            trace_id=TRACE_ID,
            event_id="audit:registry:credential-001",
        )
        recorder.append(
            event_id="trace:registry:credential-001",
            occurred_at=now + timedelta(seconds=3),
            actor_ref="caretrust:synthetic-registry-adapter",
            receiver_ref="caretrust:activation-policy",
            boundary="accountable_source_status",
            message_type="RegistryResult",
            evidence_status=EvidenceStatus.LOCAL_SIMULATION,
            standard_refs=("CareTrust RegistryResult v1",),
            linked_ids={
                "draft_id": draft.draft_id,
                "registry_result_id": registry.registry_result_id,
            },
            payload=registry.model_dump(mode="json"),
            non_claims=("The Prometric CNA Registry is not contacted.",),
        )

        activation = decide_activation(
            draft,
            review_bundle=review_bundle,
            registry_result=registry,
            claim_id=CLAIM_ID,
            issuer_ref="https://issuer.synthetic.caretrust.example",
            allowed_audiences=(APP_A_AUDIENCE, APP_B_AUDIENCE),
            allowed_purposes=(APP_A_PURPOSE, APP_B_PURPOSE),
            decided_at=now + timedelta(seconds=4),
            audit_log=audit,
            actor_ref="caretrust:credential-activation-policy",
            trace_id=TRACE_ID,
            event_id="audit:activation:credential-001",
        )
        if activation.claim is None:
            raise RuntimeError(f"credential activation denied: {activation.reason_codes}")
        claim = activation.claim
        recorder.append(
            event_id="trace:claim:credential-001",
            occurred_at=now + timedelta(seconds=4),
            actor_ref="caretrust:credential-activation-policy",
            receiver_ref="caretrust:claim-store",
            boundary="authority_bearing_activation",
            message_type="ActiveCredentialClaim",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=("CareTrust ActiveCredentialClaim v1",),
            linked_ids={
                "draft_id": draft.draft_id,
                "review_id": review.review_id,
                "registry_result_id": registry.registry_result_id,
                "claim_id": claim.claim_id,
            },
            payload=claim.model_dump(mode="json"),
            non_claims=("The native claim is not a W3C Verifiable Credential.",),
        )

        # Publicly reproducible synthetic test key. It provides no security
        # assurance and no private key bytes are written to the trace artifact.
        key = SigningKeyPair.from_private_bytes(
            hashlib.sha256(TEST_KEY_LABEL).digest(),
            kid="caretrust-public-synthetic-walkthrough-v1",
        )
        revocations = RevocationRegistry()
        issuer = CareTrustTokenIssuer(issuer=claim.issuer_ref, signing_key=key)
        verifier = CareTrustTokenVerifier(
            issuer=issuer.issuer,
            public_keys={key.kid: key.public_key},
            revocations=revocations,
        )
        token = issuer.issue(
            claim,
            now=now + timedelta(seconds=5),
            token_id="token:credential:001",
        )
        encoded_header, encoded_payload, _ = token.split(".")
        token_summary = {
            "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "header": _decode_jwt_segment(encoded_header),
            "payload": _decode_jwt_segment(encoded_payload),
            "public_jwk": key.public_jwk(),
            "signature_verified": True,
            "raw_token_retained_in_artifact": False,
            "private_key_material_retained": False,
            "synthetic_test_key": True,
        }
        verifier.verify(token, now=now + timedelta(seconds=5), expected_claim_id=CLAIM_ID)
        recorder.append(
            event_id="trace:token:credential-001",
            occurred_at=now + timedelta(seconds=5),
            actor_ref="caretrust:token-issuer",
            receiver_ref="caretrust:token-verifier",
            boundary="signed_claim_capability",
            message_type="CareTrustJwtVerificationReceipt",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=("RFC 7515 JWS", "RFC 7519 JWT", "CareTrust JWT profile"),
            linked_ids={"claim_id": claim.claim_id, "token_id": "token:credential:001"},
            payload=token_summary,
            non_claims=("The deterministic public test key is not suitable for production.",),
        )

        policy_a = AuthorizationPolicy(
            verifier=verifier, policy_version="caretrust.onboarding-policy.v1"
        )
        policy_b = AuthorizationPolicy(
            verifier=verifier, policy_version="caretrust.scheduling-policy.v2"
        )
        request_a = AuthorizationRequest(
            request_id="request:credential:app-a:001",
            subject_ref=claim.subject_ref,
            claim_id=claim.claim_id,
            requested_claim_type="professional_credential",
            audience=APP_A_AUDIENCE,
            purpose=APP_A_PURPOSE,
            requested_at=now + timedelta(seconds=6),
        )
        decision_a = policy_a.decide(
            request_a,
            claim,
            token,
            now=now + timedelta(seconds=6),
            audit_log=audit,
            actor_ref="app:onboarding:local-policy",
            trace_id=TRACE_ID,
            event_id="audit:authorization:app-a:001",
        )
        request_b = AuthorizationRequest(
            request_id="request:credential:app-b:001",
            subject_ref=claim.subject_ref,
            claim_id=claim.claim_id,
            requested_claim_type="professional_credential",
            audience=APP_B_AUDIENCE,
            purpose=APP_B_PURPOSE,
            requested_at=now + timedelta(seconds=8),
        )
        decision_b = policy_b.decide(
            request_b,
            claim,
            token,
            now=now + timedelta(seconds=8),
            audit_log=audit,
            actor_ref="app:scheduling:local-policy",
            trace_id=TRACE_ID,
            event_id="audit:authorization:app-b:001",
        )
        for index, (app, request, decision, occurred) in enumerate(
            (
                ("app-a", request_a, decision_a, now + timedelta(seconds=6)),
                ("app-b", request_b, decision_b, now + timedelta(seconds=8)),
            ),
            start=1,
        ):
            recorder.append(
                event_id=f"trace:request:{app}:001",
                occurred_at=occurred,
                actor_ref=f"{app}:synthetic-client",
                receiver_ref=f"{app}:local-policy",
                boundary="application_specific_request",
                message_type="AuthorizationRequest",
                evidence_status=EvidenceStatus.EXECUTED_LOCAL,
                standard_refs=("CareTrust AuthorizationRequest v1",),
                linked_ids={"claim_id": claim.claim_id, "request_id": request.request_id},
                payload=request.model_dump(mode="json"),
            )
            recorder.append(
                event_id=f"trace:decision:{app}:001",
                occurred_at=occurred + timedelta(milliseconds=100),
                actor_ref=f"{app}:local-policy",
                receiver_ref=f"{app}:synthetic-client",
                boundary="application_local_authorization",
                message_type="AuthorizationDecision",
                evidence_status=EvidenceStatus.EXECUTED_LOCAL,
                standard_refs=("CareTrust AuthorizationDecision v1",),
                linked_ids={
                    "claim_id": claim.claim_id,
                    "request_id": request.request_id,
                    "decision_id": decision.decision_id,
                },
                payload=decision.model_dump(mode="json"),
            )

        revoked_at = now + timedelta(seconds=10)
        revocations.revoke_claim(
            claim.claim_id,
            audit_log=audit,
            actor_ref="reviewer:synthetic-authorized",
            trace_id=TRACE_ID,
            event_id="audit:revocation:credential-001",
            occurred_at=revoked_at,
        )
        revocation = RevocationRecord(
            schema_version="caretrust.revocation-record.v1",
            revocation_id="revocation:credential:001",
            target_type=RevocationTargetType.CLAIM,
            target_id=claim.claim_id,
            claim_id=claim.claim_id,
            reason_code="CLAIM_REVOKED",
            reason="Synthetic authorized reviewer revoked the reusable credential claim.",
            actor_ref="reviewer:synthetic-authorized",
            revoked_at=revoked_at,
            synthetic=True,
        )
        recorder.append(
            event_id="trace:revocation:credential-001",
            occurred_at=revoked_at,
            actor_ref="reviewer:synthetic-authorized",
            receiver_ref="caretrust:in-memory-status-seam",
            boundary="claim_status_change",
            message_type="RevocationRecord",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=("CareTrust RevocationRecord v1",),
            linked_ids={"claim_id": claim.claim_id, "revocation_id": revocation.revocation_id},
            payload=revocation.model_dump(mode="json"),
            non_claims=("No durable or federated status distribution is deployed.",),
        )

        fresh_request_b = request_b.model_copy(
            update={
                "request_id": "request:credential:app-b:002",
                "requested_at": now + timedelta(seconds=11),
            }
        )
        fresh_decision_b = policy_b.decide(
            fresh_request_b,
            claim,
            token,
            now=now + timedelta(seconds=11),
            audit_log=audit,
            actor_ref="app:scheduling:local-policy",
            trace_id=TRACE_ID,
            event_id="audit:authorization:app-b:002",
        )
        recorder.append(
            event_id="trace:request:app-b:002",
            occurred_at=now + timedelta(seconds=11),
            actor_ref="app-b:synthetic-client",
            receiver_ref="app-b:local-policy",
            boundary="fresh_post_revocation_request",
            message_type="AuthorizationRequest",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=("CareTrust AuthorizationRequest v1",),
            linked_ids={"claim_id": claim.claim_id, "request_id": fresh_request_b.request_id},
            payload=fresh_request_b.model_dump(mode="json"),
        )
        recorder.append(
            event_id="trace:decision:app-b:002",
            occurred_at=now + timedelta(seconds=11, milliseconds=100),
            actor_ref="app-b:local-policy",
            receiver_ref="app-b:synthetic-client",
            boundary="application_local_authorization",
            message_type="AuthorizationDecision",
            evidence_status=EvidenceStatus.EXECUTED_LOCAL,
            standard_refs=("CareTrust AuthorizationDecision v1",),
            linked_ids={
                "claim_id": claim.claim_id,
                "request_id": fresh_request_b.request_id,
                "decision_id": fresh_decision_b.decision_id,
                "revocation_id": revocation.revocation_id,
            },
            payload=fresh_decision_b.model_dump(mode="json"),
            non_claims=("Earlier permit receipts are historical; existing sessions are not terminated.",),
        )

    return recorder.bundle(
        title="Deterministic synthetic Hawaii CNA trust lifecycle",
        fixture_refs=(
            str(FINAL_FIXTURE.relative_to(ROOT)).replace("\\", "/"),
            str((FINAL_RUN / "results.jsonl").relative_to(ROOT)).replace("\\", "/"),
        ),
        limitations=(
            "This deterministic lifecycle replays a retained Bedrock evaluation draft; it is not the retained Textract on-ramp trace.",
            "The registry, reviewer, applications, key, and revocation/status service are synthetic local controls.",
            "The CareTrust JWT is not a W3C Verifiable Credential and no external application or registry is contacted.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "validation" / "credential-walkthrough-trace.json",
    )
    arguments = parser.parse_args()
    bundle = build_credential_walkthrough_trace()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(arguments.output)
    print(f"trace_sha256={hashlib.sha256(canonical_json(bundle).encode('utf-8')).hexdigest()}")
    print(f"events={len(bundle.events)}")


if __name__ == "__main__":
    main()
