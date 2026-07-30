"""Provider-neutral OCR contracts and an Amazon Textract implementation.

The adapter treats OCR as untrusted evidence processing. A malformed or empty
provider response raises :class:`OcrError`; callers must not continue to model
extraction after that failure.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

from caretrust.models import EvidenceArtifact, EvidenceSpan, SourceRegion

SUPPORTED_CONTENT_TYPES = frozenset({"image/png", "image/jpeg"})


class OcrError(RuntimeError):
    """OCR failed closed and produced no evidence artifact."""


class DetectDocumentTextClient(Protocol):
    """Small portion of the Amazon Textract client used by this adapter."""

    def detect_document_text(self, **kwargs: Any) -> Mapping[str, Any]:
        """Detect text in one document supplied as bytes."""


@dataclass(frozen=True)
class OcrEvidenceSpan:
    """Provider-neutral OCR block linked to a CareTrust evidence span."""

    block_type: Literal["LINE", "WORD"]
    confidence: float
    evidence_span: EvidenceSpan

    def to_record(self) -> dict[str, Any]:
        return {
            "block_type": self.block_type,
            "confidence": self.confidence,
            "span": self.evidence_span.model_dump(mode="json"),
        }


@dataclass(frozen=True)
class OcrResult:
    """Normalized OCR result with hashes suitable for retention and replay."""

    provider: str
    operation: str
    content_type: str
    source_filename: str
    content_sha256: str
    ocr_output_sha256: str
    text: str
    spans: tuple[OcrEvidenceSpan, ...]
    request_id: str | None = None

    def normalized_output(self) -> dict[str, Any]:
        """Return the deterministic payload covered by ``ocr_output_sha256``."""

        return {
            "provider": self.provider,
            "operation": self.operation,
            "content_type": self.content_type,
            "source_filename": self.source_filename,
            "content_sha256": self.content_sha256,
            "text": self.text,
            "spans": [span.to_record() for span in self.spans],
        }

    def to_record(self) -> dict[str, Any]:
        return {
            **self.normalized_output(),
            "ocr_output_sha256": self.ocr_output_sha256,
            "request_id": self.request_id,
        }

    def to_evidence_artifact(
        self,
        *,
        artifact_id: str,
        fixture_id: str,
        aggregate_span_id: str | None = None,
    ) -> EvidenceArtifact:
        """Project normalized OCR evidence into the existing CareTrust contract."""

        spans = [item.evidence_span for item in self.spans]
        if aggregate_span_id is not None:
            spans.append(
                EvidenceSpan(
                    span_id=aggregate_span_id,
                    artifact_id=artifact_id,
                    quote=self.text,
                    start_char=0,
                    end_char=len(self.text),
                )
            )
        return EvidenceArtifact(
            artifact_id=artifact_id,
            fixture_id=fixture_id,
            synthetic=True,
            document_type="hawaii_cna_status_record",
            content_type=self.content_type,
            source_filename=self.source_filename,
            content_sha256=self.content_sha256,
            ocr_text=self.text,
            spans=tuple(spans),
        )


class OcrAdapter(Protocol):
    """Provider-neutral OCR boundary used by the vertical slice."""

    def detect(
        self,
        document: bytes,
        *,
        content_type: str,
        source_filename: str,
        artifact_id: str,
    ) -> OcrResult:
        """Return normalized OCR evidence or raise :class:`OcrError`."""


class TextractOcrAdapter:
    """Normalize Amazon Textract ``DetectDocumentText`` into CareTrust spans."""

    provider = "amazon-textract"
    operation = "DetectDocumentText"

    def __init__(
        self,
        *,
        region: str = "us-west-2",
        client: DetectDocumentTextClient | None = None,
    ) -> None:
        self.region = region
        if client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - environment guard
                raise RuntimeError(
                    "boto3 is required for live Textract OCR; install the "
                    "project's AWS optional dependency"
                ) from exc
            client = boto3.client("textract", region_name=region)
        self._client = client

    def detect(
        self,
        document: bytes,
        *,
        content_type: str,
        source_filename: str,
        artifact_id: str,
    ) -> OcrResult:
        if content_type not in SUPPORTED_CONTENT_TYPES:
            raise OcrError(f"unsupported OCR content type: {content_type}")
        if not document:
            raise OcrError("OCR document bytes must not be empty")
        if not source_filename.strip():
            raise OcrError("OCR source_filename must not be blank")
        if not artifact_id.strip():
            raise OcrError("OCR artifact_id must not be blank")

        try:
            response = self._client.detect_document_text(
                Document={"Bytes": document}
            )
        except Exception as exc:
            raise OcrError(f"Textract DetectDocumentText failed: {exc}") from exc

        if not isinstance(response, Mapping):
            raise OcrError("Textract response must be an object")
        blocks = response.get("Blocks")
        if not isinstance(blocks, list) or not blocks:
            raise OcrError("Textract response contained no Blocks")

        normalized_blocks: list[dict[str, Any]] = []
        for index, block in enumerate(blocks):
            if not isinstance(block, Mapping):
                raise OcrError("Textract Blocks entries must be objects")
            if block.get("BlockType") in {"LINE", "WORD"}:
                normalized_blocks.append(_normalize_block(block, ordinal=index))
        if not normalized_blocks:
            raise OcrError("Textract response contained no LINE or WORD blocks")
        if not any(block["block_type"] == "LINE" for block in normalized_blocks):
            raise OcrError("Textract response contained no LINE blocks")

        normalized_blocks.sort(
            key=lambda block: (
                block["page"],
                block["top"],
                block["left"],
                0 if block["block_type"] == "LINE" else 1,
                block["ordinal"],
            )
        )
        line_blocks = [
            block for block in normalized_blocks if block["block_type"] == "LINE"
        ]
        text = "\n".join(block["text"] for block in line_blocks)
        if not text.strip():
            raise OcrError("Textract LINE blocks contained no usable text")

        line_offsets: dict[int, tuple[int, int]] = {}
        cursor = 0
        for block in line_blocks:
            start = cursor
            cursor += len(block["text"])
            line_offsets[block["ordinal"]] = (start, cursor)
            cursor += 1

        spans: list[OcrEvidenceSpan] = []
        counters = {"LINE": 0, "WORD": 0}
        for block in normalized_blocks:
            block_type = block["block_type"]
            counters[block_type] += 1
            offsets = (
                line_offsets[block["ordinal"]]
                if block_type == "LINE"
                else (None, None)
            )
            evidence_span = EvidenceSpan(
                span_id=(
                    f"{artifact_id}:ocr:{block_type.lower()}:{counters[block_type]:03d}"
                ),
                artifact_id=artifact_id,
                quote=block["text"],
                start_char=offsets[0],
                end_char=offsets[1],
                region=SourceRegion(
                    page=block["page"],
                    x=block["left"],
                    y=block["top"],
                    width=block["width"],
                    height=block["height"],
                ),
            )
            spans.append(
                OcrEvidenceSpan(
                    block_type=block_type,
                    confidence=block["confidence"],
                    evidence_span=evidence_span,
                )
            )

        content_hash = hashlib.sha256(document).hexdigest()
        deterministic_output = {
            "provider": self.provider,
            "operation": self.operation,
            "content_type": content_type,
            "source_filename": source_filename,
            "content_sha256": content_hash,
            "text": text,
            "spans": [span.to_record() for span in spans],
        }
        output_hash = hashlib.sha256(
            json.dumps(
                deterministic_output,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        metadata = response.get("ResponseMetadata")
        request_id = (
            str(metadata.get("RequestId"))
            if isinstance(metadata, Mapping) and metadata.get("RequestId") is not None
            else None
        )
        return OcrResult(
            provider=self.provider,
            operation=self.operation,
            content_type=content_type,
            source_filename=source_filename,
            content_sha256=content_hash,
            ocr_output_sha256=output_hash,
            text=text,
            spans=tuple(spans),
            request_id=request_id,
        )


def _normalize_block(block: Mapping[str, Any], *, ordinal: int) -> dict[str, Any]:
    """Validate one Textract text block without silently accepting bad data."""

    block_type = block.get("BlockType")
    if block_type not in {"LINE", "WORD"}:
        raise OcrError(f"unsupported Textract text block type: {block_type!r}")
    text = block.get("Text")
    if not isinstance(text, str) or not text.strip():
        raise OcrError(f"Textract {block_type} block contained blank Text")
    confidence = block.get("Confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise OcrError(f"Textract {block_type} block contained invalid Confidence")
    if not math.isfinite(float(confidence)) or confidence < 0 or confidence > 100:
        raise OcrError(f"Textract {block_type} Confidence was outside 0..100")
    page = block.get("Page", 1)
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise OcrError(f"Textract {block_type} block contained invalid Page")

    geometry = block.get("Geometry")
    if not isinstance(geometry, Mapping):
        raise OcrError(f"Textract {block_type} block contained no Geometry")
    box = geometry.get("BoundingBox")
    if not isinstance(box, Mapping):
        raise OcrError(f"Textract {block_type} block contained no BoundingBox")
    coordinates: dict[str, float] = {}
    for provider_name, normalized_name in (
        ("Left", "left"),
        ("Top", "top"),
        ("Width", "width"),
        ("Height", "height"),
    ):
        value = box.get(provider_name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OcrError(
                f"Textract {block_type} BoundingBox.{provider_name} was invalid"
            )
        if not math.isfinite(float(value)) or value < 0 or value > 1:
            raise OcrError(
                f"Textract {block_type} BoundingBox.{provider_name} was outside 0..1"
            )
        coordinates[normalized_name] = float(value)
    if coordinates["left"] + coordinates["width"] > 1.000001:
        raise OcrError(f"Textract {block_type} BoundingBox exceeded page width")
    if coordinates["top"] + coordinates["height"] > 1.000001:
        raise OcrError(f"Textract {block_type} BoundingBox exceeded page height")

    return {
        "block_type": block_type,
        "text": text.strip(),
        "confidence": round(float(confidence) / 100, 6),
        "page": page,
        "ordinal": ordinal,
        **coordinates,
    }
