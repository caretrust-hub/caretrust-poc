# Bedrock smoke evidence

All content sent to Bedrock was synthetic. No live registry was called.

## Frozen model decision

The complete run in `20260730T083148.678843Z` is the Phase 1 smoke result:

- model: `qwen.qwen3-32b-v1:0`
- region: `us-west-2`
- cases: 5
- JSON Schema valid: 5/5
- total tokens: 6,858
- estimated cost: $0.00262350

Qwen3 32B is therefore frozen for the final controlled evaluation. The optional
Claude fallback was not used.

## Interrupted setup invocation

`20260730T083126.713397Z` was interrupted by the local command harness after
three cases and is excluded from the five-case result. Its three raw responses
are retained for transparency. They were schema valid and had a combined
estimated cost of $0.00149850. Total estimated Bedrock inference cost represented
in this directory is $0.00412200, far below the $10 Phase 1 ceiling.
