# Requirements Document

## Introduction

This feature establishes a formal, governed integration bridge between the legacy operational system (`poc-robo-ator-senior`, specifically `capture_dual_output.py` and `shadow_builder.py`) and the semantic brain system (`senior-training-os-next`, specifically the CIL module with its contracts, planner, and skill memory).

The goal is not a cosmetic adapter. It is a structural upgrade that allows the Next system to:
- formally receive real operational evidence from the Legacy system via dual-capture JSONL,
- convert that evidence into canonical contracts (`ObservedAction`, `KnownSkill`),
- classify knowledge maturity through explicit promotion gates,
- promote only what deserves to become a reusable skill,
- and close the feedback loop between the current production factory and the future semantic brain.

The scope covers the integration contract, canonical shadow schema, promotion gates, evolved data models, a mature `LegacyBridge`, a formal `ObservedAction` adapter, a promotion benchmark policy, and official integration documentation. It does not include a total rewrite of either system, immediate production promotion, or implementation of the final generalist brain.

---

## Glossary

- **Legacy**: The `poc-robo-ator-senior` system. The current operational factory. Produces roteiros, executes robots, and generates dual-capture JSONL via `capture_dual_output.py` and `shadow_builder.py`.
- **Next / CIL**: The `senior-training-os-next` system (CIL module). The semantic brain in evolution. Contains the planner, pattern engine, screen reader, and skill memory.
- **Shadow JSONL**: The line-delimited JSON file produced by `_salvar_shadow_jsonl()` in `shadow_builder.py`, stored in `shadow_exports/`. Each line is one captured interaction event.
- **Dual Capture**: The capture mode in `capture_dual_output.py` that simultaneously produces a productive roteiro output and a semantic shadow JSONL.
- **ObservedAction**: A canonical contract in the Next system representing a single observed user interaction, enriched with semantic, contextual, and quality signals.
- **KnownSkill**: A canonical contract in the Next system representing a reusable, promoted skill derived from one or more observed actions.
- **SkillMemory**: The storage and retrieval layer for `KnownSkill` records in the Next system.
- **LegacyBridge**: The adapter module in the Next system responsible for reading Legacy shadow JSONL and mapping it to Next contracts.
- **ShadowModeRunner**: The Next system component that runs in shadow mode alongside the Legacy system, comparing expected vs. observed behavior.
- **Promotion Gate**: An explicit maturity threshold that a shadow record must pass before being promoted to a higher level (e.g., from raw shadow to skill candidate).
- **HITL**: Human-In-The-Loop. A manual validation step where a human reviews and approves a skill candidate before promotion.
- **capture_scope**: A field in the shadow JSONL indicating whether the event occurred in the shell (`shell`) or inside a module iframe (`module_iframe`).
- **semantic_action**: A controlled-vocabulary field in the shadow JSONL classifying the intent of the action (e.g., `fill`, `search`, `confirm`, `delete`, `save`, `open`, `navigate`, `select`, `close`).
- **business_entity**: A field in the shadow JSONL identifying the business domain entity involved (e.g., `pasta`, `documento`, `campo`, `menu`).
- **pattern_detectado**: A field in the shadow JSONL classifying the UI interaction pattern (e.g., `menu_navigation`, `form_fill`, `button_click`, `table_selection`).
- **screen_family**: A classification of the screen type where an action occurred (e.g., `ged_list`, `ged_form`, `sign_inbox`, `erp_form`, `modal_confirm`).
- **component_family**: A classification of the UI component type involved (e.g., `toolbar_button`, `context_menu_item`, `tree_node`, `form_input`, `checkbox_row`).
- **expected_effect**: What the system was expected to change after an action (e.g., "modal opens", "row deleted from list").
- **observed_effect**: What the system actually changed after an action, as inferred from the screenshot delta or subsequent state.
- **promotion_state**: The current maturity level of a shadow record or skill (Level 0 through Level 3).
- **source_stage**: The origin of a `KnownSkill` record (e.g., `legacy_import`, `dual_shadow`, `runtime_learning`, `hitl_promoted`).
- **Triage Pipeline**: The batch ingestion pipeline in the Next system that classifies incoming shadow records as `accepted`, `review`, or `rejected`.

---

## Requirements

### Requirement 1: Formal Dual Capture Ingestion Contract

**User Story:** As a Next system developer, I want a formal, documented contract between `capture_dual_output.py` and the Next system, so that any agent or developer can understand exactly what fields are produced by the Legacy system and how they map to Next contracts.

#### Acceptance Criteria

1. THE `LegacyBridge` SHALL define an explicit ingestion schema that maps every field produced by `_montar_evento_shadow()` in `shadow_builder.py` to a corresponding field in the Next system's `ObservedAction` contract.
2. WHEN a shadow JSONL event is ingested, THE `LegacyBridge` SHALL preserve the original `id_acao`, `captured_at`, `acao`, `capture_scope`, `semantic_action`, `business_entity`, `business_target`, `pattern_detectado`, `valor_input`, `seletor_hint`, `iframe_hint`, `html_hint`, `screenshot_referencia`, `coordenadas_relativas`, `page_title`, and `url_hint` fields as explicit provenance data in the resulting `ObservedAction`.
3. THE ingestion contract SHALL be documented in `docs/LEGACY_NEXT_INTEGRATION.md` with a field-by-field mapping table.
4. IF a required field is absent from a shadow JSONL event, THEN THE `LegacyBridge` SHALL log a structured warning with the event `id_acao` and the missing field name, and SHALL classify the event as `review` rather than `accepted`.
5. THE ingestion contract SHALL explicitly declare which Legacy fields map to Layer A (raw observation), Layer B (interpretation), and Layer C (quality evidence) of the canonical shadow schema.

---

### Requirement 2: Canonical Shadow Schema with Three Layers

**User Story:** As a Next system developer, I want the shadow JSONL schema to be formally organized into three semantic layers, so that downstream consumers can reliably distinguish raw observation data from interpreted signals and quality evidence.

#### Acceptance Criteria

1. THE canonical shadow schema SHALL define Layer A as raw observation fields: `acao`, `capture_scope`, `seletor_hint`, `iframe_hint`, `html_hint`, `coordenadas_relativas`, `screenshot_referencia`, `valor_input`, `page_title`, `url_hint`, `captured_at`, `id_acao`.
2. THE canonical shadow schema SHALL define Layer B as interpretation fields: `semantic_action`, `business_entity`, `business_target`, `pattern_detectado`, `intencao_semantica`, `screen_family`, `component_family`, `expected_effect`.
3. THE canonical shadow schema SHALL define Layer C as quality evidence fields: `confianca_captura`, `is_noise`, `missing_signals`, `observed_effect`, `promotion_readiness`, `review_required`.
4. WHEN `shadow_builder.py` produces a shadow event, THE `Shadow_Schema_Validator` SHALL verify that all Layer A fields are present and SHALL set `promotion_readiness` to `false` if any Layer B field is empty or `unknown`.
5. THE canonical shadow schema SHALL be documented in `docs/DUAL_SHADOW_SCHEMA.md` with field definitions, allowed values, and examples for each layer.
6. WHERE `screen_family` cannot be inferred from available signals, THE schema SHALL use the value `unknown` and SHALL set `review_required` to `true`.

---

### Requirement 3: Explicit Promotion Gates

**User Story:** As a Next system operator, I want explicit, documented maturity levels for shadow records, so that I can govern which records are promoted to reusable skills and which require human review.

#### Acceptance Criteria

1. THE `Promotion_Gate_Engine` SHALL define exactly four promotion levels: Level 0 (raw shadow), Level 1 (reviewed shadow), Level 2 (skill candidate), and Level 3 (promoted skill).
2. WHEN a shadow event is first ingested, THE `Promotion_Gate_Engine` SHALL assign it Level 0 and SHALL set `promotion_state` to `raw_shadow`.
3. WHEN a Level 0 record has sufficient context (non-empty `screen_family`, non-empty `component_family`, `is_noise` is `false`, `confianca_captura` is `media` or `alta`, and `intencao_semantica` is non-empty), THEN THE `Promotion_Gate_Engine` SHALL promote it to Level 1 and SHALL set `promotion_state` to `reviewed_shadow`.
4. WHEN a Level 1 record has a clear `semantic_action` (not `navigate` or `unknown`), a non-empty `business_entity`, a non-empty `screen_family`, and at least two occurrences of the same `pattern_detectado` for the same `business_target`, THEN THE `Promotion_Gate_Engine` SHALL promote it to Level 2 and SHALL set `promotion_state` to `skill_candidate`.
5. WHEN a Level 2 record passes the promotion benchmark policy (Requirement 7), THEN THE `Promotion_Gate_Engine` SHALL promote it to Level 3 and SHALL set `promotion_state` to `promoted_skill`.
6. THE promotion gate rules SHALL be documented in `docs/PROMOTION_GATES.md` with the exact criteria for each level transition.
7. IF a record fails a promotion gate check, THEN THE `Promotion_Gate_Engine` SHALL record the specific failing criterion in a `gate_failure_reason` field on the record.

---

### Requirement 4: Evolved KnownSkill and SkillMemory

**User Story:** As a Next system developer, I want `KnownSkill` and `SkillMemory` to carry full provenance and governance metadata, so that any agent can understand where a skill came from, how reliable it is, and whether it needs review.

#### Acceptance Criteria

1. THE `KnownSkill` contract SHALL include the following fields in addition to its current definition: `provenance` (the original shadow event `id_acao` and source file path), `source_stage` (one of `legacy_import`, `dual_shadow`, `runtime_learning`, `hitl_promoted`), `screen_family`, `component_family`, `pattern` (the `pattern_detectado` value), `expected_effect`, `success_count`, `failure_count`, `last_seen` (ISO 8601 timestamp), `last_validated_at` (ISO 8601 timestamp or null), `promotion_state` (one of the four gate levels), `review_required` (boolean).
2. WHEN a `KnownSkill` is created from a Legacy shadow import, THE `SkillMemory` SHALL set `source_stage` to `legacy_import` and SHALL preserve the original `id_acao` in `provenance`.
3. WHEN a `KnownSkill` is executed successfully, THE `SkillMemory` SHALL increment `success_count` and SHALL update `last_seen`.
4. WHEN a `KnownSkill` execution fails, THE `SkillMemory` SHALL increment `failure_count` and SHALL set `review_required` to `true` if `failure_count` exceeds `success_count`.
5. THE `SkillMemory.retrieve()` method SHALL support three retrieval modes: `exact` (strict fingerprint match), `family` (match by `screen_family` and `component_family`), and `pattern` (match by `pattern_detectado` and `semantic_action`).
6. WHEN `SkillMemory.retrieve()` is called with mode `family` or `pattern`, THE `SkillMemory` SHALL return only skills with `promotion_state` of `skill_candidate` or `promoted_skill`.

---

### Requirement 5: Mature LegacyBridge

**User Story:** As a Next system developer, I want `LegacyBridge` to be a full-featured adapter that reads, maps, and delivers rich context from Legacy shadow JSONL, so that the Next system can consume real operational evidence without manual intervention.

#### Acceptance Criteria

1. THE `LegacyBridge` SHALL implement a `read_shadow_file(path: str) -> list[dict]` method that reads a shadow JSONL file from `shadow_exports/`, validates each line against the canonical shadow schema, and returns a list of validated event dicts.
2. THE `LegacyBridge` SHALL implement a `map_to_observed_action(shadow_event: dict) -> ObservedAction` method that converts a validated shadow event to a fully populated `ObservedAction` contract.
3. THE `LegacyBridge` SHALL implement a `lookup_by_event_id(event_id: int, source_file: str) -> dict | None` method that retrieves a specific shadow event by its `id_acao` from a given source file.
4. THE `LegacyBridge` SHALL implement a `lookup_by_skill_candidate_id(skill_id: str) -> dict | None` method that retrieves the originating shadow event for a given skill candidate.
5. WHEN `LegacyBridge.map_to_observed_action()` is called, THE `LegacyBridge` SHALL populate `raw_target`, `screen_before`, `state_change`, `artifacts`, `confidence`, and `provenance` fields of the `ObservedAction` from the corresponding shadow event fields.
6. THE `LegacyBridge` SHALL deliver a `comparative_context` dict to `ShadowModeRunner` containing: the original shadow event, the mapped `ObservedAction`, the inferred `screen_family`, the inferred `component_family`, and the `expected_effect`.

---

### Requirement 6: Formal ObservedAction Adapter

**User Story:** As a Next system developer, I want a formal adapter that converts dual JSONL events to `ObservedAction` contracts, so that the Next system can officially populate its canonical contracts from Legacy data without ambiguity.

#### Acceptance Criteria

1. THE `ObservedAction_Adapter` SHALL map the shadow event `elemento_alvo.seletor_hint` to `ObservedAction.raw_target.selector`.
2. THE `ObservedAction_Adapter` SHALL map the shadow event `elemento_alvo.screenshot_referencia` to `ObservedAction.screen_before` (as a base64 image reference).
3. THE `ObservedAction_Adapter` SHALL derive `ObservedAction.state_change` from the difference between `validacao_esperada.alvo` and the inferred `observed_effect` field.
4. THE `ObservedAction_Adapter` SHALL map the shadow event `elemento_alvo.html_hint` and `elemento_alvo.coordenadas_relativas` to `ObservedAction.artifacts`.
5. THE `ObservedAction_Adapter` SHALL map the shadow event `elemento_alvo.confianca_captura` to `ObservedAction.confidence` using the mapping: `alta` → `0.9`, `media` → `0.6`, `baixa` → `0.3`.
6. THE `ObservedAction_Adapter` SHALL preserve the shadow event `id_acao`, source file path, and `captured_at` timestamp as explicit provenance fields in the resulting `ObservedAction`.
7. THE adapter contract SHALL be documented in `docs/OBSERVED_ACTION_ADAPTER.md` with a field mapping table and example input/output pairs.
8. IF the shadow event `is_noise` field is `true`, THEN THE `ObservedAction_Adapter` SHALL set `ObservedAction.confidence` to `0.1` and SHALL set `review_required` to `true` regardless of `confianca_captura`.

---

### Requirement 7: Promotion Benchmark Policy

**User Story:** As a Next system operator, I want a minimum benchmark policy that a skill candidate must pass before being promoted to a promoted skill, so that only reliable, consistent, and well-evidenced skills enter the production skill library.

#### Acceptance Criteria

1. THE `Promotion_Benchmark` SHALL require a minimum success rate of 70% on re-execution attempts (i.e., `success_count / (success_count + failure_count) >= 0.70`) before a skill candidate can be promoted to Level 3.
2. THE `Promotion_Benchmark` SHALL require that the `semantic_action` field is consistent across at least 3 distinct shadow events that contributed to the skill candidate (semantic target consistency).
3. THE `Promotion_Benchmark` SHALL require that the `pattern_detectado` field is the same value across at least 80% of the contributing shadow events (pattern stability).
4. THE `Promotion_Benchmark` SHALL require a minimum average `confidence` of `0.6` across all contributing shadow events.
5. THE `Promotion_Benchmark` SHALL require that the post-HITL correction rate is below 20% (i.e., fewer than 1 in 5 HITL reviews resulted in a correction) if HITL validation has been performed.
6. THE `Promotion_Benchmark` SHALL require that `expected_effect` and `observed_effect` are coherent (non-empty and not contradictory) for at least 60% of contributing shadow events.
7. THE benchmark policy SHALL be documented in `docs/SKILL_PROMOTION_POLICY.md` with the exact thresholds, rationale, and override procedures for HITL promotion.
8. WHERE a skill candidate passes all benchmark criteria, THE `Promotion_Gate_Engine` SHALL automatically promote it to Level 3 without requiring HITL, unless `review_required` is `true` on any contributing event.

---

### Requirement 8: Expected Effect / Observed Effect as Central Axis

**User Story:** As a Next system developer, I want the Legacy-to-Next handoff to treat the effect axis (expected vs. observed) as a first-class citizen, so that the Next system can reason about whether an action actually achieved its goal.

#### Acceptance Criteria

1. THE `shadow_builder.py` `_montar_evento_shadow()` function SHALL populate `expected_effect` from the `validacao_esperada.alvo` field for every shadow event.
2. WHEN a shadow event has a non-empty `screenshot_referencia`, THE `ObservedAction_Adapter` SHALL attempt to infer `observed_effect` by comparing the semantic description of the screenshot with the `expected_effect` value.
3. THE `LegacyBridge` SHALL expose `expected_effect` and `observed_effect` as top-level fields in the `comparative_context` dict delivered to `ShadowModeRunner`.
4. WHEN `observed_effect` cannot be inferred, THE system SHALL set it to `null` and SHALL set `review_required` to `true` on the corresponding shadow record.
5. THE `Promotion_Benchmark` SHALL treat coherence between `expected_effect` and `observed_effect` as a required criterion (as specified in Requirement 7, criterion 6).
6. THE `KnownSkill` contract SHALL include `expected_effect` as a required field, populated from the most common `expected_effect` value across contributing shadow events.

---

### Requirement 9: Official Legacy-to-Next Integration Documentation

**User Story:** As a new agent or developer joining the project, I want official documentation that explains the full Legacy-to-Next integration, so that I can understand the system without reading source code.

#### Acceptance Criteria

1. THE system SHALL provide a `docs/LEGACY_NEXT_INTEGRATION.md` file that describes the overall architecture, the role of each system, the data flow from `capture_dual_output.py` to `KnownSkill`, and the field mapping between Legacy shadow events and Next contracts.
2. THE system SHALL provide a `docs/DUAL_SHADOW_SCHEMA.md` file that defines the canonical shadow schema with all three layers, field definitions, allowed values, and at least one complete example event.
3. THE system SHALL provide a `docs/PROMOTION_GATES.md` file that defines all four promotion levels, the exact criteria for each level transition, the `gate_failure_reason` vocabulary, and the override procedure for HITL promotion.
4. THE system SHALL provide a `docs/OBSERVED_ACTION_ADAPTER.md` file that defines the field mapping from shadow JSONL to `ObservedAction`, with example input/output pairs and notes on edge cases.
5. THE system SHALL provide a `docs/SKILL_PROMOTION_POLICY.md` file that defines the promotion benchmark thresholds, the rationale for each threshold, the HITL override procedure, and the monitoring metrics.
6. WHEN any of the five documentation files is absent from the repository, THE CI validation step SHALL fail with a descriptive error message identifying the missing file.

---

### Requirement 10: Batch Ingestion and Triage Pipeline

**User Story:** As a Next system operator, I want the Next system to be able to ingest shadow JSONL files in batch with noise tolerance and clear diagnostics, so that I can process large volumes of Legacy data without manual triage.

#### Acceptance Criteria

1. THE `Triage_Pipeline` SHALL implement a `ingest_shadow_file(path: str) -> IngestionReport` method that reads a shadow JSONL file, classifies each event as `accepted`, `review`, or `rejected`, and returns a structured report.
2. WHEN a shadow event passes all Layer A field validations and has `is_noise` set to `false`, THE `Triage_Pipeline` SHALL classify it as `accepted`.
3. WHEN a shadow event has missing Layer B fields or has `is_noise` set to `true`, THE `Triage_Pipeline` SHALL classify it as `review`.
4. WHEN a shadow event fails Layer A field validation (e.g., missing `id_acao`, missing `captured_at`, or malformed JSON), THE `Triage_Pipeline` SHALL classify it as `rejected` and SHALL log the specific validation failure.
5. THE `IngestionReport` SHALL include: total event count, accepted count, review count, rejected count, a list of rejected event identifiers with failure reasons, and a list of review event identifiers with the specific missing or problematic fields.
6. THE `Triage_Pipeline` SHALL be tolerant of noise: a file with up to 30% `review` events SHALL still complete ingestion and SHALL not raise an exception.
7. WHILE batch ingestion is in progress, THE `Triage_Pipeline` SHALL emit structured log lines at INFO level for every 10 events processed, including the running accepted/review/rejected counts.
8. THE `Triage_Pipeline` SHALL support processing multiple shadow JSONL files in a single batch call via a `ingest_shadow_directory(directory: str) -> list[IngestionReport]` method.

---

### Requirement 11: ScreenObserver Screen Family Classification

**User Story:** As a Next system developer, I want the `ScreenObserver` to classify screens into explicit families, so that the `LegacyBridge` and `SkillMemory` can use `screen_family` as a reliable retrieval and promotion signal.

#### Acceptance Criteria

1. THE `ScreenObserver` SHALL define a controlled vocabulary of `screen_family` values that includes at minimum: `ged_list`, `ged_form`, `ged_tree`, `sign_inbox`, `sign_envelope`, `erp_form`, `erp_list`, `modal_confirm`, `modal_form`, `shell_navigation`, and `unknown`.
2. WHEN the `ScreenObserver` analyzes a screenshot, THE `ScreenObserver` SHALL assign a `screen_family` value from the controlled vocabulary.
3. WHEN the `ScreenObserver` cannot confidently assign a `screen_family`, THE `ScreenObserver` SHALL assign `unknown` and SHALL set `review_required` to `true` on the associated shadow record.
4. THE `screen_family` value SHALL be propagated to the `ObservedAction` contract and to the `KnownSkill` contract via the `LegacyBridge` adapter.

---

### Requirement 12: Planner Enrichment with Dual Capture Patterns

**User Story:** As a Next system developer, I want the `Planner` to consume `pattern_detectado` and `screen_family` from promoted skills, so that it can make better-informed decisions when planning the next action.

#### Acceptance Criteria

1. WHEN the `Planner` receives a `KnownSkill` with `promotion_state` of `skill_candidate` or `promoted_skill`, THE `Planner` SHALL use the skill's `pattern_detectado` and `screen_family` to filter and rank candidate actions.
2. WHEN the `Planner` has access to a promoted skill with a matching `screen_family` and `semantic_action`, THE `Planner` SHALL prefer that skill's `expected_effect` as the validation target for the planned action.
3. THE `Planner` SHALL log the `source_stage` and `promotion_state` of any `KnownSkill` it consults, at DEBUG level.
