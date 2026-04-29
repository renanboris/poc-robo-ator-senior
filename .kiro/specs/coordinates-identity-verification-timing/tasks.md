# Implementation Plan

## Overview
This task list implements the fix for the coordinates identity verification timing bug. The workflow follows the exploratory bugfix methodology: explore the bug first, preserve existing behavior, then implement the fix with validation.

---

## Phase 1: Exploratory Bug Condition Testing (BEFORE Fix)

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Identity Verification Happens After Click
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate clicks execute before identity verification
  - **Scoped PBT Approach**: Test concrete failing cases where coordinates point to wrong element
  - Test implementation details:
    - Create test scenarios where `coords_relativas` points to wrong element (e.g., "Cancelar" button)
    - Set `label_curto` to expected element (e.g., "Confirmar")
    - Mock Playwright page with two buttons at different coordinates
    - Call `encontrar_e_clicar()` with wrong coordinates
    - Assert that click is executed BEFORE identity verification
    - Assert that function returns True despite clicking wrong element
    - Assert that telemetry reports success for wrong click
    - Assert that fallback layers are never reached
  - The test assertions should match the Expected Behavior Properties from design:
    - Identity verification MUST occur BEFORE click execution
    - Function MUST return False when identity verification fails
    - Telemetry MUST report failure when identity verification fails
    - Fallback layers MUST execute when coordinates layer fails
  - Run test on UNFIXED code (lines ~1960-2070 in current state)
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found:
    - Example 1: Coordinates point to "Cancelar", label_curto is "Confirmar" → clicks wrong button, returns True
    - Example 2: Coordinates point to row 2, label_curto has row 1 text → clicks wrong row, returns True
    - Example 3: Layout changed, coordinates point to different element → clicks wrong element, returns True
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

---

## Phase 2: Preservation Property Testing (BEFORE Fix)

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Fail-Open and Other Layers Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs:
    - Empty `label_curto` → click executes without verification (fail-open)
    - Cross-origin iframe → click executes without verification (fail-open)
    - Verification exception → click executes without verification (fail-open)
    - Correct coordinates → click executes successfully
    - Sniper layer → operates identically
    - Hint layer → operates identically
    - Brain layer → operates identically
    - Brute Force layer → operates identically
  - Write property-based tests capturing observed behavior patterns:
    - **Test 1**: For all inputs where `label_curto` is empty/None, verify click executes without verification
    - **Test 2**: For all inputs where iframe is cross-origin, verify fail-open applies
    - **Test 3**: For all inputs where verification throws exception, verify fail-open applies
    - **Test 4**: For all inputs where coordinates are correct (element matches label_curto), verify click succeeds
    - **Test 5**: For all inputs using Sniper layer, verify identical behavior
    - **Test 6**: For all inputs using Hint layer, verify identical behavior
    - **Test 7**: For all inputs using Brain layer, verify identical behavior
    - **Test 8**: For all inputs using Brute Force layer, verify identical behavior
    - **Test 9**: For all inputs with `iframe_hint`, verify coordinate adjustment works identically
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

---

## Phase 3: Implementation

- [x] 3. Fix for coordinates identity verification timing bug

  - [x] 3.1 Extract identity verification into separate function
    - Create new helper function `_verificar_identidade_por_coordenadas()` in `vision_engine.py`
    - Function signature: `async def _verificar_identidade_por_coordenadas(page: Page, x: int, y: int, label_curto: str, iframe_hint: Optional[str] = None) -> tuple[bool, bool]`
    - Return type: `(identidade_confirmada: bool, is_cross_origin: bool)`
    - Implement fail-open for empty `label_curto` → return `(True, False)` immediately
    - Implement fail-open for verification exceptions → return `(True, False)` with warning log
    - Implement fail-open for cross-origin iframe → return `(True, True)` with warning log
    - Extract identity verification logic from lines ~1970-2050 into this function
    - Preserve `iframe_hint` validation (not generic values like "Pagina Principal")
    - Preserve context resolution using `_resolver_contexto()`
    - Preserve coordinate adjustment for iframe offset
    - Preserve fallback to automatic iframe detection if `iframe_hint` fails
    - Preserve element text matching logic (case-insensitive, strip, substring)
    - Add comprehensive logging for debugging
    - _Bug_Condition: isBugCondition(input) where coords_relativas points to wrong element AND label_curto is present_
    - _Expected_Behavior: Identity verification MUST occur BEFORE click execution_
    - _Preservation: Fail-open for empty label_curto, exceptions, cross-origin iframes_
    - _Requirements: 2.2, 3.1, 3.2, 3.3_

  - [x] 3.2 Reorder operations in coordinates layer
    - Modify coordinates layer section (lines ~1960-2070) to call `_verificar_identidade_por_coordenadas()` BEFORE `_clicar_por_coordenadas()`
    - Calculate target coordinates from `coords_relativas` (existing logic)
    - Call `_verificar_identidade_por_coordenadas()` with calculated coordinates
    - Only call `_clicar_por_coordenadas()` if `identidade_confirmada == True`
    - If `identidade_confirmada == False`, skip click and log escalation message
    - If `identidade_confirmada == False`, register telemetry failure and return False (do NOT return True)
    - Preserve existing exception handling
    - _Bug_Condition: Click executed before verification in current code_
    - _Expected_Behavior: Verification before click, skip click if verification fails_
    - _Preservation: Exception handling and logging unchanged_
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [x] 3.3 Update telemetry registration logic
    - Move `_registrar_telemetria("2_coords_capturadas", True)` to execute ONLY after both verification AND click succeed
    - Ensure `_registrar_telemetria("2_coords_capturadas", False)` is called when verification fails OR click fails
    - Preserve winning strategy registration (only when both verification AND click succeed)
    - Add logging to distinguish between verification failure and click failure
    - _Bug_Condition: Telemetry reports success even when clicking wrong element_
    - _Expected_Behavior: Telemetry success only when both verification AND click succeed_
    - _Preservation: Telemetry structure and registration mechanism unchanged_
    - _Requirements: 2.6, 3.6, 3.7_

  - [x] 3.4 Add cross-origin iframe warning logging
    - When `is_cross_origin == True`, log warning message indicating fail-open was applied
    - Distinguish between normal success and fail-open success in logs
    - Preserve existing cross-origin detection logic from `_resolver_elemento_em_iframe()`
    - _Bug_Condition: N/A (enhancement for observability)_
    - _Expected_Behavior: Clear logging when fail-open applies_
    - _Preservation: Cross-origin detection logic unchanged_
    - _Requirements: 3.3_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Identity Verification Before Click
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from Phase 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify that:
      - Identity verification occurs BEFORE click execution
      - Function returns False when identity verification fails
      - Click is NOT executed when identity verification fails
      - Telemetry reports failure when identity verification fails
      - Fallback layers execute when coordinates layer fails
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Fail-Open and Other Layers Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from Phase 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Verify that:
      - Empty `label_curto` still triggers fail-open
      - Cross-origin iframe still triggers fail-open
      - Verification exceptions still trigger fail-open
      - Correct coordinates still execute successfully
      - Sniper layer still operates identically
      - Hint layer still operates identically
      - Brain layer still operates identically
      - Brute Force layer still operates identically
      - `iframe_hint` logic still works identically
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

---

## Phase 4: Unit Testing

- [ ] 4. Write unit tests for `_verificar_identidade_por_coordenadas()`

  - [x] 4.1 Test identity verification with correct coordinates
    - Mock page with element at (100, 100) containing text "Confirmar"
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, "Confirmar", None)`
    - Assert returns `(True, False)` (identity confirmed, not cross-origin)
    - _Requirements: 2.2, 2.3_

  - [ ] 4.2 Test identity verification with wrong coordinates
    - Mock page with element at (100, 100) containing text "Cancelar"
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, "Confirmar", None)`
    - Assert returns `(False, False)` (identity NOT confirmed, not cross-origin)
    - _Requirements: 2.2, 2.4_

  - [ ] 4.3 Test fail-open with empty label_curto
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, "", None)`
    - Assert returns `(True, False)` (fail-open applied)
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, None, None)`
    - Assert returns `(True, False)` (fail-open applied)
    - _Requirements: 3.1_

  - [ ] 4.4 Test fail-open with cross-origin iframe
    - Mock `_resolver_elemento_em_iframe()` to return `is_cross_origin=True`
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, "Confirmar", None)`
    - Assert returns `(True, True)` (fail-open applied, cross-origin detected)
    - _Requirements: 3.3_

  - [ ] 4.5 Test fail-open with verification exception
    - Mock page to throw exception during element resolution
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, "Confirmar", None)`
    - Assert returns `(True, False)` (fail-open applied)
    - Verify warning log is emitted
    - _Requirements: 3.2_

  - [ ] 4.6 Test iframe_hint with coordinate adjustment
    - Mock page with iframe at offset (50, 50)
    - Mock element at (150, 150) in viewport (100, 100 in iframe)
    - Call `_verificar_identidade_por_coordenadas(page, 150, 150, "Confirmar", "myIframe")`
    - Assert coordinates are adjusted correctly
    - Assert identity verification uses adjusted coordinates
    - _Requirements: 3.4, 3.5_

  - [ ] 4.7 Test case-insensitive text matching
    - Mock element with text "CONFIRMAR"
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, "confirmar", None)`
    - Assert returns `(True, False)` (case-insensitive match)
    - _Requirements: 2.2, 2.3_

  - [ ] 4.8 Test substring matching
    - Mock element with text "Clique aqui para Confirmar a operação"
    - Call `_verificar_identidade_por_coordenadas(page, 100, 100, "Confirmar", None)`
    - Assert returns `(True, False)` (substring match)
    - _Requirements: 2.2, 2.3_

---

## Phase 5: Integration Testing

- [ ] 5. Write integration tests for full workflow

  - [ ] 5.1 Test full workflow with wrong coordinates (fallback layers execute)
    - Create test roteiro with `coords_relativas` pointing to wrong element
    - Set `label_curto` to expected element text
    - Mock Sniper layer to fail
    - Mock Hint layer to succeed
    - Execute `encontrar_e_clicar()`
    - Assert coordinates layer returns False (identity verification failed)
    - Assert Hint layer executes and succeeds
    - Assert telemetry shows `2_coords_capturadas: False` and `3_hint: True`
    - Assert winning strategy is `3_hint`
    - _Requirements: 2.4, 2.5, 3.6, 3.7_

  - [ ] 5.2 Test full workflow with correct coordinates (click executes successfully)
    - Create test roteiro with `coords_relativas` pointing to correct element
    - Set `label_curto` to match element text
    - Execute `encontrar_e_clicar()`
    - Assert coordinates layer returns True (identity verified and click succeeded)
    - Assert click is executed at correct coordinates
    - Assert telemetry shows `2_coords_capturadas: True`
    - Assert winning strategy is `2_coords_capturadas`
    - _Requirements: 2.2, 2.3, 2.6, 3.6, 3.7_

  - [ ] 5.3 Test full workflow with empty label_curto (fail-open behavior)
    - Create test roteiro with `coords_relativas` and empty `label_curto`
    - Execute `encontrar_e_clicar()`
    - Assert coordinates layer returns True (fail-open applied)
    - Assert click is executed without identity verification
    - Assert telemetry shows `2_coords_capturadas: True`
    - _Requirements: 3.1_

  - [ ] 5.4 Test full workflow with cross-origin iframe (fail-open behavior)
    - Create test roteiro with `coords_relativas` pointing to element in cross-origin iframe
    - Mock `_resolver_elemento_em_iframe()` to return `is_cross_origin=True`
    - Execute `encontrar_e_clicar()`
    - Assert coordinates layer returns True (fail-open applied)
    - Assert click is executed without identity verification
    - Assert warning log indicates cross-origin fail-open
    - _Requirements: 3.3_

  - [ ] 5.5 Test full workflow with iframe_hint (coordinate adjustment and verification)
    - Create test roteiro with `coords_relativas`, `label_curto`, and `iframe_hint`
    - Mock page with iframe at offset (50, 50)
    - Mock element at (150, 150) in viewport (100, 100 in iframe)
    - Execute `encontrar_e_clicar()`
    - Assert coordinates are adjusted for iframe offset
    - Assert identity verification uses adjusted coordinates
    - Assert click executes at adjusted coordinates
    - _Requirements: 3.4, 3.5_

  - [ ] 5.6 Test Brain learning with correct coordinates (Brain learns correct coordinates)
    - Create test roteiro with correct `coords_relativas` and `label_curto`
    - Execute `encontrar_e_clicar()` multiple times
    - Assert Brain records success for `2_coords_capturadas` layer
    - Assert Brain learns correct coordinates for the action
    - Verify Brain's learned coordinates match the correct element
    - _Requirements: 2.7_

  - [ ] 5.7 Test Brain does NOT learn wrong coordinates (Brain rejects wrong coordinates)
    - Create test roteiro with wrong `coords_relativas` (points to wrong element)
    - Set `label_curto` to expected element text
    - Execute `encontrar_e_clicar()`
    - Assert coordinates layer returns False (identity verification failed)
    - Assert Brain does NOT record success for `2_coords_capturadas` layer
    - Assert Brain does NOT learn the wrong coordinates
    - Verify fallback layer succeeds and Brain learns from that layer instead
    - _Requirements: 1.6, 1.7, 2.7_

  - [ ] 5.8 Test telemetry reporting (success only when both verification AND click succeed)
    - **Scenario 1**: Identity verification succeeds, click succeeds
      - Assert telemetry shows `2_coords_capturadas: True`
    - **Scenario 2**: Identity verification fails, click not executed
      - Assert telemetry shows `2_coords_capturadas: False`
    - **Scenario 3**: Identity verification succeeds, click fails (exception)
      - Assert telemetry shows `2_coords_capturadas: False`
    - **Scenario 4**: Fail-open applied, click succeeds
      - Assert telemetry shows `2_coords_capturadas: True`
    - _Requirements: 2.6, 3.6_

---

## Phase 6: Checkpoint

- [ ] 6. Checkpoint - Ensure all tests pass
  - Run all unit tests from Phase 4
  - Run all integration tests from Phase 5
  - Run bug condition exploration test from Phase 1 (should now PASS)
  - Run preservation property tests from Phase 2 (should still PASS)
  - Verify no regressions in other layers (Sniper, Hint, Brain, Brute Force)
  - Verify fail-open behavior preserved for all edge cases
  - Verify telemetry reporting is accurate
  - Verify Brain learning is correct
  - If any test fails, investigate root cause and fix before proceeding
  - Ask the user if questions arise

---

## Notes

### Bug Condition Methodology
- **C(X)**: Bug Condition - coordinates point to wrong element AND label_curto is present
- **P(result)**: Property - identity verification BEFORE click, success only when both verification AND click succeed
- **¬C(X)**: Non-buggy inputs - empty label_curto, cross-origin iframe, verification exceptions, correct coordinates, other layers
- **F**: Original (unfixed) function - clicks first, verifies after
- **F'**: Fixed function - verifies first, clicks only if verification succeeds

### Testing Strategy
1. **Exploratory Phase**: Surface counterexamples on unfixed code (test MUST fail)
2. **Preservation Phase**: Capture baseline behavior for non-buggy inputs (tests MUST pass on unfixed code)
3. **Implementation Phase**: Apply fix and verify both exploration and preservation tests pass
4. **Unit Testing Phase**: Test individual function behavior
5. **Integration Phase**: Test full workflow with Brain learning and telemetry

### Key Requirements Mapping
- **Requirements 1.x**: Current defective behavior (what we're fixing)
- **Requirements 2.x**: Expected correct behavior (what we're implementing)
- **Requirements 3.x**: Unchanged behavior (what we're preserving)
