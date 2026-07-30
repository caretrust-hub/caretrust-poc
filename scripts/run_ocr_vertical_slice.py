"""Run the synthetic image -> Textract -> Bedrock/Qwen intake slice.

Live mode invokes Amazon Textract and Bedrock. ``--offline`` replays a retained
Textract-shaped response through the same adapter and a separately retained
real-Bedrock response, making local tests deterministic and credential-free.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from caretrust.adapters.bedrock import (
    DEFAULT_MODEL_ID,
    DEFAULT_REGION,
    BedrockModelAdapter,
)
from caretrust.adapters.ocr import OcrAdapter, OcrResult, TextractOcrAdapter
from caretrust.models import DraftCredentialClaim

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "fixtures" / "documents" / "synthetic-hawaii-cna.png"
DEFAULT_TEXTRACT_REPLAY = (
    ROOT / "fixtures" / "documents" / "synthetic-hawaii-cna.textract.json"
)
DEFAULT_BEDROCK_RESULTS = (
    ROOT / "artifacts" / "evaluation" / "20260730T085655.959974Z" / "results.jsonl"
)
DEFAULT_SCHEMA = ROOT / "schemas" / "draft-credential-claim.schema.json"
DEFAULT_PROMPT = ROOT / "prompts" / "cna-draft-extraction-v1.txt"
DEFAULT_OUTPUT = ROOT / "artifacts" / "ocr" / "retained-offline-vertical-slice.json"

ARTIFACT_ID = "artifact:final-01-clean-standard"
FIXTURE_ID = "ocr-synthetic-hawaii-cna-v1"
CASE_ID = "final-01-clean-standard"
DRAFT_ID = "draft:final-01-clean-standard"
SUBJECT_REF = "person:synthetic-leilani-testperson"
AGGREGATE_SPAN_ID = "final-01-evidence"


class RetainedTextractClient:
    """Credential-free client that replays a retained Textract response shape."""

    def __init__(self, response_path: Path) -> None:
        self.response_path = response_path
        self.calls = 0

    def detect_document_text(self, **kwargs: Any) -> Mapping[str, Any]:
        document = kwargs.get("Document")
        if (
            not isinstance(document, Mapping)
            or not isinstance(document.get("Bytes"), bytes)
        ):
            raise ValueError("retained Textract replay requires document bytes")
        self.calls += 1
        response = json.loads(self.response_path.read_text(encoding="utf-8"))
        if not isinstance(response, Mapping):
            raise ValueError("retained Textract response must be an object")
        return response


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "application/octet-stream"


def _build_user_payload(ocr: OcrResult) -> str:
    return canonical_json(
        {
            "case_id": CASE_ID,
            "synthetic": True,
            "fixed_output_identifiers": {
                "draft_id": DRAFT_ID,
                "evidence_id": ARTIFACT_ID,
                "subject_ref": SUBJECT_REF,
            },
            "document": {
                "document_type": "hawaii_cna_status_record",
                "ocr_text": ocr.text,
                "source_spans": [
                    {
                        "span_id": AGGREGATE_SPAN_ID,
                        "quote": ocr.text,
                    },
                    *[
                        {
                            "span_id": item.evidence_span.span_id,
                            "quote": item.evidence_span.quote,
                            "confidence": item.confidence,
                            "block_type": item.block_type,
                            "region": (
                                item.evidence_span.region.model_dump(mode="json")
                                if item.evidence_span.region is not None
                                else None
                            ),
                        }
                        for item in ocr.spans
                    ],
                ],
            },
        }
    )


def _retained_bedrock_response(results_path: Path) -> tuple[str, dict[str, Any]]:
    for line in results_path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("case_id") == CASE_ID:
            raw = record.get("raw_response")
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("retained Bedrock record contained no raw_response")
            metadata = {
                key: record.get(key)
                for key in (
                    "run_id",
                    "case_id",
                    "model_id",
                    "region",
                    "request_id",
                    "raw_response_sha256",
                    "started_at",
                    "completed_at",
                    "latency_ms",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "estimated_cost_usd",
                )
            }
            return raw, metadata
    raise ValueError(f"retained Bedrock case not found: {CASE_ID}")


def _validate_draft(draft: DraftCredentialClaim, permitted_spans: set[str]) -> None:
    if draft.draft_id != DRAFT_ID:
        raise ValueError("model changed fixed draft_id")
    if draft.evidence_id != ARTIFACT_ID:
        raise ValueError("model changed fixed evidence_id")
    if draft.subject_ref != SUBJECT_REF:
        raise ValueError("model changed fixed subject_ref")
    cited = {
        reference
        for _, field in draft.fields
        for reference in field.evidence_refs
    } | {
        reference
        for uncertainty in draft.uncertainties
        for reference in uncertainty.evidence_refs
    }
    invalid = sorted(cited - permitted_spans)
    if invalid:
        raise ValueError(f"model cited unknown OCR evidence spans: {invalid}")


def run_vertical_slice(
    *,
    input_path: Path = DEFAULT_INPUT,
    output_path: Path | None = None,
    offline: bool = False,
    retained_textract_path: Path = DEFAULT_TEXTRACT_REPLAY,
    retained_bedrock_path: Path = DEFAULT_BEDROCK_RESULTS,
    region: str = DEFAULT_REGION,
    model_id: str = DEFAULT_MODEL_ID,
    ocr_adapter: OcrAdapter | None = None,
    model_adapter: BedrockModelAdapter | None = None,
) -> dict[str, Any]:
    """Run OCR before model extraction and retain a judge-readable record.

    OCR is intentionally completed and validated before a live Bedrock adapter
    is constructed. Therefore an OCR failure cannot trigger a Bedrock call.
    """

    document = input_path.read_bytes()
    content_type = _content_type(input_path)
    if ocr_adapter is None:
        if offline:
            ocr_adapter = TextractOcrAdapter(
                region=region,
                client=RetainedTextractClient(retained_textract_path),
            )
        else:
            ocr_adapter = TextractOcrAdapter(region=region)

    # Fail-closed gate: do not construct or invoke Bedrock before this returns.
    ocr = ocr_adapter.detect(
        document,
        content_type=content_type,
        source_filename=input_path.name,
        artifact_id=ARTIFACT_ID,
    )
    artifact = ocr.to_evidence_artifact(
        artifact_id=ARTIFACT_ID,
        fixture_id=FIXTURE_ID,
        aggregate_span_id=AGGREGATE_SPAN_ID,
    )
    user_payload = _build_user_payload(ocr)
    schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    prompt = DEFAULT_PROMPT.read_text(encoding="utf-8")

    if offline and model_adapter is None:
        raw_response, model_metadata = _retained_bedrock_response(
            retained_bedrock_path
        )
        model_mode = "retained-real-bedrock-response"
    else:
        if model_adapter is None:
            model_adapter = BedrockModelAdapter(
                model_id=model_id,
                region=region,
            )
        response = model_adapter.extract(
            system_prompt=prompt,
            user_text=user_payload,
            json_schema=schema,
            max_tokens=2_500,
            temperature=0.0,
            request_metadata={
                "caretrust_case": CASE_ID,
                "caretrust_component": "ocr_vertical_slice",
            },
        )
        raw_response = response.raw_text
        model_metadata = {
            "model_id": response.model_id,
            "region": response.region,
            "request_id": response.request_id,
            "started_at": response.started_at.isoformat(),
            "completed_at": response.completed_at.isoformat(),
            "latency_ms": response.latency_ms,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "estimated_cost_usd": response.estimated_cost_usd,
        }
        model_mode = "live-bedrock-converse"

    draft = DraftCredentialClaim.model_validate_json(raw_response)
    permitted_spans = {span.span_id for span in artifact.spans}
    _validate_draft(draft, permitted_spans)
    record = {
        "record_type": "caretrust.ocr-bedrock-vertical-slice.v1",
        "synthetic_only": True,
        "mode": "offline-retained-replay" if offline else "live-aws",
        "input": {
            "source_file": str(input_path.relative_to(ROOT)).replace("\\", "/")
            if input_path.is_relative_to(ROOT)
            else str(input_path),
            "content_type": content_type,
            "content_sha256": hashlib.sha256(document).hexdigest(),
        },
        "ocr": ocr.to_record(),
        "evidence_artifact": artifact.model_dump(mode="json"),
        "extraction": {
            "mode": model_mode,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "schema_sha256": hashlib.sha256(
                DEFAULT_SCHEMA.read_bytes()
            ).hexdigest(),
            "user_payload_sha256": hashlib.sha256(
                user_payload.encode("utf-8")
            ).hexdigest(),
            "raw_response_sha256": hashlib.sha256(
                raw_response.encode("utf-8")
            ).hexdigest(),
            "metadata": model_metadata,
            "draft": draft.model_dump(mode="json"),
        },
        "gates": {
            "ocr_succeeded_before_model_extraction": True,
            "draft_schema_valid": True,
            "draft_only_no_activation": draft.status == "draft",
            "evidence_references_valid": True,
        },
        "limitations": (
            [
                "The Textract response is a retained synthetic response shape; "
                "offline mode makes no Textract API call.",
                "The Bedrock/Qwen response was retained from a prior real-model "
                "evaluation with equivalent synthetic CNA facts, not generated "
                "from this image during the offline replay.",
                "Offline replay proves orchestration, normalization, hashing, "
                "schema validation, and fail-closed gates; use live mode to "
                "produce same-run AWS evidence.",
            ]
            if offline
            else [
                "The document and subject are fully synthetic.",
                "OCR and model output remain unverified draft evidence; no "
                "credential activation or authorization occurs in this script.",
            ]
        ),
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--ocr", choices=("textract",), default="textract")
    parser.add_argument("--extract", choices=("bedrock",), default="bedrock")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--retained-textract",
        type=Path,
        default=DEFAULT_TEXTRACT_REPLAY,
    )
    parser.add_argument(
        "--retained-bedrock",
        type=Path,
        default=DEFAULT_BEDROCK_RESULTS,
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Validation record path. Offline mode defaults to the retained "
            "artifact; live mode creates a timestamped artifact."
        ),
    )
    parser.add_argument(
        "--region",
        default=os.getenv("CARETRUST_AWS_REGION", DEFAULT_REGION),
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("CARETRUST_BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output
    if output_path is None:
        if args.offline:
            output_path = DEFAULT_OUTPUT
        else:
            run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            output_path = ROOT / "artifacts" / "ocr" / run_id / "vertical-slice.json"
    record = run_vertical_slice(
        input_path=args.input,
        output_path=output_path,
        offline=args.offline,
        retained_textract_path=args.retained_textract,
        retained_bedrock_path=args.retained_bedrock,
        region=args.region,
        model_id=args.model_id,
    )
    print(
        json.dumps(
            {
                "mode": record["mode"],
                "content_sha256": record["ocr"]["content_sha256"],
                "ocr_output_sha256": record["ocr"]["ocr_output_sha256"],
                "draft_id": record["extraction"]["draft"]["draft_id"],
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
