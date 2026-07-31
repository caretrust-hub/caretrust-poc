from caretrust.compiler import INTENT_MODEL_REQUIRED_OUTPUT_KEYS
from scripts.run_intent_compiler_bedrock_40_v3 import (
    cases,
    frozen_configuration,
)


def test_v3_cases_and_gold_are_frozen_before_inference() -> None:
    rows = cases()
    assert len(rows) == 40
    assert [row["ordinal"] for row in rows] == list(range(1, 41))
    assert all(row["synthetic"] is True for row in rows)
    assert rows[32]["gold"]["hitl"] is True
    assert rows[35]["gold"]["hitl"] is False
    assert rows[35]["gold"]["audiences"] == ["app:synthetic-care-portal"]


def test_v3_freezes_exact_executed_request_contract() -> None:
    config = frozen_configuration()
    assert config["case_count"] == 40
    assert config["freeze_sha256"]
    for case in config["ordered_cases"]:
        request = case["model_request"]
        assert case["model_request_sha256"]
        assert set(request["json_schema"]["required"]) == set(
            INTENT_MODEL_REQUIRED_OUTPUT_KEYS
        )
        assert "delegate_directory" in request["user_text"]
        assert "allowed_vocabulary" in request["user_text"]
        assert request["max_tokens"] == 1_200
        assert request["temperature"] == 0.0
