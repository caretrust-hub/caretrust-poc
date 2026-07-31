from scripts.analyze_intent_compiler_bedrock_40_v2 import analyze


def test_v2_posthoc_analysis_keeps_model_and_fallback_quality_separate() -> None:
    result = analyze()
    assert result["record_count"] == 40
    assert result["raw_response_has_citation"] == 40
    assert (
        result["raw_response_all_citations_use_allowed_span_and_exact_quote"] == 40
    )
    assert result["full_model_candidate_accepted"]["correct"] == 0
    assert "must not be reported as model-candidate quality" in result[
        "interpretation"
    ]
