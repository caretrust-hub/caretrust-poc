from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from caretrust.adapters.bedrock import ModelResponse
from caretrust.evaluation import (
    EvaluationRunner,
    EvaluationSettings,
    build_model_payload,
    calculate_metrics,
    freeze_configuration,
    load_cases,
    write_frozen_configuration,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeAdapter:
    model_id = "fake.model"
    region = "us-test-1"
    input_usd_per_million = 0.15
    output_usd_per_million = 0.60

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.payloads: list[dict[str, Any]] = []

    def extract(self, **kwargs: Any) -> ModelResponse:
        self.payloads.append(json.loads(kwargs["user_text"]))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        now = datetime.now(UTC)
        raw = json.dumps(outcome)
        return ModelResponse(
            model_id=self.model_id,
            region=self.region,
            started_at=now,
            completed_at=now,
            latency_ms=12,
            raw_text=raw,
            parsed_json=outcome,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.000045,
            stop_reason="end_turn",
            request_id="fake-request",
        )


def read_fixture(name: str) -> dict[str, Any]:
    return json.loads(
        (ROOT / "fixtures" / "cna" / "smoke" / name).read_text(encoding="utf-8")
    )


def write_case_set(tmp_path: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    clean = read_fixture("clean.json")
    failed = read_fixture("missing-identifier.json")
    clean["fixed_output_identifiers"] = {
        "draft_id": clean["expected"]["draft"]["draft_id"],
        "evidence_id": clean["input"]["artifact_id"],
        "subject_ref": clean["expected"]["draft"]["subject_ref"],
    }
    failed["fixed_output_identifiers"] = {
        "draft_id": failed["expected"]["draft"]["draft_id"],
        "evidence_id": failed["input"]["artifact_id"],
        "subject_ref": failed["expected"]["draft"]["subject_ref"],
    }
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    entries = []
    for name, fixture in (("clean.json", clean), ("failed.json", failed)):
        path = case_dir / name
        path.write_text(json.dumps(fixture), encoding="utf-8")
        entries.append({"case_id": fixture["case_id"], "file": name})
    manifest = {"synthetic": True, "fixtures": entries}
    manifest_path = case_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, clean, failed


def test_model_payload_excludes_gold_answers() -> None:
    fixture = read_fixture("clean.json")
    fixture["fixed_output_identifiers"] = {
        "draft_id": "draft:smoke-clean",
        "evidence_id": "artifact:smoke-clean",
        "subject_ref": "person:synthetic-leilani-kealoha",
    }
    payload_text = build_model_payload(fixture)
    payload = json.loads(payload_text)

    assert "expected" not in payload_text
    assert "gold" not in payload_text
    assert payload["document"]["ocr_text"] == fixture["input"]["ocr_text"]
    assert "fields" not in payload


def test_runner_retains_provider_failure_and_freezes_before_calls(
    tmp_path: Path,
) -> None:
    manifest_path, clean, _failed = write_case_set(tmp_path)
    adapter = FakeAdapter(
        [clean["expected"]["draft"], RuntimeError("synthetic provider outage")]
    )
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("synthetic prompt", encoding="utf-8")
    policy = tmp_path / "policy.py"
    policy.write_text("POLICY_VERSION = 1\n", encoding="utf-8")
    output_root = tmp_path / "output"
    runner = EvaluationRunner(
        adapter=adapter,  # type: ignore[arg-type]
        settings=EvaluationSettings(
            model_id=adapter.model_id,
            region=adapter.region,
            budget_ceiling_usd=10,
        ),
        manifest_path=manifest_path,
        prompt_path=prompt,
        schema_path=ROOT / "schemas" / "draft-credential-claim.schema.json",
        policy_paths=(policy,),
        output_root=output_root,
    )

    summary = runner.run(run_id="test-run")

    run_dir = output_root / "test-run"
    frozen = json.loads((run_dir / "frozen-config.json").read_text())
    lines = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text().splitlines()
    ]
    retained_json = json.loads((run_dir / "results.json").read_text())
    assert frozen["state"] == "frozen_before_inference"
    assert frozen["case_order"] == ["smoke-clean", "smoke-missing-identifier"]
    assert len(lines) == len(retained_json) == summary["case_count"] == 2
    assert lines[0]["schema_valid"] is True
    assert lines[1]["status"] == "failed"
    assert lines[1]["failure_stage"] == "invocation_or_parse"
    assert "synthetic provider outage" in lines[1]["validation_errors"][0]
    assert summary["metrics"]["schema_validity"] == {"count": 1, "rate": 0.5}
    assert all("expected" not in json.dumps(payload) for payload in adapter.payloads)


def test_budget_ceiling_retains_uninvoked_cases(tmp_path: Path) -> None:
    manifest_path, clean, _failed = write_case_set(tmp_path)
    adapter = FakeAdapter([clean["expected"]["draft"]])
    # This leaves less than the reserved maximum cost of one invocation.
    settings = EvaluationSettings(
        model_id=adapter.model_id,
        region=adapter.region,
        budget_ceiling_usd=0.01,
        prior_phase_spend_usd=0.009,
        max_input_tokens=32_768,
        max_tokens=2_500,
    )
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("synthetic prompt", encoding="utf-8")
    policy = tmp_path / "policy.py"
    policy.write_text("POLICY_VERSION = 1\n", encoding="utf-8")
    runner = EvaluationRunner(
        adapter=adapter,  # type: ignore[arg-type]
        settings=settings,
        manifest_path=manifest_path,
        prompt_path=prompt,
        schema_path=ROOT / "schemas" / "draft-credential-claim.schema.json",
        policy_paths=(policy,),
        output_root=tmp_path / "output",
    )

    summary = runner.run(run_id="budget-run")
    records = json.loads(
        (tmp_path / "output" / "budget-run" / "results.json").read_text()
    )

    assert adapter.payloads == []
    assert summary["retained_record_count"] == 2
    assert all(record["failure_stage"] == "budget" for record in records)
    assert summary["phase_cumulative_accounted_cost_usd"] == 0.009


def test_metrics_are_calculated_from_outputs_and_gold_without_edits() -> None:
    clean = read_fixture("clean.json")
    ambiguous = read_fixture("ambiguous-date.json")
    clean_draft = clean["expected"]["draft"]
    unsafe_ambiguous = copy.deepcopy(ambiguous["expected"]["draft"])
    unsafe_ambiguous["fields"]["original_or_issue_date"].update(
        value="03/04/2025",
        normalized_value="2025-03-04",
        confidence=0.8,
    )
    unsafe_ambiguous["uncertainties"] = []
    unsafe_ambiguous["blocking_issues"] = []
    records = [
        {
            "case_id": clean["case_id"],
            "schema_valid": True,
            "draft": clean_draft,
            "latency_ms": 10,
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "estimated_cost_usd": 0.001,
        },
        {
            "case_id": ambiguous["case_id"],
            "schema_valid": True,
            "draft": unsafe_ambiguous,
            "latency_ms": 30,
            "input_tokens": 200,
            "output_tokens": 40,
            "total_tokens": 240,
            "estimated_cost_usd": 0.002,
        },
    ]

    metrics = calculate_metrics(
        records,
        {clean["case_id"]: clean, ambiguous["case_id"]: ambiguous},
    )

    assert metrics["field"]["true_positive"] == 16
    assert metrics["field"]["false_positive"] == 1
    assert metrics["field"]["false_negative"] == 0
    assert metrics["normalized_exact_record_match"] == {"count": 1, "rate": 0.5}
    assert metrics["uncertainty"]["false_negative"] == 1
    assert metrics["false_clear"] == {
        "count": 1,
        "eligible_material_case_count": 1,
        "rate": 1.0,
    }
    assert metrics["review_routing_agreement"] == {"count": 1, "rate": 0.5}
    assert metrics["corrections_required_count"] == 1
    assert metrics["schema_validity"] == {"count": 2, "rate": 1.0}
    assert metrics["latency"]["mean_ms"] == 20
    assert metrics["tokens"] == {"input": 300, "output": 60, "total": 360}
    assert metrics["estimated_cost_usd"] == pytest.approx(0.003)
    assert metrics["false_active_claims"] == 0
    assert metrics["draft_authorization_permits"] == 0


def test_freeze_artifact_is_stable_and_refuses_changed_inputs(
    tmp_path: Path,
) -> None:
    manifest_path, _clean, _failed = write_case_set(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("synthetic prompt v1", encoding="utf-8")
    policy = tmp_path / "policy.py"
    policy.write_text("POLICY_VERSION = 1\n", encoding="utf-8")
    settings = EvaluationSettings(model_id="fake.model", region="us-test-1")
    arguments = {
        "settings": settings,
        "manifest_path": manifest_path,
        "prompt_path": prompt,
        "schema_path": ROOT / "schemas" / "draft-credential-claim.schema.json",
        "policy_paths": (policy,),
    }
    frozen = freeze_configuration(**arguments)
    destination = tmp_path / "frozen.json"

    write_frozen_configuration(destination, frozen)
    first_bytes = destination.read_bytes()
    write_frozen_configuration(destination, freeze_configuration(**arguments))

    assert destination.read_bytes() == first_bytes
    assert "created_at" not in frozen
    prompt.write_text("synthetic prompt v2", encoding="utf-8")
    changed = freeze_configuration(**arguments)
    with pytest.raises(ValueError, match="differs"):
        write_frozen_configuration(destination, changed)


def test_gold_baseline_exercises_all_final_fixture_policy_controls() -> None:
    _manifest, cases = load_cases(
        ROOT / "fixtures" / "cna" / "final" / "manifest.json"
    )
    fixtures = {case.case_id: case.fixture for case in cases}
    records = [
        {
            "case_id": case.case_id,
            "schema_valid": True,
            "draft": case.fixture["expected"]["draft"],
        }
        for case in cases
    ]

    metrics = calculate_metrics(records, fixtures)

    assert len(cases) == 20
    assert metrics["field"]["f1"] == 1.0
    assert metrics["uncertainty"]["f1"] == 1.0
    assert metrics["review_routing_agreement"]["rate"] == 1.0
    assert metrics["activation_policy_agreement"]["rate"] == 1.0
    assert metrics["authorization_policy_agreement"]["rate"] == 1.0
    assert metrics["false_active_claims"] == 0
    assert metrics["false_permits"] == 0
