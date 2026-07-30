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

## Immediate repeat

The local command harness returned before `20260730T083126.713397Z` printed its
summary, but the process completed all five cases. The retained summary confirms
a second 5/5 schema-valid run using the same model, prompt, schema, fixtures, and
settings. It used 6,789 tokens and had an estimated cost of $0.00258210.

Across both complete runs, 10/10 outputs were schema valid. Combined estimated
Bedrock inference cost was $0.00520560, far below the $10 Phase 1 ceiling. This
repeat is useful smoke evidence but is not a substitute for the predeclared final
evaluation.
