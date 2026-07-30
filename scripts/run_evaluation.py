"""Run the frozen synthetic CNA evaluation set through Amazon Bedrock."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from caretrust.adapters.bedrock import DEFAULT_MODEL_ID, DEFAULT_REGION, BedrockModelAdapter
from caretrust.evaluation import (
    EvaluationRunner,
    EvaluationSettings,
    freeze_configuration,
    write_frozen_configuration,
)

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "fixtures" / "cna" / "final" / "manifest.json",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=ROOT / "prompts" / "cna-draft-extraction-v2.txt",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=ROOT / "schemas" / "draft-credential-claim.schema.json",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "artifacts" / "evaluation",
    )
    parser.add_argument(
        "--frozen-config",
        type=Path,
        default=ROOT / "artifacts" / "evaluation" / "frozen-run-config.json",
    )
    parser.add_argument(
        "--freeze-only",
        action="store_true",
        help="write/verify the stable pre-run manifest without constructing Bedrock",
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("CARETRUST_BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
    )
    parser.add_argument(
        "--region",
        default=os.getenv("CARETRUST_AWS_REGION", DEFAULT_REGION),
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=2_500)
    parser.add_argument("--max-input-tokens", type=int, default=32_768)
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=float(os.getenv("CARETRUST_INFERENCE_BUDGET_USD", "10.00")),
    )
    parser.add_argument(
        "--prior-spend-usd",
        type=float,
        default=float(os.getenv("CARETRUST_PRIOR_INFERENCE_SPEND_USD", "0.00")),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = EvaluationSettings(
        model_id=args.model_id,
        region=args.region,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_input_tokens=args.max_input_tokens,
        budget_ceiling_usd=args.budget_usd,
        prior_phase_spend_usd=args.prior_spend_usd,
    )
    policy_paths = (
        ROOT / "src" / "caretrust" / "workflow.py",
        ROOT / "src" / "caretrust" / "authorization.py",
        ROOT / "src" / "caretrust" / "security.py",
    )
    frozen = freeze_configuration(
        settings=settings,
        manifest_path=args.manifest,
        prompt_path=args.prompt,
        schema_path=args.schema,
        policy_paths=policy_paths,
    )
    if args.freeze_only:
        write_frozen_configuration(args.frozen_config, frozen)
        print(json.dumps(frozen, indent=2, ensure_ascii=False))
        return 0

    if not args.frozen_config.exists():
        raise SystemExit(
            "frozen configuration is missing; run this command with --freeze-only "
            "and commit the resulting artifact before live evaluation"
        )
    adapter = BedrockModelAdapter(
        model_id=settings.model_id,
        region=settings.region,
        input_usd_per_million=settings.input_usd_per_million,
        output_usd_per_million=settings.output_usd_per_million,
    )
    runner = EvaluationRunner(
        adapter=adapter,
        settings=settings,
        manifest_path=args.manifest,
        prompt_path=args.prompt,
        schema_path=args.schema,
        policy_paths=policy_paths,
        output_root=args.output_root,
        frozen_config_path=args.frozen_config,
    )
    summary = runner.run()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    metrics = summary["metrics"]
    return 0 if (
        summary["retained_record_count"] == summary["case_count"]
        and metrics["schema_validity"]["count"] == summary["case_count"]
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
