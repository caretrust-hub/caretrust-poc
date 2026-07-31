# Smart40 v2 deterministic post-hoc analysis

This analysis reads only the frozen configuration and retained results. It does not rerun or relabel any model output.

- Retained records: **40**
- Raw responses containing citations: **40/40**
- Raw responses whose citations all use the allowed span ID and an exact source quote: **40/40**
- Full model candidates accepted: **0/34 completed fallback records**
- Safety rejections: **6**

## Interpretation

Exposing canonical span IDs corrected the v1 citation-transport defect: every raw response cited an allowed span and exact source quote. Full candidate acceptance remained zero because the prompt did not adequately supply or require canonical identity and bounded vocabulary mappings. Deterministic fallback quality must not be reported as model-candidate quality.

## Next protocol change

Freeze the delegate directory, allowed vocabularies, and required output keys in model input; score partial candidate fields before deterministic fallback.
