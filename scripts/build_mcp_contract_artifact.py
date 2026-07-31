"""Execute a local stdio MCP transcript and retain inspectable adapter evidence."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from caretrust.mcp_adapter import McpAdapter
from caretrust.case_bundle import build_synthetic_case_bundle


OUTPUT = ROOT / "artifacts" / "validation" / "mcp-adapter-contract.json"
SERVER = ROOT / "scripts" / "run_mcp_server.py"

CLIENT_INITIALIZE_PARAMS = {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {"name": "caretrust-contract-artifact", "version": "0.4.0"},
}


def transcript_requests() -> list[dict[str, object]]:
    first_decision_id = build_synthetic_case_bundle()["decisions"][0]["decision_id"]
    return [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": CLIENT_INITIALIZE_PARAMS},
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "caretrust_draft_delegation", "arguments": {
                "intent_id": "intent:mcp-transcript-001", "patient_ref": "patient:synthetic-001",
                "utterance": "Let my daughter Leilani schedule appointments through 2026-12-31 in the scheduling app for appointment management.",
                "created_at": "2026-07-30T10:00:00Z",
            }},
        },
        {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "caretrust_propose_app_profile", "arguments": {
                "application_id": "app:mcp-transcript", "source_id": "source:mcp-transcript",
                "description": "Synthetic scheduling application at https://mcp-transcript.synthetic.example reads appointments for care coordination.",
                "created_at": "2026-07-30T10:00:00Z",
            }},
        },
        {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "caretrust_list_case_permissions", "arguments": {}},
        },
        {
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "caretrust_explain_decision", "arguments": {
                "decision_id": first_decision_id,
            }},
        },
        {
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": "caretrust_simulate_access", "arguments": {"request_id": "request:case:family-permit-001"}},
        },
        {
            "jsonrpc": "2.0", "id": 8, "method": "tools/call",
            "params": {"name": "caretrust_validate_case", "arguments": {}},
        },
        {
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "caretrust_project_standards", "arguments": {}},
        },
        {
            "jsonrpc": "2.0", "id": 10, "method": "tools/call",
            "params": {"name": "caretrust_approve_delegation", "arguments": {}},
        },
    ]


def execute_transcript() -> dict[str, object]:
    adapter = McpAdapter()
    state_before = adapter.canonical_state_hash()
    requests = transcript_requests()
    completed = subprocess.run(
        [sys.executable, str(SERVER)],
        input="\n".join(json.dumps(item, sort_keys=True) for item in requests) + "\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    state_after = adapter.canonical_state_hash()
    if len(responses) != len(requests) - 1:
        raise ValueError("initialized notification must not produce a JSON-RPC response")
    if state_before != state_after:
        raise ValueError("MCP transcript changed canonical case state")
    return {
        "artifact_type": "caretrust.mcp-adapter-contract.v1",
        "evidence_status": "executed_local",
        "transport": "local_stdio_jsonrpc_2_0",
        "http_oauth_protected_resource": "planned_only",
        "synthetic_only": True,
        "network_calls": False,
        "canonical_state_hash_before": state_before,
        "canonical_state_hash_after": state_after,
        "state_mutated": False,
        "transcript": {"requests": requests, "responses": responses},
        "claim_boundary": [
            "The server process was executed only over local stdio; no HTTP listener, OAuth server, or protected-resource metadata endpoint was deployed.",
            "The adapter exposes draft, read, validate, explain, and simulation behavior only; it does not approve, activate, register, issue authority, revoke, mint tokens, or mutate canonical state.",
            "Simulation re-runs existing deterministic case policy and is not a durable decision, token, or disclosure receipt.",
            "Read responses are allowlisted projections; raw source documents, extraction packets, and unrelated canonical objects are excluded.",
        ],
    }


def write_output() -> Path:
    artifact = execute_transcript()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(write_output().relative_to(ROOT))
