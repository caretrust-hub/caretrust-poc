"""Deterministically analyze the frozen corrected Smart40 v2 artifacts."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts" / "validation" / "intent-compiler-bedrock-40-v2"


def citations(value: Any) -> Iterator[dict[str, str]]:
    if isinstance(value, dict):
        if isinstance(value.get("span_id"), str) and isinstance(
            value.get("quote"), str
        ):
            yield {"span_id": value["span_id"], "quote": value["quote"]}
        for child in value.values():
            yield from citations(child)
    elif isinstance(value, list):
        for child in value:
            yield from citations(child)


def analyze() -> dict[str, Any]:
    config = json.loads((RUN / "frozen-config.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (RUN / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = {item["case_id"]: item for item in config["ordered_cases"]}
    citation_present = 0
    citation_valid = 0
    validation_errors: Counter[str] = Counter()
    for record in records:
        raw = json.loads(record["raw_response"]) if record.get("raw_response") else {}
        found = list(citations(raw))
        citation_present += bool(found)
        case = cases[record["case_id"]]
        expected_span_id = f"{record['case_id']}:full-text"
        citation_valid += bool(found) and all(
            item["span_id"] == expected_span_id
            and item["quote"] in case["utterance"]
            for item in found
        )
        for error in (
            record.get("deterministic_result", {}).get(
                "candidate_validation_errors", []
            )
        ):
            validation_errors[error] += 1

    summary = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
    result = {
        "analysis_type": "deterministic_posthoc_over_frozen_v2",
        "frozen_config_sha256": config["freeze_sha256"],
        "record_count": len(records),
        "raw_response_has_citation": citation_present,
        "raw_response_all_citations_use_allowed_span_and_exact_quote": citation_valid,
        "full_model_candidate_accepted": summary["metrics"][
            "model_candidate_accepted"
        ],
        "safety_rejections": summary["metrics"]["safety_rejections"],
        "candidate_validation_error_counts": dict(validation_errors),
        "interpretation": (
            "Exposing canonical span IDs corrected the v1 citation-transport "
            "defect: every raw response cited an allowed span and exact source "
            "quote. Full candidate acceptance remained zero because the prompt "
            "did not adequately supply or require canonical identity and bounded "
            "vocabulary mappings. Deterministic fallback quality must not be "
            "reported as model-candidate quality."
        ),
        "next_protocol_change": (
            "Freeze the delegate directory, allowed vocabularies, and required "
            "output keys in model input; score partial candidate fields before "
            "deterministic fallback."
        ),
    }
    return result


def main() -> None:
    result = analyze()
    (RUN / "posthoc-analysis.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (RUN / "POSTHOC-ANALYSIS.md").write_text(
        "# Smart40 v2 deterministic post-hoc analysis\n\n"
        "This analysis reads only the frozen configuration and retained results. "
        "It does not rerun or relabel any model output.\n\n"
        f"- Retained records: **{result['record_count']}**\n"
        f"- Raw responses containing citations: "
        f"**{result['raw_response_has_citation']}/{result['record_count']}**\n"
        f"- Raw responses whose citations all use the allowed span ID and an "
        f"exact source quote: "
        f"**{result['raw_response_all_citations_use_allowed_span_and_exact_quote']}"
        f"/{result['record_count']}**\n"
        f"- Full model candidates accepted: "
        f"**{result['full_model_candidate_accepted']['correct']}/"
        f"{result['full_model_candidate_accepted']['count']} completed "
        f"fallback records**\n"
        f"- Safety rejections: **{result['safety_rejections']}**\n\n"
        "## Interpretation\n\n"
        f"{result['interpretation']}\n\n"
        "## Next protocol change\n\n"
        f"{result['next_protocol_change']}\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
