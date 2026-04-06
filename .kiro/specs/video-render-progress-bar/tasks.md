# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Progresso de Renderização Ignorado pelo onmessage
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases — mensagens WebSocket com `data.progresso` numérico (0–100) enquanto `data.ocupado === true` e `_activeRenderStepEl` deveria estar ativo
  - Simular o handler `onmessage` do código não corrigido com `{ocupado: true, progresso: 47}` e verificar que nenhum elemento DOM de porcentagem é atualizado
  - Usar Hypothesis para gerar valores de `progresso` em [0, 100] e confirmar que o DOM nunca reflete nenhum valor no código original
  - O teste deve verificar: `isBugCondition(msg)` onde `msg.progresso IS NOT NULL AND typeof msg.progresso === 'number' AND msg.ocupado === true`
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (ex: `{ocupado: true, progresso: 47}` → elemento de porcentagem não existe no DOM; mesmo que existisse, `onmessage` não o atualizaria pois não há branch para `data.progresso`)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Comportamento Inalterado para Inputs Fora da Bug Condition
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (casos onde `data.progresso` é null/undefined, ou `data.ocupado === false`)
  - Observe: `{ocupado: false, progresso: null, sucesso: "..."}` → `_wsResolve` é chamado, Promise resolvida com `{sucesso: true}`
  - Observe: `{ocupado: false, erro: "Falha: ..."}` → `_wsResolve` é chamado, Promise resolvida com `{sucesso: false}`
  - Observe: mensagens durante steps 1–4 (SCORM, PDF, SimLink) → spinner padrão inalterado, sem indicador de progresso
  - Write property-based tests: para todo `wsMessage` onde `NOT isBugCondition(wsMessage)`, o `onmessage` corrigido SHALL produzir exatamente o mesmo comportamento que o original
  - Usar Hypothesis para gerar combinações de `{ocupado, progresso, erro, sucesso}` fora da bug condition e verificar que a lógica de resolução da Promise é idêntica
  - Verify tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix para barra de progresso na renderização de vídeo

  - [x] 3.1 Implementar o fix em `templates/index.html`
    - Declarar variável de módulo `let _activeRenderStepEl = null;` no escopo do script
    - No `runStepper`, ao iniciar o step de renderização (`i === 0`), atribuir o elemento DOM do step à variável `_activeRenderStepEl`
    - Ao concluir ou falhar o step de renderização, limpar a referência: `_activeRenderStepEl = null`
    - Adicionar elemento de progresso no template HTML do step de renderização: `<span class="step-pct" id="${stepId}-pct"></span>` inline ao lado do label
    - Estender o handler `_ws.onmessage` com branch independente: quando `data.progresso` é numérico e `_activeRenderStepEl !== null`, atualizar `textContent` do elemento de porcentagem com `data.progresso + '%'`
    - Garantir que a branch de `data.progresso` é independente da branch de `!data.ocupado` — ambas podem coexistir sem interferência
    - Garantir que `newSession()` limpa `_activeRenderStepEl = null` para evitar estado residual
    - _Bug_Condition: `isBugCondition(wsMessage)` onde `wsMessage.progresso IS NOT NULL AND typeof wsMessage.progresso === 'number' AND wsMessage.ocupado === true AND stepAtivo === STEPS[0] AND elementoProgressoNoDOM NÃO FOI ATUALIZADO`_
    - _Expected_Behavior: `elementoProgressoNoDOM.textContent === wsMessage.progresso + '%'` e `_wsResolve NÃO FOI CHAMADO` (Promise não resolvida prematuramente)_
    - _Preservation: spinner padrão nos steps 1–4 inalterado; tratamento de erro via `data.erro` preservado; fallback `_pollFallback` preservado; avanço para steps subsequentes preservado; `newSession()` sem estado residual_
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Progresso de Renderização Exibido no Frontend
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior: para todo `wsMessage` com `data.progresso` numérico e step de renderização ativo, o elemento DOM deve exibir `data.progresso + '%'`
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Comportamento Inalterado para Inputs Fora da Bug Condition
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
