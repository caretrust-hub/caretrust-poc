"""Render the retained CareTrust judge walkthrough contract to stdout."""

from __future__ import annotations

import argparse
import json

from caretrust.judge_walkthrough import build_judge_walkthrough_contract, render_walkthrough


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="write machine-readable contract")
    args = parser.parse_args()
    contract = build_judge_walkthrough_contract()
    if args.json:
        print(json.dumps(contract, indent=2, sort_keys=True))
    else:
        print(render_walkthrough(contract), end="")


if __name__ == "__main__":
    main()
