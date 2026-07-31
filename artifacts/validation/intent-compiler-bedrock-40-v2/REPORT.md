# Corrected frozen 40-case intent compiler evaluation

Version 2 exposes frozen canonical span IDs before requiring model citations. Version 1 remains retained as a protocol defect.

```json
{
  "state": "completed",
  "protocol_version": "v2_span_ids_exposed",
  "frozen_config_sha256": "5832cbc3260925df8fe2f6b9a28f2c8ad5c46f840f97b13b3e97a2682518da15",
  "retained_record_count": 40,
  "consecutive_integrity": true,
  "actual_or_estimated_cost_usd": 0.003876749999999999,
  "metrics": {
    "model_candidate_accepted": {
      "correct": 0,
      "count": 34,
      "rate": 0.0
    },
    "citation_grounded": {
      "correct": 0,
      "count": 34,
      "rate": 0.0
    },
    "action_correct": {
      "correct": 34,
      "count": 34,
      "rate": 1.0
    },
    "resource_correct": {
      "correct": 34,
      "count": 34,
      "rate": 1.0
    },
    "audience_correct": {
      "correct": 33,
      "count": 34,
      "rate": 0.9705882352941176
    },
    "purpose_correct": {
      "correct": 34,
      "count": 34,
      "rate": 1.0
    },
    "expiry_correct": {
      "correct": 34,
      "count": 34,
      "rate": 1.0
    },
    "hitl_routing_correct": {
      "correct": 33,
      "count": 34,
      "rate": 0.9705882352941176
    },
    "safety_no_authority": {
      "correct": 34,
      "count": 34,
      "rate": 1.0
    },
    "protocol_9_delta_safe": {
      "correct": 34,
      "count": 34,
      "rate": 1.0
    },
    "provider_errors": 0,
    "safety_rejections": 6
  },
  "limitations": "Synthetic benchmark only. Candidate quality is separate from deterministic draft validation; no output can activate or authorize."
}
```

All inputs are synthetic. The configuration was frozen before inference; every consecutive response or error is retained.
