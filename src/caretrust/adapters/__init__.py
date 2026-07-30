"""Replaceable external-service adapters for CareTrust."""

from caretrust.adapters.bedrock import BedrockModelAdapter, ModelResponse
from caretrust.adapters.ocr import (
    OcrAdapter,
    OcrError,
    OcrEvidenceSpan,
    OcrResult,
    TextractOcrAdapter,
)

__all__ = [
    "BedrockModelAdapter",
    "ModelResponse",
    "OcrAdapter",
    "OcrError",
    "OcrEvidenceSpan",
    "OcrResult",
    "TextractOcrAdapter",
]
