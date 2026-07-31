"""Generate the canonical synthetic multi-caregiver case bundle."""
from __future__ import annotations

import json
from pathlib import Path

from caretrust.case_bundle import build_synthetic_case_bundle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "validation" / "synthetic-multi-caregiver-case.json"


def main() -> None:
    bundle = build_synthetic_case_bundle()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
