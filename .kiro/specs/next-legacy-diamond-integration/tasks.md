# Implementation Plan: Next-Legacy Diamond Integration

## Overview

This implementation establishes a formal, governed integration bridge between the Legacy system (`poc-robo-ator-senior`) and the Next system (`senior-training-os-next` CIL module). The integration enables the Next system to consume real operational evidence from Legacy dual-capture JSONL, convert it into canonical contracts, classify knowledge maturity through explicit promotion gates, and close the feedback loop between the current production factory and the future semantic brain.

**Implementation Language:** Python 3.11+

**Key Components:**
- Canonical three-layer shadow schema
- Four-level promotion gate system
- LegacyBridge adapter with rich context delivery
- ObservedAction and KnownSkill contracts with full provenance
- Batch ingestion pipeline with noise tolerance
- Screen family classification
- Planner enrichment with dual capture patterns
- Five official integration documentation files

---

## Tasks

- [ ] 1. Create canonical shadow schema and validation infrastructure
  - [x] 1.1 Define the three-layer shadow schema data model
    - Create `shadow_schema.py` with Layer A (raw observation), Layer B (interpretation), and Layer C (quality evidence) field definitions
    - Define controlled vocabularies for `semantic_action`, `business_entity`, `pattern_detectado`, `screen_family`, and `component_family`
    - Implement `Shadow_Schema_Validator` class with validation methods for each layer
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [x] 1.2 Implement shadow schema validation logic
    - Write `validate_layer_a()` method to check required raw observation fields
    - Write `validate_layer_b()` method to check interpretation fields and set `promotion_readiness`
    - Write `validate_layer_c()` method to check quality evidence fields
    - Add structured logging for validation failures with event `id_acao` and missing field names
    - _Requirements: 2.4, 1.4_
  
  - [ ]* 1.3 Write unit tests for shadow schema validation
    - Test validation with complete events (all layers present)
    - Test validation with missing Layer A fields (should fail)
    - Test validation with missing Layer B fields (should set `promotion_readiness=false`)
    - Test controlled vocabulary enforcement
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 2. Implement promotion gate system
  - [x] 2.1 Create PromotionBenchmark data model
    - Define `PromotionBenchmark` dataclass in `promotion_models.py` with all threshold fields
    - Implement `evaluate()` method that checks all benchmark criteria and returns pass/fail with failing criteria list
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  
  - [x] 2.2 Implement Promotion_Gate_Engine core logic
    - Create `Promotion_Gate_Engine` class in `promotion_engine.py`
    - Implement `evaluate_promotion_readiness()` method that determines current level (0-3)
    - Implement `promote_to_level_1()` with criteria: non-empty screen_family, component_family, is_noise=false, confianca_captura in ['media', 'alta'], non-empty intencao_semantica
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [x] 2.3 Implement Level 2 and Level 3 promotion logic
    - Implement `promote_to_level_2()` with criteria: clear semantic_action (not 'navigate' or 'unknown'), non-empty business_entity, non-empty screen_family, at least 2 occurrences of same pattern_detectado
    - Implement `promote_to_level_3()` that delegates to PromotionBenchmark.evaluate()
    - Implement `record_gate_failure()` to capture specific failing criterion in `gate_failure_reason` field
    - _Requirements: 3.4, 3.5, 3.7_
  
  - [ ]* 2.4 Write unit tests for promotion gate logic
    - Test Level 0 → Level 1 promotion with valid and invalid records
    - Test Level 1 → Level 2 promotion with pattern frequency analysis
    - Test Level 2 → Level 3 promotion with benchmark criteria
    - Test gate failure recording
    - _Requirements: 3.3, 3.4, 3.5, 3.7_

- [ ] 3. Implement evolved KnownSkill and SkillMemory contracts
  - [x] 3.1 Define evolved KnownSkill data model
    - Create `KnownSkill` dataclass in `skill_models.py` with all required fields: skill_id, skill_name, semantic_action, business_entity, screen_family, component_family, pattern, expected_effect, selector, fallback_selectors, success_count, failure_count, average_confidence, promotion_state, source_stage, review_required, provenance, created_at, last_seen, last_validated_at
    - _Requirements: 4.1_
  
  - [x] 3.2 Implement SkillMemory storage and retrieval
    - Create `SkillMemory` class in `skill_memory.py`
    - Implement `store()` method that persists KnownSkill with full provenance and governance metadata
    - Implement `retrieve()` method with three modes: 'exact' (fingerprint match), 'family' (screen_family + component_family), 'pattern' (pattern_detectado + semantic_action)
    - Filter retrieval to only return skills with promotion_state in ['skill_candidate', 'promoted_skill']
    - _Requirements: 4.5, 4.6_
  
  - [x] 3.3 Implement SkillMemory success/failure tracking
    - Implement `increment_success()` method that increments success_count and updates last_seen
    - Implement `increment_failure()` method that increments failure_count, updates last_seen, and sets review_required=true if failure_count > success_count
    - _Requirements: 4.3, 4.4_
  
  - [ ]* 3.4 Write unit tests for SkillMemory
    - Test storage with source_stage='legacy_import' and provenance preservation
    - Test retrieval modes: exact, family, pattern
    - Test success/failure tracking and review_required flag
    - Test filtering by promotion_state
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement ObservedAction contract and adapter
  - [x] 5.1 Define ObservedAction data model
    - Create `ObservedAction` dataclass in `observed_action_models.py` with all required fields: action_id, action_type, raw_target, screen_before, state_change, artifacts, confidence, is_noise, review_required, screen_family, component_family, pattern, business_entity, business_target, provenance
    - _Requirements: 6.5_
  
  - [x] 5.2 Implement ObservedAction_Adapter field mapping
    - Create `ObservedAction_Adapter` class in `observed_action_adapter.py`
    - Implement `adapt()` method that maps shadow event fields to ObservedAction fields
    - Map `elemento_alvo.seletor_hint` → `raw_target.selector`
    - Map `elemento_alvo.screenshot_referencia` → `screen_before`
    - Map `elemento_alvo.html_hint` + `coordenadas_relativas` → `artifacts`
    - Map `id_acao` + source_file + `captured_at` → `provenance`
    - _Requirements: 6.1, 6.2, 6.4, 6.6_
  
  - [x] 5.3 Implement confidence mapping and state change inference
    - Implement `_map_confidence()` method: alta→0.9, media→0.6, baixa→0.3
    - Handle special case: if is_noise=true, set confidence=0.1 and review_required=true
    - Implement `_infer_state_change()` method that derives state_change from expected_effect vs observed_effect
    - _Requirements: 6.5, 6.8, 8.2_
  
  - [ ]* 5.4 Write unit tests for ObservedAction_Adapter
    - Test field mapping with complete shadow event
    - Test confidence mapping for all levels
    - Test is_noise=true special handling
    - Test state_change inference with matching and mismatching effects
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.8_

- [ ] 6. Implement LegacyBridge adapter
  - [x] 6.1 Create LegacyBridge core infrastructure
    - Create `LegacyBridge` class in `legacy_bridge.py`
    - Implement `read_shadow_file()` method that reads shadow JSONL from shadow_exports/, validates each line against canonical schema, returns list of validated event dicts
    - Add error handling for FileNotFoundError and ValidationError
    - _Requirements: 5.1, 1.1_
  
  - [x] 6.2 Implement LegacyBridge mapping and lookup methods
    - Implement `map_to_observed_action()` method that delegates to ObservedAction_Adapter
    - Implement `lookup_by_event_id()` method that retrieves specific shadow event by id_acao from source file
    - Implement `lookup_by_skill_candidate_id()` method that retrieves originating shadow event using provenance metadata
    - _Requirements: 5.2, 5.3, 5.4_
  
  - [x] 6.3 Implement LegacyBridge comparative context delivery
    - Implement `deliver_comparative_context()` method that returns dict with: original_shadow, mapped_action, screen_family, component_family, expected_effect, observed_effect
    - Integrate with ScreenObserver to infer screen_family and component_family
    - _Requirements: 5.6, 8.3_
  
  - [ ]* 6.4 Write integration tests for LegacyBridge
    - Test reading valid shadow JSONL file
    - Test validation error handling
    - Test mapping to ObservedAction
    - Test lookup methods
    - Test comparative context delivery
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 7. Implement Triage_Pipeline for batch ingestion
  - [x] 7.1 Define IngestionReport data model
    - Create `IngestionReport` dataclass in `triage_models.py` with fields: total_events, accepted_count, review_count, rejected_count, rejected_events, review_events, source_file, ingested_at
    - _Requirements: 10.5_
  
  - [x] 7.2 Implement Triage_Pipeline classification logic
    - Create `Triage_Pipeline` class in `triage_pipeline.py`
    - Implement `_classify_event()` method that returns (classification, reason) where classification is 'accepted', 'review', or 'rejected'
    - Classification rules: accepted = passes Layer A + is_noise=false; review = missing Layer B or is_noise=true; rejected = fails Layer A
    - _Requirements: 10.2, 10.3, 10.4_
  
  - [x] 7.3 Implement Triage_Pipeline batch ingestion
    - Implement `ingest_shadow_file()` method that reads shadow JSONL, classifies each event, returns IngestionReport
    - Implement noise tolerance: allow up to 30% review events without exception
    - Add structured logging: INFO level every 10 events with running counts
    - Implement `ingest_shadow_directory()` method for processing multiple files
    - _Requirements: 10.1, 10.6, 10.7, 10.8_
  
  - [ ]* 7.4 Write unit tests for Triage_Pipeline
    - Test classification logic for accepted, review, and rejected events
    - Test batch ingestion with mixed event quality
    - Test noise tolerance threshold (30%)
    - Test directory batch processing
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement ScreenObserver screen family classification
  - [x] 9.1 Define screen family controlled vocabulary
    - Create `ScreenObserver` class in `screen_observer.py`
    - Define `SCREEN_FAMILIES` constant with controlled vocabulary: ged_list, ged_form, ged_tree, sign_inbox, sign_envelope, erp_form, erp_list, modal_confirm, modal_form, shell_navigation, unknown
    - _Requirements: 11.1_
  
  - [x] 9.2 Implement screen classification logic
    - Implement `classify_screen()` method that takes screenshot, page_title, url_hint and returns (screen_family, review_required)
    - Use heuristics based on page_title and url_hint patterns to assign screen_family
    - Set review_required=true when confidence is low
    - Assign 'unknown' when screen_family cannot be confidently determined
    - _Requirements: 11.2, 11.3_
  
  - [x] 9.3 Implement component family classification
    - Implement `infer_component_family()` method that takes seletor_hint, tag, label and returns component_family
    - Component families: toolbar_button, context_menu_item, tree_node, form_input, checkbox_row, table_row, modal_button, unknown
    - Use selector patterns and tag hints to infer component type
    - _Requirements: 11.4_
  
  - [ ]* 9.4 Write unit tests for ScreenObserver
    - Test screen classification for each screen family
    - Test unknown classification with review_required=true
    - Test component family inference for each component type
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [ ] 10. Implement expected/observed effect tracking
  - [x] 10.1 Enhance shadow_builder.py to populate expected_effect
    - Modify `_montar_evento_shadow()` in shadow_builder.py to populate expected_effect from validacao_esperada.alvo
    - Ensure expected_effect is included in every shadow event
    - _Requirements: 8.1_
  
  - [x] 10.2 Implement observed_effect inference in ObservedAction_Adapter
    - Enhance `adapt()` method to infer observed_effect from screenshot_referencia when available
    - Compare semantic description of screenshot with expected_effect
    - Set observed_effect to null and review_required=true when inference fails
    - _Requirements: 8.2, 8.4_
  
  - [x] 10.3 Integrate effect axis into KnownSkill
    - Ensure KnownSkill.expected_effect is populated from most common expected_effect across contributing events
    - Update SkillMemory.store() to calculate and store expected_effect
    - _Requirements: 8.6_
  
  - [ ]* 10.4 Write unit tests for effect tracking
    - Test expected_effect population in shadow events
    - Test observed_effect inference with matching and mismatching screenshots
    - Test KnownSkill expected_effect aggregation
    - _Requirements: 8.1, 8.2, 8.4, 8.6_

- [ ] 11. Implement Planner enrichment with dual capture patterns
  - [x] 11.1 Enhance Planner to consume promoted skills
    - Modify `plan_next_action()` in Planner to filter candidate actions by screen_family + semantic_action
    - Rank candidates by promotion_state (promoted_skill > skill_candidate)
    - _Requirements: 12.1_
  
  - [x] 11.2 Integrate expected_effect into action planning
    - Use promoted skill's expected_effect as validation target for planned action
    - Add DEBUG logging for source_stage and promotion_state of consulted skills
    - _Requirements: 12.2, 12.3_
  
  - [ ]* 11.3 Write integration tests for Planner enrichment
    - Test action filtering by screen_family and semantic_action
    - Test ranking by promotion_state
    - Test expected_effect integration
    - Test logging of source_stage and promotion_state
    - _Requirements: 12.1, 12.2, 12.3_

- [x] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Create official integration documentation
  - [x] 13.1 Write LEGACY_NEXT_INTEGRATION.md
    - Document overall architecture and data flow from capture_dual_output.py to KnownSkill
    - Include field mapping table between Legacy shadow events and Next contracts
    - Describe role of each system component
    - _Requirements: 9.1, 1.3_
  
  - [x] 13.2 Write DUAL_SHADOW_SCHEMA.md
    - Document canonical shadow schema with all three layers
    - Define all fields with allowed values and data types
    - Include at least one complete example event for each layer
    - _Requirements: 9.2, 2.5_
  
  - [x] 13.3 Write PROMOTION_GATES.md
    - Document all four promotion levels (0-3) with exact criteria
    - Define gate_failure_reason vocabulary
    - Document HITL override procedure
    - _Requirements: 9.3, 3.6_
  
  - [x] 13.4 Write OBSERVED_ACTION_ADAPTER.md
    - Document field mapping from shadow JSONL to ObservedAction
    - Include example input/output pairs
    - Document edge cases (is_noise=true, missing fields, etc.)
    - _Requirements: 9.4, 6.7_
  
  - [x] 13.5 Write SKILL_PROMOTION_POLICY.md
    - Document promotion benchmark thresholds with rationale
    - Document HITL override procedure
    - Define monitoring metrics for promotion quality
    - _Requirements: 9.5, 7.7_

- [ ] 14. Integration and end-to-end wiring
  - [x] 14.1 Wire LegacyBridge with Triage_Pipeline
    - Integrate LegacyBridge.read_shadow_file() with Triage_Pipeline.ingest_shadow_file()
    - Ensure validation errors flow through triage classification
    - _Requirements: 1.4, 10.1_
  
  - [x] 14.2 Wire ObservedAction_Adapter with ScreenObserver
    - Integrate ObservedAction_Adapter.adapt() with ScreenObserver.classify_screen() and infer_component_family()
    - Ensure screen_family and component_family are populated in ObservedAction
    - _Requirements: 11.4_
  
  - [x] 14.3 Wire Promotion_Gate_Engine with SkillMemory
    - Integrate promotion evaluation into SkillMemory.store() workflow
    - Ensure promotion_state is set correctly on stored skills
    - _Requirements: 3.5, 4.1_
  
  - [x] 14.4 Wire LegacyBridge with ShadowModeRunner
    - Integrate LegacyBridge.deliver_comparative_context() with ShadowModeRunner
    - Ensure expected_effect and observed_effect are available for comparison
    - _Requirements: 5.6, 8.3_
  
  - [ ]* 14.5 Write end-to-end integration tests
    - Test complete flow: shadow JSONL → LegacyBridge → Triage → ObservedAction → Promotion → KnownSkill → Planner
    - Test with real shadow JSONL samples from shadow_exports/
    - Verify all provenance metadata is preserved
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at reasonable breaks
- The implementation follows a bottom-up approach: data models → validation → adapters → integration
- All code should follow Python 3.11+ type hints and dataclass patterns
- Preserve compatibility with existing Legacy system (poc-robo-ator-senior) and Next system (senior-training-os-next)
- Use structured logging throughout for observability
- All file paths should be relative to workspace root
- Shadow JSONL files are located in `shadow_exports/` directory
- Documentation files should be created in `docs/` directory

## Requirements Coverage

- **Requirement 1** (Formal Dual Capture Ingestion Contract): Tasks 1.1, 1.2, 6.1, 13.1, 14.1
- **Requirement 2** (Canonical Shadow Schema): Tasks 1.1, 1.2, 13.2
- **Requirement 3** (Explicit Promotion Gates): Tasks 2.1, 2.2, 2.3, 13.3
- **Requirement 4** (Evolved KnownSkill and SkillMemory): Tasks 3.1, 3.2, 3.3
- **Requirement 5** (Mature LegacyBridge): Tasks 6.1, 6.2, 6.3
- **Requirement 6** (Formal ObservedAction Adapter): Tasks 5.1, 5.2, 5.3, 13.4
- **Requirement 7** (Promotion Benchmark Policy): Tasks 2.1, 13.5
- **Requirement 8** (Expected/Observed Effect): Tasks 10.1, 10.2, 10.3
- **Requirement 9** (Official Documentation): Tasks 13.1, 13.2, 13.3, 13.4, 13.5
- **Requirement 10** (Batch Ingestion and Triage): Tasks 7.1, 7.2, 7.3
- **Requirement 11** (ScreenObserver Classification): Tasks 9.1, 9.2, 9.3
- **Requirement 12** (Planner Enrichment): Tasks 11.1, 11.2
