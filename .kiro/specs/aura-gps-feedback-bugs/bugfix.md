# Bugfix Requirements Document

## Introduction

Este documento cobre três bugs identificados na extensão Aura DAP após a reestruturação modular (`aura-dap-restructure`). Os bugs afetam o motor GPS, o AI Gate do backend e o sistema de feedback negativo, comprometendo a navegação guiada e a qualidade da base de conhecimento.

- **Bug 1** — O GPS trava após o primeiro passo: o validador de clique do passo 1 é removido antes de o passo 2 registrar o seu, ou o evento de clique que validou o passo 1 ainda está propagando quando o listener do passo 2 é registrado, fazendo o passo 2 ser validado imediatamente sem ação real do usuário.
- **Bug 2** — O AI Gate retorna `resultado_rapido` antes do bloco de GPS enrichment, suprimindo `gps_passos` em respostas de alta confiança — exatamente as que mais se beneficiariam de navegação guiada.
- **Bug 3** — O feedback negativo (👎) é salvo apenas no `localStorage` do browser; nenhuma chamada chega ao backend para marcar ou remover o vetor no Pinecone, permitindo que respostas ruins continuem sendo servidas indefinidamente.

---

## Bug Analysis

### Current Behavior (Defect)

**Bug 1 — GPS para no primeiro passo**

1.1 WHEN `target_selector` de um passo é vazio ou não corresponde a nenhum elemento no DOM THEN o sistema registra um listener de delegação no `document` que valida o passo ao primeiro clique em qualquer lugar da página

1.2 WHEN o clique que validou o passo 1 ainda está propagando (event bubbling) e `_avancarPasso` chama `_cleanupValidator()` seguido de `_iniciarPasso(1)` no mesmo tick THEN o sistema registra o listener do passo 2 enquanto o evento original ainda percorre a árvore DOM, fazendo o passo 2 ser validado imediatamente sem ação real do usuário

1.3 WHEN o GPS avança do passo 1 para o passo 2 via `_avancarPasso` THEN o sistema não avança para o passo 2 — a sessão GPS permanece travada no estado visual do passo 1 sem progredir

**Bug 2 — AI Gate suprime sugestão de GPS**

2.1 WHEN o score do Pinecone é maior que 0.80 e há `seletor_direto` disponível THEN o sistema retorna `resultado_rapido` imediatamente sem executar o bloco de GPS enrichment

2.2 WHEN o bloco de GPS enrichment não é executado no caminho do AI Gate THEN o sistema retorna uma resposta sem o campo `gps_passos`, impedindo que o frontend ofereça o botão "Me guie até lá"

**Bug 3 — Feedback negativo não remove entrada da base de conhecimento**

3.1 WHEN o usuário clica em 👎 na barra de feedback THEN o sistema salva `{ tipo, prompt, url, ts }` apenas no `localStorage` do browser e remove a barra visualmente

3.2 WHEN o feedback negativo é registrado THEN o sistema não envia nenhuma mensagem ao bridge nem faz chamada ao backend

3.3 WHEN nenhuma chamada chega ao backend após um dislike THEN o sistema continua servindo a mesma resposta ruim indefinidamente, pois o vetor no Pinecone e a entrada no cache SQLite permanecem intactos

---

### Expected Behavior (Correct)

**Bug 1 — GPS para no primeiro passo**

2.1 WHEN `target_selector` é vazio ou não corresponde a nenhum elemento no DOM THEN o sistema SHALL registrar o listener de delegação no `document` com uma guarda que rejeita o evento se ele ocorreu antes do timestamp de registro do listener (ou no mesmo tick de microtask), evitando que o evento que disparou `_avancarPasso` seja capturado pelo listener do próximo passo

2.2 WHEN `_avancarPasso` é chamado e o próximo passo usa delegação no `document` THEN o sistema SHALL diferir o registro do listener do passo seguinte para após o término da propagação do evento corrente, garantindo que o novo listener não capture o mesmo evento que validou o passo anterior

2.3 WHEN o GPS avança do passo N para o passo N+1 THEN o sistema SHALL exibir o painel atualizado com o intent do passo N+1 e aguardar uma ação real do usuário antes de validar

**Bug 2 — AI Gate suprime sugestão de GPS**

2.4 WHEN o score do Pinecone é maior que 0.80 e há `seletor_direto` disponível THEN o sistema SHALL executar o bloco de GPS enrichment antes de retornar `resultado_rapido`, adicionando `gps_passos` à resposta quando um roteiro relevante for encontrado

2.5 WHEN o AI Gate produz `resultado_rapido` com `gps_passos` THEN o sistema SHALL retornar a resposta rápida enriquecida com a opção de navegação guiada, sem degradar a latência do caminho de alta confiança além do tempo de lookup do roteiro

**Bug 3 — Feedback negativo não remove entrada da base de conhecimento**

2.6 WHEN o usuário clica em 👎 THEN o sistema SHALL enviar `postMessage` com `type: 'AURA_FEEDBACK_EVENT'` e payload `{ tipo: 'dislike', prompt, url, ts }` para o bridge, além de salvar no `localStorage`

2.7 WHEN o background recebe uma mensagem com `action: 'feedback_event'` e `tipo: 'dislike'` THEN o sistema SHALL chamar o endpoint `/api/feedback` no backend Python com o prompt e a URL associados

2.8 WHEN o endpoint `/api/feedback` recebe um dislike THEN o sistema SHALL marcar o vetor correspondente no Pinecone com metadata `feedback: 'negative'` ou removê-lo, e invalidar a entrada correspondente no cache SQLite

---

### Unchanged Behavior (Regression Prevention)

**Bug 1 — GPS para no primeiro passo**

3.1 WHEN `target_selector` é válido e o elemento está presente no DOM THEN o sistema SHALL CONTINUE TO registrar o listener diretamente no elemento (sem delegação no `document`) e validar o passo somente ao clique naquele elemento específico

3.2 WHEN o usuário clica no elemento correto do passo N THEN o sistema SHALL CONTINUE TO avançar para o passo N+1, atualizar o painel e aplicar spotlight no novo `target_selector`

3.3 WHEN o usuário abandona o GPS explicitamente THEN o sistema SHALL CONTINUE TO emitir `gps:abandoned`, remover o painel e retornar `aura_mode` para `assist`

3.4 WHEN o passo tem `validation_type` diferente de `click` (ex: `type`, `enter`, `url_change`) THEN o sistema SHALL CONTINUE TO usar o validador correspondente sem regressão

**Bug 2 — AI Gate suprime sugestão de GPS**

3.5 WHEN o score do Pinecone é menor que 0.80 ou não há `seletor_direto` THEN o sistema SHALL CONTINUE TO executar o caminho completo do Gemini Vision sem alteração

3.6 WHEN o AI Gate retorna `resultado_rapido` sem roteiro GPS disponível THEN o sistema SHALL CONTINUE TO retornar a resposta rápida sem o campo `gps_passos`, sem degradação

3.7 WHEN o frontend recebe uma resposta com `gps_passos` THEN o sistema SHALL CONTINUE TO apresentar o CTA explícito ao usuário sem iniciar o GPS automaticamente (conforme Requirement 2.2 do spec de referência)

**Bug 3 — Feedback negativo não remove entrada da base de conhecimento**

3.8 WHEN o usuário clica em 👍 THEN o sistema SHALL CONTINUE TO registrar o like no `localStorage` e remover a barra visualmente, sem enviar chamada ao backend (comportamento atual preservado para likes)

3.9 WHEN o endpoint `/api/feedback` não está disponível THEN o sistema SHALL CONTINUE TO remover a barra de feedback visualmente e registrar o dislike no `localStorage` como fallback, sem bloquear a UI

3.10 WHEN o cache SQLite não contém entrada correspondente ao prompt do dislike THEN o sistema SHALL CONTINUE TO marcar/remover o vetor no Pinecone normalmente, sem falhar por ausência de cache

---

## Bug Condition Pseudocode

### Bug 1 — Condição de corrida no validador de clique

```pascal
FUNCTION isBugCondition_GPS(step, eventTimestamp)
  INPUT: step de tipo StepModel, eventTimestamp de tipo number (ms)
  OUTPUT: boolean

  // Bug ocorre quando:
  // (a) target_selector está vazio ou não encontra elemento → usa delegação
  // (b) o listener do próximo passo é registrado no mesmo tick do evento que validou o anterior
  RETURN (step.target_selector = "" OR AuraSpotlight.encontrarElemento(step.target_selector) = null)
         AND eventTimestamp >= listenerRegistrationTimestamp
END FUNCTION

// Property: Fix Checking — Bug 1
FOR ALL step WHERE isBugCondition_GPS(step, eventTimestamp) DO
  result ← _iniciarPasso'(nextIndex)
  ASSERT result.listenerRegisteredAfterEventPropagation = true
         AND passo_validado_sem_acao_real = false
END FOR

// Property: Preservation Checking — Bug 1
FOR ALL step WHERE NOT isBugCondition_GPS(step, eventTimestamp) DO
  ASSERT _validadorClick(step) = _validadorClick_original(step)
END FOR
```

### Bug 2 — AI Gate sem GPS enrichment

```pascal
FUNCTION isBugCondition_AIGate(resultado_rag)
  INPUT: resultado_rag de tipo dict
  OUTPUT: boolean

  RETURN resultado_rag.score > 0.80 AND resultado_rag.seletor_direto != null
END FUNCTION

// Property: Fix Checking — Bug 2
FOR ALL resultado_rag WHERE isBugCondition_AIGate(resultado_rag) DO
  result ← _analisar_sync'(resultado_rag)
  ASSERT "gps_passos" IN result OR gps_enrichment_executado = true
END FOR

// Property: Preservation Checking — Bug 2
FOR ALL resultado_rag WHERE NOT isBugCondition_AIGate(resultado_rag) DO
  ASSERT _analisar_sync(resultado_rag) = _analisar_sync_original(resultado_rag)
END FOR
```

### Bug 3 — Feedback negativo sem propagação ao backend

```pascal
FUNCTION isBugCondition_Feedback(tipo)
  INPUT: tipo de tipo string ("like" | "dislike")
  OUTPUT: boolean

  RETURN tipo = "dislike"
END FUNCTION

// Property: Fix Checking — Bug 3
FOR ALL feedback WHERE isBugCondition_Feedback(feedback.tipo) DO
  result ← _registrar'(feedback.tipo, feedback.btn)
  ASSERT postMessageEnviado = true
         AND action = "feedback_event"
         AND backendChamado = true
END FOR

// Property: Preservation Checking — Bug 3
FOR ALL feedback WHERE NOT isBugCondition_Feedback(feedback.tipo) DO
  ASSERT _registrar(feedback.tipo, feedback.btn) = _registrar_original(feedback.tipo, feedback.btn)
END FOR
```
