1# Implementation Plan

## Overview

Este plano implementa o bugfix para detecção de contexto de modal PrimeNG e geração de seletores com escopo adequado. A abordagem segue a metodologia de bugfix com property-based testing: primeiro executamos testes exploratórios no código UNFIXED para confirmar a hipótese de causa raiz, depois implementamos o fix em duas camadas (capture JavaScript e executor Python), e finalmente validamos com testes de preservação.

---

## Tasks

- [x] 1. Write bug condition exploration test (BEFORE implementing fix)
  - **Property 1: Bug Condition** - Modal Selector Ambiguity Detection
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test implementation details from Bug Condition in design:
    - Generate test scenarios with elements inside PrimeNG modals (p-dialog, ui-dialog, s-dialog)
    - For each scenario, capture the selector using current `resolvePrimeNGComponent()` logic
    - Assert that captured selector includes modal scope prefix (e.g., `p-dialog[role="dialog"]`)
    - Assert that captured selector is unique (does not match multiple elements in DOM)
    - Property: `FOR ALL element IN modal WHERE element.type IN [search_button, table_row, autocomplete_button] THEN capturedSelector MUST contain modal_scope_prefix AND capturedSelector MUST be unique`
  - The test assertions should match the Expected Behavior Properties from design:
    - Search buttons in modal autocomplete should generate `p-dialog [name='field'] button.button-addon`
    - Table rows in modal should generate `p-dialog tr:has-text("unique_text")`
    - Transaction rows should generate `p-dialog tr:has-text("code")`
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found to understand root cause:
    - Selectors without modal scope prefix (e.g., `'ui-btn'` instead of `p-dialog button.button-addon`)
    - Selectors matching 4+ elements in DOM
    - Generic selectors like `'button'`, `'ui-btn'` that are ambiguous
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Modal PrimeNG Component Behavior
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (components outside modals):
    - Capture selector for autocomplete in main form (expect: `[name='campo'] button`)
    - Capture selector for calendar trigger in main form (expect: `[name='data'] button`)
    - Capture selector for dropdown in main form (expect: `.ui-dropdown-trigger` with anchor)
    - Capture selector for checkbox in non-modal table (expect: `:has-text()` strategy)
    - Capture selector for confirmation dialog button (expect: dialog scope with button text)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - Property: `FOR ALL element NOT IN modal WHERE element.type = primeng_component THEN capturedSelector MUST NOT contain modal_scope_prefix`
    - Property: `FOR ALL checkbox IN non_modal_table THEN capturedSelector MUST use :has-text() strategy`
    - Property: `FOR ALL confirmation_button IN dialog THEN capturedSelector MUST use existing _SELETORES_DIALOG patterns`
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Implement modal detection and scoped selector generation

  - [x] 3.1 Add modal detection to capture JavaScript (`capture_dual_output.py`)
    - **STATUS**: FIXED - Modal button pattern added
    - **VERSION**: 2.1.3-MODAL-BUTTON-FIX
    - **CHANGES**:
      1. Removed `aria-hidden` and `width` checks from `addModalScope()` (v2.1.2)
      2. Removed `aria-hidden` and `width` checks from `addModalScopeToFallback()` (v2.1.2)
      3. Removed `aria-hidden` and `width` checks from table row handling (v2.1.2)
      4. **NEW**: Added pattern for generic buttons inside modals (v2.1.3)
    - **REASON**: Generic modal buttons (like "Selecionar") were not matching any PrimeNG patterns
    - **JUSTIFICATION**: Buttons inside modals need modal scope even if they don't match specific PrimeNG patterns
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.2 Add modal-scoped candidate generation to executor (`vision_engine.py`)
    - **STATUS**: PENDING - Not needed if capture fix works
    - **NOTE**: This could be implemented independently without modifying capture JavaScript
    - _Requirements: 2.4, 2.5, 3.3, 3.4_

  - [x] 3.3 Improve modal button selector fallback in capture (`capture_dual_output.py`)
    - **STATUS**: FIXED - Part of visibility fix
    - _Requirements: 2.1, 3.5_

  - [x] 3.4 Verify bug condition exploration test now passes
    - **STATUS**: PENDING - Awaiting test with new version
    - **NOTE**: Tests are ready and passing on simulated fixed code
    - **ACTION**: Run new capture with Version 2.1.2-VISIBILITY-FIX and verify selectors have modal prefix
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.5 Verify preservation tests still pass
    - **STATUS**: PENDING - Awaiting test with new version
    - **NOTE**: Zero regressions expected (only modal elements affected)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 4. Integration testing and validation

  - [ ] 4.1 Test complete capture-to-execution flow with modal interactions
    - Record workflow in Senior X that includes:
      - Search button click in modal autocomplete (tipo de título selection)
      - Table row selection in modal search results
      - Transaction row click with specific code in modal
    - Verify captured roteiro contains modal-scoped selectors
    - Execute roteiro with robot and measure success rate
    - **EXPECTED**: >90% success rate without coordinate fallback
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 4.2 Test multiple sequential modals scenario
    - Record workflow with multiple modals opened sequentially:
      - Modal de busca → Modal de detalhes → Modal de confirmação
    - Verify each modal interaction generates unique scoped selector
    - Execute roteiro and verify no selector conflicts between modals
    - _Requirements: 2.1, 2.4_

  - [ ] 4.3 Test modal close and reopen scenario
    - Record interaction in modal, close modal, reopen, execute
    - Verify selector remains valid after modal re-rendering
    - Measure success rate across multiple open/close cycles
    - _Requirements: 2.4, 2.5_

  - [ ] 4.4 Test async modal rendering edge case
    - Record interaction in modal that appears after async operation
    - Verify capture waits for modal stabilization before generating selector
    - Check that `aria-hidden !== 'true'` and `width > 0` conditions are met
    - _Requirements: 2.1_

  - [ ] 4.5 Verify Brain telemetry for modal-scoped selectors
    - Execute workflows with modal interactions multiple times
    - Check `brain.db` for correct registration of modal-scoped selectors
    - Verify telemetry shows improved success rate for modal actions
    - Confirm no duplicate registrations or memory pollution
    - _Requirements: 2.4, 3.4_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Run complete test suite (exploration + preservation + integration)
  - Verify no regressions in non-modal workflows
  - Confirm >90% success rate for modal interactions
  - Review telemetry data for improved executor performance
  - Ask the user if questions arise

---

## Notes

- **Property-Based Testing**: Tasks 1 and 2 use property-based testing to generate many test cases automatically, providing stronger guarantees than manual unit tests
- **Observation-First**: Task 2 follows observation-first methodology - observe unfixed behavior first, then encode it in tests
- **Test Ordering**: Exploration and preservation tests MUST run on unfixed code before implementation (tasks 1-2), then re-run after fix (tasks 3.4-3.5)
- **Scoped PBT**: For deterministic bugs, scope properties to concrete failing cases for reproducibility
- **Preservation Focus**: 5 out of 10 requirements are preservation requirements - maintaining existing behavior is critical
- **Two-Layer Fix**: Implementation spans both capture (JavaScript) and executor (Python) layers for complete solution
