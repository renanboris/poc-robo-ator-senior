# Bugfix Requirements Document

## Introduction

Durante uma sessão de captura no `capture.py`, alguns cliques — especialmente os últimos realizados antes de fechar o navegador — são silenciosamente descartados e não aparecem no roteiro gerado. O problema persiste mesmo após uma tentativa anterior de correção. A causa raiz está em duas falhas combinadas:

1. **Race condition no encerramento da sessão**: o loop principal detecta `page.is_closed()` e encerra imediatamente, sem aguardar que as tarefas assíncronas de `on_capturar_elemento` (que incluem screenshot + chamada Gemini) ainda em voo sejam concluídas. Qualquer clique cujo processamento ainda esteja em andamento no momento do fechamento é perdido.

2. **Janela cega de 250ms no JS**: o listener `mousedown` usa um `setTimeout` de 250ms para distinguir clique simples de duplo clique. Se o usuário fechar o navegador dentro dessa janela após o último clique, o `setTimeout` nunca dispara e o evento nunca é enviado ao Python via `capturarElemento`.

O resultado é que `cliques_capturados` está incompleto quando `orquestrador_pos_captura` é chamado, gerando roteiros com passos faltando.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o usuário realiza um ou mais cliques e fecha o navegador imediatamente após, THEN o sistema encerra o loop de captura sem aguardar as tarefas assíncronas de `on_capturar_elemento` em andamento, descartando silenciosamente os cliques cujo processamento ainda não foi concluído.

1.2 WHEN o usuário realiza o último clique da sessão e fecha o navegador dentro da janela de 250ms do `clickTimeout` no JavaScript, THEN o sistema nunca envia o evento `capturarElemento` ao Python, pois o `setTimeout` é cancelado junto com o contexto do navegador.

1.3 WHEN múltiplos cliques são realizados em rápida sucessão próximo ao encerramento da sessão, THEN o sistema pode descartar qualquer subconjunto desses cliques cujas tarefas assíncronas não foram concluídas antes do fechamento do browser.

### Expected Behavior (Correct)

2.1 WHEN o usuário fecha o navegador após realizar cliques, THEN o sistema SHALL aguardar a conclusão de todas as tarefas assíncronas de `on_capturar_elemento` em voo antes de prosseguir para `orquestrador_pos_captura`, garantindo que nenhum clique já recebido pelo Python seja descartado.

2.2 WHEN o navegador é fechado dentro da janela de 250ms do `clickTimeout`, THEN o sistema SHALL garantir que o evento do último clique seja enviado ao Python antes do contexto do browser ser destruído, eliminando a janela cega de perda de eventos.

2.3 WHEN múltiplos cliques são realizados em rápida sucessão próximo ao encerramento, THEN o sistema SHALL registrar todos os cliques já recebidos pela binding `capturarElemento` no momento do fechamento, sem perda silenciosa.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o usuário realiza cliques durante uma sessão normal (sem fechar o navegador imediatamente após), THEN o sistema SHALL CONTINUE TO capturar e processar cada clique com screenshot e análise Gemini como antes.

3.2 WHEN o usuário realiza um duplo clique, THEN o sistema SHALL CONTINUE TO distinguir corretamente clique simples de duplo clique usando a lógica de `clickTimeout`.

3.3 WHEN o usuário realiza cliques em iframes, THEN o sistema SHALL CONTINUE TO capturar esses eventos via re-injeção do radar nos frames.

3.4 WHEN o usuário realiza clique direito, THEN o sistema SHALL CONTINUE TO capturar o evento imediatamente sem delay.

3.5 WHEN o usuário preenche campos de input e pressiona Enter, THEN o sistema SHALL CONTINUE TO capturar os eventos `digitar_e_enter` e `preencher_campo` corretamente.

3.6 WHEN o roteiro é gerado ao final da sessão, THEN o sistema SHALL CONTINUE TO passar pelo portão de qualidade `_validar_roteiro` antes do auto-rebuild da biblioteca.

---

## Bug Condition (Pseudocódigo)

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type CaptureSession
  OUTPUT: boolean

  // Bug ocorre quando há cliques cujo processamento assíncrono
  // ainda está em andamento no momento em que o browser fecha
  RETURN (X.pending_on_capturar_tasks > 0 AND X.browser_closed = true)
      OR (X.last_click_within_250ms_of_close = true)
END FUNCTION
```

```pascal
// Property: Fix Checking
FOR ALL X WHERE isBugCondition(X) DO
  result ← capturar_cliques_na_tela'(X)
  ASSERT len(cliques_capturados) = X.total_clicks_performed
  ASSERT no_click_silently_dropped(result)
END FOR

// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT capturar_cliques_na_tela(X) = capturar_cliques_na_tela'(X)
END FOR
```
