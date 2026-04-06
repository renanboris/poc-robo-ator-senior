# Production Completion Signal — Bugfix Design

## Overview

O endpoint `/api/ingest/{arquivo}` conclui com sucesso (HTTP 200) mas nunca chama `_set_estado()`, portanto nenhum broadcast WebSocket é emitido. O frontend fica aguardando indefinidamente em `aguardarStatus()` porque `_wsResolve` só é resolvido quando chega uma mensagem com `!data.ocupado` — o que nunca acontece.

A correção é mínima e cirúrgica: adicionar chamadas a `_set_estado(sucesso=...)` e `_set_estado(erro=...)` no endpoint `ingestar_no_dap`, respeitando o contrato existente de todos os outros passos da produção.

## Glossary

- **Bug_Condition (C)**: O endpoint `/api/ingest/{arquivo}` é chamado pelo stepper de produção enquanto o frontend aguarda resolução via WebSocket
- **Property (P)**: Após o endpoint retornar, `_set_estado()` deve ter sido chamado com `sucesso` ou `erro`, disparando o broadcast WebSocket
- **Preservation**: O comportamento de `executar_processo_bg` e o contrato de resposta JSON do endpoint não devem ser alterados
- **`ingestar_no_dap`**: Função em `app.py` que chama `dap_engine.ingestar_para_pinecone()` e retorna o resultado diretamente — sem chamar `_set_estado()`
- **`_set_estado`**: Função em `app.py` que atualiza `estado_servidor` e dispara `ws_manager.broadcast()` via `asyncio.run_coroutine_threadsafe`
- **`_wsResolve`**: Callback no frontend (`index.html`) que resolve a Promise de `aguardarStatus()` quando recebe `!data.ocupado` via WebSocket
- **`executar_processo_bg`**: Função que gerencia os outros passos da produção (vídeo, SCORM, PDF, SimLink) — já chama `_set_estado()` corretamente
- **`_rebuild_apos_ingest`**: Thread daemon que executa `lego_builder.construir_biblioteca()` após o ingest — executa de forma assíncrona sem bloquear a resposta HTTP

## Bug Details

### Bug Condition

O bug se manifesta quando o stepper de produção chama `/api/ingest/{arquivo}` como último passo. Diferente dos passos anteriores (que usam `executar_processo_bg`), este endpoint é síncrono e retorna diretamente o resultado de `dap_engine.ingestar_para_pinecone()` sem passar pelo mecanismo de `_set_estado()`. O frontend, que já registrou `_wsResolve` antes de fazer o fetch, nunca recebe o sinal de conclusão.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X de tipo PipelineStep
  OUTPUT: boolean

  RETURN X.endpoint = "/api/ingest/{arquivo}"
     AND X.frontend_waiting_for_ws_resolution = true
     AND _set_estado_called_after_endpoint_returns = false
END FUNCTION
```

### Examples

- **Caso normal (bug ativo)**: Usuário aciona produção completa → passos 1-4 concluem normalmente → passo 5 "Indexando na base de conhecimento" inicia → backend conclui com sucesso → frontend trava indefinidamente aguardando WebSocket
- **Caso de erro (bug ativo)**: `dap_engine.ingestar_para_pinecone()` retorna `{"status": "erro", ...}` → endpoint retorna HTTP 200 com o JSON de erro → frontend ainda trava (nunca recebe `!data.ocupado`)
- **Caso esperado (após fix)**: Endpoint conclui → `_set_estado(sucesso="✅ Indexação concluída.")` é chamado → broadcast WebSocket emitido → `_wsResolve` resolve → stepper avança para "Produção concluída"
- **Edge case — rebuild assíncrono**: Thread `_rebuild_apos_ingest` termina após a resposta HTTP → não deve interferir com o sinal de conclusão já emitido

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Os passos anteriores da produção (vídeo, SCORM, PDF, SimLink) via `executar_processo_bg` devem continuar emitindo atualizações WebSocket normalmente
- O contrato de resposta JSON do endpoint `/api/ingest/{arquivo}` deve continuar retornando o resultado de `dap_engine.ingestar_para_pinecone()` — o `return res` no final não deve ser removido
- A thread `_rebuild_apos_ingest` deve continuar executando de forma assíncrona sem bloquear a resposta HTTP
- O campo `ingestado_dap` no metadata do roteiro deve continuar sendo atualizado em caso de sucesso

**Scope:**
Todos os inputs que NÃO envolvem o endpoint `/api/ingest/{arquivo}` devem ser completamente inalterados por este fix. Isso inclui:
- Chamadas a `executar_processo_bg` (gravar, renderizar, SCORM, PDF, SimLink)
- Chamadas diretas ao endpoint de ingest fora do fluxo do stepper
- Qualquer outro endpoint da API

## Hypothesized Root Cause

Com base na análise do código, a causa raiz é direta e confirmada:

1. **Ausência de `_set_estado()` no endpoint de ingest**: Todos os outros passos da produção passam por `executar_processo_bg`, que chama `_set_estado(sucesso=...)` ou `_set_estado(erro=...)` ao final. O endpoint `ingestar_no_dap` foi implementado como uma rota síncrona simples que retorna diretamente `res` sem notificar o estado do servidor.

2. **Assimetria arquitetural**: O stepper trata todos os passos de forma uniforme — chama o endpoint, depois aguarda `pollStatus()`. Os passos 1-4 funcionam porque `executar_processo_bg` gerencia o ciclo de vida do estado. O passo 5 quebra essa expectativa por não seguir o mesmo padrão.

3. **Thread daemon sem notificação**: `_rebuild_apos_ingest` executa `lego_builder.construir_biblioteca()` e loga o resultado, mas não chama `_set_estado()`. Isso não é a causa primária do bug (o sinal deve ser emitido antes, no endpoint síncrono), mas é uma inconsistência secundária.

4. **`estado_servidor["ocupado"]` nunca é alterado**: O endpoint não chama `_set_estado(ocupado=True)` no início nem `_set_estado(ocupado=False)` ao final, então o estado permanece `ocupado=False` do início ao fim — o que paradoxalmente poderia resolver `_wsResolve` prematuramente se o WebSocket enviasse o estado inicial, mas na prática o frontend já registrou `_wsResolve` após o `limpar-status` e aguarda a próxima mensagem com `!data.ocupado`.

## Correctness Properties

Property 1: Bug Condition — Ingest Endpoint Emits Completion Signal

_For any_ chamada ao endpoint `/api/ingest/{arquivo}` onde o frontend está aguardando resolução via WebSocket (isBugCondition retorna true), o endpoint corrigido SHALL chamar `_set_estado(sucesso=<mensagem>)` em caso de sucesso ou `_set_estado(erro=<mensagem>)` em caso de falha, garantindo que um broadcast WebSocket seja emitido com `ocupado=False` e que `_wsResolve` seja resolvido no frontend.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation — Outros Passos da Produção Inalterados

_For any_ chamada a `executar_processo_bg` (passos de vídeo, SCORM, PDF, SimLink) onde isBugCondition NÃO se aplica, o código corrigido SHALL produzir exatamente o mesmo comportamento que o código original, preservando o ciclo de vida de estado WebSocket existente e o contrato de resposta JSON do endpoint de ingest.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assumindo que a análise de causa raiz está correta:

**File**: `app.py`

**Function**: `ingestar_no_dap`

**Specific Changes**:

1. **Adicionar `_set_estado(sucesso=...)` no branch de sucesso**: Após salvar `ingestado_dap=True` e antes de iniciar a thread de rebuild, chamar `_set_estado(sucesso="✅ Indexação concluída na base de conhecimento.")`. Isso dispara o broadcast WebSocket e resolve `_wsResolve` no frontend.

2. **Adicionar `_set_estado(erro=...)` no branch de falha**: No `else` do `if res.get("status") == "sucesso"`, chamar `_set_estado(erro=res.get("mensagem", "Falha na indexação."))` para que o frontend possa detectar e exibir o erro corretamente.

3. **Preservar o `return res`**: O contrato de resposta JSON do endpoint não deve ser alterado — o `return res` permanece no final da função, garantindo compatibilidade com chamadas diretas ao endpoint fora do stepper.

4. **Não alterar a thread `_rebuild_apos_ingest`**: A thread daemon continua executando de forma assíncrona. O sinal de conclusão já foi emitido pelo endpoint síncrono antes da thread iniciar — não há necessidade de emitir um segundo sinal.

5. **Não adicionar `_set_estado(ocupado=True/False)`**: O endpoint de ingest é síncrono e rápido (não é um processo longo em background). Adicionar `ocupado=True` bloquearia outros endpoints desnecessariamente. O sinal de conclusão via `sucesso` ou `erro` é suficiente para resolver `_wsResolve`.

**Pseudocode do fix:**
```
FUNCTION ingestar_no_dap(arquivo):
  ...
  res = dap_engine.ingestar_para_pinecone(dados, tenant_id=tenant)
  
  IF res.get("status") == "sucesso":
    dados["metadata"]["ingestado_dap"] = True
    salvar_roteiro(caminho, dados)
    _set_estado(sucesso="✅ Indexação concluída na base de conhecimento.")  # ← FIX
    iniciar_thread(_rebuild_apos_ingest)
  ELSE:
    _set_estado(erro=res.get("mensagem", "Falha na indexação."))  # ← FIX
  
  return res  # contrato preservado
END FUNCTION
```

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro confirmar o bug no código não corrigido (exploratory), depois verificar o fix e a preservação.

### Exploratory Bug Condition Checking

**Goal**: Confirmar que `_set_estado()` nunca é chamado no endpoint atual. Refutar ou confirmar a hipótese de causa raiz.

**Test Plan**: Mockar `dap_engine.ingestar_para_pinecone` para retornar sucesso, chamar o endpoint, e verificar que `estado_servidor` não foi alterado. Executar no código NÃO corrigido para observar a falha.

**Test Cases**:
1. **Ingest com sucesso (unfixed)**: Mock retorna `{"status": "sucesso"}` → verificar que `estado_servidor["sucesso"]` permanece vazio (demonstra o bug)
2. **Ingest com erro (unfixed)**: Mock retorna `{"status": "erro", "mensagem": "Pinecone indisponível"}` → verificar que `estado_servidor["erro"]` permanece vazio (demonstra o bug)
3. **WebSocket não resolve (unfixed)**: Simular `_wsResolve` registrado → chamar endpoint → verificar que `_wsResolve` nunca é invocado
4. **Estado ocupado não muda (unfixed)**: Verificar que `estado_servidor["ocupado"]` permanece `False` durante e após o endpoint (confirma a assimetria arquitetural)

**Expected Counterexamples**:
- `estado_servidor["sucesso"]` permanece `""` após endpoint retornar HTTP 200 com sucesso
- `_wsResolve` nunca é chamado, confirmando o travamento do frontend

### Fix Checking

**Goal**: Verificar que para todos os inputs onde isBugCondition é verdadeiro, o endpoint corrigido emite o sinal de conclusão.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  result ← ingestar_no_dap_fixed(X)
  ASSERT _set_estado_called = true
  ASSERT estado_servidor["sucesso"] != "" OR estado_servidor["erro"] != ""
  ASSERT ws_broadcast_emitted = true
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todos os inputs onde isBugCondition NÃO se aplica, o comportamento é idêntico ao original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT executar_processo_bg_original(X) = executar_processo_bg_fixed(X)
  ASSERT ingestar_no_dap_response_original(X) = ingestar_no_dap_response_fixed(X)
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente para os outros passos da produção
- Captura edge cases que testes manuais podem perder
- Fornece garantias fortes de que o comportamento de `executar_processo_bg` não foi alterado

**Test Cases**:
1. **Preservação do contrato JSON**: Verificar que `return res` continua retornando o resultado de `dap_engine.ingestar_para_pinecone()` sem modificação
2. **Preservação do executar_processo_bg**: Verificar que os passos de vídeo, SCORM, PDF e SimLink continuam emitindo WebSocket normalmente
3. **Preservação da thread assíncrona**: Verificar que `_rebuild_apos_ingest` ainda executa em background sem bloquear a resposta HTTP
4. **Preservação do ingestado_dap**: Verificar que o campo `metadata.ingestado_dap` ainda é salvo no roteiro em caso de sucesso

### Unit Tests

- Testar `ingestar_no_dap` com mock de sucesso → verificar `_set_estado(sucesso=...)` chamado
- Testar `ingestar_no_dap` com mock de erro → verificar `_set_estado(erro=...)` chamado
- Testar que `return res` preserva o JSON original de `dap_engine.ingestar_para_pinecone()`
- Testar que a thread `_rebuild_apos_ingest` é iniciada apenas em caso de sucesso

### Property-Based Tests

- Gerar estados aleatórios de `dap_engine` (sucesso/erro com mensagens variadas) e verificar que `_set_estado` sempre é chamado com o campo correto
- Gerar chamadas aleatórias a `executar_processo_bg` e verificar que o comportamento de broadcast WebSocket é preservado
- Verificar que para qualquer resposta de `ingestar_para_pinecone`, o `return res` sempre retorna exatamente o mesmo objeto

### Integration Tests

- Simular o fluxo completo do stepper (5 passos) e verificar que o último passo resolve `pollStatus()` corretamente
- Verificar que após o fix, o card de entregáveis (`addDeliverables`) é exibido ao final da produção
- Testar o endpoint de ingest chamado diretamente (fora do stepper) e verificar que a resposta JSON não mudou
- Testar que o WebSocket emite `ocupado=False` com `sucesso` preenchido após o ingest
