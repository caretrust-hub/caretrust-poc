"""Contract tests for OCR normalization without AWS calls."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from caretrust.adapters.ocr import OcrError, TextractOcrAdapter


def _block(
    block_type: str,
    text: str,
    *,
    confidence: float = 98.5,
    left: float = 0.1,
    top: float = 0.2,
    width: float = 0.4,
    height: float = 0.05,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "BlockType": block_type,
        "Text": text,
        "Confidence": confidence,
        "Page": page,
        "Geometry": {
            "BoundingBox": {
                "Left": left,
                "Top": top,
                "Width": width,
                "Height": height,
            }
        },
    }


class FakeTextractClient:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.last_request: dict[str, Any] | None = None

    def detect_document_text(self, **kwargs: Any) -> Any:
        self.last_request = kwargs
        return self.response


def test_textract_normalizes_lines_words_hashes_and_geometry() -> None:
    client = FakeTextractClient(
        {
            "Blocks": [
                {"BlockType": "PAGE", "Page": 1},
                _block("WORD", "NAME:", left=0.1, top=0.1, width=0.08),
                _block(
                    "LINE",
                    "NAME: LEILANI TESTPERSON",
                    confidence=97.25,
                    left=0.1,
                    top=0.1,
                    width=0.55,
                ),
                _block(
                    "LINE",
                    "JURISDICTION: Hl",
                    confidence=87.3,
                    left=0.1,
                    top=0.2,
                    width=0.35,
                ),
                _block("WORD", "Hl", confidence=86.9, left=0.39, top=0.2),
            ],
            "ResponseMetadata": {"RequestId": "synthetic-request"},
        }
    )
    document = b"\x89PNG\r\n\x1a\nsynthetic"
    result = TextractOcrAdapter(client=client).detect(
        document,
        content_type="image/png",
        source_filename="synthetic.png",
        artifact_id="artifact:ocr-test",
    )

    assert client.last_request == {"Document": {"Bytes": document}}
    assert result.text == "NAME: LEILANI TESTPERSON\nJURISDICTION: Hl"
    assert result.content_sha256 == hashlib.sha256(document).hexdigest()
    assert result.request_id == "synthetic-request"
    assert [span.block_type for span in result.spans] == [
        "LINE",
        "WORD",
        "LINE",
        "WORD",
    ]
    first = result.spans[0]
    assert first.confidence == pytest.approx(0.9725)
    assert first.evidence_span.start_char == 0
    assert first.evidence_span.end_char == len("NAME: LEILANI TESTPERSON")
    assert first.evidence_span.region is not None
    assert first.evidence_span.region.page == 1
    assert first.evidence_span.region.x == pytest.approx(0.1)
    second_line = result.spans[2]
    assert second_line.confidence == pytest.approx(0.873)
    assert second_line.evidence_span.start_char == len(
        "NAME: LEILANI TESTPERSON\n"
    )
    assert result.spans[1].evidence_span.start_char is None

    normalized = result.normalized_output()
    expected_hash = hashlib.sha256(
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert result.ocr_output_sha256 == expected_hash

    artifact = result.to_evidence_artifact(
        artifact_id="artifact:ocr-test",
        fixture_id="fixture:ocr-test",
        aggregate_span_id="span:aggregate",
    )
    assert artifact.content_type == "image/png"
    assert artifact.ocr_text == result.text
    assert artifact.spans[-1].span_id == "span:aggregate"
    assert artifact.spans[-1].quote == result.text


@pytest.mark.parametrize(
    ("document", "content_type", "response", "message"),
    [
        (b"x", "text/plain", {"Blocks": []}, "unsupported OCR content type"),
        (b"", "image/png", {"Blocks": []}, "must not be empty"),
        (b"x", "image/png", {}, "no Blocks"),
        (b"x", "image/png", {"Blocks": []}, "no Blocks"),
        (b"x", "image/png", {"Blocks": [{"BlockType": "PAGE"}]}, "no LINE"),
        (b"x", "image/png", {"Blocks": ["bad"]}, "must be objects"),
        (
            b"x",
            "image/png",
            {"Blocks": [_block("WORD", "ONLY")]},
            "no LINE",
        ),
    ],
)
def test_textract_fails_closed_for_unsupported_empty_or_bad_responses(
    document: bytes,
    content_type: str,
    response: Any,
    message: str,
) -> None:
    adapter = TextractOcrAdapter(client=FakeTextractClient(response))
    with pytest.raises(OcrError, match=message):
        adapter.detect(
            document,
            content_type=content_type,
            source_filename="synthetic.png",
            artifact_id="artifact:test",
        )


@pytest.mark.parametrize(
    "line",
    [
        _block("LINE", ""),
        _block("LINE", "TEXT", confidence=101),
        _block("LINE", "TEXT", confidence=float("nan")),
        _block("LINE", "TEXT", left=-0.1),
        _block("LINE", "TEXT", left=float("inf")),
        _block("LINE", "TEXT", left=0.8, width=0.3),
        {
            "BlockType": "LINE",
            "Text": "TEXT",
            "Confidence": 99,
            "Page": 1,
        },
    ],
)
def test_textract_rejects_malformed_text_blocks(line: dict[str, Any]) -> None:
    adapter = TextractOcrAdapter(
        client=FakeTextractClient({"Blocks": [line]})
    )
    with pytest.raises(OcrError):
        adapter.detect(
            b"synthetic",
            content_type="image/png",
            source_filename="synthetic.png",
            artifact_id="artifact:test",
        )


def test_textract_wraps_provider_failure_as_ocr_error() -> None:
    class FailingClient:
        def detect_document_text(self, **kwargs: Any) -> Mapping[str, Any]:
            raise TimeoutError("synthetic timeout")

    adapter = TextractOcrAdapter(client=FailingClient())
    with pytest.raises(OcrError, match="synthetic timeout"):
        adapter.detect(
            b"synthetic",
            content_type="image/png",
            source_filename="synthetic.png",
            artifact_id="artifact:test",
        )
