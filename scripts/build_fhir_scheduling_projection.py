"""Generate the synthetic FHIR R4 / SMART scheduling projection artifact."""

from __future__ import annotations

import json
from pathlib import Path

from caretrust.fhir_scheduling import build_fhir_scheduling_projection


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation" / "fhir-smart-scheduling-projection.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(build_fhir_scheduling_projection(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
