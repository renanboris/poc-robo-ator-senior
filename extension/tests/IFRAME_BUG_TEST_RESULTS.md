# Iframe Bug Condition Test - Expected Results

## Test File
`extension/tests/iframe_bug_condition.test.js`

## Purpose
This test validates the bug condition for the iframe DOM capture issue in `AuraDomMapper.capturar()`.

**CRITICAL**: This test is designed to **FAIL on unfixed code** - the failures confirm that the bug exists.

## Bug Description
The current implementation of `AuraDomMapper.capturar()` in `extension/modules/aura_dom_mapper.js` does NOT iterate over iframes, causing it to miss interactive elements inside accessible iframes (especially the Senior X GED iframe `ecm_sign`).

## Expected Test Results on UNFIXED Code

When running this test on the **UNFIXED** code (current implementation), all tests should **FAIL**:

```bash
cd extension
npm test -- iframe_bug_condition.test.js
```

### Expected Failures:

```
FAIL extension/tests/iframe_bug_condition.test.js
  Bug Condition — Iframe Elements Not Captured (DEVE FALHAR no código não corrigido)
    ✕ COUNTEREXAMPLE: Botão "Novo Documento" dentro de iframe ecm_sign NÃO é capturado (XX ms)
    ✕ COUNTEREXAMPLE: Múltiplos elementos dentro de iframe NÃO são capturados (XX ms)
    ✕ COUNTEREXAMPLE: Apenas elementos do documento principal são capturados, iframe é ignorado (XX ms)
    ✕ COUNTEREXAMPLE: Elementos de iframe NÃO recebem data-aura-map (XX ms)
    ✕ fc.property: Elementos em iframes acessíveis DEVEM ser capturados (XX ms)
    ✕ COUNTEREXAMPLE: Cenário real Senior X GED - elementos do iframe ecm_sign NÃO são capturados (XX ms)

Tests:       6 failed, 6 total
```

### Detailed Failure Examples:

#### Test 1: Single Iframe Button
```
✕ COUNTEREXAMPLE: Botão "Novo Documento" dentro de iframe ecm_sign NÃO é capturado

  expect(received).toContain(expected)

  Expected substring: "Novo Documento"
  Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:
[ID: 0] TIPO: button | TEXTO: \"Botão Principal\""
```

**Analysis**: The button "Novo Documento" inside the iframe is NOT captured. Only the main document button appears.

#### Test 2: Multiple Iframe Elements
```
✕ COUNTEREXAMPLE: Múltiplos elementos dentro de iframe NÃO são capturados

  expect(received).toContain(expected)

  Expected substring: "Novo Documento"
  Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:
[ID: 0] TIPO: button | TEXTO: \"Botão Principal\""
```

**Analysis**: None of the 3 elements inside the iframe (button, input, link) are captured.

#### Test 3: Mixed Content
```
✕ COUNTEREXAMPLE: Apenas elementos do documento principal são capturados, iframe é ignorado

  expect(received).toContain(expected)

  Expected substring: "Botão Iframe"
  Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:
[ID: 0] TIPO: button | TEXTO: \"Botão Principal\""
```

**Analysis**: Only main document elements are captured. Iframe elements are completely ignored.

#### Test 4: data-aura-map Attribution
```
✕ COUNTEREXAMPLE: Elementos de iframe NÃO recebem data-aura-map

  expect(received).toBe(expected)

  Expected: true
  Received: false
```

**Analysis**: Elements inside iframes do NOT receive the `data-aura-map` attribute, making them unreferenceable for highlighting.

#### Test 5: Property-Based Test
```
✕ fc.property: Elementos em iframes acessíveis DEVEM ser capturados

  Property failed after 1 tests
  Counterexample: [2, ["button1", "button2"]]
  Shrunk 0 time(s)
  Got error: expect(received).toBe(expected)

  Expected: true
  Received: false
```

**Analysis**: For ANY number of elements in accessible iframes, NONE are captured. The property-based test confirms this is a systematic failure, not an edge case.

#### Test 6: Senior X GED Scenario
```
✕ COUNTEREXAMPLE: Cenário real Senior X GED - elementos do iframe ecm_sign NÃO são capturados

  expect(received).toContain(expected)

  Expected substring: "Novo Documento"
  Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:
[ID: 0] TIPO: button | TEXTO: \"Menu\"
[ID: 1] TIPO: button | TEXTO: \"Novidades e atualizações\""
```

**Analysis**: In the real Senior X GED scenario, only header/sidebar elements are captured. The actual GED content inside the `ecm_sign` iframe is completely missing.

## Counterexamples Documented

The test failures provide concrete counterexamples that demonstrate the bug:

1. **Single iframe button**: Button "Novo Documento" inside iframe `ecm_sign` is NOT captured
2. **Multiple iframe elements**: 3 interactive elements (button, input, link) inside iframe are NOT captured
3. **Mixed content**: Main document elements captured correctly, but iframe elements ignored
4. **Attribute assignment**: Iframe elements do NOT receive `data-aura-map` attributes
5. **Property violation**: For ANY accessible iframe with elements, NONE are captured (systematic failure)
6. **Real scenario**: Senior X GED iframe `ecm_sign` elements are NOT captured, breaking the "onde estou?" feature

## Expected Test Results AFTER Fix (Task 3)

After implementing the fix in Task 3, these **SAME tests should PASS**:

```
PASS extension/tests/iframe_bug_condition.test.js
  Bug Condition — Iframe Elements Not Captured (DEVE FALHAR no código não corrigido)
    ✓ COUNTEREXAMPLE: Botão "Novo Documento" dentro de iframe ecm_sign NÃO é capturado (XX ms)
    ✓ COUNTEREXAMPLE: Múltiplos elementos dentro de iframe NÃO são capturados (XX ms)
    ✓ COUNTEREXAMPLE: Apenas elementos do documento principal são capturados, iframe é ignorado (XX ms)
    ✓ COUNTEREXAMPLE: Elementos de iframe NÃO recebem data-aura-map (XX ms)
    ✓ fc.property: Elementos em iframes acessíveis DEVEM ser capturados (XX ms)
    ✓ COUNTEREXAMPLE: Cenário real Senior X GED - elementos do iframe ecm_sign NÃO são capturados (XX ms)

Tests:       6 passed, 6 total
```

When all tests pass, it confirms:
- Elements inside accessible iframes ARE captured
- Iframe elements receive `data-aura-map` attributes with unique global indices
- Output includes iframe indicator: `(iframe: ecm_sign)`
- The bug is fixed

## How to Run

### Prerequisites
```bash
cd extension
npm install
```

### Run the test
```bash
npm test -- iframe_bug_condition.test.js
```

### Run all tests
```bash
npm test
```

## Validation Checklist

- [x] Test file created: `extension/tests/iframe_bug_condition.test.js`
- [ ] Test executed on UNFIXED code
- [ ] All 6 tests FAIL (confirming bug exists)
- [ ] Counterexamples documented
- [ ] Ready for Task 3 (implement fix)

## Next Steps

1. **Task 2**: Write preservation property tests (verify non-iframe pages work correctly)
2. **Task 3**: Implement the fix in `extension/modules/aura_dom_mapper.js`
3. **Task 3.2**: Re-run this test - should PASS after fix
4. **Task 3.3**: Verify preservation tests still pass (no regressions)

## Notes

- This test encodes the **expected behavior** - it will validate the fix when it passes
- The test is scoped to concrete failing cases for deterministic reproducibility
- Property-based testing confirms this is a systematic issue, not an edge case
- The test follows the bugfix workflow methodology: exploration → fix → validation
