# Implementation Plan

> Os dois bugs são independentes. As tarefas 1–3 cobrem o Bug 1 (WebSocket disconnect).
> As tarefas 4–6 cobrem o Bug 2 (dual tenant credentials).
> Ambos os grupos podem ser executados em paralelo.

---

## Bug 1 — WebSocket Disconnect (`app.py`)

- [x] 1. Escrever teste de exploração da bug condition — Bug 1
  - **Property 1: Bug Condition** - Processo não encerrado ao desconectar último cliente
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: O teste codifica o comportamento esperado — ele validará o fix quando passar após a implementação
  - **GOAL**: Surfaçar contraexemplos que demonstrem que o processo filho continua rodando após o último cliente desconectar
  - **Scoped PBT Approach**: Escopo determinístico — um único cliente conectado, processo ativo, cliente desconecta
  - Criar `tests/test_websocket_disconnect.py` (ou adicionar ao arquivo de testes existente)
  - Mockar `ws_manager`, `processo_atual` (mock de `subprocess.Popen` com `returncode=None`), e `_set_estado`
  - Simular `WebSocketDisconnect` no handler `websocket_status` com `active_connections` vazio após `disconnect()`
  - Assertar que `proc.terminate()` foi chamado — no código não corrigido, esta asserção FALHA
  - Assertar que `_set_estado(ocupado=False, progresso=None, erro="Execução interrompida: navegador fechado.")` foi chamado
  - Assertar que `processo_atual` foi setado para `None`
  - Rodar o teste no código NÃO CORRIGIDO
  - **EXPECTED OUTCOME**: Teste FALHA (correto — prova que o bug existe)
  - Documentar o contraexemplo: `processo_atual.returncode is None` após o último cliente desconectar
  - Marcar tarefa completa quando o teste estiver escrito, executado, e a falha documentada
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Escrever testes de preservação — Bug 1 (ANTES de implementar o fix)
  - **Property 2: Preservation** - Processo não encerrado enquanto há clientes ativos
  - **IMPORTANT**: Seguir metodologia observation-first
  - Observar no código NÃO CORRIGIDO: com 2 clientes conectados, um desconecta → processo continua (`returncode is None`)
  - Observar no código NÃO CORRIGIDO: `processo_atual = None`, cliente desconecta → nenhum erro lançado
  - Escrever property-based test com Hypothesis: gerar `n_clients` aleatório ≥ 2, desconectar um → assertar que processo não é terminado
  - Escrever property-based test: gerar qualquer estado com `processo_atual = None`, desconectar → assertar que nenhuma exceção é lançada
  - Escrever property-based test: gerar pares aleatórios de (n_clients_antes, processo_ativo) onde `n_clients_antes > 1` → assertar que `proc.terminate()` NÃO é chamado
  - Rodar os testes no código NÃO CORRIGIDO
  - **EXPECTED OUTCOME**: Testes PASSAM (confirma o comportamento baseline a preservar)
  - Marcar tarefa completa quando os testes estiverem escritos, executados, e passando no código não corrigido
  - _Requirements: 3.1, 3.2_

- [x] 3. Fix do Bug 1 — Encerramento automático ao desconectar

  - [x] 3.1 Implementar o patch cirúrgico em `app.py`
    - Localizar o bloco `except WebSocketDisconnect:` na função `websocket_status`
    - Após `ws_manager.disconnect(websocket)`, adicionar verificação de lista vazia:
      ```python
      if not ws_manager.active_connections:
          with _estado_lock:
              proc = processo_atual
          if proc:
              logging.info("[ws-disconnect] Último cliente desconectou com processo ativo — cancelando.")
              proc.terminate()
              _set_estado(ocupado=False, progresso=None, erro="Execução interrompida: navegador fechado.")
              with _estado_lock:
                  processo_atual = None
      ```
    - Garantir que `proc.terminate()` é chamado FORA do `_estado_lock` (evitar deadlock com `_set_estado`)
    - Garantir que a leitura de `processo_atual` e a escrita de `None` são feitas em blocos `with _estado_lock` separados
    - _Bug_Condition: `ws_manager.active_connections IS EMPTY AFTER disconnect AND processo_atual IS NOT None`_
    - _Expected_Behavior: `proc.terminate()` + `_set_estado(ocupado=False, progresso=None, erro="Execução interrompida: navegador fechado.")` + `processo_atual = None`_
    - _Preservation: lógica só dispara quando `active_connections` está vazio; se há outros clientes, processo continua_
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 3.2 Verificar que o teste de exploração da bug condition agora passa
    - **Property 1: Expected Behavior** - Processo encerrado ao desconectar último cliente
    - **IMPORTANT**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever um novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passar, confirma que o comportamento esperado está satisfeito
    - Rodar o teste de exploração da tarefa 1
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 3.3 Verificar que os testes de preservação ainda passam
    - **Property 2: Preservation** - Processo não encerrado enquanto há clientes ativos
    - **IMPORTANT**: Re-executar os MESMOS testes da tarefa 2 — NÃO escrever novos testes
    - Rodar os property-based tests de preservação da tarefa 2
    - **EXPECTED OUTCOME**: Testes PASSAM (confirma ausência de regressões)
    - Confirmar que todos os testes passam após o fix

---

## Bug 2 — Dual Tenant Credentials

- [x] 4. Escrever teste de exploração da bug condition — Bug 2
  - **Property 1: Bug Condition** - `capture_adapter` retorna credenciais genéricas em vez de credenciais de captura
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: O teste codifica o comportamento esperado — ele validará o fix quando passar após a implementação
  - **GOAL**: Demonstrar que `SeniorXAdapter().obter_credenciais()` retorna `SENIOR_USER`/`SENIOR_PASS` em vez de `SENIOR_USER_CAPTURE`/`SENIOR_PASS_CAPTURE`
  - **Scoped PBT Approach**: Escopo determinístico — setar `SENIOR_USER_CAPTURE=capture_user`, `SENIOR_USER=old_user`, chamar `obter_credenciais()`
  - Em `tests/test_capture_adapter.py`, adicionar/atualizar `test_senior_x_credenciais_de_env`:
    - `monkeypatch.setenv("SENIOR_USER_CAPTURE", "usuario_captura")`
    - `monkeypatch.setenv("SENIOR_PASS_CAPTURE", "senha_captura")`
    - `monkeypatch.setenv("SENIOR_USER", "usuario_antigo")`
    - `monkeypatch.setenv("SENIOR_PASS", "senha_antiga")`
    - Assertar que `creds["usuario"] == "usuario_captura"` — no código não corrigido, esta asserção FALHA (retorna `"usuario_antigo"`)
  - Escrever property-based test com Hypothesis: gerar strings aleatórias para `SENIOR_USER_CAPTURE`/`SENIOR_PASS_CAPTURE` → assertar que `obter_credenciais()` retorna exatamente esses valores
  - Rodar os testes no código NÃO CORRIGIDO
  - **EXPECTED OUTCOME**: Testes FALHAM (correto — prova que o bug existe)
  - Documentar o contraexemplo: `obter_credenciais()` retorna `SENIOR_USER` em vez de `SENIOR_USER_CAPTURE`
  - Marcar tarefa completa quando os testes estiverem escritos, executados, e a falha documentada
  - _Requirements: 2.5_

- [x] 5. Escrever testes de preservação — Bug 2 (ANTES de implementar o fix)
  - **Property 2: Preservation** - Fluxo de credenciais inalterado para módulos não afetados
  - **IMPORTANT**: Seguir metodologia observation-first
  - Observar no código NÃO CORRIGIDO: `obter_credenciais()` com `SENIOR_USER`/`SENIOR_PASS` setados retorna esses valores
  - Escrever property-based test com Hypothesis: gerar strings aleatórias para `SENIOR_USER_CAPTURE`/`SENIOR_PASS_CAPTURE` → após o fix, assertar que o retorno é sempre exatamente esses valores (não vazio, não fallback para variável antiga)
  - Escrever teste: `SENIOR_URL` não é afetada pela mudança de credenciais — assertar que `os.getenv("SENIOR_URL")` retorna o mesmo valor antes e depois do patch
  - Escrever teste: mensagem de erro de cada módulo quando variável ausente identifica a variável correta (ex: `"SENIOR_USER_CAPTURE"` na mensagem de erro de `capture.py`)
  - Rodar os testes no código NÃO CORRIGIDO (os testes de preservação devem passar)
  - **EXPECTED OUTCOME**: Testes PASSAM (confirma o comportamento baseline a preservar)
  - Marcar tarefa completa quando os testes estiverem escritos, executados, e passando no código não corrigido
  - _Requirements: 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [x] 6. Fix do Bug 2 — Credenciais específicas por contexto

  - [x] 6.1 Atualizar módulos de captura para usar `SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE`
    - `capture.py`: substituir `os.getenv("SENIOR_USER")` → `os.getenv("SENIOR_USER_CAPTURE")` e `os.getenv("SENIOR_PASS")` → `os.getenv("SENIOR_PASS_CAPTURE")`; atualizar mensagem de erro para `"SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE"`
    - `capture_variants/capture_dual_output.py`: mesma substituição e mensagem de erro
    - `CIL/capture/capture_semantic.py`: mesma substituição e mensagem de erro
    - `contracts/capture_adapter.py` — `SeniorXAdapter.obter_credenciais()`: substituir `os.getenv("SENIOR_USER", "")` → `os.getenv("SENIOR_USER_CAPTURE", "")` e `os.getenv("SENIOR_PASS", "")` → `os.getenv("SENIOR_PASS_CAPTURE", "")`
    - _Bug_Condition: `module reads "SENIOR_USER" OR "SENIOR_PASS" AND no distinction between capture and execute context`_
    - _Expected_Behavior: módulos de captura usam `SENIOR_USER_CAPTURE`/`SENIOR_PASS_CAPTURE`_
    - _Preservation: fluxo Playwright inalterado; apenas a leitura da variável de credencial muda_
    - _Requirements: 2.1, 2.4, 2.5_

  - [x] 6.2 Atualizar módulos de execução para usar `SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE`
    - `main.py`: substituir `os.getenv("SENIOR_USER")` → `os.getenv("SENIOR_USER_EXECUTE")` e `os.getenv("SENIOR_PASS")` → `os.getenv("SENIOR_PASS_EXECUTE")`; atualizar mensagem de erro para `"SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE"`
    - `validator.py`: mesma substituição; adicionar guard `if not usuario or not senha: print("ERRO: Credenciais de execução ausentes no .env (SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE)", flush=True); return`
    - `validator_hitl.py`: mesma substituição e mensagem de erro
    - `CIL/main_cil.py`: substituir `SENIOR_USER = os.getenv("SENIOR_USER")` → `SENIOR_USER = os.getenv("SENIOR_USER_EXECUTE")` e `SENIOR_PASS = os.getenv("SENIOR_PASS")` → `SENIOR_PASS = os.getenv("SENIOR_PASS_EXECUTE")`
    - _Bug_Condition: `module reads "SENIOR_USER" OR "SENIOR_PASS" AND no distinction between capture and execute context`_
    - _Expected_Behavior: módulos de execução usam `SENIOR_USER_EXECUTE`/`SENIOR_PASS_EXECUTE`_
    - _Preservation: fluxo Playwright inalterado; apenas a leitura da variável de credencial muda_
    - _Requirements: 2.2, 2.3, 2.6_

  - [x] 6.3 Atualizar arquivos de suporte
    - `.env.example`: remover `SENIOR_USER` e `SENIOR_PASS`; adicionar os 4 novos pares com comentários de contexto:
      ```dotenv
      # Credenciais do tenant de CAPTURA (capture.py, capture_dual_output.py,
      # capture_semantic.py, capture_adapter.py)
      SENIOR_USER_CAPTURE=email@tenant-captura.com.br
      SENIOR_PASS_CAPTURE=password_captura

      # Credenciais do tenant de EXECUÇÃO (main.py, validator.py,
      # validator_hitl.py, main_cil.py)
      SENIOR_USER_EXECUTE=email@tenant-execucao.com.br
      SENIOR_PASS_EXECUTE=password_execucao
      ```
    - `.env`: adicionar as 4 novas variáveis com valores reais (NÃO remover `SENIOR_USER`/`SENIOR_PASS` ainda — preservar ambiente atual até validação completa)
    - `tests/test_capture_adapter.py`: atualizar `test_senior_x_credenciais_de_env` e `test_senior_x_credenciais_nao_hardcoded` para usar `SENIOR_USER_CAPTURE`/`SENIOR_PASS_CAPTURE` conforme design
    - _Requirements: 2.7, 3.9_

  - [x] 6.4 Verificar que os testes de exploração da bug condition agora passam
    - **Property 1: Expected Behavior** - `capture_adapter` retorna credenciais de captura
    - **IMPORTANT**: Re-executar os MESMOS testes da tarefa 4 — NÃO escrever novos testes
    - Rodar os testes de exploração da tarefa 4
    - **EXPECTED OUTCOME**: Testes PASSAM (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 6.5 Verificar que os testes de preservação ainda passam
    - **Property 2: Preservation** - Fluxo de credenciais inalterado para módulos não afetados
    - **IMPORTANT**: Re-executar os MESMOS testes da tarefa 5 — NÃO escrever novos testes
    - Rodar os property-based tests de preservação da tarefa 5
    - **EXPECTED OUTCOME**: Testes PASSAM (confirma ausência de regressões)
    - Confirmar que `tests/test_capture_adapter.py` passa integralmente após as atualizações

---

## Checkpoint Final

- [x] 7. Checkpoint — Garantir que todos os testes passam
  - Rodar a suíte completa de testes: `pytest tests/ -v`
  - Confirmar que os testes de exploração das tarefas 1 e 4 passam (bug corrigido)
  - Confirmar que os testes de preservação das tarefas 2 e 5 passam (sem regressões)
  - Confirmar que `tests/test_capture_adapter.py` passa integralmente
  - Verificar que nenhum módulo ainda referencia `os.getenv("SENIOR_USER")` ou `os.getenv("SENIOR_PASS")` nos arquivos afetados
  - Verificar que o `.env` contém as 4 novas variáveis
  - Perguntar ao usuário se houver dúvidas antes de fechar
