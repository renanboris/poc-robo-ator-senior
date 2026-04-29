# Promotion Gates

Every shadow event starts at Level 0 and can be promoted through four maturity
levels.  Promotion is governed by explicit, deterministic criteria — not by
enthusiasm or ad-hoc decisions.

---

## Levels

| Level | State | Meaning |
|-------|-------|---------|
| 0 | `raw_shadow` | Just ingested from dual capture. No promotion yet. |
| 1 | `reviewed_shadow` | Sufficient context, low noise, plausible intent. |
| 2 | `skill_candidate` | Clear pattern + semantic action. Candidate for reuse. |
| 3 | `promoted_skill` | Passed the promotion benchmark. Ready for production reuse. |

---

## Level 0 → Level 1 Criteria

All five conditions must be true:

| Criterion | Rule |
|-----------|------|
| `screen_family` | Non-empty and not `"unknown"` |
| `component_family` | Non-empty and not `"unknown"` |
| `is_noise` | Must be `false` |
| `confianca_captura` | Must be `"media"` or `"alta"` |
| `intencao_semantica` | Non-empty string |

---

## Level 1 → Level 2 Criteria

All four conditions must be true:

| Criterion | Rule |
|-----------|------|
| `semantic_action` | Not `"navigate"` and not `"unknown"` |
| `business_entity` | Non-empty string |
| `screen_family` | Non-empty and not `"unknown"` |
| Pattern frequency | At least **2 occurrences** of the same `pattern_detectado` for the same `business_target` |

---

## Level 2 → Level 3 Criteria (Promotion Benchmark)

All six criteria must pass (see `docs/SKILL_PROMOTION_POLICY.md` for thresholds):

1. Success rate ≥ 70%
2. Semantic target consistency across ≥ 3 contributing events
3. Pattern stability ≥ 80%
4. Average confidence ≥ 0.6
5. Post-HITL correction rate < 20% (if HITL was performed)
6. Effect coherence ≥ 60% (expected_effect vs observed_effect)

---

## gate_failure_reason Vocabulary

When a record fails a gate check, `gate_failure_reason` is set to:

```
"Level {N}: {criterion}"
```

Examples:
- `"Level 1: screen_family"` — screen_family was empty or unknown
- `"Level 1: is_noise"` — event was flagged as noise
- `"Level 2: pattern_frequency"` — fewer than 2 pattern occurrences
- `"Level 3: min_success_rate"` — success rate below 70%
- `"Level 3: min_effect_coherence"` — effect coherence below 60%

---

## HITL Override Procedure

A human operator can bypass the benchmark and promote a skill directly to
Level 3 by:

1. Setting `promotion_state = "promoted_skill"` on the `KnownSkill` record.
2. Setting `source_stage = "hitl_promoted"`.
3. Setting `last_validated_at` to the current ISO 8601 timestamp.
4. Logging the override reason in the skill's `provenance` dict under key
   `"hitl_override_reason"`.

HITL-promoted skills are still subject to runtime success/failure tracking
and will be flagged for re-review if `failure_count > success_count`.
