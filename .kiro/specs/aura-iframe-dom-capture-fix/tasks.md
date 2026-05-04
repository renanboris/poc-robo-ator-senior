# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Iframe Elements Not Captured
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Create test HTML page with accessible iframe containing interactive elements (buttons, inputs)
  - Load AURA extension (unfixed version) in test environment
  - Execute `AuraDomMapper.capturar()` via console
  - Verify that iframe elements DO NOT appear in the returned DOM context string
  - Document specific counterexamples found (e.g., "button 'Novo Documento' inside iframe ecm_sign not captured")
  - Test implementation details from Bug Condition in design: `isBugCondition(input) where input.page_has_iframes = true AND input.at_least_one_iframe_is_accessible = true AND input.dom_context_includes_iframe_elements = false`
  - The test assertions should match the Expected Behavior Properties from design: elements inside accessible iframes should be captured and included in DOM context
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Iframe Page Behavior
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (pages without iframes or with inaccessible cross-origin iframes)
  - Create test HTML pages: (a) no iframes, (b) cross-origin iframe, (c) empty iframe
  - Execute `AuraDomMapper.capturar()` on UNFIXED code for each scenario
  - Document observed outputs (format, element IDs, text content)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - Main document elements are captured correctly
    - Output format matches: `[ID: ${index}] TIPO: ${tagName} | TEXTO: "${texto}"`
    - Duplicate filtering based on text works correctly
    - `data-aura-map` attributes are assigned with unique indices
    - AURA container elements are excluded
    - Visibility logic (bounding box) works correctly
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix for iframe DOM capture

  - [x] 3.1 Implement the fix in `aura_dom_mapper.js`
    - Extract current capture logic into helper function `_capturarEmDocumento(doc, frameInfo, startIndex)`
      - `doc`: Document or contentDocument to capture from
      - `frameInfo`: null for main document, or `{ name: string, element: HTMLIFrameElement }` for iframes
      - `startIndex`: starting index for element IDs to maintain global uniqueness
      - Returns: `{ elementos: Array, proximoIndice: number }`
    - Modify main `capturar()` function to:
      - Call `_capturarEmDocumento(document, null, 0)` for main document
      - Query all iframes: `document.querySelectorAll('iframe')`
      - For each iframe, wrap in try-catch:
        - Access `frame.contentDocument || frame.contentWindow.document`
        - If accessible, call `_capturarEmDocumento(frameDoc, { name: frame.name || frame.id || 'iframe', element: frame }, proximoIndice)`
        - If SecurityError (cross-origin), silently continue to next iframe
      - Concatenate all captured elements maintaining global index sequence
    - Modify output format to include iframe indicator:
      - Main document elements: `[ID: ${index}] TIPO: ${tagName} | TEXTO: "${texto}"`
      - Iframe elements: `[ID: ${index}] TIPO: ${tagName} | TEXTO: "${texto}" (iframe: ${frameName})`
    - Ensure `data-aura-map` indices remain globally unique across main document and all iframes
    - Preserve all existing filtering logic: visibility check, duplicate text filtering, AURA container exclusion
    - _Bug_Condition: isBugCondition(input) where input.page_has_iframes = true AND input.at_least_one_iframe_is_accessible = true_
    - _Expected_Behavior: For all inputs satisfying bug condition, capturar() SHALL iterate over accessible iframes and include their elements in DOM context with iframe indicator_
    - _Preservation: Main document capture, output format, duplicate filtering, data-aura-map uniqueness, AURA container exclusion, visibility logic must remain unchanged for pages without accessible iframes_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Iframe Elements Captured
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Load AURA extension (FIXED version) in test environment
    - Execute the same test HTML page from task 1
    - Run `AuraDomMapper.capturar()` via console
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify that iframe elements now appear in DOM context with iframe indicator
    - Verify that element IDs are globally unique across main document and iframes
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Iframe Page Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2 on FIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Verify that pages without iframes produce identical output to unfixed version
    - Verify that cross-origin iframes don't cause failures
    - Verify that all preservation requirements are satisfied
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Write unit tests for iframe capture logic

  - [x] 4.1 Test `_capturarEmDocumento` helper function
    - Test capture from main document (frameInfo = null)
    - Test capture from iframe document (frameInfo with name)
    - Test that startIndex is respected and indices increment correctly
    - Test that visibility filtering works in both contexts
    - Test that duplicate text filtering works in both contexts
    - Test that AURA container exclusion works in both contexts

  - [x] 4.2 Test iframe iteration and error handling
    - Test that accessible same-origin iframes are processed
    - Test that cross-origin SecurityError is caught and handled silently
    - Test that empty iframes don't add elements but don't cause errors
    - Test that multiple iframes are processed in DOM order
    - Test that iframe name/id is correctly extracted for indicator

  - [x] 4.3 Test global index uniqueness
    - Test that indices don't restart for each iframe
    - Test that `data-aura-map` values are unique across entire page
    - Test that indices increment sequentially: main doc → iframe1 → iframe2

  - [x] 4.4 Test output format with iframe indicator
    - Test that main document elements don't have iframe indicator
    - Test that iframe elements include `(iframe: ${name})` suffix
    - Test that iframe name fallback works: name → id → 'iframe'

- [x] 5. Write integration tests

  - [x] 5.1 Test complete capture flow with iframes
    - Create test page with main document elements + iframe elements
    - Execute `AuraDomMapper.capturar()`
    - Verify complete DOM context includes both main and iframe elements
    - Verify format is correct for all elements
    - Verify indices are globally unique

  - [x] 5.2 Test AuraSpotlight integration
    - Capture DOM context including iframe elements
    - Use captured element ID to call `AuraSpotlight.aplicar(elementId)`
    - Verify that highlight works correctly for iframe elements
    - Verify that scroll and backdrop work across iframe boundaries

  - [x] 5.3 Test Senior X GED scenario (manual)
    - Navigate to Senior X GED page (iframe ecm_sign)
    - Execute `AuraDomMapper.capturar()` via console
    - Verify that GED buttons/inputs appear in DOM context
    - Verify that iframe indicator shows "ecm_sign"
    - Test AURA question: "onde estou?" - verify correct location identification
    - Test AURA interaction: ask to click a button inside iframe - verify highlight works

- [x] 6. Checkpoint - Ensure all tests pass
  - Run all unit tests and verify they pass
  - Run all property-based tests and verify they pass
  - Run integration tests and verify they pass
  - Perform manual testing in Senior X GED environment
  - Verify no regressions in pages without iframes
  - Verify cross-origin iframes don't cause errors
  - Document any edge cases or limitations discovered
  - If any issues arise, investigate root cause before proceeding
