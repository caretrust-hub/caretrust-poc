"""Export deterministic JSON Schema artifacts from the Pydantic contracts."""

from __future__ import annotations

import json
from pathlib import Path

from caretrust.models import DraftCredentialClaim

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "schemas" / "draft-credential-claim.schema.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    schema = DraftCredentialClaim.model_json_schema(
        mode="validation",
        ref_template="#/$defs/{model}",
    )
    OUTPUT.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
