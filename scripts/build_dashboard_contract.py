"""Write the deterministic CareTrust dashboard integration contract artifact."""

from __future__ import annotations

import json
from pathlib import Path

from caretrust.dashboard_contract import build_dashboard_contract


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation" / "dashboard-contract.json"


def main() -> None:
    contract = build_dashboard_contract()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
