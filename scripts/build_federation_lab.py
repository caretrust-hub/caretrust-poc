"""Build the public-key-safe local two-hub federation laboratory artifact."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from caretrust.federation_lab import build_two_hub_federation_lab


OUTPUT = ROOT / "artifacts" / "validation" / "federation-two-hub-lab.json"


def write_output() -> Path:
    artifact = build_two_hub_federation_lab()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(write_output().relative_to(ROOT))
