# CareTrust local MCP adapter profile

The POC includes an executable, dependency-free MCP server over local stdio and
JSON-RPC 2.0. Its evidence status is `executed_local`, synthetic-only. It is an
optional adapter over existing CareTrust compiler and deterministic case-policy
services, never a source of authority.

The server supports the MCP `2025-11-25` lifecycle subset: `initialize`,
`notifications/initialized`, `tools/list`, and `tools/call`. Initialization
requires the client's `protocolVersion`, capabilities object, and `clientInfo`
with name/version. The server negotiates the same version and returns its tools
capability plus server information. Empty, malformed, or incompatible
initialization fails before tools are accepted. Tool calls return MCP text
content plus `structuredContent`. Unknown JSON-RPC methods fail with `-32601`;
unknown tools and unknown tool arguments fail closed in an error tool result.

The registered tools are deliberately limited to:

- `caretrust_draft_delegation` — compiler-generated, evidence-linked draft.
- `caretrust_propose_app_profile` — proposed bounded RAR/profile/data plan.
- `caretrust_list_case_permissions` — minimum-data case projection.
- `caretrust_explain_decision` — reason, policy, artifact IDs, and receipt.
- `caretrust_validate_case` — local case contract/linkage validation.
- `caretrust_simulate_access` — non-authoritative deterministic policy replay.
- `caretrust_project_standards` — published standards projection metadata.

None of these tools approves, activates, registers, issues authority, mints a
token, revokes, or mutates canonical state. Simulation derives effective
grant/claim status from canonical lifecycle times for every request, so a
historical request is denied after its relevant revocation or expiry boundary.
It omits disclosure data and labels itself as non-authoritative. Draft tools
inherit compiler prompt-injection and authority-assertion rejection; compiler
output remains draft-only. Read tools use projections only: raw document/source
packets, extraction text, unrelated canonical objects, and clinical-holder
payloads are excluded. Any internal output-boundary failure becomes a generic
tool error without serializing sensitive diagnostics.

`scripts/run_mcp_server.py` runs the local stdio server. The generated
`artifacts/validation/mcp-adapter-contract.json` records a negotiated
handshake, tool listing, all bounded tool calls, a denied unknown tool, and
identical canonical state hashes before and after execution.

HTTP deployment and OAuth protected-resource operation are planned only. If
implemented later, the target is an OAuth protected resource with resource-bound
tokens, protected-resource metadata, authorization-code plus PKCE clients, and
normal CareTrust authorization requests/decisions for every tool call. No HTTP
listener, OAuth server, upstream identity token forwarding, or production MCP
deployment is represented by this POC.
