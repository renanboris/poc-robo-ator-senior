# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Ingest Endpoint Emits No Completion Signal
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate `_set_estado()` is never called after `/api/ingest/{arquivo}` returns
  - **Scoped PBT Approach**: Scope the property to the two concrete failing cases — ingest success and ingest error — to ensure reproducibility
  - Mock `dap_engine.ingestar_para_pinecone` to return `{"status": "sucesso", ...}` and call the endpoint; assert `estado_servidor["sucesso"] != ""`
  - Mock `dap_engine.ingestar_para_pinecone` to return `{"status": "erro", "mensagem": "Pinecone indisponível"}` and call the endpoint; assert `estado_servidor["erro"] != ""`
  - Use `hypothesis` to generate varied success/error responses from `dap_engine` and assert `_set_estado` is always called
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves `_set_estado()` is never called — bug confirmed)
  - Document counterexamples found (e.g., `estado_servidor["sucesso"]` remains `""` after HTTP 200 with success)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Outros Passos da Produção e Contrato JSON Inalterados
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `executar_processo_bg` calls `_set_estado(sucesso=...)` or `_set_estado(erro=...)` at the end — verify this on unfixed code
  - Observe: `ingestar_no_dap` returns exactly the dict returned by `dap_engine.ingestar_para_pinecone()` — verify `return res` is unchanged
  - Write property-based test: for all inputs where `isBugCondition` is false (i.e., calls to `executar_processo_bg` for video/SCORM/PDF/SimLink), the WebSocket broadcast behavior is identical before and after the fix
  - Write property-based test: for any dict `res` returned by `dap_engine.ingestar_para_pinecone`, `ingestar_no_dap` always returns exactly `res` (JSON contract preserved)
  - Use `hypothesis` to generate varied `res` dicts (status, mensagem, keys) and assert the return value equals the input dict
  - Verify tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix: ingest endpoint não emite sinal de conclusão via WebSocket

  - [x] 3.1 Implement the fix in `ingestar_no_dap` (app.py)
    - No branch `if res.get("status") == "sucesso"`: adicionar `_set_estado(sucesso="✅ Indexação concluída na base de conhecimento.")` após salvar `ingestado_dap=True` e antes de iniciar a thread `_rebuild_apos_ingest`
    - No branch `else` (falha): adicionar `_set_estado(erro=res.get("mensagem", "Falha na indexação."))` para que o frontend detecte o erro
    - Preservar o `return res` no final da função — o contrato JSON do endpoint não deve ser alterado
    - Não adicionar `_set_estado(ocupado=True/False)` — o endpoint é síncrono e rápido; o sinal via `sucesso`/`erro` é suficiente para resolver `_wsResolve`
    - Não alterar a thread `_rebuild_apos_ingest` — continua executando de forma assíncrona sem bloquear a resposta HTTP
    - _Bug_Condition: isBugCondition(X) where X.endpoint = "/api/ingest/{arquivo}" AND _set_estado_called_after_endpoint_returns = false_
    - _Expected_Behavior: após o fix, `_set_estado(sucesso=...)` ou `_set_estado(erro=...)` é chamado antes do `return res`, disparando broadcast WebSocket e resolvendo `_wsResolve` no frontend_
    - _Preservation: `executar_processo_bg` e todos os outros endpoints permanecem inalterados; `return res` preserva o contrato JSON_
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Ingest Endpoint Emits Completion Signal
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior: `_set_estado()` must be called with `sucesso` or `erro` after the endpoint returns
    - Run bug condition exploration test from step 1 on FIXED code
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed — `estado_servidor["sucesso"]` or `estado_servidor["erro"]` is populated after endpoint call)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Outros Passos da Produção e Contrato JSON Inalterados
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2 on FIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions — `executar_processo_bg` behavior unchanged, `return res` contract preserved)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass; ask the user if questions arise.
