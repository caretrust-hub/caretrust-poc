"""Run the dependency-free CareTrust MCP adapter over stdio JSON-RPC 2.0."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from caretrust.mcp_adapter import McpAdapter


def main() -> int:
    adapter = McpAdapter()
    for line in sys.stdin:
        if not line.strip():
            continue
        response = adapter.handle_json(line)
        if response is not None:
            sys.stdout.write(__import__("json").dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
