"""Frozen, consecutive evaluation for synthetic CareTrust extraction cases.

The evaluator has two deliberately separate inputs:

* the model payload, built from the fixture's synthetic ``input`` only; and
* the gold labels, read only after the response has been retained.

This separation makes it difficult to accidentally leak answers into a model
request. Every case produces a JSONL record, including provider, parsing, schema,
evidence-reference, and budget failures.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from caretrust.adapters.bedrock import (
    DEFAULT_INPUT_USD_PER_MILLION,
    DEFAULT_OUTPUT_USD_PER_MILLION,
    BedrockModelAdapter,
)
from caretrust.models import DraftCredentialClaim, UncertaintyCode

FIELD_NAMES = tuple(DraftCredentialClaim.model_fields["fields"].annotation.model_fields)
MATERIAL_UNCERTAINTY_CODES = frozenset(code.value for code in UncertaintyCode)


def canonical_json(value: Any) -> str:
    """Serialize a value reproducibly for hashing and JSONL persistence."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


@dataclass(frozen=True)
class EvaluationSettings:
    """Inference and spend settings that become part of the frozen manifest."""

    model_id: str
    region: str
    temperature: float = 0.0
    max_tokens: int = 2_500
    max_input_tokens: int = 32_768
    budget_ceiling_usd: float = 10.0
    prior_phase_spend_usd: float = 0.0
    input_usd_per_million: float = DEFAULT_INPUT_USD_PER_MILLION
    output_usd_per_million: float = DEFAULT_OUTPUT_USD_PER_MILLION

    def __post_init__(self) -> None:
        if not 0 < self.budget_ceiling_usd <= 10:
            raise ValueError("budget_ceiling_usd must be greater than zero and at most $10")
        if self.prior_phase_spend_usd < 0:
            raise ValueError("prior_phase_spend_usd must not be negative")
        if self.prior_phase_spend_usd >= self.budget_ceiling_usd:
            raise ValueError("prior spend leaves no evaluation inference budget")
        if self.input_usd_per_million < 0 or self.output_usd_per_million < 0:
            raise ValueError("reference token rates must not be negative")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.max_input_tokens < 32_768:
            raise ValueError(
                "max_input_tokens must reserve at least the Qwen3 32B context limit"
            )


@dataclass(frozen=True)
class LoadedCase:
    case_id: str
    file_name: str
    path: Path
    sha256: str
    fixture: dict[str, Any]


def load_cases(manifest_path: Path) -> tuple[dict[str, Any], tuple[LoadedCase, ...]]:
    """Load and hash a predeclared synthetic case set in manifest order."""

    manifest_path = manifest_path.resolve()
    manifest = _json_file(manifest_path)
    entries = manifest.get("fixtures")
    if not isinstance(entries, list) or not entries:
        raise ValueError("fixture manifest must contain a non-empty fixtures list")
    cases: list[LoadedCase] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("every fixture manifest entry must be an object")
        file_name = str(entry.get("file", "")).strip()
        if not file_name:
            raise ValueError("every manifest entry requires file")
        path = (manifest_path.parent / file_name).resolve()
        if manifest_path.parent not in path.parents:
            raise ValueError(f"fixture escapes manifest directory: {file_name}")
        digest = sha256_file(path)
        declared_digest = entry.get("sha256")
        if declared_digest is not None and declared_digest != digest:
            raise ValueError(f"fixture hash mismatch: {file_name}")
        fixture = _json_file(path)
        fixture_case_id = str(fixture.get("case_id", "")).strip()
        declared_case_id = str(entry.get("case_id", "")).strip()
        case_id = declared_case_id or fixture_case_id
        if not case_id:
            raise ValueError(f"fixture has no case_id: {file_name}")
        if fixture_case_id != case_id:
            raise ValueError(f"fixture case_id mismatch: {file_name}")
        if case_id in seen:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen.add(case_id)
        if fixture.get("synthetic") is not True:
            raise ValueError(f"only explicitly synthetic fixtures are allowed: {case_id}")
        cases.append(
            LoadedCase(
                case_id=case_id,
                file_name=file_name,
                path=path,
                sha256=digest,
                fixture=fixture,
            )
        )
    return manifest, tuple(cases)


def build_model_payload(fixture: Mapping[str, Any]) -> str:
    """Build a request without copying any ``gold`` or ``expected`` values."""

    case_id = str(fixture["case_id"])
    input_data = fixture.get("input")
    if not isinstance(input_data, Mapping):
        raise ValueError(f"{case_id}: input must be an object")
    artifact_id = str(input_data.get("artifact_id", "")).strip()
    if not artifact_id:
        raise ValueError(f"{case_id}: input.artifact_id is required")

    fixed = fixture.get("fixed_output_identifiers")
    if fixed is None:
        fixed = input_data.get("fixed_output_identifiers")
    if fixed is None:
        subject_ref = str(input_data.get("subject_ref", "")).strip()
        if not subject_ref:
            # The identifier is deterministic test metadata, not a gold answer.
            subject_ref = f"person:synthetic:{case_id}"
        fixed = {
            "draft_id": f"draft:{case_id}",
            "evidence_id": artifact_id,
            "subject_ref": subject_ref,
        }
    if not isinstance(fixed, Mapping):
        raise ValueError(f"{case_id}: fixed_output_identifiers must be an object")
    required_fixed = ("draft_id", "evidence_id", "subject_ref")
    if any(not str(fixed.get(key, "")).strip() for key in required_fixed):
        raise ValueError(f"{case_id}: fixed output identifiers are incomplete")
    if str(fixed["evidence_id"]) != artifact_id:
        raise ValueError(f"{case_id}: fixed evidence_id must equal input.artifact_id")

    source_spans = input_data.get("source_spans")
    if not isinstance(source_spans, list):
        raise ValueError(f"{case_id}: input.source_spans must be a list")
    payload = {
        "case_id": case_id,
        "synthetic": True,
        "fixed_output_identifiers": {
            key: str(fixed[key]) for key in required_fixed
        },
        "document": {
            "document_type": input_data.get("document_type"),
            "ocr_text": input_data.get("ocr_text"),
            "source_spans": source_spans,
        },
    }
    serialized = canonical_json(payload)
    # Defense in depth: labels must never be keys in the serialized request.
    if '"gold"' in serialized or '"expected"' in serialized:
        raise AssertionError("gold labels entered the model payload")
    return serialized


def validate_evidence_refs(
    draft: DraftCredentialClaim,
    fixture: Mapping[str, Any],
) -> list[str]:
    permitted = {
        str(span["span_id"])
        for span in fixture["input"]["source_spans"]
        if isinstance(span, Mapping) and "span_id" in span
    }
    errors: list[str] = []
    for field_name in FIELD_NAMES:
        field = getattr(draft.fields, field_name)
        invalid = sorted(set(field.evidence_refs) - permitted)
        if invalid:
            errors.append(f"fields.{field_name}: unknown evidence refs {invalid}")
    for index, uncertainty in enumerate(draft.uncertainties):
        invalid = sorted(set(uncertainty.evidence_refs) - permitted)
        if invalid:
            errors.append(f"uncertainties.{index}: unknown evidence refs {invalid}")
    return errors


def _aggregate_file_hash(paths: Sequence[Path]) -> tuple[str, dict[str, str]]:
    if len({path.name for path in paths}) != len(paths):
        raise ValueError("policy file names must be unique")
    members = {path.name: sha256_file(path) for path in paths}
    return sha256_bytes(canonical_json(members).encode("utf-8")), members


def freeze_configuration(
    *,
    settings: EvaluationSettings,
    manifest_path: Path,
    prompt_path: Path,
    schema_path: Path,
    policy_paths: Sequence[Path],
) -> dict[str, Any]:
    """Build stable pre-run configuration without constructing a model client."""

    manifest_path = manifest_path.resolve()
    prompt_path = prompt_path.resolve()
    schema_path = schema_path.resolve()
    resolved_policy_paths = tuple(path.resolve() for path in policy_paths)
    if not resolved_policy_paths:
        raise ValueError("at least one deterministic policy file must be frozen")
    _manifest, cases = load_cases(manifest_path)
    prompt_bytes = prompt_path.read_bytes()
    schema_bytes = schema_path.read_bytes()
    schema = json.loads(schema_bytes)
    if not isinstance(schema, dict):
        raise ValueError("schema must be a JSON object")
    policy_sha256, policy_members = _aggregate_file_hash(resolved_policy_paths)
    fixture_members = {case.file_name: case.sha256 for case in cases}
    maximum_case_cost = (
        settings.max_input_tokens * settings.input_usd_per_million
        + settings.max_tokens * settings.output_usd_per_million
    ) / 1_000_000
    return {
        "manifest_version": "caretrust.frozen-evaluation.v1",
        "state": "frozen_before_inference",
        "synthetic_only": True,
        "model_id": settings.model_id,
        "region": settings.region,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "max_input_tokens_for_budget_reservation": settings.max_input_tokens,
        "prompt_file": prompt_path.name,
        "prompt_sha256": sha256_bytes(prompt_bytes),
        "schema_file": schema_path.name,
        "schema_sha256": sha256_bytes(schema_bytes),
        "policy_sha256": policy_sha256,
        "policy_members": policy_members,
        "fixture_manifest_file": manifest_path.name,
        "fixture_manifest_sha256": sha256_file(manifest_path),
        "fixture_set_sha256": sha256_bytes(
            canonical_json(fixture_members).encode("utf-8")
        ),
        "fixture_members": fixture_members,
        "case_order": [case.case_id for case in cases],
        "budget_ceiling_usd": settings.budget_ceiling_usd,
        "prior_phase_spend_usd": settings.prior_phase_spend_usd,
        "reference_rates_usd_per_million_tokens": {
            "input": settings.input_usd_per_million,
            "output": settings.output_usd_per_million,
        },
        "maximum_reserved_case_cost_usd": round(maximum_case_cost, 8),
    }


def write_frozen_configuration(
    destination: Path,
    frozen: Mapping[str, Any],
) -> None:
    """Create, or verify without rewriting, a pre-run freeze artifact."""

    destination = destination.resolve()
    serialized = json.dumps(frozen, indent=2, ensure_ascii=False) + "\n"
    if destination.exists():
        existing = _json_file(destination)
        if canonical_json(existing) != canonical_json(frozen):
            raise ValueError(
                f"existing frozen configuration differs: {destination}"
            )
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialized, encoding="utf-8")


class EvaluationRunner:
    """Run every frozen case exactly once and retain all observed outcomes."""

    def __init__(
        self,
        *,
        adapter: BedrockModelAdapter,
        settings: EvaluationSettings,
        manifest_path: Path,
        prompt_path: Path,
        schema_path: Path,
        policy_paths: Sequence[Path],
        output_root: Path,
        frozen_config_path: Path | None = None,
    ) -> None:
        if adapter.model_id != settings.model_id or adapter.region != settings.region:
            raise ValueError("adapter model and region must match frozen settings")
        self.adapter = adapter
        self.settings = settings
        self.manifest_path = manifest_path.resolve()
        self.prompt_path = prompt_path.resolve()
        self.schema_path = schema_path.resolve()
        self.policy_paths = tuple(path.resolve() for path in policy_paths)
        self.output_root = output_root.resolve()
        self.frozen_config_path = (
            frozen_config_path.resolve() if frozen_config_path is not None else None
        )
        if not self.policy_paths:
            raise ValueError("at least one deterministic policy file must be frozen")

    def _maximum_case_cost(self) -> float:
        input_rate = self.settings.input_usd_per_million
        output_rate = self.settings.output_usd_per_million
        return (
            self.settings.max_input_tokens * input_rate
            + self.settings.max_tokens * output_rate
        ) / 1_000_000

    def run(self, *, run_id: str | None = None) -> dict[str, Any]:
        _manifest, cases = load_cases(self.manifest_path)
        prompt_bytes = self.prompt_path.read_bytes()
        schema_bytes = self.schema_path.read_bytes()
        prompt = prompt_bytes.decode("utf-8")
        schema = json.loads(schema_bytes)
        if not isinstance(schema, dict):
            raise ValueError("schema must be a JSON object")

        started_at = datetime.now(UTC)
        run_id = run_id or started_at.strftime("%Y%m%dT%H%M%S.%fZ")
        output_dir = self.output_root / run_id
        output_dir.mkdir(parents=True, exist_ok=False)
        frozen = freeze_configuration(
            settings=self.settings,
            manifest_path=self.manifest_path,
            prompt_path=self.prompt_path,
            schema_path=self.schema_path,
            policy_paths=self.policy_paths,
        )
        if (
            float(self.adapter.input_usd_per_million)
            != self.settings.input_usd_per_million
            or float(self.adapter.output_usd_per_million)
            != self.settings.output_usd_per_million
        ):
            raise ValueError("adapter token rates must match frozen settings")
        if self.frozen_config_path is not None:
            committed_frozen = _json_file(self.frozen_config_path)
            if canonical_json(committed_frozen) != canonical_json(frozen):
                raise ValueError(
                    "committed frozen configuration no longer matches inputs"
                )
        maximum_case_cost = self._maximum_case_cost()
        # The run copy is byte-stable with the separately committable pre-run
        # artifact and is written before the first inference call.
        (output_dir / "frozen-config.json").write_text(
            json.dumps(frozen, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        records: list[dict[str, Any]] = []
        accounted_spend = self.settings.prior_phase_spend_usd
        jsonl_path = output_dir / "results.jsonl"
        for index, case in enumerate(cases):
            record: dict[str, Any] = {
                "run_id": run_id,
                "sequence": index + 1,
                "case_id": case.case_id,
                "fixture_file": case.file_name,
                "fixture_sha256": case.sha256,
                "status": "failed",
                "schema_valid": False,
                "validation_errors": [],
            }
            # Reserve the physical maximum for the next call. This is stricter
            # than merely checking observed spend after money has been incurred.
            if accounted_spend + maximum_case_cost > self.settings.budget_ceiling_usd:
                record["validation_errors"].append(
                    "budget ceiling: maximum next-call cost cannot be reserved"
                )
                record["failure_stage"] = "budget"
            else:
                invocation_attempted = False
                invocation_cost_accounted = False
                try:
                    user_payload = build_model_payload(case.fixture)
                    invocation_attempted = True
                    response = self.adapter.extract(
                        system_prompt=prompt,
                        user_text=user_payload,
                        json_schema=schema,
                        max_tokens=self.settings.max_tokens,
                        temperature=self.settings.temperature,
                        request_metadata={
                            "caretrust_case": case.case_id,
                            "caretrust_run": run_id,
                            "caretrust_evaluation": "frozen",
                        },
                    )
                    observed_cost = response.estimated_cost_usd
                    accounted_spend += (
                        maximum_case_cost if observed_cost is None else observed_cost
                    )
                    invocation_cost_accounted = True
                    record["budget_accounted_usd"] = round(
                        maximum_case_cost if observed_cost is None else observed_cost,
                        8,
                    )
                    record.update(
                        {
                            "raw_response": response.raw_text,
                            "raw_response_sha256": sha256_bytes(
                                response.raw_text.encode("utf-8")
                            ),
                            "model_id": response.model_id,
                            "region": response.region,
                            "started_at": response.started_at.isoformat(),
                            "completed_at": response.completed_at.isoformat(),
                            "latency_ms": response.latency_ms,
                            "input_tokens": response.input_tokens,
                            "output_tokens": response.output_tokens,
                            "total_tokens": response.total_tokens,
                            "estimated_cost_usd": observed_cost,
                            "stop_reason": response.stop_reason,
                            "request_id": response.request_id,
                        }
                    )
                    draft = DraftCredentialClaim.model_validate(response.parsed_json)
                    ref_errors = validate_evidence_refs(draft, case.fixture)
                    requested = json.loads(build_model_payload(case.fixture))[
                        "fixed_output_identifiers"
                    ]
                    for key in ("draft_id", "evidence_id", "subject_ref"):
                        if getattr(draft, key) != requested[key]:
                            ref_errors.append(f"model changed fixed {key}")
                    record["draft"] = draft.model_dump(mode="json")
                    if ref_errors:
                        record["validation_errors"].extend(ref_errors)
                        record["failure_stage"] = "evidence_validation"
                    else:
                        record["status"] = "schema_valid"
                        record["schema_valid"] = True
                except ValidationError as exc:
                    record["failure_stage"] = "schema_validation"
                    record["validation_errors"].extend(
                        error["msg"] for error in exc.errors(include_url=False)
                    )
                except Exception as exc:  # each provider and parsing failure is evidence
                    # A provider failure can occur after tokens were consumed but
                    # before usage metadata returns. Reserve the physical maximum
                    # rather than silently undercounting unknown spend.
                    if invocation_attempted and not invocation_cost_accounted:
                        accounted_spend += maximum_case_cost
                        record["budget_accounted_usd"] = round(
                            maximum_case_cost, 8
                        )
                    record["failure_stage"] = "invocation_or_parse"
                    record["validation_errors"].append(
                        f"{type(exc).__name__}: {exc}"
                    )
            records.append(record)
            with jsonl_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(canonical_json(record))
                stream.write("\n")

        fixtures = {case.case_id: case.fixture for case in cases}
        metrics = calculate_metrics(records, fixtures)
        (output_dir / "results.json").write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        summary = {
            "run_id": run_id,
            "frozen_config_sha256": sha256_file(output_dir / "frozen-config.json"),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "case_count": len(cases),
            "retained_record_count": len(records),
            "current_run_accounted_cost_usd": round(
                accounted_spend - self.settings.prior_phase_spend_usd, 8
            ),
            "phase_cumulative_accounted_cost_usd": round(accounted_spend, 8),
            "metrics": metrics,
        }
        (output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return summary


def _gold(fixture: Mapping[str, Any]) -> Mapping[str, Any]:
    value = fixture.get("gold", fixture.get("expected"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{fixture.get('case_id')}: fixture has no gold/expected object")
    return value


def _gold_draft(fixture: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _gold(fixture).get("draft")
    if not isinstance(value, Mapping):
        raise ValueError(f"{fixture.get('case_id')}: gold draft is required")
    return value


def _field_comparison_value(field: Mapping[str, Any]) -> Any:
    normalized = field.get("normalized_value")
    return normalized if normalized is not None else field.get("value")


def _uncertainty_keys(draft: Mapping[str, Any]) -> set[tuple[str, tuple[str, ...]]]:
    result: set[tuple[str, tuple[str, ...]]] = set()
    for item in draft.get("uncertainties", []):
        if isinstance(item, Mapping):
            result.add(
                (
                    str(item.get("code")),
                    tuple(sorted(str(path) for path in item.get("field_paths", []))),
                )
            )
    return result


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 1.0


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (
        round(2 * precision * recall / (precision + recall), 6)
        if precision + recall
        else 0.0
    )
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _expected_bool(gold: Mapping[str, Any], names: Sequence[str], default: bool) -> bool:
    for name in names:
        if name in gold:
            return bool(gold[name])
    return default


def _expected_authorization(gold: Mapping[str, Any], default: bool) -> bool:
    direct = (
        "authorization_allowed",
        "authorization_permitted",
        "authorization_allowed_after_activation",
    )
    for name in direct:
        if name in gold:
            return bool(gold[name])
    expectation = gold.get("authorization_expectation")
    if isinstance(expectation, Mapping):
        decision = str(expectation.get("decision", "")).lower()
        if decision in {"permit", "deny"}:
            return decision == "permit"
    return default


def _normalize_review_route(value: Any) -> str:
    route = str(value).lower()
    if route in {"approve", "approved"}:
        return "approve"
    return "review_required"


def _policy_predictions(
    draft: Mapping[str, Any] | None,
    fixture: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate fail-closed workflow outcomes from declared scenario controls.

    Human and simulator outcomes are scenario inputs; model-extracted fields and
    uncertainties remain untrusted. This mirrors the gates in ``workflow.py``
    while avoiding any model involvement in the policy decision.
    """

    if draft is None:
        return {
            "review_route": "review_required",
            "activation_permitted": False,
            "authorization_permitted": False,
            "draft_authorization_permitted": False,
        }
    material = {
        str(item.get("code"))
        for item in draft.get("uncertainties", [])
        if isinstance(item, Mapping)
        and str(item.get("code")) in MATERIAL_UNCERTAINTY_CODES
    }
    blocking = bool(material or draft.get("blocking_issues"))
    review_route = "review_required" if blocking else "approve"
    workflow = fixture.get("workflow_inputs")
    if not isinstance(workflow, Mapping):
        # Compatibility for the original five smoke fixtures. Final evaluation
        # fixtures carry controls outside gold so policy inputs and labels are
        # cleanly separated.
        gold = _gold(fixture)
        workflow = {
            "human_review_decision": gold.get("review_route", "deferred"),
            "registry_simulator_result": gold.get(
                "registry_result", "unavailable"
            ),
        }
    scenario_review = str(workflow.get("human_review_decision", "deferred"))
    registry_result = str(
        workflow.get("registry_simulator_result", "unavailable")
    )
    fields = draft.get("fields", {})
    required_values = {
        name: _field_comparison_value(fields.get(name, {}))
        for name in (
            "registry_id",
            "credential_type",
            "jurisdiction",
            "credential_status",
            "expiration_date",
        )
    }
    expiration_valid = False
    if required_values["expiration_date"]:
        try:
            expiration = date.fromisoformat(str(required_values["expiration_date"]))
            evaluation_date = date.fromisoformat(
                str(workflow.get("policy_evaluation_date", "2026-07-29"))
            )
            expiration_valid = expiration >= evaluation_date
        except ValueError:
            expiration_valid = False
    activation = (
        scenario_review.lower() in {"approve", "approved", "correct", "corrected"}
        and registry_result == "match"
        and not blocking
        and bool(required_values["registry_id"])
        and required_values["credential_type"] == "Certified Nurse Aide"
        and required_values["jurisdiction"] == "HI"
        and required_values["credential_status"] == "active"
        and expiration_valid
    )
    controls = workflow.get("authorization_request")
    if not isinstance(controls, Mapping):
        controls = {}
    revoked = bool(controls.get("revoked", False))
    token_valid = bool(controls.get("token_valid", True))
    authorization = (
        activation
        and not revoked
        and token_valid
        and controls.get("audience", "org:synthetic-care-provider")
        == "org:synthetic-care-provider"
        and controls.get("purpose", "credentialing") == "credentialing"
    )
    return {
        "review_route": review_route,
        "activation_permitted": activation,
        "authorization_permitted": authorization,
        "draft_authorization_permitted": False,
    }


def calculate_metrics(
    records: Sequence[Mapping[str, Any]],
    fixtures: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Calculate all reported metrics directly from retained records and gold."""

    field_tp = field_fp = field_fn = 0
    uncertainty_tp = uncertainty_fp = uncertainty_fn = 0
    exact_matches = false_clears = material_gold_cases = corrections = 0
    route_agreements = activation_agreements = authorization_agreements = 0
    false_active = false_permits = false_active_draft_permits = 0
    material_nonblocking = 0
    valid_count = 0
    latencies: list[int] = []
    input_tokens = output_tokens = total_tokens = 0
    cost = 0.0
    per_case: list[dict[str, Any]] = []

    for record in records:
        case_id = str(record["case_id"])
        fixture = fixtures[case_id]
        gold = _gold(fixture)
        expected_draft = _gold_draft(fixture)
        candidate = record.get("draft") if record.get("schema_valid") else None
        if isinstance(candidate, Mapping):
            valid_count += 1
        else:
            candidate = None

        record_exact = candidate is not None
        expected_fields = expected_draft.get("fields", {})
        predicted_fields = candidate.get("fields", {}) if candidate else {}
        case_field_tp = case_field_fp = case_field_fn = case_corrections = 0
        for name in FIELD_NAMES:
            expected_value = _field_comparison_value(expected_fields.get(name, {}))
            predicted_value = _field_comparison_value(predicted_fields.get(name, {}))
            if predicted_value is not None and predicted_value == expected_value:
                field_tp += 1
                case_field_tp += 1
            elif predicted_value is not None:
                field_fp += 1
                corrections += 1
                case_field_fp += 1
                case_corrections += 1
                if expected_value is not None:
                    field_fn += 1
                    case_field_fn += 1
            elif expected_value is not None:
                field_fn += 1
                corrections += 1
                case_field_fn += 1
                case_corrections += 1
            if predicted_value != expected_value:
                record_exact = False
        exact_matches += int(record_exact)

        expected_uncertainty = _uncertainty_keys(expected_draft)
        predicted_uncertainty = _uncertainty_keys(candidate or {})
        uncertainty_tp += len(expected_uncertainty & predicted_uncertainty)
        uncertainty_fp += len(predicted_uncertainty - expected_uncertainty)
        uncertainty_fn += len(expected_uncertainty - predicted_uncertainty)
        case_uncertainty_tp = len(expected_uncertainty & predicted_uncertainty)
        case_uncertainty_fp = len(predicted_uncertainty - expected_uncertainty)
        case_uncertainty_fn = len(expected_uncertainty - predicted_uncertainty)
        expected_material = {
            item for item in expected_uncertainty if item[0] in MATERIAL_UNCERTAINTY_CODES
        }
        material_gold_cases += int(bool(expected_material))
        predicted_block = bool(
            candidate
            and (
                candidate.get("blocking_issues")
                or any(
                    isinstance(item, Mapping)
                    and item.get("code") in MATERIAL_UNCERTAINTY_CODES
                    and item.get("blocking") is True
                    for item in candidate.get("uncertainties", [])
                )
            )
        )
        false_clears += int(
            candidate is not None and bool(expected_material) and not predicted_block
        )
        if candidate:
            material_nonblocking += sum(
                1
                for item in candidate.get("uncertainties", [])
                if isinstance(item, Mapping)
                and item.get("code") in MATERIAL_UNCERTAINTY_CODES
                and item.get("blocking") is not True
            )

        predicted_policy = _policy_predictions(candidate, fixture)
        expected_route = _normalize_review_route(
            gold.get("review_route", "review_required")
        )
        route_agreements += int(predicted_policy["review_route"] == expected_route)
        expected_activation = _expected_bool(
            gold,
            ("activation_allowed_after_review_and_match", "activation_allowed"),
            default=False,
        )
        predicted_activation = bool(predicted_policy["activation_permitted"])
        activation_agreements += int(predicted_activation == expected_activation)
        false_active += int(predicted_activation and not expected_activation)
        expected_authorization = _expected_authorization(
            gold, default=expected_activation
        )
        predicted_authorization = bool(predicted_policy["authorization_permitted"])
        authorization_agreements += int(
            predicted_authorization == expected_authorization
        )
        false_permits += int(predicted_authorization and not expected_authorization)
        false_active_draft_permits += int(
            predicted_policy["draft_authorization_permitted"]
        )
        per_case.append(
            {
                "case_id": case_id,
                "schema_valid": candidate is not None,
                "field": {
                    "true_positive": case_field_tp,
                    "false_positive": case_field_fp,
                    "false_negative": case_field_fn,
                },
                "normalized_exact_record_match": record_exact,
                "uncertainty": {
                    "true_positive": case_uncertainty_tp,
                    "false_positive": case_uncertainty_fp,
                    "false_negative": case_uncertainty_fn,
                },
                "false_clear": bool(
                    candidate is not None
                    and expected_material
                    and not predicted_block
                ),
                "expected_review_route": expected_route,
                "predicted_review_route": predicted_policy["review_route"],
                "corrections_required": case_corrections,
                "expected_activation_permitted": expected_activation,
                "predicted_activation_permitted": predicted_activation,
                "expected_authorization_permitted": expected_authorization,
                "predicted_authorization_permitted": predicted_authorization,
            }
        )

        if record.get("latency_ms") is not None:
            latencies.append(int(record["latency_ms"]))
        input_tokens += int(record.get("input_tokens") or 0)
        output_tokens += int(record.get("output_tokens") or 0)
        total_tokens += int(record.get("total_tokens") or 0)
        cost += float(record.get("estimated_cost_usd") or 0)

    count = len(records)
    latency = {
        "observed_count": len(latencies),
        "total_ms": sum(latencies),
        "mean_ms": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "min_ms": min(latencies) if latencies else None,
        "max_ms": max(latencies) if latencies else None,
    }
    return {
        "field": _prf(field_tp, field_fp, field_fn),
        "normalized_exact_record_match": {
            "count": exact_matches,
            "rate": _ratio(exact_matches, count),
        },
        "uncertainty": _prf(
            uncertainty_tp, uncertainty_fp, uncertainty_fn
        ),
        "false_clear": {
            "count": false_clears,
            "eligible_material_case_count": material_gold_cases,
            "rate": (
                round(false_clears / material_gold_cases, 6)
                if material_gold_cases
                else 0.0
            ),
        },
        "review_routing_agreement": {
            "count": route_agreements,
            "rate": _ratio(route_agreements, count),
        },
        "corrections_required_count": corrections,
        "schema_validity": {
            "count": valid_count,
            "rate": _ratio(valid_count, count),
        },
        "latency": latency,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": total_tokens,
        },
        "estimated_cost_usd": round(cost, 8),
        "activation_policy_agreement": {
            "count": activation_agreements,
            "rate": _ratio(activation_agreements, count),
        },
        "false_active_claims": false_active,
        "authorization_policy_agreement": {
            "count": authorization_agreements,
            "rate": _ratio(authorization_agreements, count),
        },
        "false_permits": false_permits,
        "draft_authorization_permits": false_active_draft_permits,
        "material_uncertainties_marked_nonblocking": material_nonblocking,
        "per_case": per_case,
    }
