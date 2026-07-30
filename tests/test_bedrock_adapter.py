"""Contract tests for the Bedrock adapter without making network calls."""

from __future__ import annotations

import json
from typing import Any

import pytest

from caretrust.adapters.bedrock import BedrockModelAdapter


class FakeConverseClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.last_request: dict[str, Any] | None = None

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.last_request = kwargs
        return self.payload


def test_structured_request_and_normalized_response() -> None:
    result_object = {"status": "draft", "evidence_refs": ["span-1"]}
    client = FakeConverseClient(
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": json.dumps(result_object)}],
                }
            },
            "usage": {
                "inputTokens": 100,
                "outputTokens": 20,
                "totalTokens": 120,
            },
            "stopReason": "end_turn",
            "ResponseMetadata": {"RequestId": "synthetic-request-id"},
        }
    )
    adapter = BedrockModelAdapter(client=client)
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "const": "draft"},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["status", "evidence_refs"],
        "additionalProperties": False,
    }

    response = adapter.extract(
        system_prompt="Extract only unverified draft values.",
        user_text="Synthetic credential evidence.",
        json_schema=schema,
        request_metadata={"caretrust_fixture": "clean"},
    )

    assert response.parsed_json == result_object
    assert response.input_tokens == 100
    assert response.output_tokens == 20
    assert response.total_tokens == 120
    assert response.estimated_cost_usd == pytest.approx(0.000027)
    assert response.request_id == "synthetic-request-id"

    assert client.last_request is not None
    assert client.last_request["modelId"] == "qwen.qwen3-32b-v1:0"
    assert (
        client.last_request["outputConfig"]["textFormat"]["type"]
        == "json_schema"
    )
    encoded_schema = client.last_request["outputConfig"]["textFormat"]["structure"][
        "jsonSchema"
    ]["schema"]
    assert json.loads(encoded_schema) == schema
    assert client.last_request["requestMetadata"]["caretrust_data"] == "synthetic_only"


def test_missing_text_block_fails_visibly() -> None:
    client = FakeConverseClient(
        {
            "output": {"message": {"role": "assistant", "content": []}},
            "usage": {},
        }
    )
    adapter = BedrockModelAdapter(client=client)

    with pytest.raises(ValueError, match="text block"):
        adapter.extract(
            system_prompt="Extract.",
            user_text="Synthetic evidence.",
            json_schema={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        )


def test_non_object_schema_rejected_before_call() -> None:
    client = FakeConverseClient({})
    adapter = BedrockModelAdapter(client=client)

    with pytest.raises(ValueError, match="top-level object"):
        adapter.extract(
            system_prompt="Extract.",
            user_text="Synthetic evidence.",
            json_schema={"type": "array", "items": {"type": "string"}},
        )
    assert client.last_request is None
