"""Render a judge-readable Markdown report from retained evaluation artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "artifacts" / "evaluation" / "20260730T085655.959974Z"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def display_bool(value: bool) -> str:
    return "yes" if value else "no"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    output = args.output or run_dir / "REPORT.md"
    summary = load_json(run_dir / "summary.json")
    frozen = load_json(run_dir / "frozen-config.json")
    records = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metrics = summary["metrics"]
    per_case = {item["case_id"]: item for item in metrics["per_case"]}
    corrected_cases = sum(
        item["corrections_required"] > 0 for item in metrics["per_case"]
    )
    activation_tp = sum(
        item["expected_activation_permitted"]
        and item["predicted_activation_permitted"]
        for item in metrics["per_case"]
    )
    activation_tn = sum(
        not item["expected_activation_permitted"]
        and not item["predicted_activation_permitted"]
        for item in metrics["per_case"]
    )
    activation_fp = sum(
        not item["expected_activation_permitted"]
        and item["predicted_activation_permitted"]
        for item in metrics["per_case"]
    )
    activation_fn = sum(
        item["expected_activation_permitted"]
        and not item["predicted_activation_permitted"]
        for item in metrics["per_case"]
    )

    lines = [
        "# CareTrust final controlled evaluation",
        "",
        "This report is generated from the retained machine-readable artifacts in this",
        "directory. It describes a synthetic controlled experiment, not production",
        "credential verification, user validation, or standards conformance.",
        "",
        "## Frozen configuration",
        "",
        "| Item | Observed value |",
        "|---|---|",
        f"| Run | `{summary['run_id']}` |",
        f"| Model | `{frozen['model_id']}` |",
        f"| Region | `{frozen['region']}` |",
        f"| Cases retained | {summary['retained_record_count']} / {summary['case_count']} |",
        f"| Prompt SHA-256 | `{frozen['prompt_sha256']}` |",
        f"| Schema SHA-256 | `{frozen['schema_sha256']}` |",
        f"| Policy SHA-256 | `{frozen['policy_sha256']}` |",
        f"| Fixture-set SHA-256 | `{frozen['fixture_set_sha256']}` |",
        f"| Temperature / max output tokens | {frozen['temperature']} / {frozen['max_tokens']:,} |",
        f"| Started / completed UTC | {summary['started_at']} / {summary['completed_at']} |",
        "",
        "The freeze manifest was committed before inference. Gold labels were not sent",
        "to the model. Every response, including failures, would have been retained.",
        "",
        "## Headline observations",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| JSON Schema valid | {metrics['schema_validity']['count']} / {summary['case_count']} ({metrics['schema_validity']['rate']:.0%}) |",
        f"| Field precision / recall / F1 | {metrics['field']['precision']:.3f} / {metrics['field']['recall']:.3f} / {metrics['field']['f1']:.3f} |",
        f"| Normalized exact-record match | {metrics['normalized_exact_record_match']['count']} / {summary['case_count']} ({metrics['normalized_exact_record_match']['rate']:.0%}) |",
        f"| Uncertainty precision / recall / F1 | {metrics['uncertainty']['precision']:.3f} / {metrics['uncertainty']['recall']:.3f} / {metrics['uncertainty']['f1']:.3f} |",
        f"| False clears among material-risk cases | {metrics['false_clear']['count']} / {metrics['false_clear']['eligible_material_case_count']} ({metrics['false_clear']['rate']:.0%}) |",
        f"| Review-routing agreement | {metrics['review_routing_agreement']['count']} / {summary['case_count']} ({metrics['review_routing_agreement']['rate']:.0%}) |",
        f"| Gold-field corrections required | {metrics['corrections_required_count']} across {corrected_cases} cases |",
        f"| Activation-policy agreement | {metrics['activation_policy_agreement']['count']} / {summary['case_count']} ({metrics['activation_policy_agreement']['rate']:.0%}) |",
        f"| Activation confusion matrix (TP / TN / FP / FN) | {activation_tp} / {activation_tn} / {activation_fp} / {activation_fn} |",
        "",
        "Field metrics compare whether each normalized field value exactly matches the",
        "predeclared gold value. `corrections required` counts mismatched field values,",
        "not people or completed human review sessions. Exact-record match requires all",
        "nine normalized field values to match; it does not include uncertainty codes,",
        "confidence, evidence links, messages, identifiers, or other record properties.",
        "",
        "## Performance and estimated inference cost",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Summed model latency | {metrics['latency']['total_ms'] / 1000:.3f} seconds |",
        f"| Mean latency | {metrics['latency']['mean_ms']:.2f} ms |",
        f"| Minimum / maximum latency | {metrics['latency']['min_ms']} / {metrics['latency']['max_ms']} ms |",
        f"| Input / output / total tokens | {metrics['tokens']['input']:,} / {metrics['tokens']['output']:,} / {metrics['tokens']['total']:,} |",
        f"| Final-run estimated inference cost | ${summary['current_run_accounted_cost_usd']:.6f} |",
        f"| Phase cumulative estimated inference cost | ${summary['phase_cumulative_accounted_cost_usd']:.7f} |",
        "",
        "Cost uses the reference rates frozen in the run configuration. It is an",
        "inference estimate, not a total cost-of-ownership claim.",
        "",
        "## Case-level outcomes",
        "",
        "| # | Case | Schema | Field TP/FP/FN | Uncertainty TP/FP/FN | Route | Active expected/predicted | Authorization expected/predicted | Latency ms |",
        "|---:|---|:---:|---:|---:|---|---|---|---:|",
    ]
    for record in records:
        case = per_case[record["case_id"]]
        field = case["field"]
        uncertainty = case["uncertainty"]
        lines.append(
            "| {sequence} | `{case_id}` | {schema} | {ftp}/{ffp}/{ffn} | "
            "{utp}/{ufp}/{ufn} | {expected_route} -> {predicted_route} | "
            "{expected_active}/{predicted_active} | {expected_auth}/{predicted_auth} | "
            "{latency} |".format(
                sequence=record["sequence"],
                case_id=record["case_id"],
                schema=display_bool(case["schema_valid"]),
                ftp=field["true_positive"],
                ffp=field["false_positive"],
                ffn=field["false_negative"],
                utp=uncertainty["true_positive"],
                ufp=uncertainty["false_positive"],
                ufn=uncertainty["false_negative"],
                expected_route=case["expected_review_route"],
                predicted_route=case["predicted_review_route"],
                expected_active=display_bool(case["expected_activation_permitted"]),
                predicted_active=display_bool(case["predicted_activation_permitted"]),
                expected_auth=display_bool(case["expected_authorization_permitted"]),
                predicted_auth=display_bool(case["predicted_authorization_permitted"]),
                latency=record["latency_ms"],
            )
        )

    lines.extend(
        [
            "",
            "## Safety interpretation",
            "",
            "- The final evaluation observed zero false clears across the seven cases whose",
            "  gold labels contained material uncertainty. All seven were routed to review;",
            "  two of thirteen non-material cases were also over-routed.",
            "- The activation proxy produced no false activations (TP=4, TN=10, FP=0,",
            "  FN=6). The six false denials show conservative failure, not correctness.",
            "- The reported authorization result is a Boolean proxy over the same activation",
            "  outcome and fixed scenario controls. It is not execution evidence for the",
            "  signed-token AuthorizationPolicy. The zero-draft-permit metric is fixed false",
            "  by the evaluator and should not be treated as an empirical result.",
            "- Separate automated tests--not this 20-case extraction run--demonstrate",
            "  signature-tamper rejection and denial after revocation.",
            "- A schema-valid response is only a draft. It is not evidence that a person,",
            "  credential, source, relationship, or access decision is verified.",
            "",
            "## Observed weaknesses and limitations",
            "",
            "- Exact-record match was 30%, and 19 field corrections across 14 cases would",
            "  be required to reach the frozen gold values. Normalization consistency needs",
            "  improvement.",
            "- Uncertainty F1 was 0.286. The model missed four expected uncertainty codes",
            "  and produced eleven extras. It should not independently decide whether a",
            "  credential can activate.",
            "- The deterministic workflow failed closed: lower activation and authorization",
            "  agreement reflects false denials from uncorrected model values, not unsafe",
            "  grants. Phase 2 must measure human correction time and burden.",
            "- Independent review after the run found that the frozen activation policy did",
            "  not explicitly require the extracted credential-status field to equal",
            "  `active`. The unreadable-status case was still denied by another gate, so",
            "  frozen counts did not change. A post-evaluation regression fix now enforces",
            "  the status gate; the frozen run was not rerun or replaced.",
            "- The freeze manifest hashes the prompt, schema, fixtures, and workflow/security",
            "  policy files. It does not hash the evaluator or Bedrock adapter source.",
            "- All people, credentials, registry responses, organizations, and requests are",
            "  synthetic. No live Hawaii registry, identity-proofing service, PHI, or real",
            "  care decision was used.",
            "- The run does not establish FHIR, W3C VC, OID4VC, SMART, or federation",
            "  conformance and does not demonstrate cross-organization portability.",
            "",
            "## Reproduction",
            "",
            "From a clean clone with valid AWS access:",
            "",
            "```powershell",
            '.\\.venv\\Scripts\\python scripts\\run_evaluation.py --freeze-only --prior-spend-usd 0.0052056',
            '.\\.venv\\Scripts\\python scripts\\run_evaluation.py --prior-spend-usd 0.0052056',
            "```",
            "",
            "Do not rerun and replace this submitted result without labeling the new run",
            "separately and explaining the configuration change.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(output)


if __name__ == "__main__":
    main()
