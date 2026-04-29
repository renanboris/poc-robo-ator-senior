# Implementation Plan

## Overview
Este plano implementa a correção do bug de localização de elementos em iframes usando a metodologia de bug condition. A estratégia é: (1) escrever testes exploratórios ANTES da correção para demonstrar o bug, (2) escrever testes de preservação para capturar comportamento existente, (3) implementar a correção, (4) validar que os testes agora passam.

---

## Phase 1: Exploratory Bug Condition Checking (BEFORE Fix)

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Iframe Element Resolution Failure
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test implementation details from Bug Condition in design:
    - Create test HTML page with iframe containing button "Salvar" at known coordinates
    - Execute `page.evaluate("document.elementFromPoint(x, y)")` in main page context
    - Assert that current implementation returns `<iframe>` element (not the button inside)
    - Assert that `innerText` of returned element is "iframe platform" (not "Salvar")
    - Assert that identity verification fails because "Salvar" not in "iframe platform"
  - The test assertions should match the Expected Behavior Properties from design:
    - After fix: should detect iframe, adjust coordinates, and find button with text "Salvar"
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found to understand root cause:
    - Example: `elementFromPoint(960, 540)` returns `<iframe>` instead of `<button>`
    - Example: Identity verification fails with "esperado 'Salvar', encontrado 'iframe platform'"
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

---

## Phase 2: Preservation Property Tests (BEFORE Fix)

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Iframe Element Behavior
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs:
    - Test 1: Click on button in main page (outside iframe) at coordinates (100, 100)
    - Observe: `elementFromPoint(100, 100)` returns `<button>` with correct text
    - Observe: Identity verification passes
    - Observe: Telemetry registers success for `2_coords_capturadas`
    - Test 2: Click with empty `label_curto` (fail-open case)
    - Observe: Identity verification skipped, click accepted
    - Test 3: Click when `page.evaluate` throws exception
    - Observe: Fail-open applied, click accepted
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - Property: For all coordinates pointing to elements outside iframes, identity verification behaves exactly as before
    - Property: For all fail-open cases (empty label, exception), behavior is unchanged
    - Property: For all other fallback layers (Brain, Sniper, Vision), behavior is unchanged
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

---

## Phase 3: Implementation

- [x] 3. Fix for iframe element location failure

  - [x] 3.1 Create helper function `_resolver_elemento_em_iframe`
    - Implement recursive iframe detection and coordinate adjustment
    - **Input**: `page: Page, x: int, y: int, max_depth: int = 5`
    - **Output**: `tuple[dict, int, int, bool]` - (elemento_info, x_ajustado, y_ajustado, is_cross_origin)
    - **Logic**:
      - Execute `elementFromPoint(x, y)` in current context
      - If element is iframe:
        - Get iframe bounding box (`getBoundingClientRect()`)
        - Calculate relative coordinates: `x_rel = x - bbox.left`, `y_rel = y - bbox.top`
        - Check if iframe is cross-origin (try/catch on `contentWindow`)
        - If cross-origin: return (iframe_info, x, y, True) with cross-origin flag
        - If accessible: find frame in `page.frames` by src/name
        - If frame found: recursively call `_resolver_elemento_em_iframe_frame` with (x_rel, y_rel)
        - If frame not found: return (iframe_info, x, y, True) with cross-origin flag
      - If element is not iframe: return (elemento_info, x, y, False)
      - If max_depth reached: log warning and return current element
    - Add comprehensive error handling with fail-open behavior
    - Add diagnostic logs for iframe detection and coordinate adjustment
    - _Bug_Condition: isBugCondition(input) where elementFromPoint returns iframe_
    - _Expected_Behavior: Detect iframe, adjust coordinates, find element inside iframe_
    - _Preservation: Elements outside iframes use original logic (no iframe detection)_
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Create helper function `_resolver_elemento_em_iframe_frame`
    - Implement Frame context version of iframe resolution
    - **Input**: `frame: Frame, x: int, y: int, max_depth: int`
    - **Output**: `tuple[dict, int, int, bool]` - (elemento_info, x_ajustado, y_ajustado, is_cross_origin)
    - **Logic**: Similar to `_resolver_elemento_em_iframe` but using `frame.evaluate` instead of `page.evaluate`
    - Handle nested iframes recursively
    - Add error handling and diagnostic logs
    - _Bug_Condition: Nested iframes require recursive resolution_
    - _Expected_Behavior: Recursively resolve through iframe hierarchy_
    - _Preservation: Single-level iframe resolution unchanged_
    - _Requirements: 2.2, 2.3_

  - [x] 3.3 Modify identity verification in `2_coords_capturadas` layer
    - Replace direct `page.evaluate("document.elementFromPoint(x, y)")` with call to `_resolver_elemento_em_iframe`
    - **Before** (lines ~1467-1476):
      ```python
      texto_elemento = await page.evaluate(
          """([x, y]) => {
              const el = document.elementFromPoint(x, y);
              return el ? (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '') : '';
          }""",
          [x, y]
      )
      ```
    - **After**:
      ```python
      elemento_info, x_final, y_final, is_cross_origin = await _resolver_elemento_em_iframe(page, x, y)
      
      if is_cross_origin:
          # Fail-open for cross-origin iframes
          logger.warning(f"   [Coords Capturadas] Iframe cross-origin detectado - fail-open aplicado")
          identidade_confirmada = True
      elif elemento_info and elemento_info.get('innerText'):
          texto_elemento = elemento_info['innerText']
          if label_curto.strip().lower() in texto_elemento.strip().lower():
              identidade_confirmada = True
          else:
              logger.warning(
                  f"   [Coords Capturadas] Identidade não confirmada: "
                  f"esperado '{label_curto}', encontrado '{texto_elemento[:50]}' em ({x_final}, {y_final})"
              )
      else:
          # Fail-open: element without text
          identidade_confirmada = True
      ```
    - Preserve existing fail-open behavior for empty `label_curto` and exceptions
    - Add new fail-open for cross-origin iframes
    - Add diagnostic logs for iframe detection and coordinate adjustment
    - _Bug_Condition: Identity verification executed in wrong context (main page instead of iframe)_
    - _Expected_Behavior: Identity verification executed in correct context (inside iframe)_
    - _Preservation: Fail-open behavior unchanged, elements outside iframes unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 3.1, 3.2, 3.3_

  - [x] 3.4 Use `iframe_hint` when available
    - Check if `iframe_hint` is present in `elemento_alvo` before executing `elementFromPoint`
    - If `iframe_hint` available:
      - Use `_resolver_contexto(page, iframe_hint)` to get frame context
      - Get frame bounding box to adjust coordinates
      - Execute `elementFromPoint` directly in frame context with adjusted coordinates
    - If `iframe_hint` not available or generic ("Pagina Principal", "iframe-cross-origin"):
      - Use `_resolver_elemento_em_iframe` for automatic detection
    - Add logs when `iframe_hint` is used vs automatic detection
    - _Bug_Condition: iframe_hint available but not used for identity verification_
    - _Expected_Behavior: Use iframe_hint to resolve context before elementFromPoint_
    - _Preservation: Behavior when iframe_hint absent unchanged_
    - _Requirements: 2.4_

  - [x] 3.5 Add diagnostic logs
    - Log when iframe is detected: `logger.info(f"[Coords Capturadas] Iframe detectado em ({x}, {y}), ajustando para ({x_rel}, {y_rel})")`
    - Log when cross-origin iframe is detected: `logger.warning(f"[Coords Capturadas] Iframe cross-origin detectado - aplicando fail-open")`
    - Log when `iframe_hint` is used: `logger.info(f"[Coords Capturadas] Usando iframe_hint: {iframe_hint}")`
    - Log when automatic iframe detection is used: `logger.info(f"[Coords Capturadas] Detecção automática de iframe ativada")`
    - Log when max_depth is reached: `logger.warning(f"[Coords Capturadas] Max depth atingido na resolução de iframes aninhados")`
    - _Expected_Behavior: Observability for iframe detection and resolution_
    - _Preservation: Existing log format and levels unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.6 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Iframe Element Resolution Success
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify that:
      - `_resolver_elemento_em_iframe` detects iframe at coordinates
      - Coordinates are adjusted correctly (x_rel, y_rel)
      - `elementFromPoint` executed in iframe context returns button (not iframe)
      - Identity verification finds "Salvar" in button text
      - Camada `2_coords_capturadas` registers success
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 3.7 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Iframe Element Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Verify that:
      - Elements outside iframes are located exactly as before
      - Fail-open behavior (empty label, exceptions) unchanged
      - Other fallback layers (Brain, Sniper, Vision) unchanged
      - Telemetry and logs unchanged for non-iframe cases
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

---

## Phase 4: Integration Testing

- [x] 4. Integration tests and validation

  - [x] 4.1 Test complete workflow with Senior X iframes
    - Execute real roteiro with elements inside Senior X iframes
    - Verify that camada `2_coords_capturadas` succeeds for iframe elements
    - Verify that identity verification passes with correct text
    - Verify that fallback layers are NOT triggered unnecessarily
    - Measure success rate of `2_coords_capturadas` layer
    - **Target**: Success rate >90% (current: 5-6%)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 4.2 Test nested iframes
    - Create test page with nested iframes (iframe inside iframe)
    - Verify that recursive resolution works correctly
    - Verify that coordinates are adjusted at each level
    - Verify that max_depth protection prevents infinite loops
    - _Requirements: 2.2, 2.3_

  - [x] 4.3 Test cross-origin iframes
    - Create test page with cross-origin iframe
    - Verify that cross-origin detection works
    - Verify that fail-open is applied (click accepted without identity verification)
    - Verify that warning log is emitted
    - _Requirements: 2.1, 2.2_

  - [x] 4.4 Test iframe_hint usage
    - Execute roteiro with `iframe_hint` present in `elemento_alvo`
    - Verify that `iframe_hint` is used to resolve context
    - Verify that automatic detection is NOT triggered when hint is available
    - Verify that log indicates hint usage
    - _Requirements: 2.4_

  - [x] 4.5 Measure HITL rate reduction
    - Execute multiple roteiros with iframe elements
    - Measure HITL (Human-in-the-Loop) intervention rate
    - **Target**: HITL rate <10% (current: 29%)
    - Compare before/after metrics
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 4.6 Verify telemetry accuracy
    - Verify that `_registrar_telemetria("2_coords_capturadas", True)` is called for successful iframe clicks
    - Verify that `_registrar_telemetria("2_coords_capturadas", False)` is called for legitimate failures
    - Verify that telemetry is NOT affected by iframe detection (only by actual success/failure)
    - Query `telemetria_camadas` table to confirm accuracy
    - _Requirements: 3.6_

---

## Phase 5: Checkpoint

- [x] 5. Final validation checkpoint
  - Ensure all tests pass (exploratory, preservation, integration)
  - Verify success rate of `2_coords_capturadas` layer >90%
  - Verify HITL rate <10%
  - Verify no regressions in other fallback layers
  - Verify telemetry accuracy
  - Ask the user if questions arise or if additional validation is needed

---

## Notes

### Test Execution Order (CRITICAL)
1. **First**: Write and run exploratory test (task 1) on UNFIXED code - MUST FAIL
2. **Second**: Write and run preservation tests (task 2) on UNFIXED code - MUST PASS
3. **Third**: Implement the fix (tasks 3.1-3.5)
4. **Fourth**: Re-run exploratory test (task 3.6) on FIXED code - MUST PASS
5. **Fifth**: Re-run preservation tests (task 3.7) on FIXED code - MUST PASS
6. **Sixth**: Run integration tests (task 4) on FIXED code

### Property-Based Testing Framework
- Use Hypothesis for Python property-based testing
- Install: `pip install hypothesis`
- Example test structure:
  ```python
  from hypothesis import given, strategies as st
  
  @given(
      x=st.integers(min_value=0, max_value=1920),
      y=st.integers(min_value=0, max_value=1080)
  )
  def test_preservation_non_iframe_elements(x, y):
      # Test that elements outside iframes behave exactly as before
      pass
  ```

### Fail-Open Behavior
The fix preserves and extends fail-open behavior:
- **Existing**: Empty `label_curto` → accept click
- **Existing**: `page.evaluate` exception → accept click
- **New**: Cross-origin iframe → accept click
- **Rationale**: Fail-open prevents blocking legitimate clicks when verification is impossible

### Diagnostic Logs
All new logs follow existing format:
- `logger.info()` for normal operation (iframe detected, coordinates adjusted)
- `logger.warning()` for fail-open cases (cross-origin, max depth)
- Prefix: `[Coords Capturadas]` for consistency with existing logs

### Success Metrics
- **Primary**: Success rate of `2_coords_capturadas` layer: 5-6% → >90%
- **Secondary**: HITL intervention rate: 29% → <10%
- **Tertiary**: No regressions in other layers (Brain, Sniper, Vision)
