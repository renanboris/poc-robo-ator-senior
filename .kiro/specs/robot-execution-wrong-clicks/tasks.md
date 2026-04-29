# Implementation Plan

## Overview

This task list implements the fix for three critical bugs in iframe detection and resolution logic that cause the robot to click on wrong elements inside iframes. The bugs are: (1) `_resolver_contexto()` returns `FrameLocator` instead of `Frame`, (2) coordinates not adjusted correctly for iframe context, and (3) wrong element found (parent container instead of target button).

The implementation follows the bug condition methodology with exploratory testing BEFORE the fix, preservation testing BEFORE the fix, then implementation with verification.

---

## Phase 1: Exploratory Bug Condition Testing (BEFORE Fix)

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - iframe_hint Resolution and Element Identification
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the three bugs exist
  - **Scoped PBT Approach**: Scope the property to concrete failing cases from Senior X "ci" iframe clicks
  - Test implementation details from Bug Condition in design:
    - Call `_resolver_contexto(page, "ci")` and verify return type is `Frame` (not `FrameLocator`)
    - Simulate click at coordinates (1633, 732) with iframe_hint="ci"
    - Verify coordinates are adjusted correctly (e.g., X: 1633 → 1568, Y should also adjust if iframe.top ≠ 0)
    - Verify `elementFromPoint` is executed in Frame context with adjusted coordinates
    - Verify element found has innerText matching target label (e.g., "Acompanhar assinaturas"), not parent container text
  - The test assertions should match the Expected Behavior Properties from design (Requirements 2.1-2.10)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS with counterexamples showing:
    - `_resolver_contexto()` returns `FrameLocator` object (not `Frame`)
    - `hasattr(contexto, 'url')` returns False
    - System logs "iframe_hint não resolveu para Frame - usando detecção automática"
    - Coordinates remain unchanged or incorrectly adjusted (e.g., Y: 732 → 732)
    - `elementFromPoint` returns parent container with text like "SIGN\nCaixa de Entrada\nFILTRAR DADOS\n..."
    - Identity verification fails, system escalates to Gemini Vision
  - Document counterexamples found to understand root cause
  - Mark task complete when test is written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

---

## Phase 2: Preservation Property Testing (BEFORE Fix)

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-iframe_hint Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (cases where isBugCondition returns false):
    - Clicks without iframe_hint (should use automatic detection)
    - Clicks with generic iframe_hint values ("Pagina Principal", "Página Principal", "iframe-cross-origin")
    - Clicks in main page context (no iframe involved)
    - Cross-origin iframe clicks (should trigger fail-open behavior)
    - Automatic detection fallback when iframe_hint resolution fails
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - Test that clicks without iframe_hint continue to use automatic detection
    - Test that generic iframe_hint values return Page context
    - Test that main page clicks work without coordinate adjustment
    - Test that cross-origin iframes trigger fail-open (accept click without verification)
    - Test that automatic detection fallback works correctly
    - Test that label_curto empty/missing skips identity verification
    - Test that nested iframe resolution continues to work up to max_depth
    - Test that error handling and logging for iframe failures continue to work
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

---

## Phase 3: Implementation

- [ ] 3. Fix iframe resolution, coordinate adjustment, and element identification bugs

  - [ ] 3.1 Fix `_resolver_contexto()` to return Frame objects (Bug 1)
    - **File**: `vision_engine.py` (lines 597-625)
    - **Change**: Modify function to return actual `Frame` objects instead of `FrameLocator` objects
    - After successfully waiting for iframe with `frame_locator().locator("body").wait_for()`, iterate through `page.frames` to find matching Frame
    - Match Frame by checking if `iframe_hint` appears in `frame.url` or `frame.name`
    - Return the matched `Frame` object instead of the `FrameLocator`
    - Preserve existing fallback logic that iterates through `page.frames` when frame_locator fails
    - Preserve early return of `page` when iframe_hint is None or generic
    - Implementation pseudocode from design:
      ```python
      async def _resolver_contexto(page: Page, iframe_hint: Optional[str]):
          if not iframe_hint or iframe_hint in ("Pagina Principal", "Página Principal", "iframe-cross-origin"):
              return page
          
          # Try frame_locator approach first
          for seletor_iframe in [
              f"iframe[name='{iframe_hint}']", f"iframe[src*='{iframe_hint}']",
              f"iframe[id='{iframe_hint}']", f"iframe[title*='{iframe_hint}']",
          ]:
              try:
                  fl = page.frame_locator(seletor_iframe)
                  await fl.locator("body").wait_for(state="attached", timeout=800)
                  
                  # FIX: After confirming iframe exists, find the actual Frame object
                  for frame in page.frames:
                      try:
                          if iframe_hint in frame.url or iframe_hint in frame.name:
                              return frame  # Return Frame, not FrameLocator
                      except Exception:
                          continue
              except Exception:
                  continue
          
          # Fallback: iterate through frames directly
          try:
              for frame in page.frames:
                  try:
                      if iframe_hint in frame.url or iframe_hint in frame.name:
                          return frame
                  except Exception:
                      continue
          except Exception:
              pass
          
          return page
      ```
    - _Bug_Condition: isBugCondition(input) where input.iframe_hint is not None and not generic_
    - _Expected_Behavior: _resolver_contexto returns Frame object with .url and .name attributes_
    - _Preservation: Preserve fallback logic, preserve generic iframe_hint handling_
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.2 Fix Frame detection check in coordinate adjustment logic (Bug 2 - Part 1)
    - **File**: `vision_engine.py` (lines 1658-1750, layer 2 coordinate capture logic)
    - **Change**: Replace `hasattr(contexto, 'url')` with robust type check
    - Import `Frame` from `playwright.async_api`
    - Use `isinstance(contexto, Frame)` to detect when contexto is a Frame
    - This ensures correct identification of Frame vs Page vs FrameLocator
    - Implementation pseudocode from design:
      ```python
      from playwright.async_api import Frame
      
      if isinstance(contexto, Frame):
          # Frame context - need coordinate adjustment
      ```
    - _Bug_Condition: isBugCondition(input) where contexto is Frame but hasattr check fails_
    - _Expected_Behavior: isinstance(contexto, Frame) correctly identifies Frame objects_
    - _Preservation: Preserve Page context handling, preserve FrameLocator fallback_
    - _Requirements: 2.2, 2.4_

  - [ ] 3.3 Fix coordinate adjustment for Frame context (Bug 2 - Part 2)
    - **File**: `vision_engine.py` (lines 1658-1750, layer 2 coordinate capture logic)
    - **Change**: Correctly obtain iframe bounding box and adjust coordinates
    - Execute JavaScript in main page context to find iframe element and get its bounding box
    - Match iframe by checking name, src, id, or title attributes against iframe_hint
    - Subtract iframe's left and top offsets from original coordinates
    - Log the coordinate transformation for debugging
    - Implementation pseudocode from design:
      ```python
      if isinstance(contexto, Frame):
          # Get iframe bounding box from main page
          iframe_bbox = await page.evaluate(f"""
              () => {{
                  const iframes = document.querySelectorAll('iframe');
                  for (const iframe of iframes) {{
                      if (iframe.name === '{iframe_hint}' || 
                          iframe.src.includes('{iframe_hint}') ||
                          iframe.id === '{iframe_hint}' ||
                          (iframe.title && iframe.title.includes('{iframe_hint}'))) {{
                          const bbox = iframe.getBoundingClientRect();
                          return {{ left: bbox.left, top: bbox.top }};
                      }}
                  }}
                  return null;
              }}
          """)
          
          if iframe_bbox:
              x_ajustado = int(x - iframe_bbox['left'])
              y_ajustado = int(y - iframe_bbox['top'])
              logger.info(f"   [Coords Capturadas] Coordenadas ajustadas: ({x}, {y}) -> ({x_ajustado}, {y_ajustado})")
      ```
    - _Bug_Condition: isBugCondition(input) where coordinates need adjustment for iframe_
    - _Expected_Behavior: Both X and Y coordinates correctly adjusted relative to iframe position_
    - _Preservation: Preserve main page coordinate handling (no adjustment)_
    - _Requirements: 2.4, 2.5_

  - [ ] 3.4 Execute elementFromPoint in correct Frame context (Bug 3)
    - **File**: `vision_engine.py` (lines 1658-1750, layer 2 coordinate capture logic)
    - **Change**: Execute elementFromPoint in Frame context with adjusted coordinates
    - Use `contexto.evaluate()` instead of `page.evaluate()` when contexto is Frame
    - Pass adjusted coordinates to Frame's elementFromPoint
    - Set is_cross_origin = False for successful Frame execution
    - Add fallback to automatic detection if iframe bbox not found
    - Implementation pseudocode from design:
      ```python
      if iframe_bbox:
          # Execute elementFromPoint in Frame context with adjusted coordinates
          elemento_info = await contexto.evaluate("""
              ([x, y]) => {
                  const el = document.elementFromPoint(x, y);
                  if (!el) return null;
                  return {
                      tagName: el.tagName,
                      innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                  };
              }
          """, [x_ajustado, y_ajustado])
          
          is_cross_origin = False
          x_final = x_ajustado
          y_final = y_ajustado
      else:
          # Fallback if iframe bbox not found
          logger.warning(f"   [Coords Capturadas] Iframe bbox não encontrado - fallback")
          elemento_info, x_final, y_final, is_cross_origin = await _resolver_elemento_em_iframe(page, x, y)
      ```
    - _Bug_Condition: isBugCondition(input) where elementFromPoint must execute in Frame_
    - _Expected_Behavior: elementFromPoint returns target element, not parent container_
    - _Preservation: Preserve automatic detection fallback, preserve Page context execution_
    - _Requirements: 2.6, 2.7, 2.8, 2.9, 2.10_

  - [ ] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - iframe_hint Resolution and Element Identification
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES with results showing:
      - `_resolver_contexto()` returns `Frame` object (not `FrameLocator`)
      - `isinstance(contexto, Frame)` returns True
      - Coordinates correctly adjusted (e.g., X: 1633 → 1568, Y adjusted if iframe.top ≠ 0)
      - `elementFromPoint` executed in Frame context with adjusted coordinates
      - Element found has innerText matching target label (e.g., "Acompanhar assinaturas")
      - Identity verification succeeds without escalating to Gemini Vision
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

  - [ ] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-iframe_hint Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all preservation tests still pass after fix:
      - Clicks without iframe_hint continue to use automatic detection
      - Generic iframe_hint values continue to return Page context
      - Main page clicks continue to work without coordinate adjustment
      - Cross-origin iframes continue to trigger fail-open behavior
      - Automatic detection fallback continues to work
      - Empty label_curto continues to skip identity verification
      - Nested iframe resolution continues to work
      - Error handling continues to work
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

---

## Phase 4: Integration Testing and Validation

- [ ] 4. Integration testing with real Senior X workflows
  - Test full robot execution flow with iframe_hint="ci" in Senior X
  - Test clicking "Acompanhar assinaturas" button inside "ci" iframe
  - Test clicking multiple buttons inside the same iframe in sequence
  - Test switching between main page clicks and iframe clicks in the same workflow
  - Verify success rate improves from 4.2% (1/24) to >90%
  - Verify Gemini Vision escalation rate decreases significantly
  - Verify no regressions in non-iframe click scenarios
  - Test nested iframe scenarios if applicable
  - Test cross-origin iframe scenarios with fail-open behavior
  - Document any edge cases or unexpected behaviors found
  - _Requirements: All requirements (1.1-3.8)_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure bug condition exploration test passes (task 3.5)
  - Ensure preservation property tests pass (task 3.6)
  - Ensure integration tests pass (task 4)
  - Review logs for any warnings or unexpected fallback behavior
  - Confirm identity verification succeeds for iframe clicks with iframe_hint
  - Confirm no escalation to Gemini Vision for correctly resolved iframe clicks
  - Ask the user if questions arise or if additional testing is needed

---

## Notes

**Testing Framework**: Use pytest with Hypothesis for property-based testing. The test file should be created in a tests directory (e.g., `tests/test_iframe_resolution.py`).

**Test Execution Order**: 
1. Run exploration test on UNFIXED code (expect failures)
2. Run preservation tests on UNFIXED code (expect passes)
3. Implement fixes (tasks 3.1-3.4)
4. Re-run exploration test on FIXED code (expect passes)
5. Re-run preservation tests on FIXED code (expect passes)
6. Run integration tests on FIXED code (expect passes)

**Success Criteria**:
- Bug condition exploration test transitions from FAIL (unfixed) to PASS (fixed)
- Preservation tests remain PASS on both unfixed and fixed code
- Integration tests show >90% success rate for iframe clicks with iframe_hint
- Gemini Vision escalation rate decreases significantly
- No regressions in non-iframe click scenarios
