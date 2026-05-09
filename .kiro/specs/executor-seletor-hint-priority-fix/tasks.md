# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - seletor_hint Ignored for Generic Labels
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test implementation details from Bug Condition in design:
    - Generate test cases where `seletor_hint` is valid (non-empty, non-fragile)
    - AND `label_curto` is generic (in `_TAGS_FRAGEIS` or PrimeNG cosmetic text like "ui-btn")
    - Call `_gerar_candidatos()` with these inputs
    - Assert that `seletor_hint` is NOT in the first 3 positions of candidatos list
    - Assert that first candidato is based on `label_curto` (contains text=, aria-label, or getByRole)
  - The test assertions should match the Expected Behavior Properties from design:
    - After fix: `seletor_hint` SHOULD be in first 3 positions
    - After fix: `seletor_hint` candidato SHOULD come before `label_curto` candidatos
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found to understand root cause:
    - Example 1: `seletor_hint="[name='e070emp'] button"`, `label_curto="ui-btn"` → first candidato is `text="ui-btn"` instead of seletor_hint
    - Example 2: `seletor_hint="p-dialog[role='dialog'] button#select"`, `label_curto="Selecionar"` → first candidato is `text="Selecionar"` instead of seletor_hint
    - Example 3: `seletor_hint="input[name='e070emp']"`, `label_curto="input"` → first candidato is `getByLabel('input')` instead of seletor_hint
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Unchanged Behavior for Non-Buggy Cases
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (cases where bug condition does NOT hold)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - **Case 1: seletor_hint ausente/vazio**
      - Observe: `_gerar_candidatos("", "Confirmar", ...)` on unfixed code
      - Record: candidatos list structure and order
      - Write property: for all cases where `seletor_hint` is empty, candidatos list should match observed pattern
    - **Case 2: seletor_hint frágil**
      - Observe: `_gerar_candidatos("button", "Confirmar", ...)` on unfixed code
      - Record: candidatos list structure and order
      - Write property: for all cases where `_e_seletor_fragil(seletor_hint)` returns True, candidatos list should match observed pattern
    - **Case 3: label_curto específico (não genérico)**
      - Observe: `_gerar_candidatos("button#generic", "Confirmar Pedido de Venda", ...)` on unfixed code
      - Record: candidatos list structure and order
      - Write property: for all cases where `label_curto` is NOT generic (not in `_TAGS_FRAGEIS`, not PrimeNG cosmetic), candidatos list should match observed pattern
    - **Case 4: Casos especiais existentes**
      - Observe: checkbox PrimeNG, dialog buttons, composite widgets on unfixed code
      - Record: candidatos list structure and order
      - Write property: special cases should continue to be handled identically
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Fix for seletor_hint priority in _gerar_candidatos()

  - [x] 3.1 Implement helper function _e_label_generico()
    - Add function to detect if `label_curto` is generic/cosmetic
    - Check if label is in `_TAGS_FRAGEIS` (button, input, span, div, etc.)
    - Check if label matches PrimeNG cosmetic patterns: "ui-btn", "ui-button-text", "ui-clickable", "ui-widget", "ui-state-default", "p-button", "p-element"
    - Check if label is very short (< 3 characters) or empty
    - Return True if any condition matches (label is generic)
    - Add unit tests for `_e_label_generico()` with various inputs
    - _Bug_Condition: isBugCondition(input) where seletor_hint is valid AND label_curto is generic_
    - _Expected_Behavior: Function correctly identifies generic labels that should not be prioritized_
    - _Preservation: Does not affect existing logic - this is a new helper function_
    - _Requirements: 2.1, 2.4_

  - [x] 3.2 Add seletor_hint as high-priority candidato in _gerar_candidatos()
    - Locate insertion point: after special cases (line ~630) and BEFORE label_curto candidatos (line ~632)
    - Add logic:
      ```python
      # ── NOVO: Candidato de alta prioridade para seletor_hint ──────────────────
      # Quando seletor_hint é válido, não-frágil, e label_curto é genérico,
      # adiciona seletor_hint como candidato de alta prioridade
      if (seletor_hint and 
          not _e_seletor_fragil(seletor_hint) and 
          _e_label_generico(label_curto)):
          
          logger.debug(f"[Sniper] Adicionando seletor_hint como alta prioridade: {seletor_hint[:60]}")
          candidatos.append(TentativaLocalizacao(
              seletor=seletor_hint,
              iframe_hint=iframe_hint,
              descricao=f"seletor_hint priority '{seletor_hint[:60]}'",
          ))
      ```
    - Position: insert AFTER line ~630 (after composite widgets special case) and BEFORE line ~632 (before `if label_curto and not is_tag_generica:`)
    - Ensure special cases (checkboxes, dialogs, composite widgets) are NOT modified
    - Add debug logging when high-priority candidato is added
    - _Bug_Condition: isBugCondition(input) where seletor_hint is valid, non-fragile, and label_curto is generic_
    - _Expected_Behavior: seletor_hint is added as high-priority candidato in first 3 positions_
    - _Preservation: Only affects cases where bug condition holds; all other cases unchanged_
    - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - seletor_hint Prioritized for Generic Labels
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify that for all test cases where bug condition holds:
      - `seletor_hint` is now in first 3 positions of candidatos list
      - `seletor_hint` candidato comes BEFORE candidatos based on `label_curto`
      - Description contains "priority" or "hint priority"
    - Verify logs show `[Sniper] Adicionando seletor_hint como alta prioridade: ...`
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Unchanged Behavior for Non-Buggy Cases
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Verify that for all test cases where bug condition does NOT hold:
      - candidatos list is identical to unfixed code
      - Special cases (checkboxes, dialogs, composite widgets) still work
      - No new candidatos are added when seletor_hint is absent/empty/fragile
      - No new candidatos are added when label_curto is specific (not generic)
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run all unit tests for `_e_label_generico()` and `_gerar_candidatos()`
  - Run all property-based tests (bug condition + preservation)
  - Verify no regressions in existing test suite
  - Review logs to confirm seletor_hint priority logic is working
  - Ask the user if questions arise or if integration testing is needed
