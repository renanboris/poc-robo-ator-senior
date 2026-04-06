# Bugfix Requirements Document

## Introduction

Ao concluir o pipeline completo de produção (vídeo → SCORM → PDF → SimLink → Indexação), o `index.html` trava indefinidamente no último passo "Indexando na base de conhecimento". O backend conclui o processo com sucesso (confirmado pelo log `Auto-rebuild pós-ingest`), mas o frontend nunca recebe o sinal de conclusão via WebSocket e permanece em estado de carregamento infinito. O usuário nunca vê a produção como concluída.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o usuário aciona a produção completa e o passo de indexação (`/api/ingest/{arquivo}`) é executado THEN o sistema não emite nenhuma transição de estado via WebSocket que resolva a promessa `pollStatus()` do frontend

1.2 WHEN o endpoint `/api/ingest/{arquivo}` retorna HTTP 200 com sucesso THEN o sistema não chama `_set_estado()` com qualquer campo que altere o estado do servidor, deixando `_wsResolve` pendente indefinidamente

1.3 WHEN o `lego_builder.construir_biblioteca()` é executado na thread daemon `_rebuild_apos_ingest` após o ingest THEN o sistema não notifica o frontend sobre a conclusão dessa etapa assíncrona

### Expected Behavior (Correct)

2.1 WHEN o endpoint `/api/ingest/{arquivo}` conclui com sucesso THEN o sistema SHALL emitir via WebSocket uma atualização de estado que satisfaça a condição `!data.ocupado` no frontend, resolvendo a promessa `pollStatus()`

2.2 WHEN o endpoint `/api/ingest/{arquivo}` retorna HTTP 200 THEN o sistema SHALL chamar `_set_estado(sucesso=<mensagem>)` para que o broadcast WebSocket seja disparado e o frontend possa detectar a conclusão

2.3 WHEN o endpoint `/api/ingest/{arquivo}` retorna um erro THEN o sistema SHALL chamar `_set_estado(erro=<mensagem>)` para que o frontend possa detectar a falha e exibir o estado de erro corretamente

### Unchanged Behavior (Regression Prevention)

3.1 WHEN os passos anteriores da produção (vídeo, SCORM, PDF, SimLink) são executados via `executar_processo_bg` THEN o sistema SHALL CONTINUE TO emitir atualizações de estado via WebSocket normalmente, sem regressão no comportamento existente

3.2 WHEN o endpoint `/api/ingest/{arquivo}` é chamado diretamente (fora do fluxo do stepper) THEN o sistema SHALL CONTINUE TO retornar a resposta JSON do `dap_engine.ingestar_para_pinecone()` sem alteração no contrato da API

3.3 WHEN o `lego_builder.construir_biblioteca()` é executado em background após o ingest THEN o sistema SHALL CONTINUE TO executar de forma assíncrona sem bloquear a resposta HTTP do endpoint

3.4 WHEN o frontend recebe o sinal de conclusão do passo de indexação THEN o sistema SHALL CONTINUE TO exibir o card de entregáveis (`addDeliverables`) e marcar a produção como concluída normalmente

---

## Bug Condition (Pseudocódigo)

```pascal
FUNCTION isBugCondition(X)
  INPUT: X de tipo PipelineStep
  OUTPUT: boolean

  // O bug ocorre quando o passo é o de ingest (não passa por executar_processo_bg)
  // e o frontend está aguardando uma transição de estado via WebSocket
  RETURN X.endpoint = "/api/ingest/{arquivo}"
     AND X.frontend_waiting_for_ws_resolution = true
END FUNCTION
```

```pascal
// Property: Fix Checking
FOR ALL X WHERE isBugCondition(X) DO
  result ← ingestar_no_dap'(X)
  ASSERT _set_estado_called_with_sucesso_or_erro(result)
  ASSERT ws_broadcast_emitted(result)
  ASSERT frontend_pollStatus_resolved(result)
END FOR
```

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT executar_processo_bg(X) = executar_processo_bg'(X)
END FOR
```
