# Skill Promotion Policy

This document defines the quantified thresholds that a skill candidate (Level 2)
must satisfy before being automatically promoted to a promoted skill (Level 3).

---

## Benchmark Thresholds

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| **Success rate** | ≥ 70% | `success_count / (success_count + failure_count)` — ensures the skill works reliably in practice |
| **Semantic consistency** | ≥ 3 contributing events | Prevents promotion from a single lucky execution |
| **Pattern stability** | ≥ 80% same `pattern_detectado` | Ensures the skill represents a stable interaction pattern |
| **Average confidence** | ≥ 0.6 | Filters out low-quality captures |
| **HITL correction rate** | < 20% | If humans reviewed the skill, fewer than 1 in 5 reviews should have required a correction |
| **Effect coherence** | ≥ 60% | `expected_effect` and `observed_effect` must be coherent for at least 60% of contributing events |

---

## Automatic Promotion

When all six criteria pass and no contributing event has `review_required=True`,
the `Promotion_Gate_Engine` automatically promotes the skill to Level 3 without
requiring HITL.

---

## HITL Override

A human operator can promote a skill directly to Level 3 by:

1. Setting `promotion_state = "promoted_skill"` on the `KnownSkill`.
2. Setting `source_stage = "hitl_promoted"`.
3. Setting `last_validated_at` to the current ISO 8601 timestamp.
4. Recording the override reason in `provenance["hitl_override_reason"]`.

---

## Monitoring Metrics

Track these metrics to assess promotion quality over time:

| Metric | Description |
|--------|-------------|
| `promotion_rate` | % of skill candidates that reach Level 3 |
| `hitl_override_rate` | % of Level 3 skills that were HITL-promoted |
| `post_promotion_failure_rate` | % of promoted skills that later get `review_required=True` |
| `avg_confidence_at_promotion` | Average confidence of promoted skills |
| `avg_contributing_events` | Average number of contributing events per promoted skill |

---

## Decay and Re-validation

A promoted skill is flagged for re-review (`review_required=True`) when:
- `failure_count > success_count` at any point after promotion.
- A HITL reviewer corrects the skill's execution.

Re-review does not automatically demote the skill.  A human operator must
decide whether to demote, retrain, or keep the skill with updated metadata.
