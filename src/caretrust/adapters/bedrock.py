"""Amazon Bedrock implementation of the provider-neutral model boundary.

Only synthetic evidence may be sent through this adapter. Provider response
metadata is normalized here so no downstream service depends on Bedrock-specific
response shapes.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol

DEFAULT_MODEL_ID = "qwen.qwen3-32b-v1:0"
DEFAULT_REGION = "us-west-2"

# Qwen3 32B on-demand reference rates recorded for us-west-2 on 2026-07-29.
# They remain configurable because AWS pricing can change.
DEFAULT_INPUT_USD_PER_MILLION = 0.15
DEFAULT_OUTPUT_USD_PER_MILLION = 0.60


class ConverseClient(Protocol):
    """Small portion of the Bedrock Runtime client used by the adapter."""

    def converse(self, **kwargs: Any) -> Mapping[str, Any]:
        """Send a Converse request."""


@dataclass(frozen=True)
class ModelResponse:
    """Provider-neutral record of one structured inference response."""

    model_id: str
    region: str
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    raw_text: str
    parsed_json: dict[str, Any]
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    stop_reason: str | None
    request_id: str | None


class BedrockModelAdapter:
    """Invoke Bedrock Converse with a strict JSON Schema output contract."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        region: str = DEFAULT_REGION,
        client: ConverseClient | None = None,
        input_usd_per_million: float | None = None,
        output_usd_per_million: float | None = None,
    ) -> None:
        self.model_id = model_id
        self.region = region
        self.input_usd_per_million = _env_rate(
            "CARETRUST_INPUT_USD_PER_MILLION",
            input_usd_per_million,
            DEFAULT_INPUT_USD_PER_MILLION,
        )
        self.output_usd_per_million = _env_rate(
            "CARETRUST_OUTPUT_USD_PER_MILLION",
            output_usd_per_million,
            DEFAULT_OUTPUT_USD_PER_MILLION,
        )

        if client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - environment guard
                raise RuntimeError(
                    "boto3 is required for live Bedrock inference; install the "
                    "project's AWS optional dependency"
                ) from exc
            client = boto3.client("bedrock-runtime", region_name=region)
        self._client = client

    def extract(
        self,
        *,
        system_prompt: str,
        user_text: str,
        json_schema: Mapping[str, Any],
        schema_name: str = "caretrust_draft_credential_claim",
        schema_description: str = (
            "Evidence-linked unverified draft of a synthetic caregiver credential"
        ),
        max_tokens: int = 2_500,
        temperature: float = 0.0,
        request_metadata: Mapping[str, str] | None = None,
    ) -> ModelResponse:
        """Return a parsed structured response and normalized run metadata."""

        if not system_prompt.strip():
            raise ValueError("system_prompt must not be blank")
        if not user_text.strip():
            raise ValueError("user_text must not be blank")
        if json_schema.get("type") != "object":
            raise ValueError("json_schema must describe a top-level object")

        metadata = {
            "caretrust_component": "credential_extraction",
            "caretrust_data": "synthetic_only",
        }
        if request_metadata:
            metadata.update({str(key): str(value) for key, value in request_metadata.items()})

        request = {
            "modelId": self.model_id,
            "system": [{"text": system_prompt}],
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_text}],
                }
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
            "outputConfig": {
                "textFormat": {
                    "type": "json_schema",
                    "structure": {
                        "jsonSchema": {
                            "schema": json.dumps(
                                json_schema,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            "name": schema_name,
                            "description": schema_description,
                        }
                    },
                }
            },
            "requestMetadata": metadata,
        }

        started_at = datetime.now(UTC)
        started_clock = time.perf_counter()
        response = self._client.converse(**request)
        completed_at = datetime.now(UTC)
        elapsed_ms = round((time.perf_counter() - started_clock) * 1_000)

        raw_text = _response_text(response)
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            raise ValueError("structured model response must be a JSON object")

        usage = response.get("usage") or {}
        input_tokens = _optional_int(usage.get("inputTokens"))
        output_tokens = _optional_int(usage.get("outputTokens"))
        total_tokens = _optional_int(usage.get("totalTokens"))
        cost = self.estimate_cost(input_tokens, output_tokens)

        response_metadata = response.get("ResponseMetadata") or {}
        return ModelResponse(
            model_id=self.model_id,
            region=self.region,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=elapsed_ms,
            raw_text=raw_text,
            parsed_json=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            stop_reason=_optional_str(response.get("stopReason")),
            request_id=_optional_str(response_metadata.get("RequestId")),
        )

    def estimate_cost(
        self,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> float | None:
        """Estimate inference cost from configured per-million token rates."""

        if input_tokens is None or output_tokens is None:
            return None
        cost = (
            input_tokens * self.input_usd_per_million
            + output_tokens * self.output_usd_per_million
        ) / 1_000_000
        return round(cost, 8)


def _response_text(response: Mapping[str, Any]) -> str:
    output = response.get("output") or {}
    message = output.get("message") or {}
    content = message.get("content") or []
    text_blocks = [
        block["text"]
        for block in content
        if isinstance(block, Mapping) and isinstance(block.get("text"), str)
    ]
    if not text_blocks:
        raise ValueError("Bedrock response did not contain a text block")
    return "".join(text_blocks).strip()


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _env_rate(name: str, explicit: float | None, default: float) -> float:
    value = explicit if explicit is not None else float(os.getenv(name, default))
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value
