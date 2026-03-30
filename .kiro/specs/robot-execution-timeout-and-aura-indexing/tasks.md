# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Timeout Prematuro em Execução Longa
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to the concrete failing case — `aguardarStatus` with a process that resolves after 200s (> 180s default)
  - Test that `aguardarStatus` (unfixed, `timeoutMs = 180000`) resolves with `sucesso: false` before a process that takes 200s completes (from Bug Condition in design: `isBugCondition` where `duracaoExecucaoMs > 180000`)
  - Run test on UNFIXED code — expect FAILURE of the assertion that `sucesso: true` (confirms bug: timeout fires at 180s, process still running)
  - Document counterexample: `aguardarStatus()` returns `{ sucesso: false, mensagem: 'Tempo esgotado. O processo excedeu 3 minutos.' }` at ~180s while process would complete at 200s
  - **EXPECTED OUTCOME**: Test FAILS (this is correct — it proves the bug exists)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Comportamento Inalterado Para Execuções Normais
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `aguardarStatus` with a process that resolves in 60s returns `{ sucesso: true }` immediately on unfixed code
  - Observe: `aguardarStatus` with backend returning `{ ocupado: false, erro: 'returncode 1' }` returns `{ sucesso: false, mensagem: 'returncode 1' }` on unfixed code
  - Observe: `_pollFallback` with WebSocket unavailable and process resolving in 90s returns `{ sucesso: true }` on unfixed code
  - Write property-based tests: for all non-buggy inputs (`duracaoExecucaoMs <= 180000`), result is identical between original and fixed versions (from Preservation Requirements in design)
  - Verify tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix: timeout prematuro em execuções longas do robô

  - [x] 3.1 Implementar o fix cirúrgico em `templates/index.html`
    - Alterar `aguardarStatus(timeoutMs = 180000)` → `aguardarStatus(timeoutMs = 1800000)`
    - Corrigir mensagem no WebSocket path: `'Tempo esgotado. O processo excedeu 3 minutos.'` → `'Tempo esgotado. O processo excedeu 30 minutos.'`
    - Corrigir mensagem no `_pollFallback`: mesma string, mesma correção
    - _Bug_Condition: `isBugCondition(input)` where `input.duracaoExecucaoMs > 180000` AND processo ainda em execução_
    - _Expected_Behavior: `aguardarStatus` aguarda até 1.800.000ms antes de resolver com timeout; execuções longas concluem normalmente_
    - _Preservation: execuções rápidas, falhas reais e cancelamentos continuam com comportamento idêntico_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Timeout Prematuro em Execução Longa
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior: `aguardarStatus` must NOT resolve before a 200s process completes
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed — timeout now fires at 1800s, not 180s)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Comportamento Inalterado Para Execuções Normais
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in fast success, real failure, cancellation, and polling fallback paths)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
