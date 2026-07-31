from scripts.run_intent_compiler_bedrock_40_v2 import (
    PROMPT,
    ordered_cases,
)


def test_corrected_protocol_exposes_canonical_span_ids_before_inference() -> None:
    cases = ordered_cases()
    assert len(cases) == 40
    assert "span_id" in PROMPT
    for case in cases:
        spans = case["retained_spans"]
        assert spans == [
            {
                "span_id": f"{case['case_id']}:full-text",
                "quote": case["utterance"],
                "start_char": 0,
                "end_char": len(case["utterance"]),
            }
        ]
