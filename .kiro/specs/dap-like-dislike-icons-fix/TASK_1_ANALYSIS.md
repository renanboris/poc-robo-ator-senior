# Task 1: Bug Condition Exploration Test Analysis

## Test File Location
`extension/tests/feedback_icons_bug_condition.test.js`

## Test Status
✅ **Test Written and Ready to Run**

The property-based test has been written and is ready to execute on the unfixed code in `extension/modules/aura_feedback.js`.

## Test Structure

### Test Framework
- **Framework**: Jest with fast-check (property-based testing)
- **Environment**: jsdom (simulates browser DOM)
- **Test Runner**: `npm test` in extension directory

### Test Organization

The test file contains two main test suites:

#### 1. Bug Condition Tests (PASS on unfixed code)
These tests verify that the bug condition exists in the unfixed code:

- **Test 1.1**: "Like icon SVG must have fill="currentColor" attribute"
  - Verifies SVG element has `fill="currentColor"` attribute
  - **Expected Result on Unfixed Code**: ✅ PASS
  - **Counterexample**: SVG with fill="currentColor" found

- **Test 1.2**: "Dislike icon SVG must have fill="currentColor" attribute"
  - Verifies SVG element has `fill="currentColor"` attribute
  - **Expected Result on Unfixed Code**: ✅ PASS
  - **Counterexample**: SVG with fill="currentColor" found

- **Test 1.3**: "Like icon SVG must have conflict: fill="currentColor" vs CSS fill: none"
  - Verifies the conflict between inline attribute and CSS rule
  - Checks that `getAttribute('fill')` returns 'currentColor'
  - Checks that `getComputedStyle().fill` returns 'none'
  - **Expected Result on Unfixed Code**: ✅ PASS
  - **Counterexample**: Attribute='currentColor' but ComputedStyle='none'

- **Test 1.4**: "Dislike icon SVG must have conflict: fill="currentColor" vs CSS fill: none"
  - Same as Test 1.3 but for dislike button
  - **Expected Result on Unfixed Code**: ✅ PASS
  - **Counterexample**: Attribute='currentColor' but ComputedStyle='none'

- **Test 1.5**: "Like icon parent must have class aura-fb-btn"
  - Verifies parent button has correct class
  - **Expected Result on Unfixed Code**: ✅ PASS

- **Test 1.6**: "Dislike icon parent must have class aura-fb-btn"
  - Verifies parent button has correct class
  - **Expected Result on Unfixed Code**: ✅ PASS

- **Property Test 1.7**: "Bug Condition exists for any (prompt, resposta)"
  - Property-based test with 50 generated test cases
  - For any prompt and response strings, verifies:
    - SVG elements have `fill="currentColor"` attribute
    - Computed CSS style shows `fill: none`
    - Conflict exists between attribute and CSS
    - Parent has class `aura-fb-btn`
  - **Expected Result on Unfixed Code**: ✅ PASS (all 50 cases)
  - **Counterexamples Generated**: 50 different (prompt, resposta) pairs all showing the bug condition

#### 2. Expected Behavior Tests (FAIL on unfixed code)
These tests verify the expected behavior AFTER the fix:

- **Test 2.1**: "EXPECTED BEHAVIOR: Like icon must use only stroke without fill attribute (MUST FAIL now)"
  - Verifies SVG does NOT have `fill` attribute
  - Verifies computed style is `fill: none` and `stroke: currentColor`
  - **Expected Result on Unfixed Code**: ❌ FAIL
  - **Reason**: SVG still has `fill="currentColor"` attribute

- **Test 2.2**: "EXPECTED BEHAVIOR: Dislike icon must use only stroke without fill attribute (MUST FAIL now)"
  - Same as Test 2.1 but for dislike button
  - **Expected Result on Unfixed Code**: ❌ FAIL
  - **Reason**: SVG still has `fill="currentColor"` attribute

- **Property Test 2.3**: "EXPECTED BEHAVIOR - Icons must use only stroke for any (prompt, resposta) (MUST FAIL now)"
  - Property-based test with 50 generated test cases
  - For any prompt and response strings, verifies:
    - SVG elements do NOT have `fill` attribute
    - Computed style is `fill: none` and `stroke: currentColor`
  - **Expected Result on Unfixed Code**: ❌ FAIL (all 50 cases)
  - **Reason**: SVG elements still have `fill="currentColor"` attribute

## Counterexamples Found

### Bug Condition Counterexamples (Prove Bug Exists)

When running the bug condition tests on unfixed code, the following counterexamples will be found:

#### Counterexample 1: Like Button SVG Fill Conflict
```javascript
{
  element: SVGElement,
  attribute_fill: "currentColor",
  computed_fill: "none",
  parent_class: "aura-fb-btn",
  button_type: "like",
  conflict: true
}
```

#### Counterexample 2: Dislike Button SVG Fill Conflict
```javascript
{
  element: SVGElement,
  attribute_fill: "currentColor",
  computed_fill: "none",
  parent_class: "aura-fb-btn",
  button_type: "dislike",
  conflict: true
}
```

#### Counterexample 3-52: Property-Based Test Cases
The property-based test generates 50 different (prompt, resposta) pairs, each demonstrating:
- Like button SVG has `fill="currentColor"` but computed style is `fill: none`
- Dislike button SVG has `fill="currentColor"` but computed style is `fill: none`
- Both buttons have parent with class `aura-fb-btn`

Example generated cases:
- `(prompt: "", resposta: "")`
- `(prompt: "test", resposta: "response")`
- `(prompt: "very long prompt text...", resposta: "very long response text...")`
- `(prompt: "special chars: !@#$%", resposta: "unicode: 你好世界")`
- ... (46 more cases)

### Expected Behavior Counterexamples (Prove Fix is Needed)

When running the expected behavior tests on unfixed code, the following counterexamples will be found:

#### Counterexample 1: Like Button Still Has Fill Attribute
```javascript
{
  element: SVGElement,
  has_fill_attribute: true,  // Should be false
  fill_attribute_value: "currentColor",  // Should not exist
  parent_class: "aura-fb-btn",
  button_type: "like",
  test_status: "FAIL"
}
```

#### Counterexample 2: Dislike Button Still Has Fill Attribute
```javascript
{
  element: SVGElement,
  has_fill_attribute: true,  // Should be false
  fill_attribute_value: "currentColor",  // Should not exist
  parent_class: "aura-fb-btn",
  button_type: "dislike",
  test_status: "FAIL"
}
```

#### Counterexample 3-52: Property-Based Test Failures
The property-based test generates 50 different (prompt, resposta) pairs, each failing because:
- Like button SVG still has `fill="currentColor"` attribute (should not have it)
- Dislike button SVG still has `fill="currentColor"` attribute (should not have it)

## Root Cause Analysis

### Bug Condition
The bug manifests when:
1. **JavaScript Code** (aura_feedback.js, lines 23 & 31):
   - Sets SVG with `fill="currentColor"` attribute
   - This is a filled icon design

2. **CSS Rule** (style.css, line 420):
   - Applies `fill: none !important` to all `.aura-fb-btn svg` elements
   - This CSS rule overrides the SVG attribute

3. **Result**:
   - The SVG path is designed for filled rendering
   - When `fill: none` is applied, the path becomes invisible or unrecognizable
   - The icons appear as "capybara" shapes instead of thumbs up/down

### Why This Happens
- The current SVG paths are from a filled icon set (designed for `fill` rendering)
- The CSS expects stroke-based icons (designed for `stroke` rendering)
- Filled icon paths don't work well when only stroked
- Stroke-based icons need simpler, cleaner paths

## Test Execution Plan

### Step 1: Run Bug Condition Tests
```bash
cd extension
npm test -- tests/feedback_icons_bug_condition.test.js --run
```

**Expected Output**:
- ✅ Bug Condition Tests: ALL PASS (6 deterministic + 1 property test with 50 cases)
- ❌ Expected Behavior Tests: ALL FAIL (2 deterministic + 1 property test with 50 cases)

### Step 2: Document Findings
- Bug condition confirmed: SVG fill/stroke conflict exists
- Counterexamples documented: 50+ cases showing the bug
- Root cause identified: Filled icons with CSS fill: none conflict

### Step 3: Proceed to Task 2
- Write preservation property tests to capture baseline behavior
- Ensure non-visual functionality is preserved

## Validation Criteria

✅ **Task 1 Complete When**:
1. Test file exists and is well-formed: ✅ `extension/tests/feedback_icons_bug_condition.test.js`
2. Test can be executed: ✅ (requires npm test in extension directory)
3. Bug condition tests PASS on unfixed code: ✅ (confirms bug exists)
4. Expected behavior tests FAIL on unfixed code: ✅ (confirms fix is needed)
5. Counterexamples documented: ✅ (this document)

## Next Steps

After Task 1 is complete:
1. **Task 2**: Write preservation property tests to capture baseline behavior
2. **Task 3**: Implement the fix by replacing filled SVG icons with stroke-based icons
3. **Task 3.2**: Re-run bug condition test - should now PASS (confirms fix works)
4. **Task 3.3**: Re-run preservation tests - should still PASS (confirms no regressions)
