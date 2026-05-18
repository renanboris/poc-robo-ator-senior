# Implementation Plan

## Overview
Este plano implementa o fix para o matching de boxes do SoM com tolerância, permitindo que cliques próximos (mas não exatamente dentro) sejam corretamente associados às boxes detectadas.

**Estratégia**: Seguir a metodologia de bug condition com testes exploratórios ANTES do fix, seguidos de testes de preservação, e finalmente a implementação com validação.

---

## Tasks

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - SoM Tolerance Matching for Near-Miss Clicks
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test implementation details from Bug Condition in design:
    - Generate click coordinates that are near boxes but outside strict boundaries
    - For each generated case, verify that `isBugCondition(input)` returns true
    - Calculate distance to center: `distance = sqrt((click_x - (box.x + box.w/2))^2 + (click_y - (box.y/2))^2)`
    - Calculate tolerance: `tolerance = max(box.w, box.h) * 0.3`
    - Verify that `distance <= tolerance` (click is within tolerance)
    - Verify that strict matching fails: `NOT (box.x <= click_x <= box.x + box.w AND box.y <= click_y <= box.y + box.h)`
  - The test assertions should match the Expected Behavior Properties from design:
    - Assert that `identificar_box_clicada(boxes, click_x, click_y)` returns the idx of the closest box within tolerance
    - Assert that the returned box is NOT null
    - Assert that the distance to the returned box's center is within tolerance
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found to understand root cause:
    - Example: Click at (256, 205) with 20 boxes detected returns None instead of closest box idx
    - Example: Click at (1199, 27) with 20 boxes detected returns None instead of closest box idx
    - Example: Click 5px outside box boundary returns None instead of matching with tolerance
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Matching Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs:
    - Test Case 1: Click exactly inside a box (strict match succeeds)
      - Observe: `identificar_box_clicada(boxes, click_x, click_y)` returns correct idx
      - Record the exact behavior for clicks at various positions inside boxes
    - Test Case 2: Click very far from any box (outside any reasonable tolerance)
      - Observe: `identificar_box_clicada(boxes, click_x, click_y)` returns None
      - Record the distance threshold where None is returned
    - Test Case 3: Click inside multiple overlapping boxes
      - Observe: `identificar_box_clicada(boxes, click_x, click_y)` returns smallest box idx
      - Record the area-based prioritization behavior
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - Property: For all clicks where `NOT isBugCondition(input)`, behavior is identical
    - Property: For all clicks strictly inside boxes, return same idx as before
    - Property: For all clicks very far from boxes, return None as before
    - Property: For all clicks inside multiple boxes, return smallest area box as before
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix for SoM box matching with tolerance

  - [x] 3.1 Implement the tolerance-based matching algorithm
    - Modify `identificar_box_clicada` function in `som_annotator.py` (line ~58)
    - **Phase 1: Preserve strict matching** (existing behavior)
      - Keep current logic that checks if click is within box boundaries
      - If strict match found, return immediately (prioritize smallest box if multiple matches)
      - This preserves existing behavior for clicks exactly inside boxes
    - **Phase 2: Add tolerance-based matching** (new behavior)
      - For each box, calculate distance to center: `center_x = box["x"] + box["w"] / 2`, `center_y = box["y"] + box["h"] / 2`
      - Calculate euclidean distance: `distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)`
      - Calculate dynamic tolerance: `tolerance = max(box["w"], box["h"]) * 0.3` (30% of largest dimension)
      - Collect boxes where `distance <= tolerance` as candidates
      - Sort candidates by distance (ascending), then by area (ascending) for tie-breaking
      - Return idx of closest box (smallest distance, smallest area if tied)
    - **Phase 3: Fallback to None** (preserved behavior)
      - If no candidates within tolerance, return None
      - This preserves existing behavior for clicks very far from any box
    - Add import for `math` module at top of file
    - Add informative logging when tolerance matching is used: `logger.info(f"SoM tolerance match: click ({x}, {y}) matched box #{idx} at distance {distance:.1f}px")`
    - _Bug_Condition: isBugCondition(input) where click is near box but strict matching fails_
    - _Expected_Behavior: Return idx of closest box within tolerance (30% of max dimension)_
    - _Preservation: Strict matches return same result, far clicks return None, overlaps prioritize smallest box_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - SoM Tolerance Matching for Near-Miss Clicks
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify that clicks near boxes (within tolerance) now return correct box idx
    - Verify that the returned box is the closest one within tolerance
    - Verify that distance-based matching works correctly
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Matching Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions):
      - Clicks exactly inside boxes still return correct idx
      - Clicks very far from boxes still return None
      - Clicks inside multiple boxes still return smallest box
      - All non-buggy inputs produce identical results to unfixed code
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run complete test suite to verify all tests pass
  - Verify no regressions in existing functionality
  - Test with real-world scenarios:
    - Ação 6 do roteiro "Senior_Flow_-_SIGN_-_Grupo_de_contatos": click at (256, 205) should now match a box
    - Ação 7 do mesmo roteiro: click at (1199, 27) should now match a box
  - Verify that `som_idx_clicado` and `som_box_clicada` are correctly populated in capture flow
  - Verify that descriptive SoM labels are used instead of generic radar labels
  - Ask the user if questions arise or if additional validation is needed

---

## Notes

### Bug Condition Methodology
- **C(X)**: Bug Condition - click is near a box (within tolerance) but strict matching fails
- **P(result)**: Property - system returns idx of closest box within tolerance
- **¬C(X)**: Non-buggy inputs - clicks exactly inside boxes or very far from any box
- **F**: Original `identificar_box_clicada` function (strict matching only)
- **F'**: Fixed `identificar_box_clicada` function (strict + tolerance matching)

### Testing Strategy
1. **Exploration Phase**: Write tests that FAIL on unfixed code to confirm bug exists
2. **Preservation Phase**: Write tests that PASS on unfixed code to capture baseline behavior
3. **Implementation Phase**: Apply fix and verify exploration tests now pass
4. **Validation Phase**: Verify preservation tests still pass (no regressions)

### Key Implementation Details
- Tolerance is dynamic: 30% of the largest dimension (width or height) of each box
- Prioritization: distance first (closest), then area (smallest) for tie-breaking
- Three-phase matching: strict → tolerance → None
- Logging added for observability when tolerance matching is used
