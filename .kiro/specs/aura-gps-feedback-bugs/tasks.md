# Implementation Plan

## Overview

Plano de implementação para os três bugs documentados em `bugfix.md` e `design.md`. A ordem de execução para cada bug segue a metodologia de bug condition: exploration test → fix → fix checking test → preservation test.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "4", "7"] },
    { "wave": 2, "tasks": ["2", "5", "8"] },
    { "wave": 3, "tasks": ["3", "6", "9"] },
    { "wave": 4, "tasks": ["10"] }
  ]
}
```

## Tasks

<!-- Bug 1 — GPS para no primeiro passo -->

- [x] 1. Escrever exploration test da race condition do GPS (Bug 1)
  - **Property 1: Bug Condition** - GPS valida passo N+1 com evento do passo N (race condition)
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Demonstrar que um único clique avança dois passos consecutivos com `target_selector` vazio
  - **Scoped PBT Approach**: Escopo determinístico — roteiro com dois passos `target_selector: ""`, um único `dispatchEvent(click)` no `document`
  - Criar roteiro `[{target_selector: ""}, {target_selector: ""}]` e inicializar `AuraGpsEngine.init(roteiro)`
  - Disparar um único `click` via `document.dispatchEvent(new MouseEvent('click', {bubbles: true}))`
  - Verificar que `_stepIndex === 2` após um único clique (confirma a race condition)
  - Verificar também o caso `[{target_selector: "#btn"}, {target_selector: ""}]`: clicar em `#btn` e checar se passo 2 é validado imediatamente
  - Verificar que o caso `[{target_selector: "#btn1"}, {target_selector: "#btn2"}]` NÃO falha (confirma que o bug é específico à delegação)
  - Documentar o counterexample: `_stepIndex === 2` após um único clique quando ambos os passos usam delegação
  - Causa raiz confirmada: `_iniciarPasso(N+1)` registra listener no `document` antes do bubbling do evento do passo N terminar
  - Marcar tarefa completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Implementar `_usaDelegacao` e corrigir `_avancarPasso` em `aura_gps_engine.js` (Bug 1)

  - [x] 2.1 Adicionar função auxiliar `_usaDelegacao(step)` antes de `_avancarPasso`
    - Retorna `true` se `step` é falsy, `step.target_selector` está vazio/ausente, ou `AuraSpotlight.encontrarElemento(step.target_selector)` retorna `null`
    - Retorna `false` quando o elemento está presente no DOM (caminho sem delegação)
    - Não modifica nenhum estado — função pura de consulta
    - _Bug_Condition: isBugCondition_GPS(step, "avancarPasso") onde step.target_selector = "" ou elemento ausente_
    - _Expected_Behavior: _usaDelegacao retorna true exatamente quando o próximo passo usaria listener no document_
    - _Preservation: passos com seletor válido e elemento presente retornam false — sem setTimeout introduzido_
    - _Requirements: 2.1, 2.2_

  - [x] 2.2 Modificar o caminho sem `branch_id` em `_avancarPasso`
    - Substituir a chamada direta `_iniciarPasso(proximo)` por `setTimeout(function() { _iniciarPasso(proximo); }, 0)` quando `_usaDelegacao(_passos[proximo])` for verdadeiro
    - Manter chamada direta `_iniciarPasso(proximo)` quando `_usaDelegacao` retornar false (seletor válido)
    - NÃO modificar o caminho `init → _iniciarPasso(0)` — sem evento em propagação, sem necessidade de setTimeout
    - NÃO modificar o caminho `branch_id` — já usa `setTimeout(fn, 0)`, preservado sem alteração
    - _Bug_Condition: isBugCondition_GPS(step, "avancarPasso") — calledFrom = "avancarPasso" AND delegação ativa_
    - _Expected_Behavior: listener do passo N+1 registrado somente após término do bubbling do evento do passo N_
    - _Preservation: Preservation Requirements do design — seletor válido, init, branch_id, outros validation_type_
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4_

  - [x] 2.3 Verificar que exploration test do passo 1 agora passa (fix checking)
    - **Property 1: Expected Behavior** - GPS não valida passo N+1 com evento do passo N
    - **IMPORTANT**: Re-executar o MESMO teste do passo 1 — NÃO escrever novo teste
    - O teste do passo 1 codifica o comportamento esperado: `_stepIndex` deve ser 1 (não 2) após um único clique
    - Verificar que `_stepIndex === 1` após um único clique com dois passos de delegação
    - Verificar que o passo 2 aguarda segundo clique real antes de avançar
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.4 Verificar preservation tests do GPS (preservation checking)
    - **Property 2: Preservation** - GPS com seletor válido não é afetado pela correção
    - **IMPORTANT**: Re-executar os MESMOS testes de preservation — NÃO escrever novos testes
    - Verificar que `_iniciarPasso` NÃO usa `setTimeout` quando elemento existe no DOM (seletor válido)
    - Verificar que `_iniciarPasso(0)` chamado de `init()` não usa `setTimeout`
    - Verificar que `validation_type: type` continua funcionando sem regressão
    - Verificar que `validation_type: url_change` (MutationObserver) continua funcionando
    - Verificar que abandono explícito continua emitindo `gps:abandoned` e retornando para modo `assist`
    - **EXPECTED OUTCOME**: Todos os testes PASSAM (confirma ausência de regressões)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Escrever property tests para Bug 1 (fix checking e preservation)
  - **Property 1: Bug Condition** - GPS não valida passo N+1 com evento do passo N
  - **Property 2: Preservation** - GPS com seletor válido não é afetado
  - **IMPORTANT**: Escrever estes testes APÓS a implementação do fix (passo 2)
  - **Property 1 — Fix Checking**: Para todo roteiro com passos de `target_selector` vazio, verificar que um único clique avança exatamente um passo (não dois)
    - Gerar roteiros aleatórios com 2–5 passos de `target_selector: ""`
    - Para cada par de passos consecutivos, disparar um clique e verificar `_stepIndex === stepAnterior + 1`
    - Verificar que `passo_validado_sem_acao_real = false` para todos os casos gerados
    - Executar no código CORRIGIDO — **EXPECTED OUTCOME**: Teste PASSA
  - **Property 2 — Preservation**: Para todo roteiro com `target_selector` válido e elemento presente no DOM, verificar que o comportamento é idêntico ao original
    - Gerar roteiros aleatórios com seletores válidos (`#btn-1`, `#btn-2`, etc.)
    - Verificar que `_iniciarPasso` não introduz `setTimeout` quando elemento existe
    - Verificar que `_iniciarPasso(0)` de `init()` não usa `setTimeout`
    - Executar no código CORRIGIDO — **EXPECTED OUTCOME**: Teste PASSA
  - _Requirements: 2.1, 2.2, 2.3 (Property 1) / 3.1, 3.2, 3.3, 3.4 (Property 2)_

<!-- Bug 2 — AI Gate suprime GPS -->

- [x] 4. Escrever exploration test da ausência de `gps_passos` no caminho AI Gate (Bug 2)
  - **Property 3: Bug Condition** - AI Gate retorna `resultado_rapido` sem `gps_passos`
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Demonstrar que `resultado_rapido` não contém `gps_passos` quando AI Gate ativa com roteiro GPS disponível
  - **Scoped PBT Approach**: Escopo determinístico — mockar `buscar_contexto_multi_namespace` para retornar `score=0.92` e `seletor_direto="#btn-sign"`, com roteiro GPS indexado
  - Mockar `buscar_contexto_multi_namespace` retornando `{"score": 0.92, "seletor_direto": "#btn-sign", "melhor_aula": "aula_sign", "texto_rag": "..."}`
  - Mockar `get_navigation_fallback_engine` retornando engine com roteiro GPS disponível
  - Chamar `_analisar_sync(prompt, url, dom_context, tenant_id)` e capturar o resultado
  - Verificar que `"gps_passos" not in resultado` (confirma o bug)
  - Verificar também o caso `score=0.65` (AI Gate inativo) — `gps_passos` pode estar presente (não falha)
  - Documentar o counterexample: `"gps_passos" not in resultado` quando `score=0.92` e roteiro GPS existe
  - Causa raiz confirmada: `return resultado_rapido` na seção 4 ocorre antes do bloco de GPS enrichment
  - Marcar tarefa completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 2.1, 2.2_

- [x] 5. Extrair `_enriquecer_com_gps` e chamar em ambos os caminhos em `dap_engine.py` (Bug 2)

  - [x] 5.1 Extrair função auxiliar `_enriquecer_com_gps(resultado, prompt_usuario, tenant_id)`
    - Mover o bloco try/except de GPS enrichment existente no caminho Gemini Vision para função de módulo
    - Função é idempotente: retorna `resultado` sem modificação se `"gps_passos"` já existe
    - Função não propaga exceção: try/except interno loga em DEBUG e ignora falhas
    - Retorna o dict `resultado` modificado in-place
    - Usar `get_navigation_fallback_engine`, `fallback_engine.indexer.search`, `fallback_engine.path_extractor.extract_navigation_path` conforme design
    - _Bug_Condition: isBugCondition_AIGate(busca_rag) onde score > 0.80 AND seletor_direto != None_
    - _Expected_Behavior: gps_passos adicionado ao resultado quando roteiro relevante encontrado_
    - _Preservation: idempotente, sem exceção propagada, sem nova lógica além da extração_
    - _Requirements: 2.4, 2.5_

  - [x] 5.2 Chamar `_enriquecer_com_gps` antes do `return resultado_rapido` no bloco AI Gate (seção 4)
    - Adicionar `_enriquecer_com_gps(resultado_rapido, prompt_usuario, tenant_id)` imediatamente antes de `_cache_set(cache_key, resultado_rapido)` e `return resultado_rapido`
    - NÃO alterar nenhuma outra lógica do bloco AI Gate
    - _Bug_Condition: isBugCondition_AIGate — score > 0.80 AND seletor_direto presente_
    - _Expected_Behavior: gps_passos presente em resultado_rapido quando roteiro GPS disponível_
    - _Requirements: 2.4, 2.5_

  - [x] 5.3 Substituir bloco inline de GPS enrichment no caminho Gemini Vision (seção 5) pela chamada à função extraída
    - Substituir o bloco try/except inline por `_enriquecer_com_gps(resultado_final, prompt_usuario, tenant_id)`
    - Verificar que o comportamento do caminho Vision é idêntico ao original
    - _Preservation: caminho Gemini Vision não alterado funcionalmente_
    - _Requirements: 3.5, 3.6_

  - [x] 5.4 Verificar que exploration test do passo 4 agora passa (fix checking)
    - **Property 3: Expected Behavior** - AI Gate inclui GPS enrichment
    - **IMPORTANT**: Re-executar o MESMO teste do passo 4 — NÃO escrever novo teste
    - Verificar que `"gps_passos" in resultado` quando `score=0.92`, `seletor_direto` presente e roteiro GPS disponível
    - Verificar que `gps_enrichment_executado = true` para todos os casos de AI Gate ativo
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.4, 2.5_

  - [x] 5.5 Verificar preservation tests do AI Gate (preservation checking)
    - **Property 4: Preservation** - Caminho Gemini Vision não é alterado
    - **IMPORTANT**: Re-executar os MESMOS testes de preservation — NÃO escrever novos testes
    - Verificar que `score=0.65` (AI Gate inativo) produz resultado idêntico ao original
    - Verificar que `seletor_direto=None` (AI Gate inativo) produz resultado idêntico ao original
    - Verificar que AI Gate ativo sem roteiro GPS retorna `resultado_rapido` sem `gps_passos` (comportamento correto)
    - Verificar idempotência: chamar `_enriquecer_com_gps` duas vezes não duplica `gps_passos`
    - **EXPECTED OUTCOME**: Todos os testes PASSAM (confirma ausência de regressões)
    - _Requirements: 3.5, 3.6, 3.7_

- [x] 6. Escrever property tests para Bug 2 (fix checking e preservation)
  - **Property 3: Bug Condition** - AI Gate inclui GPS enrichment
  - **Property 4: Preservation** - Caminho Gemini Vision não é alterado
  - **IMPORTANT**: Escrever estes testes APÓS a implementação do fix (passo 5)
  - **Property 3 — Fix Checking**: Para todo `busca_rag` com `score > 0.80` e `seletor_direto` presente, verificar que `_enriquecer_com_gps` é sempre chamado
    - Gerar scores aleatórios no intervalo `(0.80, 1.0]` com seletores CSS válidos
    - Para cada caso, verificar que `"gps_passos" in resultado OR gps_enrichment_executado = true`
    - Mockar `get_navigation_fallback_engine` com roteiro GPS disponível
    - Executar no código CORRIGIDO — **EXPECTED OUTCOME**: Teste PASSA
  - **Property 4 — Preservation**: Para todo `busca_rag` com `score <= 0.80` ou `seletor_direto=None`, verificar que o resultado é idêntico ao original
    - Gerar scores aleatórios no intervalo `[0.0, 0.80]`
    - Gerar casos com `seletor_direto=None` independentemente do score
    - Verificar que `_analisar_sync_original(busca_rag) == _analisar_sync_fixed(busca_rag)`
    - Executar no código CORRIGIDO — **EXPECTED OUTCOME**: Teste PASSA
  - _Requirements: 2.4, 2.5 (Property 3) / 3.5, 3.6, 3.7 (Property 4)_

<!-- Bug 3 — Feedback negativo sem propagação -->

- [x] 7. Escrever exploration test da ausência de `postMessage` no dislike (Bug 3)
  - **Property 5: Bug Condition** - Dislike não emite `postMessage` ao bridge
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Demonstrar que nenhum `postMessage` com `type: 'AURA_FEEDBACK_EVENT'` é emitido ao clicar 👎
  - **Scoped PBT Approach**: Escopo determinístico — interceptar `window.postMessage` antes de clicar no botão dislike
  - Carregar `aura_feedback.js` em ambiente de teste (jsdom ou Playwright)
  - Interceptar `window.postMessage` e registrar todas as mensagens emitidas
  - Clicar no botão dislike (`aura-fb-dislike`)
  - Verificar que nenhuma mensagem com `type: 'AURA_FEEDBACK_EVENT'` foi emitida (confirma o bug)
  - Verificar que `localStorage` contém a entrada após dislike (comportamento existente — não falha)
  - Verificar que clique em like também não emite `postMessage` (comportamento correto — não falha)
  - Documentar o counterexample: `postMessageEmitido = false` após clique em dislike
  - Causa raiz confirmada: `_registrar` não contém `window.postMessage` para o caminho dislike
  - Marcar tarefa completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 3.1, 3.2_

- [x] 8. Implementar as 4 camadas do fix de feedback negativo (Bug 3)

  - [x] 8.1 Modificar `_registrar` em `aura_feedback.js` — emitir `postMessage` no caminho dislike
    - Extrair payload `{ tipo, prompt, url, ts }` antes do bloco try/catch do localStorage
    - Após `localStorage.setItem`, adicionar bloco `if (tipo === 'dislike')` com `window.postMessage({ type: 'AURA_FEEDBACK_EVENT', payload }, window.location.origin)` dentro de try/catch
    - NÃO modificar o caminho `tipo === 'like'` — comportamento atual preservado
    - NÃO bloquear a remoção visual da barra em caso de falha no postMessage
    - _Bug_Condition: isBugCondition_Feedback(tipo) onde tipo = "dislike"_
    - _Expected_Behavior: postMessage emitido com type 'AURA_FEEDBACK_EVENT' e payload { tipo, prompt, url, ts }_
    - _Preservation: caminho like inalterado — apenas localStorage, sem postMessage_
    - _Requirements: 2.6, 3.8, 3.9_

  - [x] 8.2 Adicionar handler `AURA_FEEDBACK_EVENT` em `bridge.js`
    - Adicionar bloco `if (event.data.type === "AURA_FEEDBACK_EVENT")` seguindo o padrão existente de `AURA_ANALYTICS_EVENT`
    - Chamar `chrome.runtime.sendMessage({ action: "feedback_event", payload: event.data.payload }, callback)`
    - Logar warning em caso de `chrome.runtime.lastError`
    - Adicionar `return` após o handler para evitar fall-through
    - _Requirements: 2.6, 2.7_

  - [x] 8.3 Adicionar endpoint `feedback` em `AURA_ENDPOINTS` e handler `feedback_event` em `background.js`
    - Adicionar `feedback: _cfgEndpoints.feedback || 'http://localhost:8000/api/feedback'` ao objeto `AURA_ENDPOINTS`
    - Adicionar handler `if (request.action === 'feedback_event')` antes do handler `analisar_agora`
    - Handler faz `fetch(AURA_ENDPOINTS.feedback, { method: 'POST', headers: {...}, body: JSON.stringify(request.payload) })`
    - Retornar `sendResponse({ ok: true, data })` em sucesso e `sendResponse({ ok: false, reason: err.message })` em falha
    - Retornar `true` para manter canal assíncrono aberto
    - _Requirements: 2.7_

  - [x] 8.4 Adicionar modelo `FeedbackEventReq` e endpoint `POST /api/feedback` em `app.py`
    - Adicionar `class FeedbackEventReq(BaseModel)` com campos `tipo: str`, `prompt: str`, `url: str`, `ts: int`
    - Adicionar `@app.post("/api/feedback")` sem autenticação (dados de uso, não sensíveis — padrão do projeto)
    - Para `tipo != "dislike"`, retornar `{"ok": True, "action": "noop"}` imediatamente
    - Para `tipo == "dislike"`, chamar `await asyncio.to_thread(dap_engine.processar_feedback_negativo, payload.prompt, payload.url, payload.ts)`
    - Capturar exceções e retornar `{"ok": False, "reason": str(e)}` sem propagar HTTP 500
    - _Requirements: 2.8_

  - [x] 8.5 Adicionar função `processar_feedback_negativo` em `dap_engine.py`
    - Gerar embedding do prompt via `gerar_embedding`
    - Buscar vetor mais próximo no Pinecone com `top_k=1` no namespace `senior_default`
    - Se `score < SCORE_THRESHOLD` ou sem matches, retornar `{"action": "not_found"}`
    - Marcar vetor com `pinecone_index.update(id=melhor.id, namespace="senior_default", set_metadata={"feedback": "negative", "feedback_ts": ts})`
    - Invalidar cache SQLite com `DELETE FROM dap_cache WHERE cache_key LIKE ?` usando os primeiros 50 chars do prompt
    - Retornar `{"action": "marked_negative", "vector_id": melhor.id}` em sucesso
    - Capturar exceções e retornar `{"action": "error", "reason": str(e)}` sem propagar
    - _Bug_Condition: isBugCondition_Feedback(tipo) onde tipo = "dislike"_
    - _Expected_Behavior: vetor marcado com feedback='negative' E cache SQLite invalidado_
    - _Preservation: Pinecone e cache intactos para likes; UI não bloqueada se backend indisponível_
    - _Requirements: 2.8, 3.9, 3.10_

  - [x] 8.6 Verificar que exploration test do passo 7 agora passa (fix checking)
    - **Property 5: Expected Behavior** - Dislike propaga ao backend
    - **IMPORTANT**: Re-executar o MESMO teste do passo 7 — NÃO escrever novo teste
    - Verificar que `postMessageEmitido = true` com `type: 'AURA_FEEDBACK_EVENT'` após clique em dislike
    - Verificar que `payload` contém `{ tipo: 'dislike', prompt, url, ts }`
    - Verificar que `localStorage` ainda é salvo (comportamento preservado)
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.6, 2.7, 2.8_

  - [x] 8.7 Verificar preservation tests do feedback (preservation checking)
    - **Property 6: Preservation** - Like não envia chamada ao backend
    - **IMPORTANT**: Re-executar os MESMOS testes de preservation — NÃO escrever novos testes
    - Verificar que clique em 👍 NÃO emite `AURA_FEEDBACK_EVENT` (comportamento atual preservado)
    - Verificar que barra de feedback é removida visualmente mesmo quando backend retorna erro
    - Verificar que `localStorage` é salvo como fallback mesmo quando backend indisponível
    - Verificar que `processar_feedback_negativo` retorna `{"action": "not_found"}` sem exceção quando Pinecone sem match
    - **EXPECTED OUTCOME**: Todos os testes PASSAM (confirma ausência de regressões)
    - _Requirements: 3.8, 3.9, 3.10_

- [x] 9. Escrever property tests para Bug 3 (fix checking e preservation)
  - **Property 5: Bug Condition** - Dislike propaga ao backend
  - **Property 6: Preservation** - Like não envia chamada ao backend
  - **IMPORTANT**: Escrever estes testes APÓS a implementação do fix (passo 8)
  - **Property 5 — Fix Checking**: Para todo payload de dislike, verificar que `postMessage` é sempre emitido com os campos corretos
    - Gerar payloads aleatórios `{ tipo: 'dislike', prompt: str, url: str, ts: int }` com prompts de 1–100 chars e URLs válidas
    - Para cada payload, verificar que `postMessageEmitido = true`, `type = 'AURA_FEEDBACK_EVENT'`, `payload.tipo = 'dislike'`
    - Verificar que `localStorageSalvo = true` para todos os casos
    - Executar no código CORRIGIDO — **EXPECTED OUTCOME**: Teste PASSA
  - **Property 6 — Preservation**: Para todo payload de like, verificar que nenhum `postMessage` é emitido
    - Gerar payloads aleatórios `{ tipo: 'like', prompt: str, url: str, ts: int }`
    - Para cada payload, verificar que nenhuma mensagem `AURA_FEEDBACK_EVENT` foi emitida
    - Verificar que `localStorageSalvo = true` (comportamento preservado)
    - Executar no código CORRIGIDO — **EXPECTED OUTCOME**: Teste PASSA
  - _Requirements: 2.6, 2.7, 2.8 (Property 5) / 3.8, 3.9, 3.10 (Property 6)_

- [x] 10. Checkpoint — Garantir que todos os testes passam
  - Re-executar todos os property tests (Properties 1–6) e verificar que passam
  - Re-executar todos os exploration tests (passos 1, 4, 7) no código corrigido e verificar que passam
  - Verificar que nenhum teste de preservation regrediu
  - Confirmar que os três bugs estão corrigidos de forma independente (sem interferência entre fixes)
  - Perguntar ao usuário se houver dúvidas ou casos de borda não cobertos

## Notes

- Os exploration tests (tarefas 1, 4, 7) devem ser escritos e executados **antes** dos fixes correspondentes. A falha esperada confirma o bug.
- Os property tests (tarefas 3, 6, 9) devem ser escritos **após** os fixes e devem passar no código corrigido.
- Cada bug é independente — os fixes podem ser aplicados em qualquer ordem, mas a sequência exploration → fix → property tests deve ser respeitada dentro de cada bug.
- Para Bug 1 (`aura_gps_engine.js`): o fix é puramente no lado do cliente (JavaScript), sem impacto no backend.
- Para Bug 2 (`dap_engine.py`): a função `_enriquecer_com_gps` é uma extração do bloco existente — sem nova lógica de negócio.
- Para Bug 3: o fix envolve 4 arquivos (`aura_feedback.js`, `bridge.js`, `background.js`, `app.py` + `dap_engine.py`). Implementar na ordem das sub-tarefas 8.1 → 8.5 para garantir que cada camada esteja pronta antes de testar a integração.
- O endpoint `/api/feedback` não requer autenticação (dados de uso, não sensíveis) — padrão consistente com `/api/analytics/evento`.
