"""Offline integration tests for the OCR-to-draft vertical slice."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from caretrust.adapters.ocr import OcrError
from fixtures.documents.generate_synthetic_hawaii_cna import (
    render_png,
    textract_response,
)
from scripts.run_ocr_vertical_slice import (
    DEFAULT_INPUT,
    DEFAULT_SCHEMA,
    DEFAULT_TEXTRACT_REPLAY,
    run_vertical_slice,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures" / "documents" / "synthetic-hawaii-cna.source.json"


def test_synthetic_png_is_deterministic_and_visibly_marked_synthetic() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    regenerated = render_png(
        source["rendered_lines"],
        width=source["width"],
        height=source["height"],
        scale=source["scale"],
    )
    committed = DEFAULT_INPUT.read_bytes()
    regenerated_textract = textract_response(
        source["retained_ocr_lines"],
        source["line_confidence"],
        width=source["width"],
        height=source["height"],
        scale=source["scale"],
    )
    committed_textract = json.loads(
        DEFAULT_TEXTRACT_REPLAY.read_text(encoding="utf-8")
    )

    assert committed.startswith(b"\x89PNG\r\n\x1a\n")
    assert regenerated == committed
    assert regenerated_textract == committed_textract
    assert source["synthetic"] is True
    assert "NOT A REAL CREDENTIAL" in source["rendered_lines"][0]
    assert source["rendered_lines"][5].endswith("HI")
    assert source["retained_ocr_lines"][5].endswith("Hl")


def test_offline_vertical_slice_normalizes_ocr_and_validates_draft(
    tmp_path: Path,
) -> None:
    output = tmp_path / "ocr-run.json"
    record = run_vertical_slice(
        offline=True,
        output_path=output,
    )

    assert record["mode"] == "offline-retained-replay"
    assert record["ocr"]["provider"] == "amazon-textract"
    assert "JURISDICTION: Hl" in record["ocr"]["text"]
    assert len(record["ocr"]["content_sha256"]) == 64
    assert len(record["ocr"]["ocr_output_sha256"]) == 64
    assert record["gates"] == {
        "ocr_succeeded_before_model_extraction": True,
        "draft_schema_valid": True,
        "draft_only_no_activation": True,
        "evidence_references_valid": True,
    }
    assert record["extraction"]["draft"]["status"] == "draft"
    assert record["extraction"]["mode"] == "retained-real-bedrock-response"
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == record


def test_ocr_failure_prevents_bedrock_call() -> None:
    class FailingOcr:
        def detect(self, document: bytes, **kwargs: Any) -> Any:
            raise OcrError("synthetic invalid OCR")

    class RecordingModel:
        calls = 0

        def extract(self, **kwargs: Any) -> Any:
            self.calls += 1
            raise AssertionError("Bedrock must not be called")

    model = RecordingModel()
    with pytest.raises(OcrError, match="synthetic invalid OCR"):
        run_vertical_slice(
            ocr_adapter=FailingOcr(),
            model_adapter=model,
        )
    assert model.calls == 0


def test_injected_model_receives_normalized_ocr_payload() -> None:
    retained = next(
        json.loads(line)
        for line in (
            ROOT
            / "artifacts"
            / "evaluation"
            / "20260730T085655.959974Z"
            / "results.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if json.loads(line)["case_id"] == "final-01-clean-standard"
    )
    response = SimpleNamespace(
        raw_text=retained["raw_response"],
        model_id="fake-qwen",
        region="us-west-2",
        request_id="fake-request",
        started_at=SimpleNamespace(isoformat=lambda: "2026-07-30T00:00:00+00:00"),
        completed_at=SimpleNamespace(isoformat=lambda: "2026-07-30T00:00:01+00:00"),
        latency_ms=1000,
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        estimated_cost_usd=0.001,
    )

    class RecordingModel:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def extract(self, **kwargs: Any) -> Any:
            self.calls.append(kwargs)
            return response

    class RetainedClient:
        def detect_document_text(self, **kwargs: Any) -> dict[str, Any]:
            return json.loads(DEFAULT_TEXTRACT_REPLAY.read_text(encoding="utf-8"))

    from caretrust.adapters.ocr import TextractOcrAdapter

    model = RecordingModel()
    record = run_vertical_slice(
        ocr_adapter=TextractOcrAdapter(client=RetainedClient()),
        model_adapter=model,
    )

    assert len(model.calls) == 1
    request = model.calls[0]
    payload = json.loads(request["user_text"])
    assert payload["document"]["ocr_text"] == record["ocr"]["text"]
    assert payload["fixed_output_identifiers"]["evidence_id"] == (
        "artifact:final-01-clean-standard"
    )
    assert request["json_schema"] == json.loads(
        DEFAULT_SCHEMA.read_text(encoding="utf-8")
    )
    assert record["extraction"]["mode"] == "live-bedrock-converse"
