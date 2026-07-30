"""Run the frozen five-case synthetic Bedrock smoke test.

The runner writes an immutable-style evidence bundle per invocation. It never
sends expected outputs to the model and it retains schema or API failures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from caretrust.adapters.bedrock import (
    DEFAULT_INPUT_USD_PER_MILLION,
    DEFAULT_MODEL_ID,
    DEFAULT_OUTPUT_USD_PER_MILLION,
    DEFAULT_REGION,
    BedrockModelAdapter,
)
from caretrust.models import DraftCredentialClaim

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "cna" / "smoke"
SCHEMA_PATH = ROOT / "schemas" / "draft-credential-claim.schema.json"
PROMPT_PATH = ROOT / "prompts" / "cna-draft-extraction-v1.txt"
DEFAULT_OUTPUT_ROOT = ROOT / "artifacts" / "smoke"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_user_payload(fixture: dict[str, Any]) -> str:
    case_id = fixture["case_id"]
    input_data = fixture["input"]
    expected_draft = fixture["expected"]["draft"]
    payload = {
        "case_id": case_id,
        "synthetic": True,
        "fixed_output_identifiers": {
            "draft_id": expected_draft["draft_id"],
            "evidence_id": input_data["artifact_id"],
            "subject_ref": expected_draft["subject_ref"],
        },
        "document": {
            "document_type": input_data["document_type"],
            "ocr_text": input_data["ocr_text"],
            "source_spans": input_data["source_spans"],
        },
    }
    return canonical_json(payload)


def validate_evidence_refs(
    draft: DraftCredentialClaim,
    fixture: dict[str, Any],
) -> list[str]:
    permitted = {
        span["span_id"] for span in fixture["input"]["source_spans"]
    }
    errors: list[str] = []
    for field_name, field in draft.fields:
        invalid = sorted(set(field.evidence_refs) - permitted)
        if invalid:
            errors.append(f"fields.{field_name}: invalid evidence refs {invalid}")
    for index, uncertainty in enumerate(draft.uncertainties):
        invalid = sorted(set(uncertainty.evidence_refs) - permitted)
        if invalid:
            errors.append(f"uncertainties.{index}: invalid evidence refs {invalid}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default=os.getenv("CARETRUST_BEDROCK_MODEL_ID", DEFAULT_MODEL_ID))
    parser.add_argument("--region", default=os.getenv("CARETRUST_AWS_REGION", DEFAULT_REGION))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--budget-usd", type=float, default=float(os.getenv("CARETRUST_INFERENCE_BUDGET_USD", "10.00")))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.budget_usd <= 0 or args.budget_usd > 10:
        raise SystemExit("--budget-usd must be greater than zero and no more than 10")

    schema_bytes = SCHEMA_PATH.read_bytes()
    prompt_bytes = PROMPT_PATH.read_bytes()
    schema = json.loads(schema_bytes)
    system_prompt = prompt_bytes.decode("utf-8")
    fixture_manifest = load_json(FIXTURE_DIR / "manifest.json")

    run_started = datetime.now(UTC)
    run_id = run_started.strftime("%Y%m%dT%H%M%S.%fZ")
    output_dir = args.output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

    adapter = BedrockModelAdapter(model_id=args.model_id, region=args.region)
    results: list[dict[str, Any]] = []
    cumulative_cost = 0.0

    for manifest_item in fixture_manifest["fixtures"]:
        fixture_path = FIXTURE_DIR / manifest_item["file"]
        fixture_bytes = fixture_path.read_bytes()
        if sha256_bytes(fixture_bytes) != manifest_item["sha256"]:
            raise RuntimeError(f"fixture hash mismatch: {fixture_path.name}")
        fixture = json.loads(fixture_bytes)
        case_id = fixture["case_id"]
        user_payload = build_user_payload(fixture)
        record: dict[str, Any] = {
            "case_id": case_id,
            "fixture_file": manifest_item["file"],
            "fixture_sha256": manifest_item["sha256"],
            "status": "failed",
            "validation_errors": [],
        }

        if cumulative_cost >= args.budget_usd:
            record["validation_errors"].append("budget ceiling reached before invocation")
            results.append(record)
            continue

        try:
            response = adapter.extract(
                system_prompt=system_prompt,
                user_text=user_payload,
                json_schema=schema,
                max_tokens=2_500,
                temperature=0.0,
                request_metadata={
                    "caretrust_case": case_id,
                    "caretrust_run": run_id,
                },
            )
            raw_path = output_dir / f"{case_id}.raw.json"
            raw_path.write_text(response.raw_text + "\n", encoding="utf-8")
            record.update(
                {
                    "raw_response_file": raw_path.name,
                    "raw_response_sha256": sha256_bytes(response.raw_text.encode("utf-8")),
                    "model_id": response.model_id,
                    "region": response.region,
                    "started_at": response.started_at.isoformat(),
                    "completed_at": response.completed_at.isoformat(),
                    "latency_ms": response.latency_ms,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "total_tokens": response.total_tokens,
                    "estimated_cost_usd": response.estimated_cost_usd,
                    "stop_reason": response.stop_reason,
                    "request_id": response.request_id,
                }
            )
            cumulative_cost += response.estimated_cost_usd or 0.0
            try:
                draft = DraftCredentialClaim.model_validate(response.parsed_json)
                evidence_errors = validate_evidence_refs(draft, fixture)
                if draft.draft_id != fixture["expected"]["draft"]["draft_id"]:
                    evidence_errors.append("model changed fixed draft_id")
                if draft.evidence_id != fixture["input"]["artifact_id"]:
                    evidence_errors.append("model changed fixed evidence_id")
                if draft.subject_ref != fixture["expected"]["draft"]["subject_ref"]:
                    evidence_errors.append("model changed fixed subject_ref")
                if evidence_errors:
                    record["validation_errors"].extend(evidence_errors)
                else:
                    record["status"] = "schema_valid"
                parsed_path = output_dir / f"{case_id}.parsed.json"
                parsed_path.write_text(
                    json.dumps(draft.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                record["parsed_file"] = parsed_path.name
            except ValidationError as exc:
                record["validation_errors"].extend(
                    error["msg"] for error in exc.errors(include_url=False)
                )
        except Exception as exc:  # retain each live failure for judge-readable evidence
            record["validation_errors"].append(f"{type(exc).__name__}: {exc}")

        results.append(record)
        (output_dir / f"{case_id}.record.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    valid_count = sum(result["status"] == "schema_valid" for result in results)
    completed_at = datetime.now(UTC)
    summary = {
        "run_id": run_id,
        "synthetic_only": True,
        "registry_calls": "none",
        "model_id": args.model_id,
        "region": args.region,
        "temperature": 0.0,
        "max_tokens": 2_500,
        "structured_output": "Bedrock Converse JSON Schema",
        "schema_file": str(SCHEMA_PATH.relative_to(ROOT)).replace("\\", "/"),
        "schema_sha256": sha256_bytes(schema_bytes),
        "prompt_file": str(PROMPT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "prompt_sha256": sha256_bytes(prompt_bytes),
        "fixture_manifest_sha256": sha256_bytes(
            (FIXTURE_DIR / "manifest.json").read_bytes()
        ),
        "started_at": run_started.isoformat(),
        "completed_at": completed_at.isoformat(),
        "case_count": len(results),
        "schema_valid_count": valid_count,
        "all_schema_valid": valid_count == len(results),
        "estimated_cost_usd": round(cumulative_cost, 8),
        "budget_ceiling_usd": args.budget_usd,
        "reference_rates_usd_per_million_tokens": {
            "input": DEFAULT_INPUT_USD_PER_MILLION,
            "output": DEFAULT_OUTPUT_USD_PER_MILLION,
            "recorded_for": "Qwen3 32B us-west-2 on 2026-07-29",
        },
        "results": results,
    }
    (output_dir / "run-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["all_schema_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
