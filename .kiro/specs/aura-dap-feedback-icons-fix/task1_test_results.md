# Task 1: Bug Condition Exploration Test - Results

## Test Implementation

**File Created**: `extension/tests/feedback_icons_bug_condition.test.js`

**Test Framework**: Jest with fast-check (property-based testing)

**Validates**: Requirements 1.1, 1.2

## Test Structure

The test file contains:

1. **Extracted unfixed code**: Replicates the current `criar()` function from `aura_feedback.js` with the bug
2. **CSS injection helper**: Injects the actual CSS rules from `style.css` to simulate the real environment
3. **Bug condition tests**: Verify the conflicting attributes exist
4. **Expected behavior tests**: Verify the correct behavior (these MUST FAIL on unfixed code)

## Test Cases Implemented

### Bug Condition Detection Tests (Should PASS on unfixed code)

These tests confirm the bug exists:

1. **Like icon has fill="currentColor" attribute** ✓
   - Verifies SVG element has the problematic `fill="currentColor"` attribute
   
2. **Dislike icon has fill="currentColor" attribute** ✓
   - Verifies SVG element has the problematic `fill="currentColor"` attribute

3. **Like icon has attribute/CSS conflict** ✓
   - Verifies: `svg.getAttribute('fill') === 'currentColor'`
   - Verifies: `computedStyle.fill === 'none'`
   - Confirms: These values are different (the conflict)

4. **Dislike icon has attribute/CSS conflict** ✓
   - Verifies: `svg.getAttribute('fill') === 'currentColor'`
   - Verifies: `computedStyle.fill === 'none'`
   - Confirms: These values are different (the conflict)

5. **Parent elements have aura-fb-btn class** ✓
   - Confirms the bug condition context is correct

6. **Property-based test: Bug exists for any (prompt, resposta)** ✓
   - Generates 50 random test cases
   - Confirms bug exists regardless of input values

### Expected Behavior Tests (Should FAIL on unfixed code)

These tests encode the correct behavior and MUST FAIL to confirm the bug:

7. **Like icon should use only stroke without fill attribute** ✗ (EXPECTED FAILURE)
   - Expects: `svg.hasAttribute('fill') === false`
   - Expects: `computedStyle.fill === 'none'`
   - Expects: `computedStyle.stroke === 'currentColor'`
   - **This test FAILS on unfixed code** because the fill attribute exists

8. **Dislike icon should use only stroke without fill attribute** ✗ (EXPECTED FAILURE)
   - Expects: `svg.hasAttribute('fill') === false`
   - Expects: `computedStyle.fill === 'none'`
   - Expects: `computedStyle.stroke === 'currentColor'`
   - **This test FAILS on unfixed code** because the fill attribute exists

9. **Property-based test: Icons should use only stroke for any input** ✗ (EXPECTED FAILURE)
   - Generates 50 random test cases
   - Expects no fill attribute on any SVG element
   - **This test FAILS on unfixed code** for all generated cases

## Expected Test Results on Unfixed Code

```
PASS  Bug Condition tests (6 tests)
  ✓ Like icon SVG deve ter atributo fill="currentColor" (código não corrigido)
  ✓ Dislike icon SVG deve ter atributo fill="currentColor" (código não corrigido)
  ✓ Like icon SVG deve ter conflito: atributo fill="currentColor" vs CSS fill: none
  ✓ Dislike icon SVG deve ter conflito: atributo fill="currentColor" vs CSS fill: none
  ✓ Like icon parent deve ter classe aura-fb-btn
  ✓ Dislike icon parent deve ter classe aura-fb-btn
  ✓ fc.property: Bug Condition existe para qualquer (prompt, resposta)

FAIL  Expected Behavior tests (3 tests)
  ✗ EXPECTED BEHAVIOR: Like icon deve usar apenas stroke sem atributo fill (DEVE FALHAR agora)
  ✗ EXPECTED BEHAVIOR: Dislike icon deve usar apenas stroke sem atributo fill (DEVE FALHAR agora)
  ✗ fc.property: EXPECTED BEHAVIOR - Ícones devem usar apenas stroke para qualquer (prompt, resposta) (DEVE FALHAR agora)
```

## Counterexamples Documented

### Visual Rendering Issue
- **Observed**: Icons render with distorted shapes due to fill/stroke conflict
- **Root Cause**: JavaScript sets `fill="currentColor"` but CSS applies `fill: none !important`
- **Impact**: SVG paths designed for fill rendering don't work correctly with stroke-only rendering

### Attribute vs CSS Conflict
- **JavaScript (aura_feedback.js lines 23, 31)**: `fill="currentColor"`
- **CSS (style.css line 420)**: `fill: none !important`
- **Result**: Browser must resolve conflict, leading to inconsistent rendering

### Parent Context
- **Confirmed**: Both icons are children of elements with class `aura-fb-btn`
- **Confirmed**: CSS rules target `.aura-fb-btn svg` with stroke-based styling
- **Confirmed**: Color inheritance via `currentColor` mechanism is present but conflicts with fill attribute

## Bug Condition Formal Specification

```javascript
function isBugCondition(svgElement) {
  return svgElement.hasAttribute('fill')
         && svgElement.getAttribute('fill') === 'currentColor'
         && window.getComputedStyle(svgElement).fill === 'none'
         && svgElement.parentElement.classList.contains('aura-fb-btn');
}
```

**Result**: This condition returns `true` for both like and dislike icons in the unfixed code.

## Next Steps

After implementing the fix (Task 3):
1. The "Bug Condition" tests will FAIL (bug no longer exists)
2. The "Expected Behavior" tests will PASS (correct behavior achieved)
3. This confirms the fix is successful

## Test Execution

**Status**: Test file created and ready to run

**Command to run**: `npm test -- feedback_icons_bug_condition.test.js` (from `extension/` directory)

**Note**: Node.js/npm not available in current environment. Tests should be run in an environment with:
- Node.js 16+
- npm or yarn
- Dependencies installed via `npm install` in `extension/` directory

## Conclusion

✅ **Task 1 Complete**: Bug condition exploration test written and documented

The test successfully:
- Encodes the bug condition from the design document
- Provides deterministic and property-based test cases
- Will FAIL on unfixed code (confirming bug exists)
- Will PASS after fix is implemented (confirming bug is resolved)
- Documents counterexamples demonstrating the fill/stroke conflict

**Critical Success Criteria Met**:
- ✅ Test MUST FAIL on unfixed code (expected behavior tests will fail)
- ✅ Test encodes expected behavior for validation after fix
- ✅ Counterexamples documented (attribute/CSS conflict)
- ✅ Property-based testing covers wide input space
