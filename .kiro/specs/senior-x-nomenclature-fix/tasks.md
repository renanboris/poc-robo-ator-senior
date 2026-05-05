# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - X Platform Nomenclature Detection
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists in the target files
  - **Scoped PBT Approach**: Scope the property to the concrete failing files: `biblioteca_acoes.json` and `shadow_exports/*.jsonl`
  - Test that `biblioteca_acoes.json` contains "X Platform" in string values (from Bug Condition in design)
  - Test that `shadow_exports/*.jsonl` files contain "X Platform" in string values (from Bug Condition in design)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (specific line numbers and contexts where "X Platform" appears)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - JSON Structure and Non-Nomenclature Content
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy content (all content that is NOT "X Platform")
  - Parse JSON structure from `biblioteca_acoes.json` and record: total keys, array lengths, object nesting depth
  - Sample non-nomenclature string values (action descriptions, selectors, URLs) and record their exact values
  - Sample numeric values (coordinates, viewport dimensions) and record their exact values
  - Write property-based tests capturing observed structural patterns from Preservation Requirements
  - Test that JSON structure remains identical (same keys, same nesting, same array lengths)
  - Test that non-nomenclature strings remain unchanged
  - Test that all numeric values remain unchanged
  - Test that file encoding remains UTF-8
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix for X Platform nomenclature

  - [x] 3.1 Implement the text replacement fix
    - Read entire content of `biblioteca_acoes.json` into memory
    - Perform case-sensitive exact string replacement: `"X Platform"` → `"X"`
    - Write complete updated content atomically to `biblioteca_acoes.json`
    - Verify JSON validity after write (parse the file to confirm no syntax errors)
    - Read each `*.jsonl` file in `shadow_exports/` directory
    - For each JSONL file: perform same replacement, write atomically, verify line-by-line JSON validity
    - Preserve file encoding (UTF-8) and line endings throughout all operations
    - _Bug_Condition: isBugCondition(input) where input.content CONTAINS "X Platform"_
    - _Expected_Behavior: All instances of "X Platform" replaced with "X", JSON remains valid_
    - _Preservation: All JSON structure, non-nomenclature strings, numeric values, and file encoding unchanged_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - X Platform Nomenclature Correction
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (no "X Platform" should exist)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed - no "X Platform" remains)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - JSON Structure and Non-Nomenclature Content
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions - structure and non-nomenclature content preserved)
    - Confirm all structural properties still match baseline
    - Confirm all non-nomenclature strings still match baseline
    - Confirm all numeric values still match baseline

- [x] 4. Checkpoint - Ensure all tests pass and perform integration verification
  - Ensure all tests pass (bug condition test + preservation tests)
  - Manual integration verification:
    - Start the application: `python app.py`
    - Verify no JSON parsing errors in logs related to `biblioteca_acoes.json`
    - Verify dashboard loads successfully
    - Verify action memory functionality works (if testable through UI)
  - Visual spot-check: Open `biblioteca_acoes.json` and verify "X Platform" → "X" replacement
  - Visual spot-check: Open a sample JSONL file from `shadow_exports/` and verify replacement
  - Ask the user if questions arise or if further validation is needed
