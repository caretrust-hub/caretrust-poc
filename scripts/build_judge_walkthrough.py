"""Generate the machine-readable CareTrust judge walkthrough contract."""

from __future__ import annotations

import json
from pathlib import Path

from caretrust.judge_walkthrough import build_judge_walkthrough_contract


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation" / "judge-walkthrough-contract.json"


def main() -> None:
    OUT.write_text(json.dumps(build_judge_walkthrough_contract(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
