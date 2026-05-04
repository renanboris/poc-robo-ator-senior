# Test Execution Guide - Aura Extension Tests

## Overview
This guide explains how to run all Aura extension tests including bug condition exploration tests and preservation property tests.

## Test Files

### Iframe DOM Capture Fix Tests
- **Bug Condition Test**: `extension/tests/iframe_bug_condition.test.js`
- **Preservation Test**: `extension/tests/iframe_preservation.test.js`
- **Manual Test Pages**:
  - `extension/tests/manual_preservation_test_no_iframe.html`
  - `extension/tests/manual_preservation_test_cross_origin.html`
  - `extension/tests/manual_preservation_test_empty_iframe.html`

### Feedback Icons Fix Tests
- **Bug Condition Test**: `extension/tests/feedback_icons_bug_condition.test.js`
- **Preservation Test**: `extension/tests/feedback_preservation.test.js`

### Framework
- **Testing Framework**: Jest + fast-check (property-based testing)
- **Environment**: jsdom (browser DOM simulation)

## How to Run

### Prerequisites
```bash
cd extension
npm install  # if not already done
```

### Run All Tests
```bash
cd extension
npm test
```

### Run Specific Test Suites

#### Iframe DOM Capture Tests
```bash
# Bug condition test (should FAIL on unfixed code)
npm test -- iframe_bug_condition.test.js

# Preservation test (should PASS on unfixed code and after fix)
npm test -- iframe_preservation.test.js

# Run both iframe tests
npm test -- iframe
```

#### Feedback Icons Tests
```bash
# Bug condition test
npm test -- feedback_icons_bug_condition.test.js

# Preservation test
npm test -- feedback_preservation.test.js

# Run both feedback tests
npm test -- feedback
```

### Manual Testing
Open the manual test HTML pages in a browser with the Aura extension loaded:
1. Open browser with Aura extension
2. Navigate to `file:///path/to/extension/tests/manual_preservation_test_no_iframe.html`
3. Open console (F12)
4. Execute `window.testarCaptura()` or `AuraDomMapper.capturar()`
5. Compare output with expected results in the page

## Expected Test Results

### Iframe DOM Capture Fix Tests

#### On UNFIXED Code (Current State)
```
FAIL extension/tests/iframe_bug_condition.test.js
  Bug Condition — Iframe Elements Not Captured
    ✕ COUNTEREXAMPLE: Botão "Novo Documento" dentro de iframe ecm_sign NÃO é capturado
    ✕ COUNTEREXAMPLE: Múltiplos elementos dentro de iframe NÃO são capturados
    ✕ COUNTEREXAMPLE: Apenas elementos do documento principal são capturados, iframe é ignorado
    ✕ COUNTEREXAMPLE: Elementos de iframe NÃO recebem data-aura-map
    ✕ fc.property: Elementos em iframes acessíveis DEVEM ser capturados
    ✕ COUNTEREXAMPLE: Cenário real Senior X GED - elementos do iframe ecm_sign NÃO são capturados

PASS extension/tests/iframe_preservation.test.js
  Preservation — Non-Iframe Page Behavior
    ✓ Preservation: Página sem iframes captura elementos corretamente
    ✓ Preservation: Formato de saída [ID: X] TIPO: Y | TEXTO: "Z" é preservado
    ✓ Preservation: data-aura-map é atribuído com índices únicos
    ✓ Preservation: Filtragem de duplicatas baseada em texto funciona
    ✓ Preservation: Elementos dentro do container AURA são ignorados
    ✓ Preservation: Apenas elementos visíveis (bounding box válido) são capturados
    ✓ Preservation: Iframe cross-origin (simulado) não causa falha
    ✓ Preservation: Iframe vazio não adiciona elementos à saída
    ✓ fc.property: Páginas sem iframes produzem saída consistente (50 runs)
    ✓ fc.property: Índices data-aura-map são sempre únicos (30 runs)
    ✓ fc.property: Filtragem de duplicatas é consistente (30 runs)
    ✓ fc.property: Apenas elementos visíveis são capturados (30 runs)
```

**Summary**:
- ❌ Bug Condition Tests: FAIL (confirms bug exists)
- ✅ Preservation Tests: PASS (confirms baseline behavior)

#### After Implementing Fix (Task 3)
```
PASS extension/tests/iframe_bug_condition.test.js
  Bug Condition — Iframe Elements Not Captured
    ✓ COUNTEREXAMPLE: Botão "Novo Documento" dentro de iframe ecm_sign NÃO é capturado
    ✓ COUNTEREXAMPLE: Múltiplos elementos dentro de iframe NÃO são capturados
    ✓ COUNTEREXAMPLE: Apenas elementos do documento principal são capturados, iframe é ignorado
    ✓ COUNTEREXAMPLE: Elementos de iframe NÃO recebem data-aura-map
    ✓ fc.property: Elementos em iframes acessíveis DEVEM ser capturados
    ✓ COUNTEREXAMPLE: Cenário real Senior X GED - elementos do iframe ecm_sign NÃO são capturados

PASS extension/tests/iframe_preservation.test.js
  Preservation — Non-Iframe Page Behavior
    ✓ Preservation: Página sem iframes captura elementos corretamente
    ✓ Preservation: Formato de saída [ID: X] TIPO: Y | TEXTO: "Z" é preservado
    ✓ Preservation: data-aura-map é atribuído com índices únicos
    ✓ Preservation: Filtragem de duplicatas baseada em texto funciona
    ✓ Preservation: Elementos dentro do container AURA são ignorados
    ✓ Preservation: Apenas elementos visíveis (bounding box válido) são capturados
    ✓ Preservation: Iframe cross-origin (simulado) não causa falha
    ✓ Preservation: Iframe vazio não adiciona elementos à saída
    ✓ fc.property: Páginas sem iframes produzem saída consistente (50 runs)
    ✓ fc.property: Índices data-aura-map são sempre únicos (30 runs)
    ✓ fc.property: Filtragem de duplicatas é consistente (30 runs)
    ✓ fc.property: Apenas elementos visíveis são capturados (30 runs)
```

**Summary**:
- ✅ Bug Condition Tests: PASS (confirms fix works)
- ✅ Preservation Tests: PASS (confirms no regressions)

### Feedback Icons Fix Tests

### Summary
- **Bug Condition Tests**: ✅ ALL PASS (confirms bug exists)
- **Expected Behavior Tests**: ❌ ALL FAIL (confirms fix is needed)

### Detailed Results

#### Bug Condition Tests (PASS)
These tests verify the bug condition exists in the unfixed code:

1. ✅ "Like icon SVG must have fill="currentColor" attribute"
   - Verifies SVG has the buggy attribute
   - Status: PASS

2. ✅ "Dislike icon SVG must have fill="currentColor" attribute"
   - Verifies SVG has the buggy attribute
   - Status: PASS

3. ✅ "Like icon SVG must have conflict: fill="currentColor" vs CSS fill: none"
   - Verifies the conflict between attribute and CSS
   - Attribute says: `fill="currentColor"`
   - CSS says: `fill: none !important`
   - Status: PASS (conflict confirmed)

4. ✅ "Dislike icon SVG must have conflict: fill="currentColor" vs CSS fill: none"
   - Verifies the conflict between attribute and CSS
   - Status: PASS (conflict confirmed)

5. ✅ "Like icon parent must have class aura-fb-btn"
   - Status: PASS

6. ✅ "Dislike icon parent must have class aura-fb-btn"
   - Status: PASS

7. ✅ "fc.property: Bug Condition exists for any (prompt, resposta)"
   - Property-based test with 50 generated cases
   - Each case verifies the bug condition exists
   - Status: PASS (all 50 cases confirm bug)

#### Expected Behavior Tests (FAIL)
These tests verify the expected behavior AFTER the fix:

1. ❌ "EXPECTED BEHAVIOR: Like icon must use only stroke without fill attribute (MUST FAIL now)"
   - Expects: SVG does NOT have `fill` attribute
   - Actual: SVG has `fill="currentColor"` attribute
   - Status: FAIL (as expected - confirms fix is needed)

2. ❌ "EXPECTED BEHAVIOR: Dislike icon must use only stroke without fill attribute (MUST FAIL now)"
   - Expects: SVG does NOT have `fill` attribute
   - Actual: SVG has `fill="currentColor"` attribute
   - Status: FAIL (as expected - confirms fix is needed)

3. ❌ "fc.property: EXPECTED BEHAVIOR - Icons must use only stroke for any (prompt, resposta) (MUST FAIL now)"
   - Property-based test with 50 generated cases
   - Each case expects SVG to NOT have `fill` attribute
   - Actual: All 50 cases have `fill="currentColor"` attribute
   - Status: FAIL (all 50 cases fail - confirms fix is needed)

## Counterexamples Found

### Bug Condition Counterexamples (Prove Bug Exists)

The property-based test will generate 50 different (prompt, resposta) pairs, each demonstrating:

```
Counterexample 1:
  prompt: ""
  resposta: ""
  like_svg_fill_attribute: "currentColor"
  like_svg_computed_fill: "none"
  dislike_svg_fill_attribute: "currentColor"
  dislike_svg_computed_fill: "none"
  conflict: true

Counterexample 2:
  prompt: "test prompt"
  resposta: "test response"
  like_svg_fill_attribute: "currentColor"
  like_svg_computed_fill: "none"
  dislike_svg_fill_attribute: "currentColor"
  dislike_svg_computed_fill: "none"
  conflict: true

... (48 more cases with different prompt/resposta combinations)
```

### Expected Behavior Counterexamples (Prove Fix is Needed)

The property-based test will generate 50 different (prompt, resposta) pairs, each showing:

```
Counterexample 1:
  prompt: ""
  resposta: ""
  like_svg_has_fill_attribute: true (should be false)
  like_svg_fill_value: "currentColor" (should not exist)
  dislike_svg_has_fill_attribute: true (should be false)
  dislike_svg_fill_value: "currentColor" (should not exist)

Counterexample 2:
  prompt: "test prompt"
  resposta: "test response"
  like_svg_has_fill_attribute: true (should be false)
  like_svg_fill_value: "currentColor" (should not exist)
  dislike_svg_has_fill_attribute: true (should be false)
  dislike_svg_fill_value: "currentColor" (should not exist)

... (48 more cases)
```

## What This Proves

### Bug Condition Tests Passing
✅ Confirms that the bug condition exists in the unfixed code:
- SVG elements have `fill="currentColor"` attribute
- CSS rule applies `fill: none !important`
- This creates a conflict that causes incorrect rendering

### Expected Behavior Tests Failing
❌ Confirms that the expected behavior is NOT present in the unfixed code:
- SVG elements should NOT have `fill` attribute
- SVG elements should use stroke-based rendering
- The fix is needed to achieve the expected behavior

## Next Steps

### After Confirming Test Results
1. ✅ Bug condition confirmed: SVG fill/stroke conflict exists
2. ✅ Counterexamples documented: 50+ cases showing the bug
3. ✅ Root cause identified: Filled icons with CSS fill: none conflict
4. ➡️ Proceed to Task 2: Write preservation property tests
5. ➡️ Proceed to Task 3: Implement the fix

### After Implementing the Fix
1. Re-run the same test file
2. Bug condition tests should still PASS (confirms bug existed)
3. Expected behavior tests should now PASS (confirms fix works)
4. Preservation tests should still PASS (confirms no regressions)

## Test Code Structure

### Bug Condition Function
```javascript
function criar_unfixed(prompt, resposta) {
    // Creates feedback bar with unfixed SVG icons
    // SVG has fill="currentColor" (the bug)
    // Returns HTMLElement with like/dislike buttons
}
```

### CSS Injection
```javascript
function injectFeedbackCSS() {
    // Injects the CSS rules from style.css
    // Includes: .aura-fb-btn svg { fill: none !important; }
    // Simulates the real browser environment
}
```

### Test Assertions
```javascript
// Bug condition: attribute vs CSS conflict
expect(svg.getAttribute('fill')).toBe('currentColor');
expect(window.getComputedStyle(svg).fill).toBe('none');
expect(svg.getAttribute('fill')).not.toBe(window.getComputedStyle(svg).fill);

// Expected behavior: stroke-based rendering
expect(svg.hasAttribute('fill')).toBe(false);
expect(window.getComputedStyle(svg).fill).toBe('none');
expect(window.getComputedStyle(svg).stroke).toBe('currentColor');
```

## Troubleshooting

### Test Won't Run
- Ensure Node.js and npm are installed
- Run `npm install` in extension directory
- Check that jest is in node_modules

### Tests Pass When They Should Fail
- Verify the unfixed code still has `fill="currentColor"` in aura_feedback.js
- Verify the CSS still has `fill: none !important` in style.css
- Check that the test is using the unfixed version

### Tests Fail When They Should Pass
- Verify the test file is correctly structured
- Check that jsdom is properly configured
- Ensure CSS is being injected correctly

## References

- **Unfixed Code**: `extension/modules/aura_feedback.js` (lines 23, 31)
- **CSS Rule**: `extension/style.css` (line 420)
- **Test File**: `extension/tests/feedback_icons_bug_condition.test.js`
- **Design Doc**: `.kiro/specs/dap-like-dislike-icons-fix/design.md`
- **Requirements**: `.kiro/specs/dap-like-dislike-icons-fix/bugfix.md`
